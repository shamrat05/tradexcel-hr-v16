import sys
from decimal import Decimal
from pathlib import Path
import inspect

sys.path.insert(0, str(Path(__file__).parent))

from workforce_suite.workforce_suite.payroll_rules import (
    calculate_attendance_pay,
    calculate_daily_worker_wage,
    calculate_overtime_hours,
    employee_joins_after_period,
    source_gross,
)


def test_generic_payroll_runtime_has_no_implicit_salary_split():
    from workforce_suite.workforce_suite import native_payroll, payroll_rules

    source = inspect.getsource(payroll_rules)
    assert "DEFAULT_COMPONENTS" not in source
    assert "def calculate_wage(" not in source
    assert "def calculate_dated_worker_pay(" not in source
    assert '"daily_wage"' not in source
    assert not hasattr(payroll_rules, "calculate_wage")
    assert not hasattr(payroll_rules, "calculate_dated_worker_pay")
    assert "payroll_rules" not in inspect.getsource(native_payroll)


def test_source_salary_is_not_fabricated_when_missing():
    assert source_gross({"employeeId": "e1"}) is None


def test_payroll_excludes_employee_who_joined_after_period_end():
    assert employee_joins_after_period("2026-09-01", "2026-08-31") is True
    assert employee_joins_after_period("2026-08-31", "2026-08-31") is False
    assert employee_joins_after_period(None, "2026-08-31") is False


def test_nested_source_salary_is_supported():
    assert source_gross({"salary": {"monthlySalary": "12500"}}) == Decimal("12500.00")


def test_overtime_grace_rounds_50_minutes_to_one_hour_but_not_49():
    policy = dict(standard_hours=8, grace_minutes=10, rounding_minutes=60, max_daily_hours=2)
    assert calculate_overtime_hours(8 + 49 / 60, **policy) == Decimal("0.00")
    assert calculate_overtime_hours(8 + 50 / 60, **policy) == Decimal("1.00")


def test_overtime_rounding_is_monotonic_and_capped():
    policy = dict(standard_hours=8, grace_minutes=10, rounding_minutes=60, max_daily_hours=2)
    one_hour = calculate_overtime_hours(8 + 50 / 60, **policy)
    two_hours = calculate_overtime_hours(8 + 110 / 60, **policy)

    assert two_hours >= one_hour
    assert two_hours == Decimal("2.00")
    assert calculate_overtime_hours(11, **policy) == Decimal("2.00")


def test_daily_worker_overtime_rate_is_configurable_at_one_or_two_times():
    assert calculate_daily_worker_wage(1, 350, 1, hours_per_day=8, overtime_multiplier=1)["overtime"] == Decimal("43.75")
    assert calculate_daily_worker_wage(1, 350, 1, hours_per_day=8, overtime_multiplier=2)["overtime"] == Decimal("87.50")
    assert calculate_daily_worker_wage(10, 350, 2, hours_per_day=8, overtime_multiplier=2)["gross"] == Decimal("3675.00")


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

    result = calculate_attendance_pay(
        records, standard_hours=8, break_minutes=0, grace_minutes=10,
        rounding_minutes=60, max_daily_overtime_hours=2,
    )

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

    policy = dict(standard_hours=8, grace_minutes=10, rounding_minutes=60, max_daily_overtime_hours=2)
    assert calculate_attendance_pay([record], break_minutes=0, **policy)["overtime_hours"] == Decimal("1.00")
    assert calculate_attendance_pay([record], break_minutes=60, **policy)["overtime_hours"] == Decimal("0.00")


def test_daily_rate_math_accepts_only_explicit_inputs():
    result = calculate_daily_worker_wage(
        paid_days=10,
        daily_rate=425,
        overtime_hours=0,
        hours_per_day=9,
        overtime_multiplier=1,
    )
    assert result["regular"] == Decimal("4250.00")
