"""Employee-scoped income-tax exemptions applied to salary slips."""

from __future__ import annotations

import frappe
from frappe.utils import getdate


TAX_ACTIONS = ("Mark Tax Exempt",)


def _in_window(rule, day):
    if rule.get("effective_from") and getdate(rule["effective_from"]) > day:
        return False
    if rule.get("effective_to") and getdate(rule["effective_to"]) < day:
        return False
    return True


def is_tax_exempt(employee, company, day, rules):
    day = getdate(day)
    return any(
        rule.get("employee") == employee
        and rule.get("company") == company
        and rule.get("tax_action") == "Mark Tax Exempt"
        and _in_window(rule, day)
        for rule in rules
    )


def tax_component_names():
    """Tax components are data-driven.

    Primary: any component HRMS flags as taxable-salary based.
    Fallback: component names containing 'tax' when nothing is flagged yet,
    so exemptions work before the flag is configured.
    """
    flagged = set(frappe.get_all(
        "Salary Component",
        filters={"variable_based_on_taxable_salary": 1},
        pluck="name",
    ))
    if flagged:
        return flagged
    return {
        name for name in frappe.get_all("Salary Component", pluck="name")
        if "tax" in name.casefold()
    }


def strip_tax_deductions(doc, tax_components):
    if not tax_components:
        return False
    kept = [row for row in doc.deductions if row.salary_component not in tax_components]
    if len(kept) == len(doc.deductions):
        return False
    doc.deductions = []
    for row in kept:
        doc.append("deductions", {
            "salary_component": row.salary_component,
            "abbr": row.abbr,
            "amount": row.amount,
        })
    return True


def _load(company):
    return frappe.get_all(
        "Tradexcel Policy Exception",
        filters={"docstatus": 1, "company": company, "exception_type": "Tax"},
        fields=["name", "company", "employee", "tax_action", "effective_from", "effective_to"],
    )


def load_tax_rules(company):
    cache = getattr(frappe.local, "tradex_tax_rules", None)
    if cache is None:
        cache = {}
        frappe.local.tradex_tax_rules = cache
    if company not in cache:
        cache[company] = _load(company)
    return cache[company]


def apply_tax_exemption(doc, method=None):
    """Doc event: exempt employees get tax deduction lines removed from their slips."""
    if not doc.employee or not doc.company:
        return
    rules = load_tax_rules(doc.company)
    if not rules:
        return
    day = doc.start_date or frappe.utils.today()
    if not is_tax_exempt(doc.employee, doc.company, day, rules):
        return
    if strip_tax_deductions(doc, tax_component_names()):
        from tradex_hr.tradexcel_hr.deduction_rules import recompute_totals

        recompute_totals(doc)
