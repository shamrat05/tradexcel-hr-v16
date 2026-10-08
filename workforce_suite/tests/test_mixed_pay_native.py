"""Native v16 integration checks for the mixed-pay input boundary."""

from datetime import date, timedelta
import os

import frappe
import pytest
from hrms.payroll.doctype.payroll_entry.payroll_entry import PayrollEntry
from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip
from hrms.payroll.doctype.salary_structure.salary_structure import make_salary_slip

from workforce_suite.workforce_suite import daily_wage_input
from workforce_suite.workforce_suite.daily_wage_input import calculate_daily_wage_input, create_daily_wage_input


@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(
        site=os.environ.get("FRAPPE_TEST_SITE", "test_workforce.localhost"),
        sites_path=os.environ.get("FRAPPE_TEST_SITES_PATH", "./sites"),
    )
    frappe.connect()
    yield
    frappe.destroy()


def _employee():
    return frappe.db.get_value(
        "Employee",
        {"name": "TEST-WORKFORCE-DAILY", "company": "Example Company A", "status": "Active"},
        ["name", "company"],
        as_dict=True,
    )


def _safe_structure(employee, name):
    component = frappe.get_doc({
        "doctype": "Salary Component",
        "salary_component": f"Factory Day Rate {frappe.generate_hash(6)}",
        "salary_component_abbr": f"FDR{frappe.generate_hash(3).upper()}",
        "type": "Earning",
        "depends_on_payment_days": 0,
        "is_tax_applicable": 0,
    }).insert(ignore_permissions=True)
    structure = frappe.get_doc({
        "doctype": "Salary Structure",
        "name": name,
        "company": employee.company,
        "currency": "BDT",
        "payroll_frequency": "Monthly",
        "is_active": "Yes",
        "custom_workforce_pay_basis": "Daily Wage",
        "custom_workforce_daily_wage_component": component.name,
        "earnings": [{"salary_component": component.name, "amount": 0, "depends_on_payment_days": 0}],
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
        "company": "Example Company A",
        "half_day_status": half_day_status,
    })
    doc.insert(ignore_permissions=True)
    doc.submit()


def test_daily_wage_native_chain_is_exact_and_idempotent(monkeypatch):
    employee = _employee()
    if not employee:
        pytest.skip("No active COMPANY_A staging employee")
    savepoint = "mixed_daily_native"
    frappe.db.savepoint(savepoint)
    try:
        structure = _safe_structure(employee, f"TEST Daily Wage {frappe.generate_hash(6)}")
        probe = SalarySlip({"doctype": "Salary Slip"})
        probe.employee = employee.name
        probe.start_date = date(2026, 12, 1)
        probe.end_date = date(2026, 12, 31)
        holidays = set(probe.get_holidays_for_employee(probe.start_date, probe.end_date))
        working_days = [
            probe.start_date + timedelta(days=offset)
            for offset in range(31)
            if probe.start_date + timedelta(days=offset) not in holidays
        ]
        for index, day in enumerate(working_days):
            _attendance(employee.name, day, "Present" if index < 10 else "Absent")

        period = frappe.get_doc({
            "doctype": "Workforce Attendance Period",
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
        wage_rows = [row for row in slip.earnings if row.salary_component == structure.custom_workforce_daily_wage_component]
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
    result = calculate_daily_wage_input("TEST-WORKFORCE-DAILY", "2026-09-01", "2026-09-30")
    if not frappe.db.exists("Salary Structure", "Example Daily Wage"):
        pytest.skip("Example Daily Wage is not configured on staging")
    assert result["status"] == "UNRESOLVED"
    assert "no configured Daily Wage Salary Component" in result["reason"]


def test_native_attendance_status_and_holiday_semantics(monkeypatch):
    employee = _employee()
    if not employee:
        pytest.skip("No active COMPANY_A staging employee")
    savepoint = "mixed_native_statuses"
    frappe.db.savepoint(savepoint)
    try:
        _safe_structure(employee, f"TEST Daily Wage {frappe.generate_hash(6)}")
        probe = SalarySlip({"doctype": "Salary Slip"})
        probe.employee = employee.name
        probe.start_date = date(2026, 12, 1)
        probe.end_date = date(2026, 12, 31)
        holidays = set(probe.get_holidays_for_employee(probe.start_date, probe.end_date))
        working_days = [
            probe.start_date + timedelta(days=offset)
            for offset in range(31)
            if probe.start_date + timedelta(days=offset) not in holidays
        ]
        if len(working_days) < 3 or not holidays:
            pytest.skip("Staging employee needs three working days and one holiday")

        settings = type("Settings", (), {
            "consider_marked_attendance_on_holidays": 0,
            "include_holidays_in_total_working_days": 0,
        })()
        monkeypatch.setattr(daily_wage_input, "_half_day_fraction", lambda: 0.5)
        monkeypatch.setattr(daily_wage_input.frappe, "get_cached_doc", lambda _doctype: settings)

        present_day, absent_day, half_day = working_days[:3]
        _attendance(employee.name, present_day, "Present")
        _attendance(employee.name, absent_day, "Absent")
        _attendance(employee.name, half_day, "Half Day", half_day_status="Absent")

        assert daily_wage_input._native_attendance_units(employee.name, present_day, present_day)["payable_units"] == 1
        assert daily_wage_input._native_attendance_units(employee.name, absent_day, absent_day)["payable_units"] == 0
        assert daily_wage_input._native_attendance_units(employee.name, half_day, half_day)["payable_units"] == 0.5

        holiday = next(iter(holidays))
        _attendance(employee.name, holiday, "Absent")
        assert daily_wage_input._native_attendance_units(employee.name, holiday, holiday)["payable_units"] == 0
        settings.include_holidays_in_total_working_days = 1
        assert daily_wage_input._native_attendance_units(employee.name, holiday, holiday)["payable_units"] == 1
    finally:
        frappe.db.rollback(save_point=savepoint)
