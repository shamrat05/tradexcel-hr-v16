"""Native v16 integration checks for the mixed-pay input boundary."""

from datetime import date, timedelta
import os

import frappe
import pytest
from hrms.payroll.doctype.payroll_entry.payroll_entry import PayrollEntry
from hrms.payroll.doctype.salary_structure.salary_structure import make_salary_slip

from tradex_hr.tradexcel_hr import daily_wage_input
from tradex_hr.tradexcel_hr.daily_wage_input import calculate_daily_wage_input, create_daily_wage_input


@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(
        site=os.environ.get("FRAPPE_TEST_SITE", "hrms-v16.localhost"),
        sites_path=os.environ.get("FRAPPE_TEST_SITES_PATH", "/home/sanchita/frappe-bench-v16/sites"),
    )
    frappe.connect()
    yield
    frappe.destroy()


def _employee():
    return frappe.db.get_value(
        "Employee",
        {"name": "HR-EMP-00225", "company": "Tradexcel Ceramics Ltd.", "status": "Active"},
        ["name", "company"],
        as_dict=True,
    )


def _safe_structure(employee, name):
    structure = frappe.get_doc({
        "doctype": "Salary Structure",
        "name": name,
        "company": employee.company,
        "currency": "BDT",
        "payroll_frequency": "Monthly",
        "is_active": "Yes",
        "custom_tradex_pay_basis": "Daily Wage",
        "earnings": [{"salary_component": "Daily Wage", "amount": 0, "depends_on_payment_days": 0}],
    })
    structure.insert(ignore_permissions=True)
    structure.submit()
    assignment = frappe.get_doc({
        "doctype": "Salary Structure Assignment",
        "employee": employee.name,
        "company": employee.company,
        "currency": "BDT",
        "salary_structure": structure.name,
        "from_date": "2026-12-01",
        "base": 350,
        "payroll_payable_account": frappe.db.get_value("Company", employee.company, "default_payroll_payable_account"),
    })
    assignment.insert(ignore_permissions=True)
    assignment.submit()
    return structure


def _attendance(employee, day, status="Present", half_day_status=None):
    doc = frappe.get_doc({
        "doctype": "Attendance",
        "employee": employee,
        "attendance_date": day,
        "status": status,
        "company": "Tradexcel Ceramics Ltd.",
        "half_day_status": half_day_status,
    })
    doc.insert(ignore_permissions=True)
    doc.submit()


def test_daily_wage_native_chain_is_exact_and_idempotent(monkeypatch):
    employee = _employee()
    if not employee:
        pytest.skip("No active TCL staging employee")
    savepoint = "mixed_daily_native"
    frappe.db.savepoint(savepoint)
    try:
        structure = _safe_structure(employee, f"TEST Daily Wage {frappe.generate_hash(6)}")
        for offset in range(10):
            _attendance(employee.name, date(2026, 12, 1) + timedelta(days=offset))

        period = frappe.get_doc({
            "doctype": "Tradexcel Attendance Period",
            "company": employee.company,
            "from_date": "2026-12-01",
            "to_date": "2026-12-31",
            "status": "Finalized",
            "revision": 1,
            "attendance_hash": "synthetic-finalized-test",
        })
        period._finalize_context = True
        period.insert(ignore_permissions=True)
        monkeypatch.setattr(daily_wage_input, "require_finalized_attendance", lambda *_args: period)

        first = create_daily_wage_input(employee.name, period.name)
        second = create_daily_wage_input(employee.name, period.name)
        assert first["status"] == "CREATED"
        assert second["status"] == "EXISTING"
        assert first["amount"] == 3500

        slip = make_salary_slip(structure.name, employee=employee.name, posting_date="2026-12-31")
        wage_rows = [row for row in slip.earnings if row.salary_component == "Daily Wage"]
        assert sum(row.amount for row in wage_rows) == 3500
    finally:
        frappe.db.rollback(save_point=savepoint)


def test_native_payroll_dates_narrow_joiner_and_leaver_periods():
    entry = frappe.new_doc("Payroll Entry")
    entry.start_date = date(2026, 9, 1)
    entry.end_date = date(2026, 9, 30)
    joiner = frappe.db.get_value("Employee", {"date_of_joining": [">", "2026-09-01"]}, ["date_of_joining", "relieving_date"], as_dict=True)
    if not joiner:
        pytest.skip("No mid-period joiner in staging")
    start, end = PayrollEntry.get_payroll_dates_for_employee(entry, joiner)
    assert start == joiner.date_of_joining
    assert end == date(2026, 9, 30)


def test_legacy_staging_daily_structure_remains_blocked():
    result = calculate_daily_wage_input("HR-EMP-00225", "2026-09-01", "2026-09-30")
    if not frappe.db.exists("Salary Structure", "TCL Daily Wage"):
        pytest.skip("TCL Daily Wage is not configured on staging")
    assert result["status"] == "BLOCKED_UNSAFE_STRUCTURE"
