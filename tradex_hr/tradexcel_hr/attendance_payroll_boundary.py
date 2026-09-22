"""Keep payroll input on native Attendance and approved native overtime.

This module is deliberately a boundary, not a second attendance ledger. It
uses HRMS's Payroll Entry attendance check for coverage and only reads native
Attendance, Attendance Request, Leave Application, Overtime Slip, and the
small Tradexcel evidence tables needed to find unresolved inputs.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
import hashlib
import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import getdate


READY = "READY"
REVIEW = "REVIEW"
BLOCKED = "BLOCKED"


def _row_value(row: Any, field: str, default=None):
    if isinstance(row, dict):
        return row.get(field, default)
    return getattr(row, field, default)


def _period_dates(start_date: str | date, end_date: str | date) -> tuple[date, date]:
    start = getdate(start_date)
    end = getdate(end_date)
    if not start or not end or start > end:
        frappe.throw(_("Attendance period dates are invalid"))
    return start, end


def classify_employment_boundaries(
    rows: list[dict[str, Any]], start_date: str | date, end_date: str | date
) -> dict[str, dict[str, Any]]:
    """Return one explicit result for every employee in the period universe."""
    start, end = _period_dates(start_date, end_date)
    results = {}
    for row in rows:
        employee = row["name"]
        joining = getdate(row.get("date_of_joining")) if row.get("date_of_joining") else None
        relieving = getdate(row.get("relieving_date")) if row.get("relieving_date") else None
        status = row.get("status") or "Active"
        if joining and start < joining <= end:
            results[employee] = {
                "status": "BLOCKED_JOIN_MID_PERIOD",
                "employee": employee,
                "reason": "Employee joined during the payroll period; native proration is not part of this boundary.",
            }
        elif relieving and start <= relieving < end:
            results[employee] = {
                "status": "BLOCKED_RELIEVE_MID_PERIOD",
                "employee": employee,
                "reason": "Employee left during the payroll period; native final-settlement handling is not part of this boundary.",
            }
        elif status not in {"Active", "Left"}:
            results[employee] = {
                "status": "BLOCKED_EMPLOYMENT_STATUS",
                "employee": employee,
                "reason": f"Employment status {status!r} has no approved payroll meaning for this period.",
            }
        else:
            results[employee] = {"status": READY, "employee": employee}
    return results


def build_boundary_result(blockers: list[dict[str, Any]]) -> dict[str, Any]:
    """Turn validator findings into a small operator-facing result."""
    if any(item.get("severity", "block") == "block" for item in blockers):
        status = BLOCKED
    elif blockers:
        status = REVIEW
    else:
        status = READY
    return {"status": status, "blockers": blockers, "blocker_count": len(blockers)}


def _json_default(value: Any):
    if isinstance(value, date) or hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def attendance_period_hash(attendance_rows: list[dict[str, Any]], overtime_rows: list[dict[str, Any]]) -> str:
    """Hash only native payroll inputs so a late edit makes finalization stale."""
    payload = {
        "attendance": sorted(
            [dict(row) for row in attendance_rows],
            key=lambda row: (str(row.get("employee")), str(row.get("attendance_date")), str(row.get("name"))),
        ),
        "overtime": sorted(
            [dict(row) for row in overtime_rows],
            key=lambda row: (str(row.get("employee")), str(row.get("start_date")), str(row.get("name"))),
        ),
    }
    encoded = json.dumps(payload, sort_keys=True, default=_json_default, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def payment_day_component_findings(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Find the known native double-proration shape without changing salary data."""
    findings = []
    for row in rows:
        formula = str(row.get("formula") or "").replace(" ", "").casefold()
        if row.get("depends_on_payment_days") and "payment_days" in formula:
            findings.append({
                "code": "UNSAFE_PAYMENT_DAY_FORMULA",
                "salary_structure": row.get("parent"),
                "salary_component": row.get("salary_component"),
                "reason": "Native HRMS evaluates payment_days in the formula and then prorates components flagged depends_on_payment_days.",
            })
    return findings


def _employees_for_period(company: str, start: date, end: date, employee_ids: list[str] | None):
    filters = {"company": company, "date_of_joining": ["<=", end]}
    if employee_ids:
        filters["name"] = ["in", employee_ids]
    rows = frappe.get_all(
        "Employee",
        filters=filters,
        fields=["name", "employee_name", "date_of_joining", "relieving_date", "status"],
        order_by="name asc",
    )
    return [row for row in rows if not _row_value(row, "relieving_date") or getdate(_row_value(row, "relieving_date")) >= start]


def _native_unmarked_attendance(company: str, start: date, end: date, employees: list[dict[str, Any]]):
    """Ask native Payroll Entry for coverage; do not reproduce its holiday math."""
    if not employees:
        return []
    payroll_entry = frappe.new_doc("Payroll Entry")
    payroll_entry.company = company
    payroll_entry.start_date = start
    payroll_entry.end_date = end
    payroll_entry.validate_attendance = 1
    payroll_entry.employees = [
        frappe._dict({"employee": _row_value(row, "name"), "employee_name": _row_value(row, "employee_name")})
        for row in employees
    ]
    return payroll_entry.get_employees_with_unmarked_attendance() or []


