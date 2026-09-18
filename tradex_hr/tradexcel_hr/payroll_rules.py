"""Deterministic, configurable wage calculations used by TradeX payroll.

The rules are intentionally data-only. Frappe documents and source API calls
belong in the adapters around this module, which keeps the calculation easy to
test and prevents a missing salary from becoming a made-up wage.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

DEFAULT_COMPONENTS = {
    "Basic Salary": Decimal(50),
    "House Rent Allowance": Decimal(25),
    "Medical Allowance": Decimal(10),
    "Conveyance Allowance": Decimal(10),
    "Food Allowance": Decimal(5),
}
ABBR = {
    "Basic Salary": "BS",
    "House Rent Allowance": "HRA",
    "Medical Allowance": "MA",
    "Conveyance Allowance": "CA",
    "Food Allowance": "FA",
}
MONEY = Decimal("0.01")


def employee_joins_after_period(date_of_joining: Any, period_end: Any) -> bool:
    """Return whether an employee cannot be paid in a completed period."""
    if not date_of_joining or not period_end:
        return False
    return str(date_of_joining)[:10] > str(period_end)[:10]


def as_money(value: Any) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid salary amount: {value!r}") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError(f"Salary amount must be a finite non-negative number: {value!r}")
    return amount.quantize(MONEY, rounding=ROUND_HALF_UP)


def validate_components(components: Mapping[str, Any]) -> dict[str, Decimal]:
    if not components:
        raise ValueError("At least one salary component is required")
    parsed = {str(name): as_money(percent) for name, percent in components.items()}
    total = sum(parsed.values(), Decimal(0))
    if total != Decimal("100.00"):
        raise ValueError(f"Salary component percentages must total 100.00, got {total}")
    return parsed


def calculate_wage(gross: Any, components: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Split a source gross wage into configured earnings without rounding drift."""
    gross_amount = as_money(gross)
    percentages = validate_components(components or DEFAULT_COMPONENTS)
    earnings: list[dict[str, Any]] = []
    running = Decimal(0)
    names = list(percentages)
    for name in names[:-1]:
        amount = (gross_amount * percentages[name] / Decimal(100)).quantize(
            MONEY, rounding=ROUND_HALF_UP
        )
        running += amount
        earnings.append({"salary_component": name, "abbr": ABBR.get(name, name[:3].upper()),
                         "amount": amount})
    last = names[-1]
    final_amount = gross_amount - running
    earnings.append({"salary_component": last, "abbr": ABBR.get(last, last[:3].upper()),
                     "amount": final_amount})
    return {
        "gross": gross_amount,
        "earnings": earnings,
        "deductions": [],
        "net": gross_amount,
    }


