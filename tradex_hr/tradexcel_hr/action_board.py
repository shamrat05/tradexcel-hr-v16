"""Read-only adapters for the existing native Tradexcel HR Workspace.

No stored task/approval state: every item comes from a permission-checked native
record queue or an existing report/readiness service. Counts are scoped work,
not headcounts or a declaration that the Company is compliant/payroll-ready.
"""
from __future__ import annotations

from collections import Counter

import frappe
from frappe import _
from frappe.utils import getdate, get_first_day, today

from tradex_hr.tradexcel_hr.report_scope import permitted_employee_query

BOARD_ROLES = frozenset({
    "System Manager", "Tradexcel Owner/Director", "Tradexcel HR Manager",
    "Tradexcel HR/Attendance Officer", "Tradexcel Factory Supervisor",
    "Tradexcel Branch Manager", "Tradexcel Department Manager",
    "Tradexcel Payroll Manager", "Tradexcel Payroll Approver",
    "Tradexcel Finance/Accounts Officer", "Tradexcel Compliance Auditor",
    "Tradexcel Device/IT Administrator", "Tradexcel Attendance Correction Approver",
    "Tradexcel Leave Approver",
})
FINANCIAL_ROLES = frozenset({
    "System Manager", "Tradexcel Owner/Director", "Tradexcel HR Manager",
    "Tradexcel Payroll Manager", "Tradexcel Payroll Approver",
    "Tradexcel Finance/Accounts Officer", "Tradexcel Compliance Auditor",
})
OPERATIONS_ROLES = frozenset({
    "System Manager", "Tradexcel Owner/Director", "Tradexcel HR Manager",
    "Tradexcel HR/Attendance Officer", "Tradexcel Factory Supervisor",
    "Tradexcel Branch Manager", "Tradexcel Department Manager",
    "Tradexcel Compliance Auditor", "Tradexcel Attendance Correction Approver",
})
COMPLIANCE_ROLES = frozenset({
    "System Manager", "Tradexcel Owner/Director", "Tradexcel HR Manager",
    "Tradexcel Compliance Auditor",
})
REVIEW_DOCTYPES = (
    "Tradexcel Wage Floor Classification", "Tradexcel Statutory Benefit Enrollment",
    "Tradexcel Working Time Classification", "Tradexcel Maternity Review",
    "Tradexcel Workplace Welfare Review", "Tradexcel Statutory Rule Set",
)


def _authorize():
    user = frappe.session.user
    roles = set(frappe.get_roles(user))
    if user == "Guest" or not frappe.get_cached_value("User", user, "enabled") or not roles & BOARD_ROLES:
        frappe.throw(_("This work board is available to HR operations and review roles."), frappe.PermissionError)
    return roles


def _employee_names(company):
    employee = frappe.qb.DocType("Employee")
    return tuple(row[0] for row in permitted_employee_query().where(employee.company == company).run())


def _companies():
    # Company identity is already part of the permitted Employee population.
    # This also supports device operators' select-only Employee identity access
    # without granting them Company or Employee master-form access.
    result = set()
    if frappe.has_permission("Employee", "select"):
        employee = frappe.qb.DocType("Employee")
        result.update(row[0] for row in frappe.qb.from_(employee).select(employee.company)
            .where(employee.name.isin(permitted_employee_query())).distinct().run() if row[0])
    if frappe.has_permission("Company", "read"):
        result.update(frappe.get_list("Company", pluck="name", limit_page_length=0))
    return sorted(result)


@frappe.whitelist()
def get_board_context():
    _authorize()
    companies = _companies()
    default = frappe.defaults.get_user_default("Company")
    return {"companies": companies, "company": default if default in companies else (companies[0] if len(companies) == 1 else ""),
            "as_of_date": today()}


def _item(category, title, reason, count, company, route, source, *, severity="Review", filters=None):
    return {"category": category, "severity": severity, "title": _(title), "reason": _(reason),
            "count": count, "company": company, "route": route, "filters": filters or {}, "source": source}