def _pending_mobile_events(start: date, end: date, employee_ids: list[str]):
    if not employee_ids or not frappe.db.has_column("Employee Checkin", "custom_tradex_review_status"):
        return []
    return frappe.get_all(
        "Employee Checkin",
        filters={
            "employee": ["in", employee_ids],
            "time": ["between", [start, end + timedelta(days=1)]],
            "custom_tradex_review_status": "Pending",
        },
        fields=["name", "employee", "time"],
    )


def _unsafe_payment_day_structures(company: str, start: date, employee_ids: list[str]):
    if not employee_ids:
        return []
    assignments = frappe.get_all(
        "Salary Structure Assignment",
        filters={
            "company": company,
            "employee": ["in", employee_ids],
            "docstatus": 1,
            "from_date": ["<=", start],
        },
        fields=["employee", "salary_structure", "from_date"],
        order_by="employee asc, from_date desc",
    )
    latest_by_employee = {}
    for row in assignments:
        latest_by_employee.setdefault(_row_value(row, "employee"), row)
    structures = sorted({
        _row_value(row, "salary_structure")
        for row in latest_by_employee.values()
        if _row_value(row, "salary_structure")
    })
    if not structures:
        return []
    rows = frappe.get_all(
        "Salary Detail",
        filters={"parent": ["in", structures], "parenttype": "Salary Structure"},
        fields=["parent", "salary_component", "formula", "depends_on_payment_days"],
    )
    return payment_day_component_findings(rows)


def _ambiguous_biometric_mappings(employee_ids: list[str]):
    if not employee_ids or not frappe.db.exists("DocType", "Tradexcel Employee Biometric"):
        return []
    rows = frappe.get_all(
        "Tradexcel Employee Biometric",
        filters={"employee": ["in", employee_ids], "enabled": 1, "enrollment_status": "Enrolled"},
        fields=["employee", "device_serial", "biometric_id"],
    )
    grouped = defaultdict(set)
    for row in rows:
        key = (str(_row_value(row, "device_serial") or "").casefold(), str(_row_value(row, "biometric_id") or "").casefold())
        grouped[key].add(_row_value(row, "employee"))
    return [
        {"device_serial": key[0], "biometric_id": key[1], "employees": sorted(employees)}
        for key, employees in grouped.items()
        if len(employees) > 1
    ]


def _pending_attendance_requests(company: str, start: date, end: date, employee_ids: list[str]):
    if not employee_ids:
        return []
    return frappe.get_all(
        "Attendance Request",
        filters={
            "company": company,
            "employee": ["in", employee_ids],
            "docstatus": 0,
            "from_date": ["<=", end],
            "to_date": [">=", start],
        },
        fields=["name", "employee", "from_date", "to_date"],
    )


def _leave_contradictions(company: str, start: date, end: date, employee_ids: list[str]):
    """Submitted approved leave must have the native Attendance it creates."""
    if not employee_ids:
        return []
    leaves = frappe.get_all(
        "Leave Application",
        filters={
            "company": company,
            "employee": ["in", employee_ids],
            "docstatus": 1,
            "status": "Approved",
            "from_date": ["<=", end],
            "to_date": [">=", start],
        },
        fields=["name", "employee", "from_date", "to_date", "half_day", "half_day_date"],
    )
    if not leaves:
        return []
    attendance = frappe.get_all(
        "Attendance",
        filters={
            "employee": ["in", employee_ids],
            "attendance_date": ["between", [start, end]],
            "docstatus": 1,
        },
        fields=["employee", "attendance_date", "status", "leave_application"],
    )
    by_day = {(_row_value(row, "employee"), getdate(_row_value(row, "attendance_date"))): row for row in attendance}
    findings = []
    for leave in leaves:
        day = max(start, getdate(_row_value(leave, "from_date")))
        leave_end = min(end, getdate(_row_value(leave, "to_date")))
        while day <= leave_end:
            expected = "Half Day" if _row_value(leave, "half_day") and getdate(_row_value(leave, "half_day_date")) == day else "On Leave"
            row = by_day.get((_row_value(leave, "employee"), day))
            if not row or _row_value(row, "status") not in {expected, "Half Day"}:
                findings.append({"leave": _row_value(leave, "name"), "employee": _row_value(leave, "employee"), "date": day, "expected": expected})
            day += timedelta(days=1)
    return findings


def _unapproved_overtime(company: str, start: date, end: date, employee_ids: list[str]):
    if not employee_ids or not frappe.db.exists("DocType", "Overtime Slip"):
        return []
    attendance = frappe.get_all(
        "Attendance",
        filters={
            "employee": ["in", employee_ids],
            "attendance_date": ["between", [start, end]],
            "docstatus": 1,
            "status": "Present",
            "overtime_type": ["!=", ""],
            "actual_overtime_duration": [">", 0],
        },
        fields=["name", "employee", "attendance_date", "actual_overtime_duration"],
    )
    if not attendance:
        return []
    slips = frappe.get_all(
        "Overtime Slip",
        filters={
            "company": company,
            "employee": ["in", employee_ids],
            "start_date": ["<=", end],
            "end_date": [">=", start],
            "docstatus": 1,
        },
        fields=["name"],
    )
    if not slips:
        return attendance
    refs = {
        _row_value(row, "reference_document")
        for row in frappe.get_all(
            "Overtime Details",
            filters={"parent": ["in", [_row_value(item, "name") for item in slips]], "parenttype": "Overtime Slip"},
            fields=["reference_document"],
        )
        if _row_value(row, "reference_document")
    }
    return [row for row in attendance if _row_value(row, "name") not in refs]


