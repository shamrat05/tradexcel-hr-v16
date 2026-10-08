"""Validation for explicit Daily Wage component routing on native structures."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt


def validate_salary_structure(doc, method=None):
    """Require a neutral, explicit receiver row for Daily Wage structures."""
    pay_basis = doc.get("custom_workforce_pay_basis")
    component = doc.get("custom_workforce_daily_wage_component")
    if pay_basis == "Monthly Salary":
        if component:
            frappe.throw(_("Monthly Salary structures must not set a Daily Wage Salary Component."))
        return
    if pay_basis != "Daily Wage":
        return
    if not component:
        frappe.throw(_("Select the Daily Wage Salary Component for this Salary Structure."))

    master = frappe.db.get_value(
        "Salary Component", component, ["type", "disabled"], as_dict=True
    )
    if not master:
        frappe.throw(_("The configured Daily Wage Salary Component does not exist."))
    if master.disabled:
        frappe.throw(_("The configured Daily Wage Salary Component must be enabled."))
    if master.type != "Earning":
        frappe.throw(_("The configured Daily Wage Salary Component must be an Earning."))

    matching_rows = [row for row in (doc.get("earnings") or []) if row.salary_component == component]
    if len(matching_rows) != 1:
        frappe.throw(_("The configured Daily Wage Salary Component must appear exactly once in Earnings."))

    row = matching_rows[0]
    if row.get("depends_on_payment_days"):
        frappe.throw(_("The configured Daily Wage Salary Component must not depend on payment days."))
    if row.get("amount_based_on_formula") or (row.get("formula") or "").strip():
        frappe.throw(_("The configured Daily Wage Salary Component must not calculate a separate formula amount."))
    if flt(row.get("amount")) != 0:
        frappe.throw(_("The configured Daily Wage Salary Component must have a zero structure amount."))
