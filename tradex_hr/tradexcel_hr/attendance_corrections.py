"""One-day bulk preparation for native Attendance Requests.

Attendance Request remains the correction object and native Attendance remains
the payable record. This module only prepares drafts; HRMS owns approval effects.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate

from tradex_hr.tradexcel_hr.report_scope import permitted_employee_names


MAKER_ROLES = {"Tradexcel HR Manager", "Tradexcel HR/Attendance Officer"}
APPROVER_ROLE = "Tradexcel Attendance Correction Approver"
ACTION_FIELDS = {
    "Present": {"reason": "On Duty", "half_day": 0},
    "Half Day": {"reason": "On Duty", "half_day": 1},
    "Work From Home": {"reason": "Work From Home", "half_day": 0},
}


def _require_maker():
    if not MAKER_ROLES.intersection(frappe.get_roles()):
        frappe.throw(_("Only HR Manager or HR/Attendance Officer can prepare attendance corrections."),
                     frappe.PermissionError)
    frappe.has_permission("Attendance Request", "create", throw=True)


def _employee_scope(company, branch=None, department=None):
    return set(permitted_employee_names(company, branch=branch, department=department))


def _normalise_names(employee_names):
    if isinstance(employee_names, str):
        employee_names = frappe.parse_json(employee_names)
    if not isinstance(employee_names, (list, tuple)):
        frappe.throw(_("Select Employees from the attendance report."))
    return list(dict.fromkeys(str(name).strip() for name in employee_names if str(name).strip()))


def _day_context(employee, attendance_date):
    attendance = frappe.get_all(
        "Attendance",
        filters={"employee": employee.name, "attendance_date": attendance_date, "docstatus": ["<", 2]},
        fields=["name", "status", "docstatus", "shift", "in_time", "out_time"],
        order_by="creation desc",
    )
    checkin_fields = ["time", "log_type"]
    if frappe.db.has_column("Employee Checkin", "custom_tradex_review_status"):
        checkin_fields.append("custom_tradex_review_status")
    checkins = frappe.get_all(
        "Employee Checkin",
        filters={"employee": employee.name, "time": ["between", [f"{attendance_date} 00:00:00", f"{attendance_date} 23:59:59"]]},
        fields=checkin_fields,
        order_by="time asc",
    )
    inbound = [row.time for row in checkins if row.log_type == "IN"]
    outbound = [row.time for row in checkins if row.log_type == "OUT"]
    pending = any(row.get("custom_tradex_review_status") == "Pending" for row in checkins)
    existing = attendance[0] if attendance else None
    return {
        "attendance": existing.name if existing else None,
        "attendance_status": existing.status if existing else "Not Marked",
        "attendance_state": ("Draft Attendance" if existing.docstatus == 0 else "Submitted Attendance") if existing else "Not Marked",
        "attendance_docstatus": existing.docstatus if existing else None,
        "attendance_shift": existing.shift if existing else None,
        "checkin_count": len(checkins),
        "in_time": inbound[0] if inbound else None,
        "out_time": outbound[-1] if outbound else None,
        "mobile_review_pending": pending,
    }


def _pending_mobile_event(employee, attendance_date):
    if not frappe.db.exists("DocType", "Tradex Mobile Event"):
        return False
    return bool(frappe.get_all(
        "Tradex Mobile Event",
        filters={"employee": employee, "status": "Pending", "device_time": ["between", [f"{attendance_date} 00:00:00", f"{attendance_date} 23:59:59"]]},
        pluck="name", limit=1,
    ))


def _payroll_consumed(employee, attendance_date):
    """A submitted Salary Slip consumes the inclusive period it records."""
    return frappe.get_all(
        "Salary Slip",
        filters={
            "employee": employee,
            "docstatus": 1,
            "start_date": ["<=", attendance_date],
            "end_date": [">=", attendance_date],
        },
        fields=["name"],
        limit=1,
    )


def _existing_request(employee, attendance_date):
    return frappe.get_all(
        "Attendance Request",
        filters={
            "employee": employee,
            "docstatus": ["<", 2],
            "from_date": ["<=", attendance_date],
            "to_date": [">=", attendance_date],
        },
        fields=["name", "docstatus"],
        order_by="creation desc",
        limit=1,
    )


def _biometric_ambiguity(employee_names):
    from tradex_hr.tradexcel_hr.attendance_payroll_boundary import _ambiguous_biometric_mappings

    rows = _ambiguous_biometric_mappings(employee_names)
    return {employee for row in rows for employee in row.get("employees", [])}


def _candidate(employee, company, attendance_date, action, explanation):
    values = ACTION_FIELDS[action]
    return frappe.get_doc({
        "doctype": "Attendance Request",
        "employee": employee.name,
        "company": company,
        "from_date": attendance_date,
        "to_date": attendance_date,
        "reason": values["reason"],
        "half_day": values["half_day"],
        "half_day_date": attendance_date if values["half_day"] else None,
        "explanation": explanation,
    })


def _warning_message(reasons):
    if "Holiday" in reasons:
        return _("Skipped — holiday")
    if "On Leave" in reasons:
        return _("Skipped — approved leave")
    return _("Skipped — the requested attendance status is already in place")


def _preview_one(employee, company, attendance_date, action, explanation, ambiguous):
    context = _day_context(employee, attendance_date)
    row = {
        "employee": employee.name,
        "employee_name": employee.employee_name,
        "branch": employee.branch,
        "department": employee.department,
        "current_attendance": context["attendance"],
        "current_state": context["attendance_state"],
        "current_status": context["attendance_status"],
        "attendance_docstatus": context["attendance_docstatus"],
        "checkin_count": context["checkin_count"],
        "in_time": context["in_time"],
        "out_time": context["out_time"],
        "active_shift": None,
        "proposed_status": action,
        "outcome": "Blocked",
        "message": "",
    }
    if context["attendance_state"] == "Draft Attendance":
        row["message"] = _("A draft Attendance exists. Review that record before requesting a correction.")
        return row
    if _payroll_consumed(employee.name, attendance_date):
        row["outcome"] = "Blocked — payroll already processed"
        row["message"] = _("This date has already been consumed by submitted payroll.")
        return row
    if context["mobile_review_pending"] or _pending_mobile_event(employee.name, attendance_date):
        row["message"] = _("Attendance evidence is still under mobile review.")
        return row
    if employee.name in ambiguous:
        row["message"] = _("The biometric identity is ambiguous. Resolve it before preparing a correction.")
        return row
    requests = _existing_request(employee.name, attendance_date)
    if requests:
        row["outcome"] = "Blocked — existing request"
        row["message"] = _("An existing Attendance Request already covers this date.")
        row["existing_request"] = requests[0].name
        return row

    request = _candidate(employee, company, attendance_date, action, explanation)
    messages_before = len(getattr(frappe.local, "message_log", []))
    try:
        request.validate()
        shifts = request.get_active_shifts()
        row["active_shift"] = request.shift or (shifts[0] if len(shifts) == 1 else None)
        warnings = request.get_attendance_warnings()
    except Exception:
        warnings = request.get_attendance_warnings() if request.employee and request.from_date and request.to_date else []
        if warnings and all(item.get("action") == "Skip" for item in warnings):
            row["outcome"] = "Skipped"
            row["message"] = _warning_message({item.get("reason") for item in warnings})
            # Remove only the expected skip message emitted by native validate_no_attendance_to_create
            if hasattr(frappe.local, "message_log"):
                del frappe.local.message_log[messages_before:]
        else:
            row["message"] = _("Native Attendance Request checks need review. Open the Employee's Attendance Request for details.")
        return row

    if warnings and all(item.get("action") == "Skip" for item in warnings):
        row["outcome"] = "Skipped"
        row["message"] = _warning_message({item.get("reason") for item in warnings})
    elif context["attendance"]:
        row["outcome"] = "Will overwrite after approval"
        row["message"] = _("Approval will update the existing Attendance through native HRMS.")
    else:
        row["outcome"] = "Will create"
        row["message"] = _("A draft request will be created; Attendance changes only after approval.")
    row["native_warnings"] = [
        {"reason": item.get("reason"), "action": item.get("action"), "record": item.get("record")}
        for item in warnings
    ]
    return row


def _preview(company, attendance_date, branch, department, employee_names, action, explanation):
    _require_maker()
    if action not in ACTION_FIELDS:
        frappe.throw(_("Choose Present, Half Day, or Work From Home."))
    explanation = (explanation or "").strip()
    if len(explanation) < 8:
        frappe.throw(_("Enter a meaningful explanation (at least 8 characters)."))
    if len(explanation) > 2000:
        frappe.throw(_("Keep the explanation under 2,000 characters."))
    attendance_date = getdate(attendance_date)
    if not attendance_date:
        frappe.throw(_("Choose one Attendance Date."))
    names = _normalise_names(employee_names)
    if not names:
        frappe.throw(_("Select at least one Employee."))
    allowed = _employee_scope(company, branch, department)
    allowed_selected = sorted(set(names).intersection(allowed))
    allowed_docs = {}
    if allowed_selected:
        for employee in frappe.get_list(
            "Employee",
            filters={"name": ["in", allowed_selected], "company": company},
            fields=["name", "employee_name", "company", "branch", "department", "status", "date_of_joining", "relieving_date"],
        ):
            allowed_docs[employee.name] = employee
    ambiguous = _biometric_ambiguity(list(allowed))
    rows = []
    for name in names:
        employee = allowed_docs.get(name)
        if not employee or not frappe.has_permission("Employee", "read", doc=employee.name):
            rows.append({"employee": name, "outcome": "Blocked — outside permitted scope",
                         "message": _("The selected employee is outside your permitted Company/Branch/Department scope.")})
            continue
        if employee.status == "Inactive":
            rows.append({"employee": name, "employee_name": employee.employee_name,
                         "outcome": "Blocked", "message": _("Inactive Employees cannot receive attendance corrections.")})
            continue
        if employee.date_of_joining and attendance_date < getdate(employee.date_of_joining):
            rows.append({"employee": name, "employee_name": employee.employee_name,
                         "outcome": "Blocked", "message": _("The date is before the Employee's joining date.")})
            continue
        if employee.relieving_date and attendance_date > getdate(employee.relieving_date):
            rows.append({"employee": name, "employee_name": employee.employee_name,
                         "outcome": "Blocked", "message": _("The date is after the Employee's relieving date.")})
            continue
        rows.append(_preview_one(employee, company, attendance_date, action, explanation, ambiguous))
    return {"company": company, "attendance_date": str(attendance_date), "action": action, "rows": rows}


@frappe.whitelist(methods=["POST"])
def preview_attendance_corrections(company, attendance_date, employee_names, action, explanation,
                                   branch=None, department=None):
    """Return a server-validated, one-day correction preview without writes."""
    return _preview(company, attendance_date, branch, department, employee_names, action, explanation)


@frappe.whitelist(methods=["POST"])
def prepare_attendance_corrections(company, attendance_date, employee_names, action, explanation,
                                   branch=None, department=None):
    """Create only draft native Attendance Requests, isolated per Employee."""
    preview = _preview(company, attendance_date, branch, department, employee_names, action, explanation)
    by_name = {row.get("employee"): row for row in preview["rows"]}
    created, errors = [], []
    for employee_name in _normalise_names(employee_names):
        row = by_name.get(employee_name) or {}
        if row.get("outcome") not in {"Will create", "Will overwrite after approval"}:
            errors.append({"employee": employee_name, "outcome": row.get("outcome", "Blocked"),
                           "message": row.get("message", _("This Employee was not eligible for preparation."))})
            continue
        savepoint = "attendance_request_" + frappe.generate_hash(length=8)
        frappe.db.savepoint(savepoint)
        try:
            employee = frappe.get_doc("Employee", employee_name)
            request = _candidate(employee, company, getdate(attendance_date), action, explanation)
            request.insert()
            created.append({"employee": employee_name, "attendance_request": request.name,
                            "outcome": "Draft request created"})
            frappe.db.release_savepoint(savepoint)
        except Exception:
            frappe.db.rollback(save_point=savepoint)
            errors.append({"employee": employee_name, "outcome": "Blocked",
                           "message": _("This request could not be prepared. Review the Employee's native Attendance Request warnings.")})
    return {"created": created, "results": errors}


def _request_employee_scope(doc):
    roles = set(frappe.get_roles())
    if frappe.session.user == "Administrator":
        return
    if not roles.intersection(MAKER_ROLES | {APPROVER_ROLE}):
        return
    employee = frappe.db.get_value("Employee", doc.employee, ["company", "status"], as_dict=True)
    if not employee or employee.company != doc.company:
        frappe.throw(_("Attendance Request Company must match the Employee's Company."))
    permitted = _employee_scope(doc.company)
    if doc.employee not in permitted:
        frappe.throw(_("This Employee is outside your permitted Company/Branch/Department scope."),
                     frappe.PermissionError)


def _assert_payroll_not_consumed(doc):
    start, end = getdate(doc.from_date), getdate(doc.to_date)
    if not start or not end:
        return
    slips = frappe.get_all(
        "Salary Slip",
        filters={"employee": doc.employee, "docstatus": 1,
                 "start_date": ["<=", end], "end_date": [">=", start]},
        fields=["name"], limit=5,
    )
    if slips:
        frappe.throw(
            _("This attendance date has already been consumed by submitted payroll. Use the reviewed payroll correction/arrear process."),
            title=_("Payroll already processed"),
        )


def _validate_existing_attendance_overwrites(doc):
    """Run Tradexcel Attendance safety hooks HRMS db_set would otherwise skip."""
    from frappe.utils import add_days, date_diff

    from tradex_hr.tradexcel_hr.attendance_exceptions import apply_to_attendance, sync_scope_fields
    from tradex_hr.tradexcel_hr.employee_separation import validate_no_payable_work_after_relieving_date
    from tradex_hr.tradexcel_hr.maternity_welfare import validate_maternity_attendance

    for offset in range(date_diff(doc.to_date, doc.from_date) + 1):
        day = add_days(doc.from_date, offset)
        if not doc.should_mark_attendance(day):
            continue
        attendance = doc.get_attendance_doc(day)
        if not attendance or doc.status_unchanged(day):
            continue
        projected = frappe._dict(attendance.as_dict())
        projected.status = doc.get_attendance_status(day)
        projected.attendance_request = doc.name
        if projected.status == "Half Day":
            if attendance.status != "Half Day":
                projected.half_day_status = "Absent"
            elif doc.half_day and attendance.half_day_status == "Absent":
                projected.half_day_status = "Present"
        sync_scope_fields(projected, "validate")
        apply_to_attendance(projected, "before_save")
        validate_no_payable_work_after_relieving_date(projected, "before_submit")
        validate_maternity_attendance(projected, "before_submit")


def validate_attendance_request_before_submit(doc, method=None):
    """Enforce scoped approval and maker/checker before native HRMS applies it."""
    roles = set(frappe.get_roles())
    _request_employee_scope(doc)
    if frappe.session.user != "Administrator" and APPROVER_ROLE in roles:
        if doc.owner == frappe.session.user:
            frappe.throw(_("A different Attendance Correction Approver must submit this request."),
                         frappe.PermissionError)
    _validate_existing_attendance_overwrites(doc)
    _assert_payroll_not_consumed(doc)


def validate_attendance_request_before_cancel(doc, method=None):
    _request_employee_scope(doc)
    _assert_payroll_not_consumed(doc)
