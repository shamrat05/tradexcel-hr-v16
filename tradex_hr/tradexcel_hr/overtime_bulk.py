"""Prepare native Overtime Slip drafts from approved Attendance evidence.

HRMS' Payroll Entry bulk helper is useful after a Payroll Entry exists, but
Tradexcel payroll readiness requires reviewed OT before that entry is prepared.
This adapter only selects Employees and invokes the native Overtime Slip
controller; it does not calculate money or submit slips.
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import getdate

from tradex_hr.tradexcel_hr.company_context import assert_company_access
from tradex_hr.tradexcel_hr.pay_basis import DAILY, MONTHLY, resolve_pay_basis


def prevent_consumed_overtime_cancel(doc, _method=None) -> None:
    """Fail before mutation when native Additional Salary still uses this OT."""
    if frappe.db.exists("Additional Salary", {
        "ref_doctype": "Overtime Slip", "ref_docname": doc.name,
        "docstatus": ["<", 2],
    }):
        frappe.throw(
            _("This overtime has a salary input. Review that input before cancelling the Overtime Slip; processed payroll requires a reviewed correction."),
            frappe.ValidationError,
        )


def _maker_context(company: str, from_date: str, to_date: str) -> tuple:
    if "Tradexcel HR Manager" not in frappe.get_roles() or not frappe.has_permission(
        "Overtime Slip", "create"
    ):
        frappe.throw(_("Only an HR Manager can prepare overtime drafts."), frappe.PermissionError)
    assert_company_access(company, require_explicit_scope=True)
    start, end = getdate(from_date), getdate(to_date)
    if not start or not end or start > end:
        frappe.throw(_("Choose a valid overtime date range."), frappe.ValidationError)
    return start, end


def _eligible_rows(company: str, start, end) -> list[dict]:
    """Use native Employee permission queries and HRMS' OT eligibility rule."""
    from hrms.hr.doctype.overtime_slip.overtime_slip import (
        filter_employees_for_overtime_slip_creation,
    )

    employees = frappe.get_list(
        "Employee",
        filters={"company": company, "status": ["in", ["Active", "Left"]]},
        fields=["name", "employee_name", "branch", "department", "date_of_joining", "relieving_date"],
        limit_page_length=0,
    )
    visible = [
        row for row in employees
        if (not row.date_of_joining or getdate(row.date_of_joining) <= end)
        and (not row.relieving_date or getdate(row.relieving_date) >= start)
    ]
    eligible = set(filter_employees_for_overtime_slip_creation(start, end, [row.name for row in visible]))
    if not eligible:
        return []
    # HRMS' native predicate checks submitted Present Attendance and an OT
    # Type, but a zero-duration row cannot create an OT detail. Keep it out of
    # the operator preview while leaving native slip validation authoritative.
    evidence = frappe.get_all(
        "Attendance",
        filters={
            "company": company,
            "employee": ["in", sorted(eligible)],
            "attendance_date": ["between", [start, end]],
            "docstatus": 1,
            "status": "Present",
            "actual_overtime_duration": [">", 0],
            "overtime_type": ["is", "set"],
        },
        fields=["employee", "name"],
        limit_page_length=0,
    )
    evidence_by_employee: dict[str, int] = {}
    for row in evidence:
        evidence_by_employee[row.employee] = evidence_by_employee.get(row.employee, 0) + 1
    result = []
    for row in visible:
        if row.name not in eligible or not evidence_by_employee.get(row.name):
            continue
        effective_end = min(end, getdate(row.relieving_date)) if row.relieving_date else end
        authority = resolve_pay_basis(row.name, start, effective_end)
        result.append({
            "employee": row.name,
            "employee_name": row.employee_name,
            "branch": row.branch,
            "department": row.department,
            "attendance_count": evidence_by_employee[row.name],
            "pay_basis": authority.get("status"),
            "eligible": authority.get("status") in {MONTHLY, DAILY},
            "reason": authority.get("reason") or "",
            "effective_end": str(effective_end),
        })
    return result


