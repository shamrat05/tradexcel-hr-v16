"""Retired payroll runner and pure helpers retained for legacy comparisons."""

from __future__ import annotations

import argparse
import os
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import frappe

def _as_date(value):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def preflight_payroll_assignments(rows, start_date, end_date):
    """Classify assignment boundaries without writing payroll records."""
    start = _as_date(start_date)
    end = _as_date(end_date)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["employee_name"]].append(dict(row))

    results = []
    for employee_name in sorted(grouped):
        employee_rows = grouped[employee_name]
        assignments = [row for row in employee_rows if row.get("assignment_name")]
        employee = dict(employee_rows[0])
        employee["name"] = employee_name

        joining_date = _as_date(employee.get("date_of_joining"))
        relieving_date = _as_date(employee.get("relieving_date"))
        if joining_date and start < joining_date <= end:
            results.append({
                "employee": employee_name,
                "employee_data": employee,
                "assignment": None,
                "status": "BLOCKED_JOIN_MID_PERIOD",
                "reason": "Employee joins during the period; legacy runner does not prorate joiners.",
            })
            continue
        if relieving_date and start <= relieving_date < end:
            results.append({
                "employee": employee_name,
                "employee_data": employee,
                "assignment": None,
                "status": "BLOCKED_RELIEVE_MID_PERIOD",
                "reason": "Employee leaves during the period; legacy runner does not prorate leavers.",
            })
            continue
        if employee.get("status") not in (None, "Active", "Left"):
            results.append({
                "employee": employee_name,
                "employee_data": employee,
                "assignment": None,
                "status": "BLOCKED_EMPLOYMENT_STATUS",
                "reason": f"Employment status {employee.get('status')!r} has no configured payroll behavior.",
            })
            continue

        if not assignments:
            results.append({
                "employee": employee_name,
                "employee_data": employee,
                "assignment": None,
                "status": "BLOCKED_MISSING_ASSIGNMENT",
                "reason": "No submitted Salary Structure Assignment applies to the payroll period.",
            })
            continue

        dates = [_as_date(row.get("from_date")) for row in assignments]
        if any(value is None for value in dates):
            results.append({
                "employee": employee_name,
                "employee_data": employee,
                "assignment": None,
                "status": "BLOCKED_INVALID_ASSIGNMENT",
                "reason": "An applicable Salary Structure Assignment has no effective date.",
            })
            continue

        mid_period = [
            row for row, effective_date in zip(assignments, dates)
            if start < effective_date <= end
        ]
        if mid_period:
            results.append({
                "employee": employee_name,
                "employee_data": employee,
                "assignment": None,
                "status": "BLOCKED_MID_PERIOD_CHANGE",
                "reason": "Salary Structure Assignment changes during the period; legacy runner does not prorate it.",
            })
            continue

        period_start_assignments = [
            row for row, effective_date in zip(assignments, dates) if effective_date <= start
        ]
        if not period_start_assignments:
            results.append({
                "employee": employee_name,
                "employee_data": employee,
                "assignment": None,
                "status": "BLOCKED_MISSING_ASSIGNMENT",
                "reason": "No submitted Salary Structure Assignment applies at period start.",
            })
            continue

        latest_from_date = max(_as_date(row["from_date"]) for row in period_start_assignments)
        latest_assignments = [
            row for row in period_start_assignments if _as_date(row["from_date"]) == latest_from_date
        ]
        if len(latest_assignments) != 1:
            names = ", ".join(sorted(str(row["assignment_name"]) for row in latest_assignments))
            results.append({
                "employee": employee_name,
                "employee_data": employee,
                "assignment": None,
                "status": "BLOCKED_ASSIGNMENT_OVERLAP",
                "reason": f"Conflicting assignments share effective date {latest_from_date}: {names}.",
            })
            continue

        assignment = latest_assignments[0]
        if Decimal(str(assignment.get("base") or 0)) <= 0:
            results.append({
                "employee": employee_name,
                "employee_data": employee,
                "assignment": assignment,
                "status": "BLOCKED_MISSING_BASE",
                "reason": "Salary Structure Assignment base must be greater than zero.",
            })
            continue

        results.append({
            "employee": employee_name,
            "employee_data": employee,
            "assignment": assignment,
            "status": "READY",
            "reason": "One valid assignment applies for the complete period.",
        })

    return results


def structure_earnings(salary_structure: str, gross) -> list[dict[str, Any]]:
    """Read a legacy structure split for comparison without creating payroll."""
    from decimal import ROUND_HALF_UP

    structure = frappe.get_doc("Salary Structure", salary_structure)
    base = Decimal(str(gross))
    out: list[dict[str, Any]] = []
    for row in structure.earnings:
        formula = (row.formula or "").strip()
        if formula and "payment_days" in formula:
            # Daily-wage structures are paid per attendance day and are handled
            # by native Salary Structure Assignment authority, not a payroll-policy split.
            raise ValueError(
                f"{salary_structure} is attendance-based (formula {formula!r}); "
                f"monthly gross splitting does not apply."
            )
        if formula:
            # structures declare `base * <factor>`; anything else is refused
            # rather than guessed, so a new formula cannot silently mis-pay.
            if not formula.replace(" ", "").startswith("base*"):
                raise ValueError(
                    f"{salary_structure}: earnings row {row.salary_component!r} uses "
                    f"formula {formula!r}, which this runner cannot evaluate safely. "
                    f"Use `base * <factor>` or move the logic into Additional Salary."
                )
            factor = Decimal(formula.replace(" ", "")[len("base*"):])
            amount = (base * factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            amount = Decimal(str(row.amount or 0)).quantize(Decimal("0.01"))
        out.append({"salary_component": row.salary_component,
                    "abbr": row.abbr or row.salary_component[:3].upper(),
                    "amount": amount})

    declared = sum((r["amount"] for r in out), Decimal(0))
    if declared != base:
        raise ValueError(
            f"{salary_structure}: earnings total {declared} does not equal the "
            f"assignment base {base}. Fix the structure percentages — they must "
            f"sum to 100%."
        )
    return out


def run_payroll_for_month(
    year,
    month,
    company,
    *,
    site: str | None = None,
    sites_path: str | None = None,
):
    raise RuntimeError(
        "The legacy manual Salary Slip payroll runner is disabled. "
        "Use Tradexcel Payroll Readiness and the native Payroll Entry workflow."
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Legacy manual payroll runner (disabled)")
    parser.add_argument("--year", type=int)
    parser.add_argument("--month", type=int)
    parser.add_argument("--company", default=os.environ.get("TRADEX_PAYROLL_COMPANY"))
    parser.add_argument("--site", default=os.environ.get("FRAPPE_SITE"))
    parser.add_argument("--sites-path", default=os.environ.get("FRAPPE_SITES_PATH"))
    args = parser.parse_args(argv)
    missing = [
        option for option, value in (
            ("--year", args.year),
            ("--month", args.month),
            ("--company or TRADEX_PAYROLL_COMPANY", args.company),
            ("--site or FRAPPE_SITE", args.site),
            ("--sites-path or FRAPPE_SITES_PATH", args.sites_path),
        ) if value in (None, "")
    ]
    if missing:
        parser.error("required payroll target missing: " + ", ".join(missing))
    try:
        return (
            0
            if run_payroll_for_month(
                args.year,
                args.month,
                company=args.company,
                site=args.site,
                sites_path=args.sites_path,
            )
            else 1
        )
    except RuntimeError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
