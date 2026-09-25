"""Read-only smoke checks for the new operations reports and Desk shortcuts."""

import json
import os

import frappe
import pytest

from tradex_hr.install import BULK_WORKSPACE_SHORTCUTS


def value(row, label):
    return next(value for key, value in row.items() if key.split(":", 1)[0] == label)


@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(
        site=os.environ.get("FRAPPE_TEST_SITE", "hrms-v16.localhost"),
        sites_path=os.environ.get(
            "FRAPPE_TEST_SITES_PATH", os.path.expanduser("~/frappe-bench-v16/sites")
        ),
    )
    frappe.connect()
    yield
    frappe.destroy()


def test_operations_reports_registered():
    from tradex_hr.role_setup import STANDARD_PERMISSION_MATRIX

    financial_roles = {
        "Tradexcel Owner/Director",
        "Tradexcel HR Manager",
        "Tradexcel Payroll Manager",
        "Tradexcel Payroll Approver",
        "Tradexcel Finance/Accounts Officer",
        "Tradexcel Compliance Auditor",
    }
    for name in ("Tradexcel Pay Component Register", "Tradexcel Payroll Variance"):
        report = frappe.get_doc("Report", name)
        assert report.report_type == "Script Report"
        assert report.is_standard == "Yes"
        assert report.module == "Tradexcel HR"
        assert report.ref_doctype == "Salary Slip"
        roles = {row.role for row in report.roles}
        assert roles == financial_roles
        for role in roles:
            assert {"read", "report"} <= STANDARD_PERMISSION_MATRIX["Salary Slip"][role]
        assert not roles & {
            "Tradexcel Employee/Worker", "Tradexcel Factory Supervisor",
            "Tradexcel Branch Manager", "Tradexcel Department Manager",
            "Tradexcel HR/Attendance Officer",
        }
        assert not report.query
        assert not report.report_script

    for name, ref_doctype in (
        ("Tradexcel Shift Coverage", "Employee"),
        ("Tradexcel Joiners and Leavers", "Employee"),
    ):
        report = frappe.get_doc("Report", name)
        assert report.report_type == "Script Report"
        assert report.is_standard == "Yes"
        assert report.module == "Tradexcel HR"
        assert report.ref_doctype == ref_doctype
        assert report.roles
        assert "Tradexcel Employee/Worker" not in {row.role for row in report.roles}

    query_reports = set(frappe.get_all(
        "Report", filters={"module": "Tradexcel HR", "report_type": "Query Report"}, pluck="name"
    ))
    assert query_reports == set()
    from tradex_hr import hooks
    assert "frappe.desk.query_report.run" not in getattr(hooks, "override_whitelisted_methods", {})


def test_shift_coverage_and_movement_script_reports_run_directly():
    from tradex_hr.tradexcel_hr.report.tradexcel_joiners_and_leavers.tradexcel_joiners_and_leavers import execute as run_movements
    from tradex_hr.tradexcel_hr.report.tradexcel_shift_coverage.tradexcel_shift_coverage import execute as run_coverage

    frappe.set_user("Administrator")
    _, coverage = run_coverage({
        "company": "Tradexcel Ceramics Ltd.", "as_of_date": "2026-09-17",
        "branch": "", "department": "", "coverage": "All",
    })
    names = [row.employee for row in coverage]
    assert len(names) == len(set(names))
    assert all(row.coverage in {
        "Multiple active assignments — review", "Assigned",
        "Default shift only", "No shift assigned — review",
    } for row in coverage)

    _, events = run_movements({
        "company": "Tradexcel Ceramics Ltd.", "from_date": "2026-01-01",
        "to_date": "2026-12-31", "branch": "", "department": "",
    })
    assert all(row.movement in {"Joined", "Left"} for row in events)
    assert all(row.movement_date for row in events)


def test_workspace_links_only_to_installed_doctypes():
    workspace = frappe.get_doc("Workspace", "tradexcel-hr")
    shortcuts = {row.label: row.link_to for row in workspace.shortcuts}
    blocks = json.loads(workspace.content)
    rendered = {
        block["data"]["shortcut_name"]
        for block in blocks
        if block["type"] == "shortcut"
    }
    for label, doctype, _ in BULK_WORKSPACE_SHORTCUTS:
        if frappe.db.exists("DocType", doctype):
            assert shortcuts[label] == doctype
            assert label in rendered
        else:
            assert label not in shortcuts
            assert label not in rendered


def test_gaps_board_opens_employee_update_import():
    javascript = frappe.db.get_value("Report", "Employee Data Gaps", "javascript")
    assert 'frappe.new_doc("Data Import"' in javascript
    assert 'reference_doctype: "Employee"' in javascript
    assert 'import_type: "Update Existing Records"' in javascript


