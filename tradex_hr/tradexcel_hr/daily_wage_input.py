"""Derive Daily Wage payroll input from finalized native Attendance.

This is an input adapter, not a Salary Slip engine.  It counts submitted
Attendance, reads the effective SSA.base, and emits one native Additional
Salary document.  Raw Employee Checkin is intentionally absent from this
module.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

from tradex_hr.tradexcel_hr.attendance_payroll_boundary import (
    payment_day_component_findings,
    require_finalized_attendance,
)
from tradex_hr.tradexcel_hr.pay_basis import DAILY, resolve_daily_rate, resolve_pay_basis


DEFAULT_COMPONENT = "Daily Wage"


def _attendance_rows(employee: str, start: date, end: date) -> list[dict[str, Any]]:
    return frappe.get_all(
        "Attendance",
        filters={
            "employee": employee,
            "attendance_date": ["between", [start, end]],
            "docstatus": 1,
        },
        fields=["name", "attendance_date", "status", "leave_type", "half_day_status"],
        order_by="attendance_date asc",
    )


def _half_day_fraction() -> float:
    value = frappe.db.get_single_value("Payroll Settings", "daily_wages_fraction_for_half_day")
    value = flt(value)
    if value <= 0 or value > 1:
        frappe.throw(_("Payroll Settings must contain a valid daily-wage half-day fraction"))
    return value


def _native_attendance_units(
    employee: str,
    start: date,
    end: date,
) -> dict[str, Any]:
    """Use HRMS Salary Slip's attendance semantics without creating a slip.

    This deliberately delegates holidays, LWP/PPL, half-day handling and the
    holiday-attendance setting to native HRMS methods. The caller must still
    require a finalized Attendance Period before creating payroll input.
    """
    from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip

    settings = frappe.get_cached_doc("Payroll Settings")
    fraction = _half_day_fraction()
    slip = SalarySlip({"doctype": "Salary Slip"})
    slip.employee = employee
    slip.start_date = start
    slip.end_date = end

    holidays = slip.get_holidays_for_employee(start, end)
    lwp, absent = slip.calculate_lwp_ppl_and_absent_days_based_on_attendance(
        holidays,
        fraction,
        cint(settings.consider_marked_attendance_on_holidays),
    )
    payment_days = slip.get_payment_days(cint(settings.include_holidays_in_total_working_days))
    if payment_days <= lwp:
        units = 0.0
    else:
        units = payment_days - lwp - absent
        half_absent = slip.get_half_absent_days(
            cint(settings.consider_marked_attendance_on_holidays), holidays
        )
        units -= half_absent * fraction

    return {"status": "READY", "payable_units": flt(max(units, 0)), "native": True}


def calculate_daily_wage_input(employee: str, start_date: str | date, end_date: str | date) -> dict[str, Any]:
    """Calculate an auditable Daily Wage amount without creating payroll data."""
    start, end = getdate(start_date), getdate(end_date)
    basis = resolve_pay_basis(employee, start, end)
    if basis.get("status") != DAILY:
        return {"status": basis.get("status"), "employee": employee, "reason": basis.get("reason")}
    rate = resolve_daily_rate(basis)
    if rate["status"] != "READY":
        return rate
    structure_rows = frappe.get_all(
        "Salary Detail",
        filters={"parent": basis["salary_structure"], "parenttype": "Salary Structure"},
        fields=["parent", "salary_component", "formula", "depends_on_payment_days"],
    )
    unsafe = payment_day_component_findings(structure_rows)
    if unsafe:
        return {
            "status": "BLOCKED_UNSAFE_STRUCTURE",
            "employee": employee,
            "salary_structure": basis["salary_structure"],
            "reason": "Daily Wage structure still calculates payment_days; converge it to a zero/non-prorated wage row before creating native inputs",
        }

    employee_row = frappe.db.get_value(
        "Employee", employee, ["date_of_joining", "relieving_date"], as_dict=True
    )
    joining = employee_row.get("date_of_joining") if isinstance(employee_row, dict) else employee_row.date_of_joining
    relieving = employee_row.get("relieving_date") if isinstance(employee_row, dict) else employee_row.relieving_date
    actual_start = max(start, getdate(joining)) if joining else start
    actual_end = min(end, getdate(relieving)) if relieving else end
    rows = _attendance_rows(employee, actual_start, actual_end) if actual_start <= actual_end else []
    if len({str(row.get("attendance_date")) for row in rows}) != len(rows):
        return {
            "status": "CONFLICT",
            "employee": employee,
            "reason": "Multiple submitted Attendance rows exist for one employee/date",
        }
    units = _native_attendance_units(
        employee,
        actual_start,
        actual_end,
    )
    units["attendance_count"] = len(rows)
    if units["status"] != "READY":
        return {"status": units["status"], "employee": employee, "reason": units["reason"]}
    amount = flt(rate["rate"] * units["payable_units"])
    return {
        "status": "READY",
        "employee": employee,
        "assignment": basis["assignment"],
        "salary_structure": basis["salary_structure"],
        "rate": rate["rate"],
        "payable_units": units["payable_units"],
        "attendance_count": units["attendance_count"],
        "amount": amount,
        "source": "submitted Attendance + Salary Structure Assignment.base",
    }


def create_daily_wage_input(
    employee: str,
    attendance_period: str,
    *,
    salary_component: str = DEFAULT_COMPONENT,
    submit: bool = True,
) -> dict[str, Any]:
    """Create/reuse one native Additional Salary for a finalized period."""
    period = require_finalized_attendance(
        frappe.db.get_value("Tradexcel Attendance Period", attendance_period, "company"),
        frappe.db.get_value("Tradexcel Attendance Period", attendance_period, "from_date"),
        frappe.db.get_value("Tradexcel Attendance Period", attendance_period, "to_date"),
    )
    if period.name != attendance_period:
        frappe.throw(_("Attendance period resolution changed unexpectedly"))

    result = calculate_daily_wage_input(employee, period.from_date, period.to_date)
    if result["status"] != "READY":
        frappe.throw(_("Daily Wage input is blocked for {0}: {1}").format(employee, result.get("reason", result["status"])))
    if result["amount"] <= 0:
        return {**result, "status": "NO_PAYABLE_UNITS"}

    key = f"DAILY-WAGE:{period.name}:r{period.revision}:{employee}:{salary_component}"
    company = frappe.db.get_value("Employee", employee, "company")
    expected = {
        "employee": employee,
        "company": company,
        "salary_component": salary_component,
        "amount": result["amount"],
        "payroll_date": period.to_date,
        "ref_doctype": "Tradexcel Attendance Period",
        "ref_docname": period.name,
    }
    existing = _get_existing_input(key)
    if existing:
        return _reuse_existing_input(existing, expected, submit=submit, result=result)

    doc = frappe.get_doc({
        "doctype": "Additional Salary",
        "employee": employee,
        "company": company,
        "salary_component": salary_component,
        "amount": result["amount"],
        "payroll_date": period.to_date,
        "overwrite_salary_structure_amount": 0,
        "ref_doctype": "Tradexcel Attendance Period",
        "ref_docname": period.name,
        "custom_tradex_payroll_input_key": key,
    })
    try:
        doc.insert(ignore_permissions=True)
        if submit:
            doc.submit()
    except frappe.DuplicateEntryError:
        # The unique key is the concurrency boundary. A racing request may
        # lose the insert after both callers observed no existing row; recover
        # the winner and return the same idempotent result.
        recovered = _recover_duplicate_input(key, expected, submit=submit, result=result)
        if recovered is None:
            raise
        return recovered
    return {**result, "status": "CREATED", "additional_salary": doc.name}


def _get_existing_input(key: str):
    return frappe.db.get_value(
        "Additional Salary",
        {"custom_tradex_payroll_input_key": key},
        [
            "name",
            "employee",
            "company",
            "salary_component",
            "amount",
            "payroll_date",
            "ref_doctype",
            "ref_docname",
            "docstatus",
            "disabled",
        ],
        as_dict=True,
    )


def _recover_duplicate_input(key: str, expected: dict[str, Any], *, submit: bool, result: dict[str, Any]):
    existing = _get_existing_input(key)
    if not existing:
        return None
    return _reuse_existing_input(existing, expected, submit=submit, result=result)


def _reuse_existing_input(existing, expected: dict[str, Any], *, submit: bool, result: dict[str, Any]):
    def value(field: str):
        return existing.get(field) if hasattr(existing, "get") else getattr(existing, field, None)

    mismatches = []
    for field in ("employee", "company", "salary_component", "payroll_date", "ref_doctype", "ref_docname"):
        if str(value(field) or "") != str(expected.get(field) or ""):
            mismatches.append(field)
    if flt(value("amount")) != flt(expected["amount"]):
        mismatches.append("amount")
    if mismatches:
        frappe.throw(
            _("Existing Daily Wage input {0} does not match finalized Attendance ({1})").format(
                value("name"), ", ".join(mismatches)
            )
        )
    if value("docstatus") == 2 or value("disabled"):
        frappe.throw(
            _("Daily Wage input key {0} belongs to a cancelled or disabled record; review the period revision").format(
                value("name")
            )
        )
    if submit and value("docstatus") == 0:
        frappe.get_doc("Additional Salary", value("name")).submit()
    return {**result, "status": "EXISTING", "additional_salary": value("name")}
