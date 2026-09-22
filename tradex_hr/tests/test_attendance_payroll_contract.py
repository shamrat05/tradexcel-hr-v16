import inspect
import os

import frappe
import pytest
from hrms.payroll.doctype.payroll_entry.payroll_entry import PayrollEntry
from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip
from hrms.payroll.doctype.salary_structure.salary_structure import make_salary_slip

from tradex_hr.tradexcel_hr.attendance_payroll_boundary import payment_day_component_findings


@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(
        site=os.environ.get("FRAPPE_TEST_SITE", "hrms-v16.localhost"),
        sites_path=os.environ.get(
            "FRAPPE_TEST_SITES_PATH", "/home/sanchita/frappe-bench-v16/sites"
        ),
    )
    frappe.connect()
    yield
    frappe.destroy()


def test_native_payroll_entry_is_the_attendance_coverage_owner():
    source = inspect.getsource(PayrollEntry.get_employees_with_unmarked_attendance)
    assert "get_employee_and_attendance_details" in source
    assert "get_holidays_count" in source


def test_native_salary_slip_selects_latest_applicable_assignment():
    source = inspect.getsource(SalarySlip.set_salary_structure_assignment)
    assert '"from_date": ("<=", self.actual_start_date)' in source
    assert 'order_by="from_date desc"' in source


def test_native_salary_slip_calculates_payment_days_from_attendance():
    source = inspect.getsource(SalarySlip.get_working_days_details)
    assert "calculate_lwp_ppl_and_absent_days_based_on_attendance" in source
    assert "get_unmarked_days" in source
    assert "self.payment_days" in source


def test_daily_wage_formula_and_native_proration_cannot_be_silently_combined():
    findings = payment_day_component_findings([
        {
            "parent": "TCL Daily Wage",
            "salary_component": "Daily Wage",
            "formula": "base * payment_days",
            "depends_on_payment_days": 1,
        },
        {
            "parent": "TCL Daily Wage",
            "salary_component": "Safe Wage",
            "formula": "base * payment_days",
            "depends_on_payment_days": 0,
        },
    ])

    assert len(findings) == 1
    assert findings[0]["salary_structure"] == "TCL Daily Wage"


def test_native_daily_wage_configuration_gives_350_per_payable_day():
    """Exercise SalarySlip's real component path without saving a Salary Slip."""
    employee = frappe.db.get_value(
        "Salary Structure Assignment",
        {"salary_structure": "TCL Daily Wage", "docstatus": 1},
        "employee",
    )
    if not employee:
        pytest.skip("TCL Daily Wage is not assigned on this test site")

    for payable_days, expected in ((1, 350), (10, 3500)):
        slip = make_salary_slip("TCL Daily Wage", employee=employee, posting_date="2026-09-01")
        slip.payment_days = payable_days
        slip.total_working_days = 26
        slip.earnings = []
        slip.data = {"base": 350, "payment_days": payable_days}
        slip.default_data = {"base": 350, "payment_days": payable_days}
        rows = []
        for row in slip._evaluated_components["earnings"]:
            if row.salary_component == "Daily Wage":
                row.depends_on_payment_days = 0
                rows.append(row)
        slip._evaluated_components["earnings"] = rows
        slip.calculate_component_amounts("earnings")

        assert slip.earnings[0].amount == expected
