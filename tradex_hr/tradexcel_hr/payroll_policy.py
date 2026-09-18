"""Resolve the most specific editable TradeX payroll policy for an employee."""

from __future__ import annotations

from datetime import date

import frappe
from frappe.utils import getdate, today

from tradex_hr.tradexcel_hr.effective_policy_rules import resolve_values


def employee_category(employee: dict | str) -> str:
    if isinstance(employee, str):
        employee = frappe.db.get_value(
            "Employee", employee, ["employment_type", "branch", "department"], as_dict=True
        )
    return "Worker" if employee and employee.get("employment_type") == "Worker" else "Staff"


def resolve_policy(employee: dict | str, as_of: date | str | None = None):
    if isinstance(employee, str):
        employee = frappe.db.get_value(
            "Employee", employee,
            ["name", "company", "branch", "department", "designation", "employment_type", "date_of_joining"],
            as_dict=True,
        )
    if not employee:
        return None

    as_of = getdate(as_of or today())
    candidates = frappe.get_all(
        "Tradexcel Payroll Policy",
        filters={
            "enabled": 1,
            "company": employee.get("company"),
            "employee_category": employee_category(employee),
            "effective_from": ["<=", as_of],
        },
        fields="*",
        order_by="modified desc",
    )
    matching = [
        policy
        for policy in candidates
        if (not policy.branch or policy.branch == employee.get("branch"))
        and (not policy.department or policy.department == employee.get("department"))
    ]
    matching.sort(
        key=lambda policy: (
            bool(policy.department),
            bool(policy.branch),
            getdate(policy.effective_from),
            policy.modified,
        ),
        reverse=True,
    )
    if not matching:
        return None
    policy = frappe._dict(dict(matching[0]))
    exceptions = frappe.get_all(
        "Tradexcel Policy Exception",
        # exception_type is REQUIRED here. The approval preview filters on
        # "Payroll" (tradexcel_policy_exception.py). Omitting the filter meant
        # runtime applied a strictly larger set than was ever previewed, so a
        # non-payroll exception carrying a payroll field_name could change wages
        # without appearing in the preview at all.
        filters={"docstatus": 1, "company": employee.get("company"),
                 "exception_type": "Payroll",
                 "effective_from": ["<=", as_of]},
        fields=["name", "company", "employee_category", "branch", "department", "designation",
                "employee", "min_tenure_months", "field_name", "value", "effective_from", "effective_to"],
    )
    for field, winner in resolve_values(employee, as_of, exceptions).items():
        policy[field] = winner["value"]
    return policy