def calculate_overtime_hours(
    worked_hours: Any,
    standard_hours: Any = 8,
    grace_minutes: Any = 10,
    rounding_minutes: Any = 60,
    max_daily_hours: Any | None = None,
) -> Decimal:
    """Return whole billable overtime hours using the configured grace period.

    Ten minutes of grace means 50 minutes beyond the standard day becomes one
    hour, while 49 minutes remains zero. Partial billable hours are never
    returned. The optional daily cap keeps the result within the configured
    operating policy.
    """
    worked = Decimal(str(worked_hours))
    standard = Decimal(str(standard_hours))
    grace = Decimal(str(grace_minutes))
    rounding = Decimal(str(rounding_minutes))
    if any(value.is_nan() or value.is_infinite() for value in (worked, standard, grace, rounding)):
        raise ValueError("Overtime values must be finite")
    if standard <= 0 or grace < 0 or rounding <= 0:
        raise ValueError("Overtime configuration must use positive hours and minutes")

    overtime_minutes = max((worked - standard) * Decimal(60), Decimal(0))
    billable_units = (overtime_minutes + grace) // rounding
    overtime_hours = (billable_units * rounding / Decimal(60)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    if max_daily_hours is not None:
        cap = Decimal(str(max_daily_hours))
        if cap < 0 or cap.is_nan() or cap.is_infinite():
            raise ValueError("Maximum daily overtime must be non-negative and finite")
        overtime_hours = min(overtime_hours, cap)
    return overtime_hours


def calculate_daily_worker_wage(
    paid_days: Any,
    daily_rate: Any,
    overtime_hours: Any = 0,
    hours_per_day: Any = 8,
    overtime_multiplier: Any = 2,
) -> dict[str, Decimal]:
    """Calculate a daily worker's regular and overtime pay without drift."""
    days = Decimal(str(paid_days))
    rate = as_money(daily_rate)
    overtime = Decimal(str(overtime_hours))
    hours = Decimal(str(hours_per_day))
    multiplier = Decimal(str(overtime_multiplier))
    if days < 0 or overtime < 0 or hours <= 0 or multiplier not in (Decimal(1), Decimal(2)):
        raise ValueError("Daily wage inputs are outside the supported range")
    regular = (days * rate).quantize(MONEY, rounding=ROUND_HALF_UP)
    overtime_amount = (overtime * rate / hours * multiplier).quantize(MONEY, rounding=ROUND_HALF_UP)
    gross = regular + overtime_amount
    return {"regular": regular, "overtime": overtime_amount, "gross": gross, "net": gross}


def calculate_attendance_pay(
    records: list[Mapping[str, Any]],
    *,
    standard_hours: Any = 8,
    break_minutes: Any = 0,
    grace_minutes: Any = 10,
    rounding_minutes: Any = 60,
    max_daily_overtime_hours: Any | None = 2,
) -> dict[str, Any]:
    """Aggregate one employee's payable source attendance into paid days and OT.

    A source can contain more than one row for a day.  The longest complete,
    payable interval is selected so duplicate device imports cannot pay twice.
    """
    break_value = Decimal(str(break_minutes))
    if break_value < 0 or break_value.is_nan() or break_value.is_infinite():
        raise ValueError("Break minutes must be a finite non-negative number")

    days: dict[str, dict[str, Decimal]] = {}
    for record in records:
        if not record.get("isPayable") or not record.get("checkInTime") or not record.get("checkOutTime"):
            continue
        day = str(record.get("date") or "")
        if not day:
            continue
        try:
            check_in = datetime.fromisoformat(str(record["checkInTime"]).replace("Z", "+00:00"))
            check_out = datetime.fromisoformat(str(record["checkOutTime"]).replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid attendance timestamp for {day}") from exc
        elapsed_minutes = Decimal(str((check_out - check_in).total_seconds() / 60))
        if elapsed_minutes < 0:
            continue
        worked_minutes = max(elapsed_minutes - break_value, Decimal(0))
        worked_hours = worked_minutes / Decimal(60)
        overtime_hours = calculate_overtime_hours(
            worked_hours,
            standard_hours=standard_hours,
            grace_minutes=grace_minutes,
            rounding_minutes=rounding_minutes,
            max_daily_hours=max_daily_overtime_hours,
        )
        candidate = {
            "worked_hours": worked_hours,
            "overtime_hours": overtime_hours,
        }
        if day not in days or candidate["worked_hours"] > days[day]["worked_hours"]:
            days[day] = candidate

    worked_hours = sum((row["worked_hours"] for row in days.values()), Decimal(0))
    overtime_hours = sum((row["overtime_hours"] for row in days.values()), Decimal(0))
    return {
        "paid_days": len(days),
        "worked_hours": worked_hours.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "overtime_hours": overtime_hours,
        "days": days,
    }


def calculate_dated_worker_pay(records, policy_for_day):
    """Price each attendance day under the rule effective on that day."""
    grouped = {}
    for record in records:
        grouped.setdefault(str(record["date"]), []).append(record)
    regular = overtime = worked = overtime_hours = Decimal(0)
    paid_days = 0
    rates = set()
    for day, day_records in sorted(grouped.items()):
        policy = policy_for_day(day)
        if not policy or policy.get("pay_basis", "Daily Wage") != "Daily Wage":
            raise ValueError(f"No daily-wage policy on {day}")
        attendance = calculate_attendance_pay(
            day_records,
            standard_hours=policy.get("overtime_after_hours") or policy["standard_hours_per_day"],
            break_minutes=policy["break_minutes"],
            grace_minutes=policy["overtime_grace_minutes"],
            rounding_minutes=policy["overtime_rounding_minutes"],
            max_daily_overtime_hours=policy["max_daily_overtime_hours"],
        )
        billable_ot = attendance["overtime_hours"] if policy["overtime_enabled"] else Decimal(0)
        pay = calculate_daily_worker_wage(
            attendance["paid_days"], policy["daily_wage"], billable_ot,
            policy["standard_hours_per_day"], policy["overtime_multiplier"],
        )
        regular += pay["regular"]
        overtime += pay["overtime"]
        worked += attendance["worked_hours"]
        overtime_hours += billable_ot
        paid_days += attendance["paid_days"]
        if attendance["paid_days"]:
            rates.add(Decimal(str(policy["daily_wage"])) / Decimal(str(policy["standard_hours_per_day"])))
    return {
        "regular": regular, "overtime": overtime, "gross": regular + overtime,
        "paid_days": paid_days, "worked_hours": worked, "overtime_hours": overtime_hours,
        "single_hour_rate": next(iter(rates)) if len(rates) == 1 else Decimal(0),
    }


SOURCE_GROSS_FIELDS = (
    "grossSalary", "gross_salary", "monthlySalary", "monthly_salary",
    "salaryAmount", "salary_amount", "basicSalary", "basic_salary",
    "monthlyWage", "monthly_wage", "baseSalary", "base_salary",
    "currentSalaryAmount", "current_salary_amount", "grossAmount", "gross_amount",
    "amount",
)


def source_gross(record: Mapping[str, Any]) -> Decimal | None:
    """Return a source-provided wage; return None when the source has no wage."""
    normalized = record.get("source_gross_amount")
    if normalized not in (None, ""):
        return as_money(normalized)
    nested = record.get("salary") if isinstance(record.get("salary"), Mapping) else record
    if not isinstance(nested, Mapping):
        nested = record
    for field in SOURCE_GROSS_FIELDS:
        value = nested.get(field)
        if value not in (None, ""):
            return as_money(value)
    for key in ("currentCompensation", "current_compensation", "compensation"):
        nested = record.get(key)
        if isinstance(nested, Mapping):
            for field in SOURCE_GROSS_FIELDS:
                value = nested.get(field)
                if value not in (None, ""):
                    return as_money(value)
    return None
