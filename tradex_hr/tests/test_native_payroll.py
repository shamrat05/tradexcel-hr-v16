from datetime import date, timedelta
import os

import frappe
import pytest
from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip

from tradex_hr.tradexcel_hr import daily_wage_input, native_payroll


@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(
        site=os.environ.get("FRAPPE_TEST_SITE", "hrms-v16.localhost"),
        sites_path=os.environ.get("FRAPPE_TEST_SITES_PATH", "/home/sanchita/frappe-bench-v16/sites"),
        force=True,
    )
    frappe.connect()
    yield
    frappe.destroy()


def test_native_readiness_does_not_block_joiner_or_leaver_for_native_proration(monkeypatch):
    employees = [{
        "name": "EMP-JOIN",
        "employee_name": "Joiner",
        "company": "TCL",
        "status": "Active",
        "date_of_joining": date(2026, 9, 10),
        "relieving_date": None,
    }]
    monkeypatch.setattr(native_payroll, "_employees_for_period", lambda *_args: employees)
    monkeypatch.setattr(native_payroll, "resolve_pay_basis", lambda *_args: {"status": "Monthly Salary"})
    monkeypatch.setattr(native_payroll, "_period_attendance_gate", lambda *_args: [])
    monkeypatch.setattr(native_payroll, "_unapproved_overtime", lambda *_args: [])

    result = native_payroll.inspect_native_payroll_readiness(
        "TCL", date(2026, 9, 1), date(2026, 9, 30)
    )

    assert result["status"] == "READY"
    assert result["outcomes"][0]["status"] == "READY"


def test_native_readiness_blocks_stale_attendance(monkeypatch):
    employees = [{
        "name": "EMP-DAILY",
        "employee_name": "Daily",
        "company": "TCL",
        "status": "Active",
        "date_of_joining": date(2026, 1, 1),
        "relieving_date": None,
    }]
    monkeypatch.setattr(native_payroll, "_employees_for_period", lambda *_args: employees)
    monkeypatch.setattr(native_payroll, "resolve_pay_basis", lambda *_args: {"status": "Daily Wage"})
    monkeypatch.setattr(native_payroll, "_period_attendance_gate", lambda *_args: [{
        "employee": "EMP-DAILY", "code": "BLOCKED_ATTENDANCE_STALE", "reason": "stale"
    }])
    monkeypatch.setattr(native_payroll, "_unapproved_overtime", lambda *_args: [])
    monkeypatch.setattr(native_payroll, "calculate_daily_wage_input", lambda *_args: pytest.fail("stale input must stop first"))

    result = native_payroll.inspect_native_payroll_readiness(
        "TCL", date(2026, 9, 1), date(2026, 9, 30)
    )

    assert result["status"] == "BLOCKED"
    assert result["outcomes"][0]["status"] == "BLOCKED_ATTENDANCE_STALE"


def test_prepare_reuses_existing_native_payroll_entry(monkeypatch):
    existing = {"name": "PAY-1", "docstatus": 0, "status": "Draft", "salary_slips_created": 0}
    monkeypatch.setattr(native_payroll, "inspect_native_payroll_readiness", lambda *_args, **_kwargs: {
        "status": "READY", "outcomes": [], "employee_count": 0, "ready_count": 0, "blocked_count": 0,
    })
    monkeypatch.setattr(native_payroll, "_existing_payroll_entry", lambda *_args: existing)

    result = native_payroll.prepare_native_payroll("TCL", date(2026, 9, 1), date(2026, 9, 30))

    assert result["status"] == "EXISTING"
    assert result["payroll_entry"] == "PAY-1"


def test_prepare_blocks_missing_payroll_account_before_daily_input(monkeypatch):
    readiness = {
        "status": "READY",
        "outcomes": [{"employee": "EMP-DAILY", "employee_data": {}, "pay_basis": {"status": "Daily Wage"}}],
        "employee_count": 1,
        "ready_count": 1,
        "blocked_count": 0,
    }
    monkeypatch.setattr(native_payroll, "inspect_native_payroll_readiness", lambda *_args, **_kwargs: readiness)
    monkeypatch.setattr(native_payroll, "_existing_payroll_entry", lambda *_args: None)
    monkeypatch.setattr(native_payroll.frappe, "get_cached_value", lambda *_args: (None, None))
    monkeypatch.setattr(
        native_payroll,
        "create_daily_wage_input",
        lambda *_args: pytest.fail("payroll inputs must not be written without a payable account"),
    )

    result = native_payroll.prepare_native_payroll("TCL", date(2026, 9, 1), date(2026, 9, 30))

    assert result["status"] == "BLOCKED_PAYROLL_ACCOUNT"


def test_prepare_checks_payroll_entry_permission_before_insert(monkeypatch):
    readiness = {
        "status": "READY",
        "outcomes": [{"employee": "EMP-MONTHLY", "employee_data": {}, "pay_basis": {"status": "Monthly Salary"}}],
        "employee_count": 1,
        "ready_count": 1,
        "blocked_count": 0,
    }
    monkeypatch.setattr(native_payroll, "inspect_native_payroll_readiness", lambda *_args, **_kwargs: readiness)
    monkeypatch.setattr(native_payroll, "_existing_payroll_entry", lambda *_args: None)
    monkeypatch.setattr(native_payroll.frappe, "get_cached_value", lambda *_args: ("BDT", "ACC-PAYABLE"))
    monkeypatch.setattr(
        native_payroll.frappe,
        "has_permission",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(frappe.PermissionError("denied")),
    )
    monkeypatch.setattr(
        native_payroll.frappe,
        "get_doc",
        lambda *_args: pytest.fail("Payroll Entry must not be inserted without permission"),
    )

    with pytest.raises(frappe.PermissionError, match="denied"):
        native_payroll.prepare_native_payroll("TCL", date(2026, 9, 1), date(2026, 9, 30))


