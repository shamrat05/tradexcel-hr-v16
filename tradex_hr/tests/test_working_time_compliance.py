from datetime import date

from tradex_hr.tradexcel_hr.working_time_compliance import (
	evaluate_attendance_compliance,
	evaluate_festival_holiday_calendar,
	evaluate_weekly_rest_calendar,
	evaluate_rolling_weekly_average,
	evaluate_leave_configuration,
	evaluate_overtime_configuration,
)


def _rule(**overrides):
	return {
		"daily_standard_hours": 8,
		"daily_max_hours": 10,
		"weekly_standard_hours": 48,
		"weekly_max_hours": 60,
		"week_start_day": "Monday",
		"spread_over_hours": 10,
		"break_requirements": [],
		**overrides,
	}


def _attendance(day, hours, overtime=0, **overrides):
	return {
		"name": f"ATT-{day}",
		"attendance_date": day,
		"status": "Present",
		"working_hours": hours,
		"actual_overtime_duration": overtime,
		"overtime_type": "Synthetic OT" if overtime else None,
		**overrides,
	}


def _codes(findings):
	return {finding["code"] for finding in findings}


def test_daily_limit_blocks_and_does_not_recalculate_attendance():
	row = _attendance(date(2026, 9, 7), 11, 3)
	findings = evaluate_attendance_compliance(_rule(), [row], date(2026, 9, 1), date(2026, 9, 30))
	assert "DAILY_HOUR_LIMIT_EXCEEDED" in _codes(findings)
	assert row["working_hours"] == 11


def test_missing_native_overtime_evidence_blocks_approval():
	findings = evaluate_attendance_compliance(
		_rule(), [_attendance(date(2026, 9, 7), 9)], date(2026, 9, 1), date(2026, 9, 30)
	)
	assert "OVERTIME_REQUIRED" in _codes(findings)
	assert next(item for item in findings if item["code"] == "OVERTIME_REQUIRED")["severity"] == "block"


def test_weekly_maximum_uses_attendance_and_approved_week_start():
	rows = [_attendance(date(2026, 9, day), 9, 1) for day in range(7, 14)]
	findings = evaluate_attendance_compliance(
		_rule(weekly_max_hours=60), rows, date(2026, 9, 7), date(2026, 9, 13)
	)
	assert "WEEKLY_HOUR_LIMIT_EXCEEDED" in _codes(findings)



def test_partial_week_still_blocks_known_weekly_maximum_breach():
	rows = [_attendance(date(2026, 9, day), 10, 2) for day in range(7, 13)]
	findings = evaluate_attendance_compliance(
		_rule(weekly_max_hours=56), rows, date(2026, 9, 7), date(2026, 9, 13)
	)
	assert "WEEKLY_HOUR_LIMIT_EXCEEDED" in _codes(findings)
	assert "WORKING_TIME_EVIDENCE_REQUIRED" in _codes(findings)


def test_missing_break_and_spread_evidence_are_review_findings():
	rule = _rule(break_requirements=[{"minimum_work_duration": 6, "required_break_minutes": 30}])
	findings = evaluate_attendance_compliance(
		rule, [_attendance(date(2026, 9, 7), 8)], date(2026, 9, 7), date(2026, 9, 7)
	)
	assert {"BREAK_EVIDENCE_REVIEW_REQUIRED", "SPREAD_OVER_EVIDENCE_REQUIRED"} <= _codes(findings)


def test_leave_settings_compare_native_leave_type_without_allocating_leave():
	requirements = [{"leave_category": "Casual", "leave_type": "Casual Leave", "annual_entitlement_days": 10, "paid": 1, "carry_forward": 0}]
	configured = {"Casual Leave": {"max_leaves_allowed": 10, "is_lwp": 0, "is_carry_forward": 0}}
	assert evaluate_leave_configuration(requirements, configured) == []
	configured["Casual Leave"]["is_carry_forward"] = 1
	assert "CASUAL_LEAVE_CONFIGURATION_MISMATCH" in _codes(evaluate_leave_configuration(requirements, configured))


def test_native_overtime_multiplier_and_wage_basis_must_match_rule():
	rule = {"overtime_multiplier": 2, "overtime_components": [{"salary_component": "Basic"}]}
	native = {"standard_multiplier": 1.5, "overtime_calculation_method": "Salary Component Based", "applicable_salary_component": [{"salary_component": "Gross"}]}
	findings = evaluate_overtime_configuration(rule, native)
	assert {"OVERTIME_RATE_CONFIGURATION_MISMATCH", "OVERTIME_WAGE_BASIS_MISMATCH"} <= _codes(findings)


