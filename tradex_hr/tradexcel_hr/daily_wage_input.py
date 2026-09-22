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
from frappe.utils import flt, getdate

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


def _leave_type_map(names: set[str]) -> dict[str, dict[str, Any]]:
    if not names:
        return {}
    rows = frappe.get_all(
        "Leave Type",
        filters={"name": ["in", sorted(names)]},
        fields=["name", "is_lwp", "is_ppl", "fraction_of_daily_salary_per_leave", "include_holiday"],
    )
    return {row.name: row for row in rows}


def _attendance_units(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Translate native Attendance statuses using explicit native settings."""
    if len({str(row.get("attendance_date")) for row in rows}) != len(rows):
        return {"status": "CONFLICT", "reason": "Multiple submitted Attendance rows exist for one employee/date"}

    half_day_fraction = _half_day_fraction()
    leave_types = _leave_type_map({row.get("leave_type") for row in rows if row.get("leave_type")})
    units = 0.0
    for row in rows:
        status = row.get("status")
        if status in {"Present", "Work From Home"}:
            units += 1
        elif status == "Absent":
            continue
        elif status == "Half Day":
            # HRMS treats the other half as Absent when explicitly marked;
            # otherwise the full day remains payable. The configured native
            # fraction is therefore applied only to the absent half.
            units += half_day_fraction if row.get("half_day_status") == "Absent" else 1
        elif status == "On Leave":
            leave = leave_types.get(row.get("leave_type"))
            if not leave:
                return {"status": "UNRESOLVED", "reason": "On Leave Attendance has no valid Leave Type"}
            if leave.is_lwp:
                continue
            if leave.is_ppl:
                units += flt(leave.fraction_of_daily_salary_per_leave)
            else:
                units += 1
        else:
            return {"status": "UNRESOLVED", "reason": f"Unsupported Attendance status {status!r}"}
    return {"status": "READY", "payable_units": flt(units), "attendance_count": len(rows)}


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
    units = _attendance_units(rows)
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
    existing = frappe.db.get_value(
        "Additional Salary",
        {"custom_tradex_payroll_input_key": key},
        ["name", "amount", "docstatus"],
        as_dict=True,
    )
    if existing:
        if flt(existing.amount) != flt(result["amount"]):
            frappe.throw(_("Existing Daily Wage input {0} does not match finalized Attendance").format(existing.name))
        return {**result, "status": "EXISTING", "additional_salary": existing.name}

    doc = frappe.get_doc({
        "doctype": "Additional Salary",
        "employee": employee,
        "company": frappe.db.get_value("Employee", employee, "company"),
        "salary_component": salary_component,
        "amount": result["amount"],
        "payroll_date": period.to_date,
        "overwrite_salary_structure_amount": 0,
        "ref_doctype": "Tradexcel Attendance Period",
        "ref_docname": period.name,
        "custom_tradex_payroll_input_key": key,
    })
    doc.insert(ignore_permissions=True)
    if submit:
        doc.submit()
    return {**result, "status": "CREATED", "additional_salary": doc.name}
