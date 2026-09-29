"""Explicit financial pay-basis resolution.

Employment Type remains useful for HR grouping, but it is not a monetary
authority.  Salary Structure Assignment selects the effective structure and
the structure's explicit Tradexcel pay-basis field selects the financial
meaning.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date
from typing import Any

import frappe
from frappe.utils import flt, getdate


MONTHLY = "Monthly Salary"
DAILY = "Daily Wage"
UNRESOLVED = "UNRESOLVED"
CONFLICT = "CONFLICT"
MID_PERIOD_CHANGE = "MID_PERIOD_CHANGE"



_read_snapshot = ContextVar("tradexcel_pay_basis_read_snapshot", default=None)


@contextmanager
def pay_basis_read_context(employee_names):
    """Batch facts for an explicitly read-only, already-authorized report call.

    This is not a process/session cache. Reset even on failure; mutation paths
    never enter this context. The single canonical resolver still decides all
    dates, conflicts, missing bases and amounts.
    """
    names = frozenset(employee_names)
    previous = _read_snapshot.get()
    if not names or (previous and names <= previous["names"]):
        yield
        return
    assignments = frappe.get_all(
        "Salary Structure Assignment", filters={"employee": ["in", sorted(names)], "docstatus": 1},
        fields=["name", "employee", "salary_structure", "base", "from_date", "company"],
        order_by="from_date desc, name desc", limit_page_length=0,
    )
    rows = {employee: [] for employee in names}
    for row in assignments:
        rows[row.employee].append(row)
    structures = sorted({row.salary_structure for row in assignments if row.salary_structure})
    structures_config = {row.name: {
        "pay_basis": row.custom_tradex_pay_basis,
        "daily_wage_component": row.custom_tradex_daily_wage_component,
    } for row in frappe.get_all(
        "Salary Structure", filters={"name": ["in", structures]},
        fields=["name", "custom_tradex_pay_basis", "custom_tradex_daily_wage_component"], limit_page_length=0,
    )} if structures else {}
    joining = {row.name: row.date_of_joining for row in frappe.get_all(
        "Employee", filters={"name": ["in", sorted(names)]}, fields=["name", "date_of_joining"], limit_page_length=0,
    )}
    token = _read_snapshot.set({"names": names, "rows": rows, "structures": structures_config, "joining": joining})
    try:
        yield
    finally:
        _read_snapshot.reset(token)

def _assignment_rows(employee: str, as_of: date, period_end: date | None = None) -> list[dict[str, Any]]:
    snapshot = _read_snapshot.get()
    if snapshot and employee in snapshot["names"]:
        rows = snapshot["rows"][employee]
        earlier = [row for row in rows if getdate(row.from_date) <= as_of]
        later = sorted(
            (row for row in rows if period_end and as_of < getdate(row.from_date) <= period_end),
            key=lambda row: (getdate(row.from_date), row.name),
        )
        return earlier + later
    filters: dict[str, Any] = {
        "employee": employee,
        "docstatus": 1,
        "from_date": ["<=", as_of],
    }
    fields = ["name", "employee", "salary_structure", "base", "from_date", "company"]
    rows = frappe.get_all(
        "Salary Structure Assignment",
        filters=filters,
        fields=fields,
        order_by="from_date desc, name desc",
    )
    if period_end and period_end > as_of:
        later_filters = {
            "employee": employee,
            "docstatus": 1,
            "from_date": [">", as_of],
        }
        rows.extend(
            row
            for row in frappe.get_all(
                "Salary Structure Assignment",
                filters=later_filters,
                fields=fields,
                order_by="from_date asc, name asc",
            )
            if getdate(row.get("from_date")) <= period_end
        )
    return rows


def _structure_configuration(structure: str | None) -> dict[str, Any]:
    if not structure:
        return {}
    snapshot = _read_snapshot.get()
    if snapshot and structure in snapshot["structures"]:
        return snapshot["structures"][structure]
    values = frappe.db.get_value(
        "Salary Structure", structure,
        ["custom_tradex_pay_basis", "custom_tradex_daily_wage_component"], as_dict=True,
    )
    return dict(values or {})


def resolve_pay_basis(
    employee: str,
    as_of_date: str | date,
    period_end: str | date | None = None,
) -> dict[str, Any]:
    """Resolve one explicit pay basis without financial inference.

    When ``period_end`` is supplied, a later effective assignment is reported
    as ``MID_PERIOD_CHANGE`` rather than silently applying one basis to a
    mixed period.  Same-date submitted assignment conflicts are reported as
    ``CONFLICT`` even though native HRMS normally prevents them.
    """
    as_of = getdate(as_of_date)
    end = getdate(period_end) if period_end else None
    if end and as_of and as_of < end:
        snapshot = _read_snapshot.get()
        employee_joining_date = snapshot["joining"].get(employee) if snapshot and employee in snapshot["names"] else frappe.db.get_value(
            "Employee", employee, "date_of_joining"
        )
        joining_date = getdate(employee_joining_date) if employee_joining_date else None
        if joining_date and as_of < joining_date <= end:
            as_of = joining_date
    if not as_of:
        return {"status": UNRESOLVED, "employee": employee, "reason": "Missing effective date"}

    rows = _assignment_rows(employee, as_of, end)
    applicable = [row for row in rows if getdate(row.get("from_date")) <= as_of]
    if not applicable:
        return {
            "status": UNRESOLVED,
            "employee": employee,
            "reason": f"No submitted Salary Structure Assignment applies on {as_of}",
        }

    latest_date = getdate(applicable[0].get("from_date"))
    same_date = [row for row in applicable if getdate(row.get("from_date")) == latest_date]
    if len(same_date) != 1:
        return {
            "status": CONFLICT,
            "employee": employee,
            "from_date": latest_date,
            "assignments": [row.get("name") for row in same_date],
            "reason": "Multiple submitted Salary Structure Assignments have the same effective date",
        }

    later = []
    if end and end > as_of:
        later = [row for row in rows if as_of < getdate(row.get("from_date")) <= end]
    if later:
        return {
            "status": MID_PERIOD_CHANGE,
            "employee": employee,
            "assignment": same_date[0].get("name"),
            "from_date": latest_date,
            "later_assignments": [row.get("name") for row in later],
            "reason": "Pay basis or rate may change during the period; the mixed legacy adapter will not guess",
        }

    assignment = same_date[0]
    structure = assignment.get("salary_structure")
    configuration = _structure_configuration(structure)
    basis = configuration.get("custom_tradex_pay_basis") or configuration.get("pay_basis")
    component = configuration.get("custom_tradex_daily_wage_component") or configuration.get("daily_wage_component")
    if basis not in {MONTHLY, DAILY}:
        return {
            "status": UNRESOLVED,
            "employee": employee,
            "assignment": assignment.get("name"),
            "salary_structure": structure,
            "reason": "The assigned Salary Structure has no explicit Tradexcel pay basis",
        }
    if basis == DAILY and not component:
        return {
            "status": UNRESOLVED,
            "employee": employee,
            "assignment": assignment.get("name"),
            "salary_structure": structure,
            "reason": "The assigned Daily Wage Salary Structure has no configured Daily Wage Salary Component.",
        }

    return {
        "status": basis,
        "employee": employee,
        "assignment": assignment.get("name"),
        "salary_structure": structure,
        "base": flt(assignment.get("base")),
        "from_date": latest_date,
        "source": "Salary Structure Assignment + Salary Structure.custom_tradex_pay_basis",
        **({"daily_wage_component": component} if basis == DAILY else {}),
    }


def resolve_daily_rate(result: dict[str, Any]) -> dict[str, Any]:
    """Return the SSA rate or an explicit blocker; never use policy.daily_wage."""
    if result.get("status") != DAILY:
        return {"status": result.get("status", UNRESOLVED), "reason": result.get("reason")}
    base = flt(result.get("base"))
    if base <= 0:
        return {
            "status": "BLOCKED_MISSING_BASE",
            "employee": result.get("employee"),
            "assignment": result.get("assignment"),
            "reason": "Daily Wage requires a positive Salary Structure Assignment.base",
        }
    return {"status": "READY", "employee": result.get("employee"), "rate": base, "assignment": result.get("assignment")}