def test_desk_report_endpoint_renders_both_reports():
    from frappe.desk.query_report import run

    frappe.set_user("Administrator")
    for report_name in (
        "Tradexcel Daily Attendance Board",
        "Tradexcel Leave Balance Board",
        "Tradexcel Payroll Register",
    ):
        result = run(report_name, filters={})
        assert result["columns"]
        assert isinstance(result["result"], list)

    for report_name, filters in (
        (
            "Tradexcel Daily Attendance Board",
            {
                "company": "Tradexcel Ceramics Ltd.",
                "attendance_date": "2026-09-17",
            },
        ),
        (
            "Tradexcel Leave Balance Board",
            {
                "company": "Tradexcel Ceramics Ltd.",
                "as_of_date": "2026-09-17",
            },
        ),
        (
            "Tradexcel Payroll Register",
            {
                "company": "Tradexcel Ceramics Ltd.",
                "from_date": "2026-09-01",
                "to_date": "2026-09-30",
            },
        ),
        (
            "Tradexcel Shift Coverage",
            {
                "company": "Tradexcel Ceramics Ltd.",
                "as_of_date": "2026-09-17",
                "branch": "",
                "department": "",
                "coverage": "All",
            },
        ),
        (
            "Tradexcel Pay Component Register",
            {
                "company": "Tradexcel Ceramics Ltd.",
                "from_date": "2026-09-01",
                "to_date": "2026-09-30",
                "branch": "",
                "department": "",
                "component_type": "All",
                "component": "",
            },
        ),
        (
            "Tradexcel Payroll Variance",
            {
                "company": "Tradexcel Ceramics Ltd.",
                "from_date": "2026-09-01",
                "to_date": "2026-09-30",
                "branch": "",
                "department": "",
            },
        ),
        (
            "Tradexcel Joiners and Leavers",
            {
                "company": "Tradexcel Ceramics Ltd.",
                "from_date": "2026-01-01",
                "to_date": "2026-12-31",
                "branch": "",
            },
        ),
    ):
        result = run(report_name, filters=filters)
        assert result["columns"]
        assert isinstance(result["result"], list)


@pytest.mark.parametrize("role", [
    "Tradexcel Employee/Worker",
    "Tradexcel Factory Supervisor",
    "Tradexcel Branch Manager",
    "Tradexcel Department Manager",
    "Tradexcel HR/Attendance Officer",
])
def test_operational_roles_cannot_read_financial_reports(monkeypatch, role):
    from frappe.desk.query_report import run

    for report_name in ("Tradexcel Pay Component Register", "Tradexcel Payroll Variance"):
        report = frappe.get_doc("Report", report_name)
        monkeypatch.setattr(frappe, "get_roles", lambda *args, **kwargs: [role])
        assert not report.is_permitted()
        frappe.set_user("Administrator")
        with pytest.raises(frappe.PermissionError):
            run(report_name, filters={
                "company": "Tradexcel Ceramics Ltd.",
                "from_date": "2026-09-01",
                "to_date": "2026-09-30",
                "branch": "",
                "department": "",
                "component_type": "All",
                "component": "",
            })


def test_guest_cannot_run_financial_reports():
    from frappe.desk.query_report import run

    frappe.set_user("Guest")
    for report_name in ("Tradexcel Pay Component Register", "Tradexcel Payroll Variance"):
        with pytest.raises(frappe.PermissionError):
            run(report_name, filters={
                "company": "Tradexcel Ceramics Ltd.",
                "from_date": "2026-09-01",
                "to_date": "2026-09-30",
            })


@pytest.mark.parametrize(("from_date", "to_date", "expected"), [
    ("2026-09-01", "2026-09-30", ("2026-08-01", "2026-08-31")),
    ("2026-09-10", "2026-09-30", ("2026-08-20", "2026-09-09")),
    ("2026-03-31", "2026-03-31", ("2026-03-30", "2026-03-30")),
])
def test_variance_compares_full_month_or_equal_length_preceding_interval(from_date, to_date, expected):
    from tradex_hr.tradexcel_hr.report.tradexcel_payroll_variance.tradexcel_payroll_variance import (
        _previous_period,
    )

    previous_from, previous_to = _previous_period(from_date, to_date)
    assert (previous_from.isoformat(), previous_to.isoformat()) == expected


