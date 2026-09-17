"""Dynamic salary-slip deductions from structure configuration, exception-aware.

Deductions are read from the slip's Salary Structure rows, so nothing is
hardcoded: configure a deduction component on the structure and every slip
carries it. Component and Tax exceptions then exclude/override/strip lines,
and recompute_totals() makes net pay reflect the exception immediately.
"""

from __future__ import annotations

import frappe
from math import isfinite
from frappe.utils.safe_exec import safe_eval
from frappe.utils import rounded


def compute_deductions(rows, gross, *, base=None, payment_days=None, total_working_days=None, earnings=None):
    """rows: Salary Structure deduction rows (documents or dicts)."""
    gross = float(gross or 0)
    data = {
        "base": float(base if base is not None else gross),
        "gross": gross,
        "payment_days": float(payment_days or 0),
        "total_working_days": float(total_working_days or 0),
    }
    for earning in earnings or []:
        if earning.get("abbr"):
            data[earning.get("abbr")] = float(earning.get("amount") or 0)
    result = []
    for row in rows:
        component = row.get("salary_component")
        if not component:
            continue
        if row.get("statistical_component"):
            raise ValueError(f"Statistical deduction {component} is not supported by manual payroll")
        condition = row.get("condition")
        if condition:
            try:
                if not safe_eval(str(condition), data):
                    continue
            except Exception as exc:
                raise ValueError(f"Deduction condition for {component} failed: {exc}") from exc
        if row.get("amount_based_on_formula") and row.get("formula"):
            try:
                value = safe_eval(str(row["formula"]), data)
            except Exception as exc:
                raise ValueError(
                    f"Deduction formula for {component} failed: {row.get('formula')} ({exc})"
                ) from exc
        else:
            value = row.get("amount") or 0
        value = float(value or 0)
        if not isfinite(value) or value < 0:
            raise ValueError(f"Deduction {component} must be a finite non-negative amount")
        if value:
            depends_on_payment_days = int(row.get("depends_on_payment_days") or 0)
            if depends_on_payment_days:
                if not total_working_days:
                    raise ValueError(f"Deduction {component} needs total working days for proration")
                value = value * float(payment_days or 0) / float(total_working_days)
            value = round(value, 2)
            result.append({
                "salary_component": component,
                "abbr": row.get("abbr"),
                "amount": value,
                "default_amount": 0,
                "amount_based_on_formula": 0,
                "depends_on_payment_days": 0,
            })
            data[row.get("abbr") or component] = value
    return result


def structure_deductions(salary_structure, gross, **context):
    structure = frappe.get_doc("Salary Structure", salary_structure)
    return compute_deductions(structure.deductions, gross, **context)


def recompute_totals(doc):
    """Rebuild gross/deduction/net totals from the slip's own rows."""
    gross = sum(float(row.amount or 0) for row in doc.earnings)
    total_deduction = sum(float(row.amount or 0) for row in doc.deductions)
    doc.gross_pay = gross
    doc.total_deduction = total_deduction
    loan_repayment = float(getattr(doc, "total_loan_repayment", 0) or 0)
    doc.net_pay = gross - total_deduction - loan_repayment
    if doc.net_pay < -0.005:
        raise ValueError("Salary slip has negative net pay; review deductions before saving")
    doc.rounded_total = rounded(doc.net_pay)
    rate = float(getattr(doc, "exchange_rate", 1) or 1)
    doc.base_gross_pay = gross * rate
    doc.base_total_deduction = total_deduction * rate
    doc.base_net_pay = doc.net_pay * rate
    doc.base_rounded_total = rounded(doc.base_net_pay)