def inspect_attendance_payroll_boundary(
    company: str,
    start_date: str | date,
    end_date: str | date,
    employee_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Inspect whether native Attendance is safe to use as payroll input."""
    start, end = _period_dates(start_date, end_date)
    employees = _employees_for_period(company, start, end, employee_ids)
    employee_ids = [_row_value(row, "name") for row in employees]
    blockers: list[dict[str, Any]] = []

    employment = classify_employment_boundaries(employees, start, end)
    blockers.extend(
        {"code": result["status"], "employee": employee, "reason": result["reason"]}
        for employee, result in employment.items()
        if result["status"] != READY
    )

    for row in _native_unmarked_attendance(company, start, end, employees):
        blockers.append({"code": "ATTENDANCE_UNMARKED", "employee": _row_value(row, "employee"),
                         "reason": f"Native Payroll Entry found {_row_value(row, 'unmarked_days')} unmarked day(s)."})
    for row in _pending_mobile_events(start, end, employee_ids):
        blockers.append({"code": "MOBILE_REVIEW_PENDING", "employee": _row_value(row, "employee"), "record": _row_value(row, "name"),
                         "reason": "Quarantined mobile evidence has not been approved or rejected."})
    blockers.extend(_unsafe_payment_day_structures(company, start, employee_ids))
    for row in _ambiguous_biometric_mappings(employee_ids):
        blockers.append({"code": "BIOMETRIC_ID_AMBIGUOUS", "reason": "One device/PIN identifies multiple employees.", **row})
    for row in _pending_attendance_requests(company, start, end, employee_ids):
        blockers.append({"code": "ATTENDANCE_REQUEST_PENDING", "employee": _row_value(row, "employee"), "record": _row_value(row, "name"),
                         "reason": "An attendance correction request is still draft/unresolved."})
    for row in _leave_contradictions(company, start, end, employee_ids):
        blockers.append({"code": "LEAVE_ATTENDANCE_CONFLICT", "employee": _row_value(row, "employee"), "record": _row_value(row, "leave"),
                         "reason": f"Approved leave on {_row_value(row, 'date')} is not reflected in submitted Attendance."})
    for row in _unapproved_overtime(company, start, end, employee_ids):
        blockers.append({"code": "OVERTIME_NOT_APPROVED", "employee": _row_value(row, "employee"), "record": _row_value(row, "name"),
                         "reason": "Attendance contains overtime that is not in a submitted native Overtime Slip."})

    return {"company": company, "from_date": start, "to_date": end, "employee_count": len(employees),
            **build_boundary_result(blockers)}


def get_native_period_state(company: str, start_date: str | date, end_date: str | date):
    start, end = _period_dates(start_date, end_date)
    attendance = frappe.get_all(
        "Attendance",
        filters={"company": company, "attendance_date": ["between", [start, end]], "docstatus": 1},
        fields=["name", "employee", "attendance_date", "status", "leave_application", "overtime_type",
                "actual_overtime_duration", "docstatus", "modified"],
    )
    overtime = (
        frappe.get_all(
            "Overtime Slip",
            filters={"company": company, "start_date": ["<=", end], "end_date": [">=", start], "docstatus": 1},
            fields=["name", "employee", "start_date", "end_date", "total_overtime_duration", "modified"],
        )
        if frappe.db.exists("DocType", "Overtime Slip")
        else []
    )
    return attendance, overtime


def current_attendance_period_hash(company: str, start_date: str | date, end_date: str | date) -> str:
    return attendance_period_hash(*get_native_period_state(company, start_date, end_date))


def require_finalized_attendance(company: str, start_date: str | date, end_date: str | date):
    """Future native payroll orchestration can call this single gate."""
    start, end = _period_dates(start_date, end_date)
    period = frappe.get_all(
        "Tradexcel Attendance Period",
        filters={"company": company, "from_date": start, "to_date": end, "status": "Finalized"},
        fields=["name", "attendance_hash"],
        limit=1,
    )
    if not period:
        frappe.throw(_("Attendance period {0} to {1} is not finalized.").format(start, end))
    result = inspect_attendance_payroll_boundary(company, start, end)
    if result["status"] != READY:
        frappe.throw(_("Attendance finalization needs review before payroll: {0}").format(
            "; ".join(item.get("reason", item.get("code", "Unknown issue")) for item in result["blockers"][:8])
        ))
    current_hash = current_attendance_period_hash(company, start, end)
    if current_hash != _row_value(period[0], "attendance_hash"):
        frappe.throw(_("Attendance finalization is stale; review and finalize the period again."))
    return period[0]
