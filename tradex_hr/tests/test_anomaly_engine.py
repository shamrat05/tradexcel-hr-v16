from datetime import date, datetime

import pytest

from tradex_hr.tradexcel_hr.anomaly_checks import (
    check_duplicate_slips,
    check_leave_balance_negative,
    check_present_without_punch,
    check_slip_arithmetic,
    pair_punches,
    run_all,
    validate_finding,
)
from tradex_hr.tradexcel_hr.statistics import cohort_findings, trend_outliers


def observation(key, cohort, value, **extra):
    return {"key": key, "cohort": cohort, "value": value, **extra}


def slip(name="S1", **overrides):
    base = {
        "name": name,
        "employee": "E1",
        "employee_name": "One",
        "salary_structure": "Staff Structure",
        "start_date": date(2026, 9, 1),
        "end_date": date(2026, 9, 30),
        "gross_pay": 100,
        "net_pay": 95,
        "total_deduction": 5,
        "payment_days": 30,
    }
    base.update(overrides)
    return base


def test_cohort_findings_skip_small_groups():
    rows = [observation(f"E{i}", "dept", 100) for i in range(3)]
    rows.append(observation("E9", "dept", 900))
    assert cohort_findings(rows, 3.5, 5) == []


def test_cohort_findings_flag_zero_spread_deviation():
    rows = [observation(f"E{i}", "dept", 100) for i in range(9)]
    rows.append(observation("E9", "dept", 400))
    hits = cohort_findings(rows, 3.5, 5)
    assert [hit["row"]["key"] for hit in hits] == ["E9"]
    assert hits[0]["z"] is None


def test_cohort_findings_flag_robust_z_outlier():
    rows = [observation(f"E{i}", "dept", 100 + i) for i in range(20)]
    rows.append(observation("OUT", "dept", 200))
    hits = cohort_findings(rows, 3.5, 5)
    assert [hit["row"]["key"] for hit in hits] == ["OUT"]
    assert hits[0]["z"] > 3.5


def test_trend_outliers_need_previous_activity():
    rows = [{"key": f"E{i}", "cohort": "dept", "current": 20 + i, "previous": 20} for i in range(10)]
    rows.append({"key": "DROP", "cohort": "dept", "current": 2, "previous": 40})
    rows.append({"key": "LOWBASE", "cohort": "dept", "current": 0, "previous": 2})
    hits = trend_outliers(rows, 3.5, 5, 5)
    keys = [hit["row"]["key"] for hit in hits]
    assert "DROP" in keys
    assert "LOWBASE" not in keys


def test_pair_punches_handles_midnight_and_problems():
    events = [
        (datetime(2026, 9, 1, 22, 0), "IN"),
        (datetime(2026, 9, 2, 6, 0), "OUT"),
        (datetime(2026, 9, 3, 8, 0), "OUT"),
        (datetime(2026, 9, 4, 8, 0), "IN"),
        (datetime(2026, 9, 4, 9, 0), "IN"),
    ]
    pairs, issues = pair_punches(events)
    assert len(pairs) == 1
    assert (pairs[0][1] - pairs[0][0]).total_seconds() == 8 * 3600
    assert issues == {"extra_ins": 1, "orphan_outs": 1, "unclosed": 1}


def test_run_all_is_empty_and_safe_without_data():
    assert run_all({}) == []


def test_slip_arithmetic_and_duplicates_are_detected():
    broken = slip(gross_pay=100, net_pay=90)
    arithmetic = check_slip_arithmetic({
        "slips": [broken],
        "earning_totals": {"S1": 95},
        "deduction_totals": {"S1": 5},
    })
    assert len(arithmetic) == 1
    assert arithmetic[0]["severity"] == "High"
    assert len(check_duplicate_slips({"slips": [broken, slip(name="S2")]})) == 1
    assert check_duplicate_slips({"slips": [slip()]}) == []


def test_leave_balance_negative_is_detected():
    findings = check_leave_balance_negative({"leave_balances": [
        {"employee": "E1", "employee_name": "One", "leave_type": "Casual", "allocated": 10, "used": 12},
        {"employee": "E2", "employee_name": "Two", "leave_type": "Casual", "allocated": 10, "used": 4},
    ]})
    assert [finding["employee"] for finding in findings] == ["E1"]


def test_present_without_punch_counts_uncovered_days():
    context = {
        "attendance_rows": [
            {"employee": "E1", "employee_name": "One", "attendance_date": "2026-09-01", "status": "Present"},
            {"employee": "E1", "employee_name": "One", "attendance_date": "2026-09-02", "status": "Present"},
            {"employee": "E1", "employee_name": "One", "attendance_date": "2026-09-03", "status": "Present"},
            {"employee": "E2", "employee_name": "Two", "attendance_date": "2026-09-01", "status": "On Leave"},
        ],
        "paired_days": {"E1": {"2026-09-01"}},
        "leave_cover": {"E1|2026-09-03"},
    }
    findings = check_present_without_punch(context)
    assert len(findings) == 1
    assert findings[0]["observed"] == "1 day(s)"


def test_every_check_emits_full_schema():
    context = {
        "slips": [slip(gross_pay=0, net_pay=0, payment_days=0, salary_structure="Wage X")],
        "earning_totals": {"S1": 500},
        "deduction_totals": {"S1": 0},
        "slip_punch_any": {"S1": 5},
        "slip_paired_days": {"S1": 3},
        "wage_structures": {"Wage X"},
    }
    findings = run_all(context)
    assert findings
    for finding in findings:
        validate_finding(finding)


def test_validate_finding_rejects_incomplete_rows():
    with pytest.raises(ValueError):
        validate_finding({"category": "Payroll"})
