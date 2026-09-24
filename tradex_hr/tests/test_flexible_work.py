from datetime import date, datetime
from types import SimpleNamespace

from tradex_hr.tradexcel_hr.attendance_payroll_boundary import attendance_period_hash
from tradex_hr.tradexcel_hr.flexible_work_records import (
    _daily_wage_override_candidates,
    _holiday_payable_work_rows,
)
from tradex_hr.tradexcel_hr import flexible_work
from tradex_hr.tradexcel_hr.flexible_work import (
    apply_flexible_work_adjustments,
    apply_policy_to_daily_wage,
    calculate_flexible_work_units,
    detect_mass_early_release_candidates,
    flexible_policy_scope_state,
    shift_assignment_covers_period,
)


def test_flexible_daily_wage_units_are_capped_and_proportional():
    policy = {"standard_paid_hours": 8, "full_day_minimum_hours": 7}
    assert calculate_flexible_work_units(8, policy) == 1
    assert calculate_flexible_work_units(7, policy) == 1
    assert calculate_flexible_work_units(6, policy) == 0.75
    assert calculate_flexible_work_units(4, policy) == 0.5
    assert calculate_flexible_work_units(0, policy) == 0
    assert calculate_flexible_work_units(9, policy) == 1


def test_missing_hours_on_work_attendance_requires_review():
    result = apply_flexible_work_adjustments(
        1, [{"status": "Present", "attendance_date": date(2026, 9, 1), "working_hours": None}],
        {"standard_paid_hours": 8, "full_day_minimum_hours": 7},
    )
    assert result["status"] == "NEEDS_ATTENTION"
    assert result["findings"][0]["code"] == "FLEX_WORKING_HOURS_REQUIRED"


def test_flexible_adjustment_changes_only_work_days_without_leave():
    policy = {"standard_paid_hours": 8, "full_day_minimum_hours": 7}
    rows = [
        {"attendance_date": date(2026, 9, 1), "status": "Present", "working_hours": 6},
        {"attendance_date": date(2026, 9, 2), "status": "Half Day", "half_day_status": "Absent", "working_hours": 5.5},
        {"attendance_date": date(2026, 9, 3), "status": "Half Day", "half_day_status": "Absent", "working_hours": 4, "leave_application": "LAP-1", "leave_type": "Casual Leave"},
        {"attendance_date": date(2026, 9, 4), "status": "Absent", "working_hours": 0},
        {"attendance_date": date(2026, 9, 5), "status": "On Leave", "working_hours": 0, "leave_application": "LAP-2", "leave_type": "Casual Leave"},
    ]
    result = apply_flexible_work_adjustments(2.5, rows, policy, half_day_fraction=0.5)
    assert result == {"status": "READY", "payable_units": 2.4375, "findings": []}


def test_operational_override_only_upgrades_present_work_only_days():
    policy = {"standard_paid_hours": 8, "full_day_minimum_hours": 7}
    rows = [
        {"attendance_date": date(2026, 9, 1), "status": "Present", "working_hours": 6, "branch": "Factory"},
        {"attendance_date": date(2026, 9, 2), "status": "Absent", "working_hours": 0, "branch": "Factory"},
        {"attendance_date": date(2026, 9, 3), "status": "Present", "working_hours": 6, "leave_type": "Casual Leave", "leave_application": "LAP-1", "branch": "Factory"},
        {"attendance_date": date(2026, 9, 4), "status": "Present", "working_hours": 9, "branch": "Factory"},
        {"attendance_date": date(2026, 9, 5), "status": "Work From Home", "working_hours": 6, "branch": "Factory"},
    ]
    overrides = [{"attendance_date": date(2026, 9, 1), "branch": "Factory", "department": None}]
    result = apply_flexible_work_adjustments(
        4, rows, policy, overrides=overrides, employee={"branch": "Factory"}
    )
    assert result["status"] == "READY"
    assert result["payable_units"] == 3.75


def test_absent_or_on_leave_with_positive_hours_is_not_silently_ignored():
    result = apply_flexible_work_adjustments(
        0, [{"attendance_date": date(2026, 9, 1), "status": "Absent", "working_hours": 5}],
        {"standard_paid_hours": 8, "full_day_minimum_hours": 7},
    )
    assert result["status"] == "NEEDS_ATTENTION"
    assert result["findings"][0]["code"] == "FLEX_ATTENDANCE_STATUS_CONFLICT"


def test_working_hours_are_part_of_finalized_attendance_fingerprint():
    before = attendance_period_hash([{"employee": "EMP-1", "attendance_date": "2026-09-01", "status": "Present", "working_hours": 6, "remarks": "old"}])
    changed_hours = attendance_period_hash([{"employee": "EMP-1", "attendance_date": "2026-09-01", "status": "Present", "working_hours": 7, "remarks": "old"}])
    changed_note = attendance_period_hash([{"employee": "EMP-1", "attendance_date": "2026-09-01", "status": "Present", "working_hours": 6, "remarks": "new"}])
    assert before != changed_hours
    assert before == changed_note


