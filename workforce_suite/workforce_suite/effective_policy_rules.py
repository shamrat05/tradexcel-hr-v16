"""Pure, effective-dated field rule resolution. No database or payroll writes."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation


SCOPE_FIELDS = ("branch", "department", "designation")
POSITIVE_FIELDS = {"daily_wage", "standard_hours_per_day", "overtime_after_hours",
                   "overtime_rounding_minutes", "max_weekly_hours"}
NONNEGATIVE_FIELDS = {"break_minutes", "overtime_grace_minutes", "max_daily_overtime_hours"}
INTEGER_FIELDS = {"break_minutes", "overtime_grace_minutes", "overtime_rounding_minutes"}
ALLOWED_FIELDS = POSITIVE_FIELDS | NONNEGATIVE_FIELDS | {"overtime_multiplier", "overtime_enabled"}


class RuleConflict(ValueError):
    """Two applicable rules set one field without a safe precedence."""

    def __init__(self, field: str, names: list[str]):
        self.field = field
        self.names = sorted(names)
        super().__init__(f"Conflicting {field} rules: {', '.join(self.names)}")


def _date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _anniversary(joined: date, months: int) -> date:
    month_index = joined.year * 12 + joined.month - 1 + months
    year, month_index = divmod(month_index, 12)
    month = month_index + 1
    return date(year, month, min(joined.day, calendar.monthrange(year, month)[1]))


def validate_rule(rule: dict) -> None:
    if not str(rule.get("reason") or "").strip():
        raise ValueError("Reason is required")
    field = rule.get("field_name")
    if field not in ALLOWED_FIELDS:
        raise ValueError("Unsupported setting")
    start = _date(rule["effective_from"])
    if rule.get("effective_to") and _date(rule["effective_to"]) < start:
        raise ValueError("Effective To must not precede Effective From")
    try:
        value = Decimal(str(rule["value"]))
    except (InvalidOperation, KeyError, TypeError):
        raise ValueError("New Value must be a number") from None
    if not value.is_finite():
        raise ValueError("New Value must be finite")
    if field in POSITIVE_FIELDS and value <= 0:
        raise ValueError(f"{field} must be greater than zero")
    if field in NONNEGATIVE_FIELDS and value < 0:
        raise ValueError(f"{field} cannot be negative")
    if field in INTEGER_FIELDS and value != int(value):
        raise ValueError(f"{field} must be a whole number")
    if field == "overtime_multiplier" and value not in (1, 2):
        raise ValueError("Overtime multiplier must be 1 or 2")
    if field == "overtime_enabled" and value not in (0, 1):
        raise ValueError("Overtime Enabled must be 0 or 1")
    tenure = Decimal(str(rule.get("min_tenure_months") or 0))
    if tenure < 0 or tenure != int(tenure):
        raise ValueError("Minimum service must be a non-negative whole number of months")


def _matches(employee: dict, day: date, rule: dict) -> bool:
    if rule.get("company") != employee.get("company"):
        return False
    if rule.get("employee_category"):
        category = "Worker" if employee.get("employment_type") == "Worker" else "Staff"
        if rule["employee_category"] != category:
            return False
    if _date(rule["effective_from"]) > day:
        return False
    if rule.get("effective_to") and day > _date(rule["effective_to"]):
        return False
    if rule.get("employee") and rule["employee"] != employee.get("name"):
        return False
    if any(rule.get(field) and rule[field] != employee.get(field) for field in SCOPE_FIELDS):
        return False
    months = int(rule.get("min_tenure_months") or 0)
    if months:
        joined = employee.get("date_of_joining")
        if not joined or _anniversary(_date(joined), months) > day:
            return False
    return True


def _outranks(left: dict, right: dict) -> bool:
    # Personal exceptions are explicit and always take precedence.
    if bool(left.get("employee")) != bool(right.get("employee")):
        return bool(left.get("employee"))

    left_scope = {field for field in SCOPE_FIELDS if left.get(field)}
    right_scope = {field for field in SCOPE_FIELDS if right.get(field)}
    if not left_scope.issuperset(right_scope):
        return False  # Incomparable scopes must be reviewed, not ranked arbitrarily.

    left_tenure = int(left.get("min_tenure_months") or 0)
    right_tenure = int(right.get("min_tenure_months") or 0)
    if left_tenure < right_tenure:
        return False
    if left_scope > right_scope or left_tenure > right_tenure:
        return True
    return _date(left["effective_from"]) > _date(right["effective_from"])


def resolve_values(employee: dict, day: date | str, rules: list[dict]) -> dict:
    """Return field -> {value, rule}; raise on conflicting incomparable winners."""
    day = _date(day)
    by_field = {}
    for rule in rules:
        if _matches(employee, day, rule):
            by_field.setdefault(rule["field_name"], []).append(rule)

    result = {}
    for field, candidates in by_field.items():
        winners = [
            rule for rule in candidates
            if not any(_outranks(other, rule) for other in candidates if other is not rule)
        ]
        if len({str(rule["value"]) for rule in winners}) > 1:
            raise RuleConflict(field, [rule["name"] for rule in winners])
        winner = sorted(winners, key=lambda rule: rule["name"])[0]
        result[field] = {"value": winner["value"], "rule": winner["name"]}
    return result


def preview_change(
    employees: list[dict],
    active_rules: list[dict],
    proposed: dict,
    start: date | str,
    end: date | str,
    submitted_slips: list[dict],
    *,
    draft_slips: list[dict] | None = None,
    base_value=None,
) -> dict:
    """Compare field values by day; never mutate employees, rules, or payroll."""
    start, end = _date(start), _date(end)
    if end < start:
        raise ValueError("Preview end must not precede start")
    if (end - start).days >= 366:
        raise ValueError("Preview cannot exceed 366 days")
    field = proposed["field_name"]
    changes = []
    affected_days = 0
    impacted_slips = set()
    impacted_drafts = set()
    slips_by_employee = {}
    for slip in submitted_slips:
        slips_by_employee.setdefault(slip["employee"], []).append((slip, impacted_slips))
    for slip in draft_slips or []:
        slips_by_employee.setdefault(slip["employee"], []).append((slip, impacted_drafts))
    for employee in employees:
        open_change = None
        day = start
        while day <= end:
            if not _matches(employee, day, proposed):
                open_change = None
                day += timedelta(days=1)
                continue
            old_rule = resolve_values(employee, day, active_rules).get(field)
            new_rule = resolve_values(employee, day, [*active_rules, proposed]).get(field)
            default = base_value(employee, day, field) if base_value else None
            old = old_rule["value"] if old_rule else default
            new = new_rule["value"] if new_rule else default
            if old != new:
                affected_days += 1
                if open_change and open_change["old_value"] == old and open_change["new_value"] == new:
                    open_change["to_date"] = day.isoformat()
                else:
                    open_change = {
                        "employee": employee["name"],
                        "from_date": day.isoformat(),
                        "to_date": day.isoformat(),
                        "old_value": old,
                        "new_value": new,
                        "source_rule": new_rule["rule"] if new_rule else None,
                    }
                    changes.append(open_change)
                for slip, impacted in slips_by_employee.get(employee["name"], []):
                    if _date(slip["start_date"]) <= day <= _date(slip["end_date"]):
                        impacted.add(slip["name"])
            else:
                open_change = None
            day += timedelta(days=1)
    return {
        "field_name": field,
        "affected_days": affected_days,
        "affected_employees": len({row["employee"] for row in changes}),
        "changes": changes,
        "submitted_slips": sorted(impacted_slips),
        "draft_slips": sorted(impacted_drafts),
    }