@frappe.whitelist()
def preview_overtime_drafts(company: str, from_date: str, to_date: str) -> dict:
    start, end = _maker_context(company, from_date, to_date)
    return {"company": company, "from_date": str(start), "to_date": str(end),
            "rows": _eligible_rows(company, start, end)}


def _prepare_now(company: str, from_date: str, to_date: str, employees: list[str],
                 *, requested_by: str) -> dict:
    # Frappe captures the enqueueing user. Its retry path can omit that user;
    # fail closed if a delayed job ever loses the original identity.
    if frappe.session.user != requested_by or not frappe.db.get_value("User", requested_by, "enabled"):
        frappe.throw(_("The overtime requester's access changed. Start a new review."), frappe.PermissionError)
    start, end = _maker_context(company, from_date, to_date)
    current = {row["employee"]: row for row in _eligible_rows(company, start, end)}
    if any(name not in current for name in employees):
        frappe.throw(_("Refresh the overtime preview. A selected Employee is outside your scope or no longer eligible."), frappe.PermissionError)

    results = []
    for index, employee in enumerate(employees):
        row = current[employee]
        if not row["eligible"]:
            results.append({"employee": employee, "status": "Blocked", "reason": row["reason"] or _("Salary authority needs review.")})
            continue
        savepoint = f"tradex_ot_{index}"
        frappe.db.savepoint(savepoint)
        try:
            slip = frappe.get_doc({
                "doctype": "Overtime Slip",
                "employee": employee,
                "company": company,
                "posting_date": str(end),
                "start_date": str(start),
                "end_date": row["effective_end"],
            })
            slip.get_emp_and_overtime_details()
            if not slip.name or not slip.overtime_details:
                frappe.throw(_("No qualifying overtime details were found."), frappe.ValidationError)
            results.append({"employee": employee, "status": "Draft", "overtime_slip": slip.name})
        except Exception:
            frappe.db.rollback(save_point=savepoint)
            frappe.clear_last_message()
            results.append({"employee": employee, "status": "Failed",
                            "reason": _("Review submitted Attendance and Overtime Type, then retry this Employee.")})
    result = {"status": "Completed", "rows": results}
    if getattr(frappe.local, "job", None):
        frappe.publish_realtime("tradex_overtime_drafts_completed", result, user=requested_by)
    return result


@frappe.whitelist(methods=["POST"])
def prepare_overtime_drafts(company: str, from_date: str, to_date: str,
                            employees: list[str] | str) -> dict:
    start, end = _maker_context(company, from_date, to_date)
    if isinstance(employees, str):
        try:
            employees = json.loads(employees)
        except ValueError:
            frappe.throw(_("Select Employees from the current overtime preview."), frappe.ValidationError)
    if not isinstance(employees, list) or not employees or any(not isinstance(name, str) for name in employees):
        frappe.throw(_("Select Employees from the current overtime preview."), frappe.ValidationError)
    if len(employees) != len(set(employees)):
        frappe.throw(_("Each Employee can be selected only once."), frappe.ValidationError)
    selected = tuple(employees)
    current = {row["employee"] for row in _eligible_rows(company, start, end)}
    if not set(selected).issubset(current):
        frappe.throw(_("Refresh the overtime preview. A selected Employee is outside your scope or no longer eligible."), frappe.PermissionError)
    if len(selected) > 30:
        job_id = f"tradex-overtime-{frappe.generate_hash(length=12)}"
        frappe.enqueue(
            _prepare_now,
            queue="long", timeout=1800, enqueue_after_commit=True,
            job_id=job_id,
            company=company, from_date=str(start), to_date=str(end),
            employees=list(selected), requested_by=frappe.session.user,
        )
        return {"status": "Queued", "job_id": job_id, "count": len(selected)}
    return _prepare_now(company, str(start), str(end), list(selected), requested_by=frappe.session.user)