def test_mass_early_release_detector_only_suggests_a_candidate():
    rows = [
        {"attendance_date": date(2026, 9, 18), "employee": f"EMP-{index:03}", "branch": "Factory", "department": "Production", "status": "Present", "working_hours": 6, "early_exit": int(index < 15), "out_time": datetime(2026, 9, 18, 18 if index < 15 else 20, 0)}
        for index in range(18)
    ]
    result = detect_mass_early_release_candidates(rows, minimum_headcount=10, minimum_percentage=0.75, clustering_window_minutes=30)
    assert len(result) == 1
    assert result[0]["code"] == "MASS_EARLY_RELEASE_CANDIDATE"
    assert result[0]["affected_count"] == 15
    assert result[0]["present_count"] == 18
    assert result[0]["affected_ratio"] == 15 / 18
    assert result[0]["suggested_release_time"] == "18:00"
    assert result[0]["creates_override"] is False


def test_policy_for_an_unrelated_branch_does_not_block_employee():
    policy = {"branch": "Factory B", "department": None}
    assert flexible_policy_scope_state(policy, {("Factory A", "Production")}) == "outside"
    assert flexible_policy_scope_state(policy, {("Factory B", "Production")}) == "all"
    assert flexible_policy_scope_state(
        policy, {("Factory A", "Production"), ("Factory B", "Production")}
    ) == "partial"


def test_flexible_shift_assignment_must_cover_the_requested_period():
    assignment = {"start_date": date(2026, 9, 1), "end_date": date(2026, 9, 30)}
    assert shift_assignment_covers_period(assignment, date(2026, 9, 1), date(2026, 9, 30))
    later_assignment = {"start_date": date(2026, 9, 2), "end_date": date(2026, 9, 30)}
    assert not shift_assignment_covers_period(later_assignment, date(2026, 9, 1), date(2026, 9, 30))


def test_operational_override_preview_respects_native_holiday_payroll_setting():
    rows = [
        {"employee": "EMP-1", "status": "Present"},
        {"employee": "EMP-2", "status": "Present"},
    ]
    assert _holiday_payable_work_rows(rows, {"EMP-1"}, False) == [rows[1]]
    assert _holiday_payable_work_rows(rows, {"EMP-1"}, True) == rows


def test_operational_override_readiness_ignores_configured_monthly_workers():
    rows = [
        {"employee": "DAILY", "status": "Present"},
        {"employee": "MONTHLY", "status": "Present"},
        {"employee": "UNASSIGNED", "status": "Present"},
    ]
    assignments = {
        "DAILY": {"pay_basis": "Daily Wage"},
        "MONTHLY": {"pay_basis": "Monthly Salary"},
        "UNASSIGNED": None,
    }
    assert _daily_wage_override_candidates(rows, assignments) == [rows[0], rows[2]]


def test_unrelated_branch_override_does_not_block_daily_wage_input(monkeypatch):
    employee = SimpleNamespace(company="TCL", branch="Factory B", department="Production")
    rows = [{
        "attendance_date": date(2026, 9, 18), "status": "Present", "working_hours": 6,
        "branch": "Factory B", "department": "Production",
    }]
    native = {"status": "READY", "payable_units": 1, "holidays": set(), "include_holidays": False}
    monkeypatch.setattr(flexible_work, "resolve_flexible_work_policy", lambda *_args: {"status": "READY", "policy": None})
    monkeypatch.setattr(flexible_work, "load_operational_overrides", lambda *_args: [{
        "attendance_date": date(2026, 9, 18), "branch": "Factory A", "department": "Production",
        "preview_stale": True,
    }])
    assert apply_policy_to_daily_wage("EMP-1", employee, date(2026, 9, 1), date(2026, 9, 30), rows, native) == native


def test_applicable_stale_override_blocks_daily_wage_input(monkeypatch):
    employee = SimpleNamespace(company="TCL", branch="Factory B", department="Production")
    rows = [{
        "attendance_date": date(2026, 9, 18), "status": "Present", "working_hours": 6,
        "branch": "Factory B", "department": "Production",
    }]
    native = {"status": "READY", "payable_units": 1, "holidays": set(), "include_holidays": False}
    monkeypatch.setattr(flexible_work, "resolve_flexible_work_policy", lambda *_args: {"status": "READY", "policy": None})
    monkeypatch.setattr(flexible_work, "load_operational_overrides", lambda *_args: [{
        "attendance_date": date(2026, 9, 18), "branch": "Factory B", "department": "Production",
        "preview_stale": True,
    }])
    result = apply_policy_to_daily_wage("EMP-1", employee, date(2026, 9, 1), date(2026, 9, 30), rows, native)
    assert result["status"] == "NEEDS_ATTENTION"
