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

from workforce_suite.workforce_suite.attendance_payroll_boundary import (
    require_finalized_attendance, native_attendance_fields,
)
from workforce_suite.workforce_suite.pay_basis import DAILY, resolve_daily_rate, resolve_pay_basis
from workforce_suite.workforce_suite.flexible_work import apply_policy_to_daily_wage


def _attendance_rows(employee: str, start: date, end: date) -> list[dict[str, Any]]:
    return frappe.get_all(
        "Attendance",
        filters={
            "employee": employee,
            "attendance_date": ["between", [start, end]],
            "docstatus": 1,
        },
        fields=native_attendance_fields(["name", "attendance_date", "status", "leave_type", "leave_application", "half_day_status", "working_hours", "branch", "department"]),
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
    consider_marked_holidays = cint(settings.include_holidays_in_total_working_days) and cint(
        settings.consider_marked_attendance_on_holidays
    )
    lwp, absent = slip.calculate_lwp_ppl_and_absent_days_based_on_attendance(
        holidays,
        fraction,
        consider_marked_holidays,
    )
    payment_days = slip.get_payment_days(cint(settings.include_holidays_in_total_working_days))
    if payment_days <= lwp:
        units = 0.0
    else:
        units = payment_days - lwp - absent
        half_absent = slip.get_half_absent_days(consider_marked_holidays, holidays)
        units -= half_absent * fraction

    return {"status": "READY", "payable_units": flt(max(units, 0)), "native": True,
            "holidays": holidays, "include_holidays": cint(settings.include_holidays_in_total_working_days),
            "half_day_fraction": fraction}


def _inspect_daily_wage_structure(basis: dict[str, Any]) -> dict[str, Any]:
    if basis.get("status") != DAILY:
        return {"status": basis.get("status"), "reason": basis.get("reason")}
    component = basis.get("daily_wage_component")
    if not component:
        return {
            "status": "UNRESOLVED",
            "employee": basis.get("employee"),
            "salary_structure": basis.get("salary_structure"),
            "reason": "The assigned Daily Wage Salary Structure has no configured Daily Wage Salary Component.",
        }
    structure_rows = frappe.get_all(
        "Salary Detail",
        filters={
            "parent": basis["salary_structure"], "parenttype": "Salary Structure",
            "salary_component": component,
        },
        fields=["parent", "salary_component", "formula", "amount", "amount_based_on_formula", "depends_on_payment_days"],
    )
    component_master = frappe.db.get_value(
        "Salary Component",
        component,
        ["type", "disabled"],
        as_dict=True,
    )
    if isinstance(component_master, str):
        component_master = {"type": component_master, "disabled": 0}
    if not component_master:
        return {
            "status": "BLOCKED_UNSAFE_STRUCTURE",
            "employee": basis.get("employee"),
            "salary_structure": basis.get("salary_structure"),
            "reason": "The configured Daily Wage Salary Component does not exist.",
        }
    if cint(component_master.get("disabled", 0)):
        return {
            "status": "BLOCKED_UNSAFE_STRUCTURE",
            "employee": basis.get("employee"),
            "salary_structure": basis.get("salary_structure"),
            "reason": "The configured Daily Wage Salary Component is disabled.",
        }
    if component_master.get("type") != "Earning":
        return {
            "status": "BLOCKED_UNSAFE_STRUCTURE",
            "employee": basis.get("employee"),
            "salary_structure": basis.get("salary_structure"),
            "reason": "The configured Daily Wage Salary Component must be an Earning.",
        }
    if (
        len(structure_rows) != 1
        or structure_rows[0].get("depends_on_payment_days")
        or structure_rows[0].get("amount_based_on_formula")
        or (structure_rows[0].get("formula") or "").strip()
        or flt(structure_rows[0].get("amount")) != 0
    ):
        return {
            "status": "BLOCKED_UNSAFE_STRUCTURE",
            "employee": basis.get("employee"),
            "salary_structure": basis.get("salary_structure"),
            "reason": "The configured Daily Wage Salary Component must be one neutral, zero-valued Earning row with no formula or payment-day proration.",
        }
    return {
        "status": "READY",
        "employee": basis["employee"],
        "salary_structure": basis["salary_structure"],
        "salary_component": component,
    }


def inspect_daily_wage_structure(
    employee: str,
    start_date: str | date,
    end_date: str | date | None = None,
) -> dict[str, Any]:
    """Inspect the effective structure without calculating money or requiring attendance."""
    basis = resolve_pay_basis(
        employee,
        getdate(start_date),
        getdate(end_date) if end_date else None,
    )
    return _inspect_daily_wage_structure(basis)


def calculate_daily_wage_input(employee: str, start_date: str | date, end_date: str | date) -> dict[str, Any]:
    """Calculate an auditable Daily Wage amount without creating payroll data."""
    start, end = getdate(start_date), getdate(end_date)
    basis = resolve_pay_basis(employee, start, end)
    if basis.get("status") != DAILY:
        return {"status": basis.get("status"), "employee": employee, "reason": basis.get("reason")}
    rate = resolve_daily_rate(basis)
    if rate["status"] != "READY":
        return rate
    structure = _inspect_daily_wage_structure(basis)
    if structure["status"] != "READY":
        return structure

    employee_row = frappe.db.get_value(
        "Employee", employee,
        ["date_of_joining", "relieving_date", "company", "branch", "department"],
        as_dict=True,
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
    units = apply_policy_to_daily_wage(employee, employee_row, actual_start, actual_end, rows, units)
    units["attendance_count"] = len(rows)
    if units["status"] != "READY":
        return {"status": units["status"], "employee": employee, "reason": units["reason"]}
    amount = flt(rate["rate"] * units["payable_units"])
    return {
        "status": "READY",
        "employee": employee,
        "assignment": basis["assignment"],
        "salary_structure": basis["salary_structure"],
        "salary_component": basis["daily_wage_component"],
        "rate": rate["rate"],
        "payable_units": units["payable_units"],
        "attendance_count": units["attendance_count"],
        "amount": amount,
        "payroll_date": actual_end,
        "source": "submitted Attendance + Salary Structure Assignment.base",
    }


def _submit_derived_daily_wage(doc, period, expected: dict[str, Any]) -> None:
    """Submit only an exact finalized, system-derived Daily Wage input."""
    if frappe.session.user != "Administrator":
        roles = set(frappe.get_roles())
        if "Workforce Payroll Manager" not in roles:
            frappe.throw(_("Workforce Payroll Manager role is required for derived Daily Wage payroll input."), frappe.PermissionError)
        frappe.has_permission("Payroll Entry", "create", throw=True)
        if not frappe.has_permission("Employee", "read", doc.employee):
            frappe.throw(_("You do not have access to this employee."), frappe.PermissionError)

    current = require_finalized_attendance(period.company, period.from_date, period.to_date)
    if current.name != period.name or current.revision != period.revision:
        frappe.throw(_("Finalized Attendance changed before Daily Wage input submission."))
    recalculated = calculate_daily_wage_input(doc.employee, period.from_date, period.to_date)
    expected_key = f"DAILY-WAGE:{period.name}:r{period.revision}:{doc.employee}:{expected['salary_component']}"
    if (
        recalculated.get("status") != "READY"
        or recalculated.get("amount") != expected["amount"]
        or recalculated.get("salary_component") != expected["salary_component"]
        or doc.company != expected["company"]
        or doc.salary_component != expected["salary_component"]
        or doc.amount != expected["amount"]
        or doc.payroll_date != expected["payroll_date"]
        or doc.ref_doctype != expected["ref_doctype"]
        or doc.ref_docname != expected["ref_docname"]
        or doc.custom_workforce_payroll_input_key != expected_key
    ):
        frappe.throw(_("Daily Wage input no longer matches its finalized Attendance and pay assignment."))

    if frappe.session.user == "Administrator" or doc.has_permission("submit"):
        doc.submit()
    else:
        # The manager cannot submit arbitrary Additional Salary; only this
        # provenance- and amount-checked server action may submit this record.
        doc.flags.ignore_permissions = True
        doc.submit()


def create_daily_wage_input(
    employee: str,
    attendance_period: str,
    *,
    submit: bool = True,
) -> dict[str, Any]:
    """Create/reuse one native Additional Salary for a finalized period."""
    period = require_finalized_attendance(
        frappe.db.get_value("Workforce Attendance Period", attendance_period, "company"),
        frappe.db.get_value("Workforce Attendance Period", attendance_period, "from_date"),
        frappe.db.get_value("Workforce Attendance Period", attendance_period, "to_date"),
    )
    if period.name != attendance_period:
        frappe.throw(_("Attendance period resolution changed unexpectedly"))

    result = calculate_daily_wage_input(employee, period.from_date, period.to_date)
    if result["status"] != "READY":
        frappe.throw(_("Daily Wage input is blocked for {0}: {1}").format(employee, result.get("reason", result["status"])))
    if result["amount"] <= 0:
        return {**result, "status": "NO_PAYABLE_UNITS"}

    salary_component = result["salary_component"]
    key = f"DAILY-WAGE:{period.name}:r{period.revision}:{employee}:{salary_component}"
    company = frappe.db.get_value("Employee", employee, "company")
    expected = {
        "employee": employee,
        "company": company,
        "salary_component": salary_component,
        "amount": result["amount"],
        "payroll_date": result["payroll_date"],
        "ref_doctype": "Workforce Attendance Period",
        "ref_docname": period.name,
    }
    existing = _get_existing_input(key)
    if existing:
        reused = _reuse_existing_input(existing, expected, submit=False, result=result)
        if submit and existing.docstatus == 0:
            _submit_derived_daily_wage(frappe.get_doc("Additional Salary", existing.name), period, expected)
        return reused
    prior = _find_period_daily_wage_input(employee, period)
    if prior:
        frappe.throw(
            _("Existing Daily Wage input {0} uses a different configured Salary Component. Review and reconcile it before retrying.").format(prior.name)
        )

    doc = frappe.get_doc({
        "doctype": "Additional Salary",
        "employee": employee,
        "company": company,
        "salary_component": salary_component,
        "amount": result["amount"],
        "payroll_date": result["payroll_date"],
        "overwrite_salary_structure_amount": 0,
        "ref_doctype": "Workforce Attendance Period",
        "ref_docname": period.name,
        "custom_workforce_payroll_input_key": key,
    })
    try:
        doc.insert()
        if submit:
            _submit_derived_daily_wage(doc, period, expected)
    except frappe.DuplicateEntryError:
        # The unique key is the concurrency boundary. A racing request may
        # lose the insert after both callers observed no existing row; recover
        # the winner and return the same idempotent result.
        recovered = _recover_duplicate_input(key, expected, submit=False, result=result)
        if recovered is None:
            raise
        if submit:
            existing = _get_existing_input(key)
            if existing and existing.docstatus == 0:
                _submit_derived_daily_wage(frappe.get_doc("Additional Salary", existing.name), period, expected)
        return recovered
    return {**result, "status": "CREATED", "additional_salary": doc.name}


def _get_existing_input(key: str):
    return frappe.db.get_value(
        "Additional Salary",
        {"custom_workforce_payroll_input_key": key},
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


def _find_period_daily_wage_input(employee: str, period):
    """Find a prior derived input for this employee/revision under old component authority."""
    return _find_period_daily_wage_inputs([employee], period).get(employee)


def _find_period_daily_wage_inputs(employees: list[str], period):
    """Batch prior period inputs so managed payroll does not add an N+1 query."""
    if not employees:
        return {}
    prefixes = {
        employee: f"DAILY-WAGE:{period.name}:r{period.revision}:{employee}:"
        for employee in employees
    }
    found = {}
    rows = frappe.get_all(
        "Additional Salary",
        filters={
            "employee": ["in", employees],
            "ref_doctype": "Workforce Attendance Period",
            "ref_docname": period.name,
        },
        fields=["name", "employee", "salary_component", "custom_workforce_payroll_input_key", "docstatus", "disabled"],
    )
    for row in rows:
        key = row.custom_workforce_payroll_input_key or ""
        if key.startswith(prefixes.get(row.employee, "\0")):
            found[row.employee] = row
    return found


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
