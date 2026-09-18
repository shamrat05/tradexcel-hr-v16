import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pytest

from tradex_hr.tradexcel_hr.payroll_rules import (
    calculate_attendance_pay,
    calculate_daily_worker_wage,
    calculate_dated_worker_pay,
    calculate_overtime_hours,
    calculate_wage,
    employee_joins_after_period,
    source_gross,
    validate_components,
)


def test_default_components_reconcile_exactly_to_gross():
    result = calculate_wage("18000")

    assert result["gross"] == Decimal("18000.00")
    assert sum(row["amount"] for row in result["earnings"]) == result["gross"]
    assert result["net"] == result["gross"]


def test_zero_wage_is_a_valid_boundary_and_stays_zero():
    result = calculate_wage(0)

    assert all(row["amount"] == 0 for row in result["earnings"])


def test_component_percentages_must_reconcile():
    with pytest.raises(ValueError):
        validate_components({"Basic Salary": 60, "Allowance": 30})


def test_source_salary_is_not_fabricated_when_missing():
    assert source_gross({"employeeId": "e1"}) is None


def test_payroll_excludes_employee_who_joined_after_period_end():
    assert employee_joins_after_period("2026-09-01", "2026-08-31") is True
    assert employee_joins_after_period("2026-08-31", "2026-08-31") is False
    assert employee_joins_after_period(None, "2026-08-31") is False


def test_nested_source_salary_is_supported():
    assert source_gross({"salary": {"monthlySalary": "12500"}}) == Decimal("12500.00")


def test_overtime_grace_rounds_50_minutes_to_one_hour_but_not_49():
    assert calculate_overtime_hours(8 + 49 / 60) == Decimal("0.00")
    assert calculate_overtime_hours(8 + 50 / 60) == Decimal("1.00")


def test_overtime_rounding_is_monotonic_and_capped():
    one_hour = calculate_overtime_hours(8 + 50 / 60)
    two_hours = calculate_overtime_hours(8 + 110 / 60)

    assert two_hours >= one_hour
    assert two_hours == Decimal("2.00")
    assert calculate_overtime_hours(11, max_daily_hours=2) == Decimal("2.00")


def test_daily_worker_overtime_rate_is_configurable_at_one_or_two_times():
    assert calculate_daily_worker_wage(1, 350, 1, 8, 1)["overtime"] == Decimal("43.75")
    assert calculate_daily_worker_wage(1, 350, 1, 8, 2)["overtime"] == Decimal("87.50")
    assert calculate_daily_worker_wage(10, 350, 2, 8, 2)["gross"] == Decimal("3675.00")


def test_attendance_pay_deduplicates_a_day_and_applies_zero_break_policy():
    records = [
        {
            "date": "2026-08-17",
            "isPayable": True,
            "checkInTime": "2026-08-17T00:00:00Z",
            "checkOutTime": "2026-08-17T08:49:00Z",
        },
        {
            "date": "2026-08-17",
            "isPayable": True,
            "checkInTime": "2026-08-17T00:00:00Z",
            "checkOutTime": "2026-08-17T09:00:00Z",
        },
        {
            "date": "2026-08-18",
            "isPayable": False,
            "checkInTime": "2026-08-18T00:00:00Z",
            "checkOutTime": "2026-08-18T09:00:00Z",
        },
    ]

    result = calculate_attendance_pay(records, break_minutes=0)

    assert result["paid_days"] == 1
    assert result["worked_hours"] == Decimal("9.00")
    assert result["overtime_hours"] == Decimal("1.00")


def test_attendance_pay_break_can_remove_an_apparent_overtime_hour():
    record = {
        "date": "2026-08-17",
        "isPayable": True,
        "checkInTime": "2026-08-17T00:00:00Z",
        "checkOutTime": "2026-08-17T09:00:00Z",
    }

    assert calculate_attendance_pay([record], break_minutes=0)["overtime_hours"] == Decimal("1.00")
    assert calculate_attendance_pay([record], break_minutes=60)["overtime_hours"] == Decimal("0.00")


def test_worker_pay_applies_midmonth_rate_and_break_on_each_day():
    records = [
        {"date": day, "isPayable": True, "checkInTime": f"{day}T08:00:00",
         "checkOutTime": f"{day}T17:00:00"}
        for day in ("2026-09-16", "2026-09-17")
    ]
    policies = {
        "2026-09-16": {"daily_wage": 350, "break_minutes": 0},
        "2026-09-17": {"daily_wage": 400, "break_minutes": 60},
    }
    def policy_for_day(day):
        return {"standard_hours_per_day": 8, "overtime_after_hours": 8,
                "overtime_grace_minutes": 10, "overtime_rounding_minutes": 60,
                "max_daily_overtime_hours": 2, "overtime_enabled": 1,
                "overtime_multiplier": 2, **policies[day]}

    result = calculate_dated_worker_pay(records, policy_for_day)
    assert result["paid_days"] == 2
    assert result["regular"] == Decimal("750.00")
    assert result["overtime"] == Decimal("87.50")
    assert result["gross"] == Decimal("837.50")
    assert result["worked_hours"] == Decimal("17.00")
