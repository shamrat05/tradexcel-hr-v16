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