def test_native_payroll_creates_draft_entry_and_slip_from_finalized_daily_attendance(monkeypatch):
    employee = frappe.db.get_value(
        "Employee",
        {"name": "HR-EMP-00225", "company": "Tradexcel Ceramics Ltd.", "status": "Active"},
        ["name", "employee_name", "company"],
        as_dict=True,
    )
    if not employee:
        pytest.skip("No active TCL staging employee")

    created = {
        "attendance": [],
        "period": None,
        "assignment": None,
        "structure": None,
        "additional_salary": [],
        "payroll_entry": None,
        "salary_slips": [],
    }

    def cleanup():
        for name in created["salary_slips"]:
            _delete_test_doc("Salary Slip", name)
        if created["payroll_entry"]:
            _delete_test_doc("Payroll Entry", created["payroll_entry"])
        for name in created["additional_salary"]:
            _delete_test_doc("Additional Salary", name)
        if created["assignment"]:
            _delete_test_doc("Salary Structure Assignment", created["assignment"])
        if created["structure"]:
            _delete_test_doc("Salary Structure", created["structure"])
        if created["period"]:
            _delete_test_doc("Tradexcel Attendance Period", created["period"])
        for name in created["attendance"]:
            _delete_test_doc("Attendance", name)
        frappe.db.commit()

    try:
        structure = frappe.get_doc({
            "doctype": "Salary Structure",
            "name": f"TEST Native Daily {frappe.generate_hash(6)}",
            "company": employee.company,
            "currency": "BDT",
            "payroll_frequency": "Monthly",
            "is_active": "Yes",
            "custom_tradex_pay_basis": "Daily Wage",
            "earnings": [{"salary_component": "Daily Wage", "amount": 0, "depends_on_payment_days": 0}],
        })
        structure.insert(ignore_permissions=True)
        created["structure"] = structure.name
        structure.submit()
        assignment = frappe.get_doc({
            "doctype": "Salary Structure Assignment",
            "employee": employee.name,
            "company": employee.company,
            "currency": "BDT",
            "salary_structure": structure.name,
            "from_date": "2027-01-01",
            "base": 350,
            "payroll_payable_account": frappe.db.get_value("Company", employee.company, "default_payroll_payable_account"),
        })
        assignment.insert(ignore_permissions=True)
        created["assignment"] = assignment.name
        assignment.submit()

        start, end = date(2027, 1, 1), date(2027, 1, 31)
        probe = SalarySlip({"doctype": "Salary Slip"})
        probe.employee = employee.name
        probe.start_date = start
        probe.end_date = end
        holidays = set(probe.get_holidays_for_employee(start, end))
        for offset in range((end - start).days + 1):
            day = start + timedelta(days=offset)
            if day in holidays:
                continue
            attendance = frappe.get_doc({
                "doctype": "Attendance",
                "employee": employee.name,
                "attendance_date": day,
                "status": "Present" if offset < 10 else "Absent",
                "company": employee.company,
            })
            attendance.insert(ignore_permissions=True)
            created["attendance"].append(attendance.name)
            attendance.submit()

        period = frappe.get_doc({
            "doctype": "Tradexcel Attendance Period",
            "company": employee.company,
            "from_date": start,
            "to_date": end,
            "status": "Finalized",
            "revision": 1,
            "attendance_hash": native_payroll.current_attendance_period_hash(employee.company, start, end),
        })
        period._finalize_context = True
        period.insert(ignore_permissions=True)
        created["period"] = period.name
        monkeypatch.setattr(daily_wage_input, "require_finalized_attendance", lambda *_args: period)

        result = native_payroll.prepare_native_payroll(employee.company, start, end, employee_ids=[employee.name])

        assert result["status"] == "DRAFTS_CREATED"
        created["payroll_entry"] = result["payroll_entry"]
        created["salary_slips"] = list(result["salary_slips"])
        created["additional_salary"] = [item["additional_salary"] for item in result["daily_inputs"]]
        entry = frappe.get_doc("Payroll Entry", result["payroll_entry"])
        assert entry.docstatus == 0
        slips = frappe.get_all("Salary Slip", filters={"payroll_entry": entry.name, "docstatus": 0}, fields=["name"])
        assert len(slips) == 1
        slip = frappe.get_doc("Salary Slip", slips[0].name)
        wage_rows = [row for row in slip.earnings if row.salary_component == "Daily Wage"]
        assert sum(row.amount for row in wage_rows) == 3500

        retry = native_payroll.prepare_native_payroll(employee.company, start, end, employee_ids=[employee.name])
        assert retry["status"] == "EXISTING"
    finally:
        cleanup()


def _delete_test_doc(doctype, name):
    if not name or not frappe.db.exists(doctype, name):
        return
    doc = frappe.get_doc(doctype, name)
    if doc.docstatus == 1:
        doc.cancel()
    frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