def _report_items(company, day, name, category, title, predicate, reason):
    from frappe.desk.query_report import get_report_doc

    try:
        report = get_report_doc(name)
    except frappe.PermissionError:
        return []
    filters = {"company": company, "as_of_date": day, "attendance_date": day,
               "payroll_month": day, "from_date": str(get_first_day(day)), "to_date": day}
    try:
        # Execute the source-backed report, without native prepared-report
        # automation (which may write Report metadata after a slow query).
        if report.is_standard != "Yes" or report.report_type != "Script Report":
            frappe.throw(_("This review requires its installed standard report."))
        rows = report.execute_module(filters)[1]
    except frappe.PermissionError:
        return [_item(category, title, "This review is not available within your current access. Ask an administrator to review your scope.",
                      None, company, [], name, severity="Configuration")]
    except (frappe.ValidationError, ValueError):
        return [_item(category, title, "This review could not be loaded for your current scope or configuration. Open the review for details.",
                      None, company, ["query-report", name], name, filters=filters)]
    count = sum(bool(predicate(row)) for row in rows)
    return [_item(category, title, reason, count, company, ["query-report", name], name, filters=filters)] if count else []


def _queue(company, names, doctype, category, title, *, extra=None, independent=False):
    if not frappe.has_permission(doctype, "read"):
        return []
    meta = frappe.get_meta(doctype)
    filters = dict(extra or {})
    or_filters = []
    if meta.has_field("employee"):
        if doctype == "Employee Onboarding":
            # A recruited joiner legitimately has no Employee yet. Native
            # onboarding Company/Department permissions govern that draft;
            # already-linked identities still need current Employee scope.
            or_filters = [["employee", "is", "not set"]]
            if names:
                or_filters.append(["employee", "in", names])
        elif not names:
            return []
        else:
            filters["employee"] = ["in", names]
    if meta.has_field("company"):
        filters["company"] = company
    if meta.is_submittable:
        filters["docstatus"] = 0
    if independent and frappe.has_permission(doctype, "submit"):
        filters["owner"] = ["!=", frappe.session.user]
    rows = frappe.get_list(doctype, filters=filters, or_filters=or_filters, fields=["name"], limit_page_length=0)
    if not rows:
        return []
    # Drill through to exactly the source records counted, rather than a
    # broader Company list. This is navigation only, never the ACL boundary.
    route_filters = {"name": ["in", [row.name for row in rows]]}
    return [_item(category, title, "Open the native records to review the outstanding work.", len(rows), company,
                  ["List", doctype, "List"], doctype, filters=route_filters)]


def _attendance_items(company, day, names):
    if not names or not frappe.has_permission("Attendance", "read"):
        return []
    from tradex_hr.tradexcel_hr.attendance_payroll_boundary import inspect_attendance_integrity

    result = inspect_attendance_integrity(company, day, day, list(names))
    counts = Counter(row["code"] for row in result["blockers"])
    destinations = {
        "ATTENDANCE_UNMARKED": ("Attendance needs review", "Required attendance has not been marked. Missing attendance is not an Absent decision.",
                                ["query-report", "Tradexcel Daily Attendance Board"]),
        "ATTENDANCE_REQUEST_PENDING": ("Attendance corrections awaiting review", "Draft correction requests still need review; punches do not approve attendance.",
                                       ["List", "Attendance Request", "List"]),
    }
    items = []
    for code, (title, reason, route) in destinations.items():
        if counts[code]:
            target_ok = frappe.has_permission("Attendance Request", "read") if route[0] == "List" else _can_report(route[1])
            if target_ok:
                items.append(_item("Attendance", title, reason, counts[code], company, route,
                    "inspect_attendance_integrity", filters={"company": company, "attendance_date": day} if route[0] == "query-report" else {"name": ["in", [row["record"] for row in result["blockers"] if row["code"] == code and row.get("record")]]}))
    # Mobile/biometric findings are not silently resolved or presented as money.
    evidence = counts["MOBILE_REVIEW_PENDING"] + counts["BIOMETRIC_ID_AMBIGUOUS"]
    if evidence and _can_report("Tradexcel Daily Attendance Board"):
        items.append(_item("Attendance", "Attendance evidence needs review", "Quarantined mobile evidence or ambiguous biometric mapping needs separate review before attendance approval.",
                           evidence, company, ["query-report", "Tradexcel Daily Attendance Board"], "inspect_attendance_integrity",
                           filters={"company": company, "attendance_date": day}))
    return items


