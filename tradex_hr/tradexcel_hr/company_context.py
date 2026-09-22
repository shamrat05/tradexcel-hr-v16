"""Company resolution and access checks for multi-company reports."""

from __future__ import annotations

import frappe
from frappe import _


def user_default_company() -> str | None:
    """Return the current user's default company without inventing a tenant."""
    company = frappe.defaults.get_user_default("Company")
    return str(company).strip() if company else None


def resolve_company(filters: dict | None = None) -> str:
    """Resolve an explicit company or the current user's default company.

    There is intentionally no TCL fallback. A shared HRMS must never silently
    run an EFL request against TCL just because a filter was omitted.
    """
    values = filters or {}
    company = values.get("company") or user_default_company()
    company = str(company).strip() if company else ""
    if not company:
        raise ValueError(_("Company is required. Select a company or set your user default."))
    return company


def assert_company_access(company: str) -> str:
    """Reject unknown or unauthorized companies before report SQL runs."""
    if not frappe.db.exists("Company", company):
        frappe.throw(_("Company {0} does not exist").format(company))
    if not frappe.has_permission("Company", "read"):
        frappe.throw(
            _("You do not have permission to view company {0}").format(company),
            frappe.PermissionError,
        )
    # has_permission() checks role rights, not the user's allowed records.
    # get_list() applies User Permissions; this exact-name query prevents the
    # raw SQL reports from bypassing a user's TCL/EFL company boundary.
    allowed = frappe.get_list(
        "Company",
        filters={"name": company},
        fields=["name"],
        limit_page_length=1,
    )
    if not allowed:
        frappe.throw(
            _("You do not have permission to view company {0}").format(company),
            frappe.PermissionError,
        )
    return company
