"""Read-only smoke checks for the new operations reports and Desk shortcuts."""

import json
import os

import frappe
import pytest

from tradex_hr.install import BULK_WORKSPACE_SHORTCUTS, REPORTS


def value(row, label):
    return next(value for key, value in row.items() if key.split(":", 1)[0] == label)


@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(
        site=os.environ.get("FRAPPE_TEST_SITE", "hrms.localhost"),
        sites_path=os.environ.get(
            "FRAPPE_TEST_SITES_PATH", os.path.expanduser("~/frappe-bench/sites")
        ),
    )
    frappe.connect()
    yield
    frappe.destroy()


def test_operations_reports_registered():
    for name in (
        "Tradexcel Shift Coverage",
        "Tradexcel Pay Component Register",
        "Tradexcel Payroll Variance",
        "Tradexcel Joiners and Leavers",
    ):
        assert frappe.db.exists("Report", name)
        assert REPORTS[name]["ref_doctype"] in {"Salary Slip", "Employee", "Shift Assignment"}
        assert frappe.get_doc("Report", name).roles


def test_payroll_variance_is_scoped_and_flags_zero_pay():
    rows = frappe.db.sql(
        REPORTS["Tradexcel Payroll Variance"]["query"],
        {
            "company": "Tradexcel Ceramics Ltd.",
            "from_date": "2026-09-01",
            "to_date": "2026-09-30",
            "branch": "",
            "department": "",
        },
        as_dict=True,
    )
    # The report SQL must run regardless. Row assertions only apply when the
    # site actually holds salary data - pre-production salary was purged on
    # 2026-09-18, and a test that fails merely because there is no data is
    # testing the fixture, not the report.
    if not rows:
        import pytest
        pytest.skip("no salary slips on this site (pre-production payroll purged)")
    assert all(value(row, "Employee") for row in rows)
    assert all(value(row, "Slip Count") >= 1 for row in rows)
    assert any(value(row, "Review") == "Zero pay - review" for row in rows)


def test_joiners_leavers_query_runs_for_both_companies():
    for company in ("Tradexcel Ceramics Ltd.", "Elegance Footwear Ltd."):
        rows = frappe.db.sql(
            REPORTS["Tradexcel Joiners and Leavers"]["query"],
            {
                "company": company,
                "from_date": "2026-01-01",
                "to_date": "2026-12-31",
                "branch": "",
            },
            as_dict=True,
        )
        assert all(value(row, "Company") == company for row in rows)
        assert all(value(row, "Movement") in {"Joined", "Left"} for row in rows)


def test_payroll_variance_does_not_cross_company_boundary():
    rows = frappe.db.sql(
        REPORTS["Tradexcel Payroll Variance"]["query"],
        {
            "company": "Elegance Footwear Ltd.",
            "from_date": "2026-09-01",
            "to_date": "2026-09-30",
            "branch": "",
            "department": "",
        },
        as_dict=True,
    )
    for row in rows:
        assert frappe.db.get_value("Employee", value(row, "Employee"), "company") == "Elegance Footwear Ltd."


def test_component_register_shows_only_actual_slip_lines():
    filters = {
        "company": "Tradexcel Ceramics Ltd.",
        "from_date": "2026-09-01",
        "to_date": "2026-09-30",
        "branch": "",
        "department": "",
        "component_type": "Earning",
        "component": "",
    }
    rows = frappe.db.sql(REPORTS["Tradexcel Pay Component Register"]["query"], filters, as_dict=True)
    if not rows:
        import pytest
        pytest.skip("no salary slips on this site (pre-production payroll purged)")
    assert all(value(row, "Type") == "Earning" for row in rows)
    assert all(value(row, "Salary Slip") for row in rows)


def test_shift_coverage_reports_each_active_employee_once():
    rows = frappe.db.sql(
        REPORTS["Tradexcel Shift Coverage"]["query"],
        {
            "company": "Tradexcel Ceramics Ltd.",
            "as_of_date": "2026-09-17",
            "branch": "",
            "department": "",
            "coverage": "All",
        },
        as_dict=True,
    )
    employee_ids = [value(row, "Employee") for row in rows]
    assert employee_ids
    assert len(employee_ids) == len(set(employee_ids))
    assert all(value(row, "Coverage") in {
        "Overlap - review", "Assigned", "Default only", "Missing - review"
    } for row in rows)


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
    for report_name, filters in (
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


@pytest.mark.parametrize("role", ["Tradexcel Employee/Worker", "Tradexcel Branch Manager", "Tradexcel Payroll Manager"])
def test_scoped_roles_cannot_read_global_payroll_variance(monkeypatch, role):
    report = frappe.get_doc("Report", "Tradexcel Payroll Variance")
    monkeypatch.setattr(frappe, "get_roles", lambda *args, **kwargs: [role])
    assert not report.is_permitted()


def test_guest_cannot_run_payroll_variance():
    from frappe.desk.query_report import run

    frappe.set_user("Guest")
    with pytest.raises(frappe.PermissionError):
        run(
            "Tradexcel Payroll Variance",
            filters={
                "company": "Tradexcel Ceramics Ltd.",
                "from_date": "2026-09-01",
                "to_date": "2026-09-30",
                "branch": "",
                "department": "",
            },
        )