def _can_report(name):
    from frappe.desk.query_report import get_report_doc
    try:
        get_report_doc(name)
        return True
    except frappe.PermissionError:
        return False


@frappe.whitelist()
def get_action_board(company: str, as_of_date: str | None = None):
    """Return only this caller's work. Client Company/date never grant access."""
    roles = _authorize()
    if company not in _companies():
        frappe.throw(_("You do not have access to this Company's work board."), frappe.PermissionError)
    day = str(getdate(as_of_date or today()))
    names = _employee_names(company) if frappe.has_permission("Employee", "select") else ()
    items = []
    if roles & OPERATIONS_ROLES:
        items += _attendance_items(company, day, names)
        items += _report_items(company, day, "Tradexcel Shift Coverage", "Shifts", "Shift coverage needs review",
            lambda r: r.get("coverage") in {"No shift assigned — review", "Multiple active assignments — review"},
            "Review missing or conflicting native Shift Assignments.")
    if roles & COMPLIANCE_ROLES:
        items += _report_items(company, day, "Employee Data Gaps", "People", "Employee setup needs attention",
            lambda r: bool(r.get("gaps")), "Open the findings and use the native resolution workflow.")
    if roles & FINANCIAL_ROLES:
        items += _report_items(company, day, "Tradexcel Salary Coverage Board", "Payroll", "Salary authority needs review",
            lambda r: r.get("assignment_status") != "Assigned" or r.get("salary_basis") == "Pay Basis Missing",
            "Review the effective submitted salary assignment and its explicit pay basis.")
        items += _report_items(company, day, "Tradexcel Payroll Readiness", "Payroll", "Payroll blockers need attention",
            lambda r: r.get("status_label") != _("READY") or r.get("financial_status") not in {None, "", "-", _("READY")},
            "Open payroll readiness for attendance, pay authority, tax and financial blockers.")
        items += _queue(company, names, "Salary Structure Assignment", "Payroll", "Draft salary assignments", independent=True)
        items += _queue(company, names, "Overtime Slip", "Payroll", "Draft overtime reviews", independent=True)
        items += _payment_items(company, names)
    if roles & COMPLIANCE_ROLES:
        items += _legal_configuration_items(company, day)
        for doctype in REVIEW_DOCTYPES:
            items += _queue(company, names, doctype, "Compliance", "Draft " + doctype.removeprefix("Tradexcel "))
    if "Tradexcel Leave Approver" in roles or "System Manager" in roles:
        items += _queue(company, names, "Leave Application", "Leave", "Leave requests awaiting your review",
                        extra={"status": "Open", "leave_approver": frappe.session.user})
    if roles & {"Tradexcel HR Manager", "Tradexcel Owner/Director", "System Manager"}:
        items += _people_items(company, day, names)
        items += _queue(company, names, "Employee Onboarding", "People", "Joiner onboarding drafts")
        items += _queue(company, names, "Employee Separation", "People", "Separation drafts")
        items += _queue(company, names, "Full and Final Statement", "People", "Settlement drafts")
    if roles & {"Tradexcel Device/IT Administrator", "System Manager"}:
        items += _queue(company, names, "Tradexcel Employee Biometric", "Devices", "Biometric enrollment needs review",
                        extra={"enabled": 1, "enrollment_status": "Pending"})
    return {"company": company, "as_of_date": day, "items": items,
            "notice": _("Attendance uses the selected day; payroll uses that month. Open drafts can be from other dates. This board shows work within your access; an empty board does not certify payroll or legal readiness.")}


