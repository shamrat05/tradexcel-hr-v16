"""Native Employee scope for Tradexcel reports and Employee-linked records.

Report SQL does not apply Frappe User Permissions. Resolve the caller's
permitted Employee rows with ``get_list`` first, then bind those names into
report SQL. Report filters are applied only after native scope is resolved,
so a caller can narrow access but cannot expand it.
"""

from __future__ import annotations

import frappe
from frappe import _


def permitted_employee_query(user: str | None = None):
    """Native permission-aware Employee identity query, suitable for a subquery.

    Query Builder applies the same native User Permissions, including blank
    Link semantics, as list queries. Select-only identity access does not grant
    Employee document read or access to compensation/bank fields.
    """
    return frappe.qb.get_query(
        "Employee", fields=["name"], ignore_permissions=False,
        user=user or frappe.session.user, db_query_compat=True,
    )


EMPLOYEE_LINK_SCOPED_DOCTYPES = frozenset({
    "Attendance Request", "Employee Checkin", "Salary Structure Assignment",
    "Shift Assignment", "Shift Schedule Assignment", "Shift Request",
    'Leave Policy Assignment', 'Leave Application', 'Full and Final Statement', 'Tradexcel Field Duty', 'Tradexcel Location Ping',
    "Tradex Mobile Event", "Leave Allocation", "Additional Salary", "Overtime Slip", "Tradexcel Employee Biometric",
})


def employee_link_query_conditions(user=None, doctype=None):
    """Close native records whose missing Branch/Company fields lose scope."""
    user = user or frappe.session.user
    if doctype not in EMPLOYEE_LINK_SCOPED_DOCTYPES:
        return "1=0"
    if user == "Guest" or not frappe.get_cached_value("User", user, "enabled"):
        return "1=0"
    if not frappe.has_permission("Employee", "select", user=user):
        return "1=0"
    table = frappe.qb.DocType(doctype)
    return table.employee.isin(permitted_employee_query(user)).get_sql(quote_char="`", with_namespace=True)


def employee_link_has_permission(doc, ptype=None, user=None, **_kwargs):
    """Additional restriction only; native target DocPerms still decide rights."""
    user = user or frappe.session.user
    if user == "Guest" or not frappe.get_cached_value("User", user, "enabled"):
        return False
    if not doc.get("employee"):
        # A new empty form has no selected identity yet. Normal Link validation
        # and this check on the populated document still govern insertion.
        return True
    return bool(frappe.has_permission("Employee", "select", doc.employee, user=user))


def permitted_employee_names(company: str, *, branch: str | None = None,
                             department: str | None = None) -> tuple[str, ...]:
    """Return visible Employee IDs in one Company, narrowed by optional filters."""
    from tradex_hr.tradexcel_hr.company_context import assert_company_access

    assert_company_access(company)
    try:
        employees = frappe.get_list(
            "Employee",
            filters={"company": company},
            fields=["name", "branch", "department"],
            order_by="name asc",
            limit_page_length=0,
        )
    except frappe.PermissionError:
        frappe.throw(
            _("You do not have permission to view employees for this report."),
            frappe.PermissionError,
        )

    return tuple(
        row.name
        for row in employees
        if (not branch or row.branch == branch)
        and (not department or row.department == department)
    )


def permitted_salary_slips(company: str, employee_names: tuple[str, ...], *,
                           from_date: str, to_date: str, branch: str = "",
                           department: str = "", overlapping_period: bool = False) -> list[frappe._dict]:
    """Return submitted Salary Slips visible through native Employee/Slip permissions.

    These financial Script Reports read Salary Detail with SQL after this
    permission-aware parent lookup. Both native Salary Slip access and the
    caller's permitted Employee population are required; caller filters only
    narrow the returned period.
    """
    from tradex_hr.tradexcel_hr.company_context import assert_company_access

    assert_company_access(company)
    if not frappe.has_permission("Salary Slip", "read") or not frappe.has_permission("Salary Slip", "report"):
        frappe.throw(
            _("You do not have permission to view salary reports."),
            frappe.PermissionError,
        )
    if not employee_names:
        return []

    filters = {
        "company": company,
        "employee": ["in", employee_names],
        "docstatus": 1,
        "start_date": ["between", [from_date, to_date]],
    }
    if overlapping_period:
        filters["start_date"] = ["<=", to_date]
        filters["end_date"] = [">=", from_date]
    if branch:
        filters["branch"] = branch
    if department:
        filters["department"] = department

    try:
        return frappe.get_list(
            "Salary Slip",
            filters=filters,
            fields=[
                "name", "employee", "employee_name", "company", "branch",
                "department", "designation", "start_date", "end_date",
                "posting_date", "gross_pay", "total_deduction", "net_pay",
                "docstatus", "salary_structure", "payment_days",
            ],
            order_by="start_date asc, employee asc, name asc",
            limit_page_length=0,
        )
    except frappe.PermissionError:
        frappe.throw(
            _("You do not have permission to view salary reports."),
            frappe.PermissionError,
        )


def payroll_entry_query_conditions(user=None, doctype=None):
    """A payroll parent cannot expose children outside native Employee scope."""
    user = user or frappe.session.user
    if user == "Guest" or not frappe.get_cached_value("User", user, "enabled"):
        return "1=0"
    if not frappe.has_permission("Employee", "select", user=user):
        return "1=0"
    child = frappe.qb.DocType("Payroll Employee Detail")
    parent = frappe.qb.DocType("Payroll Entry")
    hidden_parents = (
        frappe.qb.from_(child).select(child.parent)
        .where(child.parenttype == "Payroll Entry")
        .where(child.employee.notin(permitted_employee_query(user)))
    )
    return parent.name.notin(hidden_parents).get_sql(quote_char="`", with_namespace=True)


def payroll_entry_has_permission(doc, ptype=None, user=None, **_kwargs):
    user = user or frappe.session.user
    if user == "Guest" or not frappe.get_cached_value("User", user, "enabled"):
        return False
    return all(
        frappe.has_permission("Employee", "select", row.employee, user=user)
        for row in doc.get("employees", []) if row.employee
    )
