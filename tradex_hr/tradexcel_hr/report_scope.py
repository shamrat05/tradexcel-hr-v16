"""Permission-aware Employee scope for Tradexcel reports.

Report SQL does not apply Frappe User Permissions. Resolve the caller's
permitted Employee rows with ``get_list`` first, then bind those names into
report SQL. Report filters are applied only after native scope is resolved,
so a caller can narrow access but cannot expand it.
"""

from __future__ import annotations

import frappe
from frappe import _


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
                           department: str = "") -> list[frappe._dict]:
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
                "docstatus",
            ],
            order_by="start_date asc, employee asc, name asc",
        )
    except frappe.PermissionError:
        frappe.throw(
            _("You do not have permission to view salary reports."),
            frappe.PermissionError,
        )