def test_payroll_variance_uses_adjacent_native_period_and_current_employee_scope(monkeypatch):
    from tradex_hr.tradexcel_hr.report.tradexcel_payroll_variance import (
        tradexcel_payroll_variance as report,
    )

    current = [frappe._dict(
        name="SYNTH-CURRENT", employee="SYNTH-A", employee_name="Synthetic A",
        company="Synthetic Co", branch="Payroll Branch A", department="Payroll Dept A",
        start_date="2026-09-01", end_date="2026-09-30", gross_pay=120,
        total_deduction=10, net_pay=110, docstatus=1,
    ), frappe._dict(
        name="SYNTH-MULTI-1", employee="SYNTH-C", employee_name="Synthetic C",
        company="Synthetic Co", branch="Payroll Branch A", department="Payroll Dept A",
        start_date="2026-09-01", end_date="2026-09-30", gross_pay=60,
        total_deduction=10, net_pay=50, docstatus=1,
    ), frappe._dict(
        name="SYNTH-MULTI-2", employee="SYNTH-C", employee_name="Synthetic C",
        company="Synthetic Co", branch="Payroll Branch A", department="Payroll Dept A",
        start_date="2026-09-01", end_date="2026-09-30", gross_pay=0,
        total_deduction=0, net_pay=0, docstatus=1,
    ), frappe._dict(
        name="SYNTH-ZERO", employee="SYNTH-D", employee_name="Synthetic D",
        company="Synthetic Co", branch="Payroll Branch A", department="Payroll Dept A",
        start_date="2026-09-01", end_date="2026-09-30", gross_pay=0,
        total_deduction=0, net_pay=0, docstatus=1,
    )]
    previous = [
        frappe._dict(
            name="SYNTH-PREVIOUS", employee="SYNTH-A", employee_name="Synthetic A",
            company="Synthetic Co", branch="Payroll Branch A", department="Payroll Dept A",
            start_date="2026-08-01", end_date="2026-08-31", gross_pay=100,
            total_deduction=10, net_pay=90, docstatus=1,
        ),
        frappe._dict(
            name="SYNTH-PREVIOUS-C", employee="SYNTH-C", employee_name="Synthetic C",
            company="Synthetic Co", branch="Payroll Branch A", department="Payroll Dept A",
            start_date="2026-08-01", end_date="2026-08-31", gross_pay=50,
            total_deduction=10, net_pay=40, docstatus=1,
        ),
        # A prior-period slip outside the permitted Employee population must
        # never generate an output row or be joined to another employee.
        frappe._dict(
            name="SYNTH-OUTSIDE", employee="SYNTH-B", employee_name="Synthetic B",
            company="Synthetic Co", branch="Payroll Branch B", department="Payroll Dept B",
            start_date="2026-08-01", end_date="2026-08-31", gross_pay=999,
            total_deduction=0, net_pay=999, docstatus=1,
        ),
    ]
    calls = []

    monkeypatch.setattr(report, "resolve_company", lambda _filters: "Synthetic Co")
    monkeypatch.setattr(report, "permitted_employee_names", lambda _company: ("SYNTH-A",))

    def salary_slips(company, employees, *, from_date, to_date, branch="", department=""):
        calls.append((company, employees, str(from_date), str(to_date), branch, department))
        return current if from_date == "2026-09-01" else previous

    monkeypatch.setattr(report, "permitted_salary_slips", salary_slips)
    columns, rows = report.execute({
        "company": "Synthetic Co", "from_date": "2026-09-01", "to_date": "2026-09-30",
        "branch": "Payroll Branch A", "department": "Payroll Dept A",
    })
    assert columns and {row.employee for row in rows} == {"SYNTH-A", "SYNTH-C", "SYNTH-D"}
    by_employee = {row.employee: row for row in rows}
    assert by_employee["SYNTH-A"].current_net == 110
    assert by_employee["SYNTH-A"].previous_net == 90
    assert by_employee["SYNTH-A"].change == 20
    assert by_employee["SYNTH-A"].gross == 120 and by_employee["SYNTH-A"].deductions == 10
    assert by_employee["SYNTH-A"].review == "Compare"
    assert by_employee["SYNTH-C"].slip_count == 2
    assert by_employee["SYNTH-C"].review == "Multiple slips — review"
    assert by_employee["SYNTH-D"].current_net == 0
    assert by_employee["SYNTH-D"].review == "Zero pay — review"
    assert calls == [
        ("Synthetic Co", ("SYNTH-A",), "2026-09-01", "2026-09-30", "Payroll Branch A", "Payroll Dept A"),
        ("Synthetic Co", ("SYNTH-A",), "2026-08-01", "2026-08-31", "Payroll Branch A", "Payroll Dept A"),
    ]


@pytest.mark.parametrize("report_name", ["tradexcel_pay_component_register", "tradexcel_payroll_variance"])
def test_financial_report_empty_employee_scope_never_falls_back(report_name, monkeypatch):
    from tradex_hr.tradexcel_hr.report import (
        tradexcel_pay_component_register,
        tradexcel_payroll_variance,
    )

    report = {
        "tradexcel_pay_component_register": tradexcel_pay_component_register.tradexcel_pay_component_register,
        "tradexcel_payroll_variance": tradexcel_payroll_variance.tradexcel_payroll_variance,
    }[report_name]
    monkeypatch.setattr(report, "resolve_company", lambda _filters: "Synthetic Co")
    monkeypatch.setattr(report, "permitted_employee_names", lambda _company: ())
    monkeypatch.setattr(
        report,
        "permitted_salary_slips",
        lambda _company, employee_names, **_kwargs: [] if not employee_names else pytest.fail(
            "salary scope should receive the empty permission-aware Employee population"
        ),
    )
    filters = {
        "company": "Synthetic Co", "from_date": "2026-09-01", "to_date": "2026-09-30",
        "branch": "", "department": "", "component_type": "All", "component": "",
    }
    columns, rows = report.execute(filters)
    assert columns and rows == []