def _payment_items(company, names):
    from tradex_hr.tradexcel_hr.payment_readiness import inspect_payroll_payment_readiness
    from tradex_hr.tradexcel_hr.native_payroll import MANAGED_RUN_FIELD

    if not names or not frappe.has_permission("Payroll Entry", "read"):
        return []
    items = []
    allowed = set(names)
    for row in frappe.get_list("Payroll Entry", filters={"company": company, "docstatus": 1},
                              pluck="name", limit_page_length=0):
        entry = frappe.get_doc("Payroll Entry", row)
        entry.check_permission("read")
        if not entry.get(MANAGED_RUN_FIELD):
            continue
        # Company payroll reconciliation cannot be reduced to partial-company
        # figures without misleading totals. Do not call it for hidden staff.
        if not {r.employee for r in entry.employees}.issubset(allowed):
            continue
        state = inspect_payroll_payment_readiness(entry)
        if state.get("status") != "BANK_RECONCILED":
            items.append(_item("Finance", "Payroll payment needs review", "Open the native Payroll Entry payment readiness and reconciliation review.",
                               1, company, ["Form", "Payroll Entry", row], "inspect_payroll_payment_readiness"))
            items[-1]["context"] = f"{row} · {entry.start_date} – {entry.end_date}"
    return items


def _people_items(company, day, names):
    from tradex_hr.tradexcel_hr.joiner_readiness import inspect_joiner_readiness
    from tradex_hr.tradexcel_hr.employee_separation import inspect_employee_exit_readiness, inspect_full_and_final_readiness

    if not names or not frappe.has_permission("Employee", "read"):
        return []
    items = []
    for field, title, inspector, has_problem in (
        ("date_of_joining", "Joiner setup needs review", inspect_joiner_readiness, lambda r: bool(r.get("findings"))),
        ("relieving_date", "Exit tasks need review", inspect_employee_exit_readiness, lambda r: bool(r.get("blockers"))),
        ("relieving_date", "Settlement needs review", inspect_full_and_final_readiness, lambda r: bool(r.get("blockers"))),
    ):
        for employee in frappe.get_list("Employee", filters={"name": ["in", names], field: ["between", [str(get_first_day(day)), day]]},
                                        fields=["name", "employee_name"], limit_page_length=0):
            try:
                result = inspector(employee.name)
            except frappe.PermissionError:
                continue
            if has_problem(result):
                item = _item("People", title, "Open the Employee readiness review for the selected month's joining or leaving date.",
                             1, company, ["Form", "Employee", employee.name], inspector.__name__)
                item["employee"] = employee.name
                item["context"] = f"{employee.employee_name} · {employee.name}"
                items.append(item)
    return items


def _legal_configuration_items(company, day):
    items = []
    for doctype in ("Tradexcel Statutory Rule Set", "Tradexcel Wage Floor Rule Set",
                    "Tradexcel Statutory Benefit Rule Set", "Tradexcel Working Time Rule Set",
                    "Tradexcel Maternity Rule Set", "Tradexcel Workplace Welfare Review"):
        if not frappe.has_permission(doctype, "read"):
            continue
        rows = frappe.get_list(doctype, filters={"company": company, "docstatus": 1},
                               fields=["name", "effective_from", "effective_to"], limit_page_length=0)
        available = any(row.effective_from and getdate(row.effective_from) <= getdate(day)
                        and (not row.effective_to or getdate(row.effective_to) >= getdate(day)) for row in rows)
        if not available:
            items.append(_item("Compliance", doctype.removeprefix("Tradexcel ") + " needs configuration review",
                "No approved effective record is available in your scope. Confirm applicability with the responsible reviewer; the board does not infer legal obligations.",
                None, company, ["List", doctype, "List"], doctype, filters={"company": company}, severity="Configuration"))
    return items