def test_fixed_hourly_native_overtime_needs_explicit_legal_review():
	rule = {"overtime_multiplier": 2, "overtime_components": []}
	native = {"standard_multiplier": 2, "overtime_calculation_method": "Fixed Hourly Rate", "applicable_salary_component": []}
	findings = evaluate_overtime_configuration(rule, native)
	assert "FIXED_OT_RATE_LEGAL_REVIEW_REQUIRED" in _codes(findings)
	assert next(item for item in findings if item["code"] == "FIXED_OT_RATE_LEGAL_REVIEW_REQUIRED")["severity"] == "block"


def test_weekly_standard_hours_require_native_overtime_evidence():
	rows = [_attendance(date(2026, 9, day), 7) for day in range(7, 14)]
	findings = evaluate_attendance_compliance(
		_rule(weekly_standard_hours=48), rows, date(2026, 9, 7), date(2026, 9, 13)
	)
	assert "OVERTIME_REQUIRED" in _codes(findings)
	assert next(item for item in findings if item["code"] == "OVERTIME_REQUIRED")["severity"] == "block"


def test_weekly_standard_hours_with_native_overtime_evidence_are_reviewable():
	rows = [_attendance(date(2026, 9, day), 7, 1) for day in range(7, 14)]
	findings = evaluate_attendance_compliance(
		_rule(weekly_standard_hours=48), rows, date(2026, 9, 7), date(2026, 9, 13)
	)
	assert "OVERTIME_REQUIRED" not in _codes(findings)


def test_weekly_rest_and_festival_work_require_separate_compensation_review():
	rows = [
		_attendance(date(2026, 9, 7), 8, holiday_category="Weekly Rest"),
		_attendance(date(2026, 9, 8), 8, holiday_category="Festival Holiday"),
	]
	findings = evaluate_attendance_compliance(
		_rule(), rows, date(2026, 9, 7), date(2026, 9, 13)
	)
	assert {"COMPENSATORY_REST_REQUIRED", "FESTIVAL_HOLIDAY_COMPENSATION_REVIEW_REQUIRED"} <= _codes(findings)


def test_overtime_weekend_and_festival_multipliers_must_match():
	rule = {"overtime_multiplier": 2, "weekend_multiplier": 2, "festival_multiplier": 2, "overtime_components": [{"salary_component": "Basic"}]}
	native = {
		"standard_multiplier": 2, "weekend_multiplier": 1.5, "public_holiday_multiplier": 1.5,
		"overtime_calculation_method": "Salary Component Based",
		"applicable_salary_component": [{"salary_component": "Basic"}],
	}
	assert {"OVERTIME_RATE_CONFIGURATION_MISMATCH"} <= _codes(evaluate_overtime_configuration(rule, native))


def test_festival_holiday_count_uses_explicit_native_calendar_classification():
	from datetime import date

	categorized = [
		(date(2026, 1, 1), {"Festival Holiday"}),
		(date(2026, 1, 2), {"Weekly Rest"}),
	]
	assert evaluate_festival_holiday_calendar(1, categorized, 2026) == []
	assert "FESTIVAL_HOLIDAY_CONFIGURATION_MISMATCH" in _codes(
		evaluate_festival_holiday_calendar(2, categorized, 2026)
	)


def test_weekly_rest_calendar_uses_native_weekly_off_categories():
	start, end = date(2026, 9, 7), date(2026, 9, 20)
	categorized = [
		(date(2026, 9, 11), {"Weekly Rest"}),
		(date(2026, 9, 18), {"Weekly Rest"}),
	]
	assert evaluate_weekly_rest_calendar(1, categorized, start, end, "Monday") == []
	assert "WEEKLY_REST_CONFIGURATION_MISMATCH" in _codes(
		evaluate_weekly_rest_calendar(1, categorized[:1], start, end, "Monday")
	)
	assert "WEEKLY_REST_CONFIGURATION_REVIEW_REQUIRED" in _codes(
		evaluate_weekly_rest_calendar(1.5, categorized, start, end, "Monday")
	)


def test_rolling_average_requires_full_history_then_checks_52_weeks():
	start = date(2026, 9, 7)
	window_start = date(2025, 9, 8)
	rows = [
		_attendance(window_start.fromordinal(window_start.toordinal() + offset), 8)
		for offset in range(364)
	]
	findings = evaluate_rolling_weekly_average(
		{"week_start_day": "Monday", "weekly_average_max_hours": 55}, rows, start
	)
	assert "WEEKLY_AVERAGE_LIMIT_EXCEEDED" in _codes(findings)
	assert "WEEKLY_AVERAGE_HISTORY_INSUFFICIENT" in _codes(
		evaluate_rolling_weekly_average(
			{"week_start_day": "Monday", "weekly_average_max_hours": 55}, rows[:30], start
		)
	)
