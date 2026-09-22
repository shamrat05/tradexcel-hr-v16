"""Prepare native HRMS draft payroll without calculating payroll locally."""

from __future__ import annotations

from datetime import date
from typing import Any

import frappe
from frappe import _
from frappe.utils import getdate
from hrms.payroll.doctype.payroll_entry.payroll_entry import PayrollEntry

from tradex_hr.tradexcel_hr.attendance_payroll_boundary import (
    _attendance_required_for_payroll,
    _employees_for_period,
    _row_value,
    _unapproved_overtime,
    current_attendance_period_hash,
    inspect_attendance_integrity,
)
from tradex_hr.tradexcel_hr.daily_wage_input import calculate_daily_wage_input, create_daily_wage_input
from tradex_hr.tradexcel_hr.pay_basis import DAILY, MONTHLY, resolve_pay_basis


def _dates(start_date: str | date, end_date: str | date) -> tuple[date, date]:
    start, end = getdate(start_date), getdate(end_date)
    if not start or not end or start > end:
        frappe.throw(_("Payroll dates are invalid"))
    return start, end


def _period_attendance_gate(company: str, start: date, end: date, employee_ids: list[str]):
    if not employee_ids and not _attendance_required_for_payroll():
        return []

    periods = frappe.get_all(
        "Tradexcel Attendance Period",
        filters={"company": company, "from_date": start, "to_date": end, "status": "Finalized"},
        fields=["name", "attendance_hash"],
    )
    if len(periods) != 1:
        return [
            {
                "code": "BLOCKED_ATTENDANCE_PERIOD",
                "employee": employee,
                "reason": "The exact Attendance Period is not finalized once for this payroll range.",
            }
            for employee in employee_ids
        ]

    if current_attendance_period_hash(company, start, end) != _row_value(periods[0], "attendance_hash"):
        return [
            {
                "code": "BLOCKED_ATTENDANCE_STALE",
                "employee": employee,
                "reason": "Finalized Attendance changed after review; reopen and finalize it again.",
            }
            for employee in employee_ids
        ]

    inspection = inspect_attendance_integrity(company, start, end, employee_ids)
    return [
        {
            "code": "BLOCKED_ATTENDANCE",
            "employee": item.get("employee") or employee,
            "reason": item.get("reason", item.get("code", "Attendance needs review.")),
        }
        for item in inspection.get("blockers", [])
        for employee in ([item.get("employee")] if item.get("employee") else employee_ids)
    ]


