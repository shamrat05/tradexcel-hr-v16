import inspect
import os

import frappe
import pytest
from hrms.payroll.doctype.payroll_entry.payroll_entry import PayrollEntry
from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip

from workforce_suite.workforce_suite.attendance_payroll_boundary import payment_day_component_findings


@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(
        site=os.environ.get("FRAPPE_TEST_SITE", "test_workforce.localhost"),
        sites_path=os.environ.get(
            "FRAPPE_TEST_SITES_PATH", "./sites"
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
            "parent": "Example Daily Wage",
            "salary_component": "Daily Wage",
            "formula": "base * payment_days",
            "depends_on_payment_days": 1,
        },
        {
            "parent": "Example Daily Wage",
            "salary_component": "Safe Wage",
            "formula": "base * payment_days",
            "depends_on_payment_days": 0,
        },
    ])

    assert len(findings) == 1
    assert findings[0]["salary_structure"] == "Example Daily Wage"


def test_current_daily_wage_structure_is_explicitly_detected_as_unsafe():
    """The legacy linked structure must stay blocked until migrated safely."""
    from workforce_suite.workforce_suite.attendance_payroll_boundary import payment_day_component_findings

    rows = frappe.get_all(
        "Salary Detail",
        filters={"parent": "Example Daily Wage", "parenttype": "Salary Structure"},
        fields=["parent", "salary_component", "formula", "depends_on_payment_days"],
    )
    if not rows:
        pytest.skip("Example Daily Wage is not configured on this test site")
    assert payment_day_component_findings(rows)