def inspect_native_payroll_readiness(
    company: str,
    start_date: str | date,
    end_date: str | date,
    employee_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Return one explainable outcome for every employee in native scope."""
    start, end = _dates(start_date, end_date)
    employees = _employees_for_period(company, start, end, employee_ids)
    ids = [_row_value(row, "name") for row in employees]
    outcomes = {
        employee: {"employee": employee, "employee_data": row, "status": "READY"}
        for employee, row in ((_row_value(row, "name"), row) for row in employees)
    }

    def block(employee: str, code: str, reason: str):
        if outcomes[employee]["status"] == "READY":
            outcomes[employee].update({"status": code, "reason": reason})

    for row in employees:
        employee = _row_value(row, "name")
        if _row_value(row, "status") not in {"Active", "Left"}:
            block(employee, "BLOCKED_EMPLOYMENT_STATUS", f"Employment status {_row_value(row, 'status')!r} has no approved payroll meaning.")
            continue
        basis = resolve_pay_basis(employee, start, end)
        if basis.get("status") not in {MONTHLY, DAILY}:
            block(employee, "BLOCKED_PAY_BASIS", basis.get("reason", basis.get("status", "Pay basis is unresolved.")))
        else:
            outcomes[employee]["pay_basis"] = basis

    required_attendance = [employee for employee, result in outcomes.items() if result.get("pay_basis", {}).get("status") == DAILY]
    if _attendance_required_for_payroll():
        required_attendance = ids
    for finding in _period_attendance_gate(company, start, end, required_attendance):
        employee = finding.get("employee")
        if employee in outcomes:
            block(employee, finding["code"], finding["reason"])

    for row in _unapproved_overtime(company, start, end, ids):
        employee = _row_value(row, "employee")
        if employee in outcomes:
            block(employee, "BLOCKED_OT", "Attendance overtime is not in a submitted native Overtime Slip.")

    for employee, outcome in outcomes.items():
        if outcome["status"] != "READY" or outcome.get("pay_basis", {}).get("status") != DAILY:
            continue
        result = calculate_daily_wage_input(employee, start, end)
        if result.get("status") != "READY":
            block(employee, "BLOCKED_DAILY_WAGE_STRUCTURE", result.get("reason", result.get("status", "Daily Wage input is blocked.")))

    blockers = [result for result in outcomes.values() if result["status"] != "READY"]
    return {
        "company": company,
        "from_date": start,
        "to_date": end,
        "employee_count": len(employees),
        "ready_count": len(employees) - len(blockers),
        "blocked_count": len(blockers),
        "status": "BLOCKED" if blockers else "READY",
        "outcomes": list(outcomes.values()),
    }


def _existing_payroll_entry(company: str, start: date, end: date):
    rows = frappe.get_all(
        "Payroll Entry",
        filters={"company": company, "start_date": start, "end_date": end, "docstatus": ["<", 2]},
        fields=["name", "docstatus", "status", "salary_slips_created"],
        order_by="creation asc",
        limit=1,
    )
    return rows[0] if rows else None


def prepare_native_payroll(
    company: str,
    start_date: str | date,
    end_date: str | date,
    *,
    posting_date: str | date | None = None,
    employee_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Create/reuse a native Payroll Entry and native draft Salary Slips."""
    start, end = _dates(start_date, end_date)
    readiness = inspect_native_payroll_readiness(company, start, end, employee_ids)
    if readiness["status"] != "READY":
        return readiness

    existing = _existing_payroll_entry(company, start, end)
    if existing:
        return {
            **readiness,
            "status": "EXISTING",
            "payroll_entry": _row_value(existing, "name"),
        }

    currency, payable_account = frappe.get_cached_value(
        "Company", company, ["default_currency", "default_payroll_payable_account"]
    )
    if not currency or not payable_account:
        return {
            **readiness,
            "status": "BLOCKED_PAYROLL_ACCOUNT",
            "blockers": [{"code": "BLOCKED_PAYROLL_ACCOUNT", "reason": "Company currency/payroll payable account is not configured."}],
        }

    daily_results = []
    for outcome in readiness["outcomes"]:
        if outcome.get("pay_basis", {}).get("status") != DAILY:
            continue
        try:
            daily_results.append(create_daily_wage_input(outcome["employee"], _finalized_period_name(company, start, end)))
        except Exception as exc:
            return {
                **readiness,
                "status": "BLOCKED_DAILY_WAGE_INPUT",
                "blocked_count": 1,
                "blockers": [{"employee": outcome["employee"], "code": "BLOCKED_DAILY_WAGE_INPUT", "reason": str(exc)}],
            }

    frappe.has_permission("Payroll Entry", "create", throw=True)
    entry = frappe.get_doc({
        "doctype": "Payroll Entry",
        "company": company,
        "posting_date": posting_date or end,
        "start_date": start,
        "end_date": end,
        "payroll_frequency": "Monthly",
        "currency": currency,
        "exchange_rate": 1,
        "payroll_payable_account": payable_account,
        "salary_slip_based_on_timesheet": 0,
        "validate_attendance": 1 if _attendance_required_for_payroll() else 0,
        "employees": [
            {"employee": outcome["employee"], "employee_name": _row_value(outcome["employee_data"], "employee_name")}
            for outcome in readiness["outcomes"]
        ],
    })
    entry.insert()
    entry.create_salary_slips()
    entry.reload()
    return {
        **readiness,
        "status": "DRAFTS_CREATED" if entry.salary_slips_created else "QUEUED",
        "payroll_entry": entry.name,
        "daily_inputs": daily_results,
        "salary_slips": [row.name for row in entry.get_sal_slip_list(ss_status=0, as_dict=True)],
    }


def _finalized_period_name(company: str, start: date, end: date) -> str:
    rows = frappe.get_all(
        "Tradexcel Attendance Period",
        filters={"company": company, "from_date": start, "to_date": end, "status": "Finalized"},
        pluck="name",
    )
    if len(rows) != 1:
        frappe.throw(_("Exactly one finalized Attendance Period is required before Daily Wage preparation."))
    return rows[0]
