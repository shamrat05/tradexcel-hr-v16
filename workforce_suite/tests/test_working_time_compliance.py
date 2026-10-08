from datetime import date, timedelta

import pytest

from workforce_suite.workforce_suite.working_time_compliance import (
	evaluate_attendance_compliance,
	evaluate_festival_holiday_calendar,
	evaluate_weekly_rest_calendar,
	evaluate_rolling_weekly_average,
	evaluate_leave_configuration,
	evaluate_overtime_configuration,
)
from workforce_suite.workforce_suite import working_time_compliance as working_time


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


def test_half_day_and_work_from_home_hours_count_for_statutory_hours():
	for status, hours in (("Half Day", 6), ("Work From Home", 8)):
		row = _attendance(date(2026, 9, 7), hours, status=status)
		findings = evaluate_attendance_compliance(_rule(), [row], date(2026, 9, 7), date(2026, 9, 7))
		assert "WORKING_TIME_ATTENDANCE_STATUS_CONFLICT" not in _codes(findings)
		assert "DAILY_HOUR_LIMIT_EXCEEDED" not in _codes(findings)


def test_absent_or_leave_with_positive_working_hours_is_a_conflict():
	for status in ("Absent", "On Leave"):
		findings = evaluate_attendance_compliance(
			_rule(), [_attendance(date(2026, 9, 7), 5, status=status)], date(2026, 9, 7), date(2026, 9, 7)
		)
		assert "WORKING_TIME_ATTENDANCE_STATUS_CONFLICT" in _codes(findings)


def test_daily_overtime_duration_must_cover_statutory_excess():
	day = date(2026, 9, 7)
	adequate = evaluate_attendance_compliance(_rule(), [_attendance(day, 10, 2)], day, day)
	insufficient = evaluate_attendance_compliance(_rule(), [_attendance(day, 10, 0.5)], day, day)
	assert "OVERTIME_DURATION_INCOMPLETE" not in _codes(adequate)
	assert "OVERTIME_DURATION_INCOMPLETE" in _codes(insufficient)


def test_weekly_overtime_duration_must_cover_weekly_excess():
	start, end = date(2026, 9, 7), date(2026, 9, 13)
	adequate = [_attendance(start.fromordinal(start.toordinal() + offset), 8) for offset in range(7)]
	adequate[0]["actual_overtime_duration"] = 8
	adequate[0]["overtime_type"] = "Synthetic OT"
	insufficient = [dict(row) for row in adequate]
	insufficient[0]["actual_overtime_duration"] = 0.5
	assert "OVERTIME_DURATION_INCOMPLETE" not in _codes(
		evaluate_attendance_compliance(_rule(), adequate, start, end)
	)
	assert "OVERTIME_DURATION_INCOMPLETE" in _codes(
		evaluate_attendance_compliance(_rule(), insufficient, start, end)
	)


def test_native_holidays_account_for_non_attendance_dates_in_complete_weeks():
	start, end = date(2026, 9, 7), date(2026, 9, 13)
	rows = [_attendance(start.fromordinal(start.toordinal() + offset), 8) for offset in range(6)]
	assert "WORKING_TIME_EVIDENCE_REQUIRED" not in _codes(
		evaluate_attendance_compliance(_rule(), rows, start, end, {date(2026, 9, 13)})
	)
	assert "WORKING_TIME_EVIDENCE_REQUIRED" not in _codes(
		evaluate_attendance_compliance(_rule(), rows[:5], start, end, {date(2026, 9, 12), date(2026, 9, 13)})
	)
	assert "WORKING_TIME_EVIDENCE_REQUIRED" in _codes(
		evaluate_attendance_compliance(_rule(), rows[:5], start, end, {date(2026, 9, 12)})
	)


def test_rolling_average_uses_holidays_and_previous_calendar_year():
	start = date(2026, 9, 7)
	last_week = date(2026, 8, 31)
	first_week = last_week.fromordinal(last_week.toordinal() - 357)
	holiday = date(2025, 9, 14)
	rows = [
		_attendance(first_week.fromordinal(first_week.toordinal() + offset), 8)
		for offset in range(364)
		if first_week.fromordinal(first_week.toordinal() + offset) != holiday
	]
	findings = evaluate_rolling_weekly_average(
		{"week_start_day": "Monday", "weekly_average_max_hours": 55}, rows, start, {holiday}
	)
	assert "WEEKLY_AVERAGE_HISTORY_INSUFFICIENT" not in _codes(findings)
	assert "WEEKLY_AVERAGE_LIMIT_EXCEEDED" in _codes(findings)


def test_holiday_loader_covers_rolling_window_before_calendar_year(monkeypatch):
	from frappe import _dict

	queried = {}
	db = _dict(get_value=lambda *args, **kwargs: "SYN-HOLIDAYS")
	def get_all(doctype, filters=None, **kwargs):
		if doctype == "Holiday":
			queried.update(filters)
			return []
		return [_dict(name="SYN-HOLIDAYS", holiday_list=None)]
	monkeypatch.setattr(working_time, "frappe", _dict(db=db, get_all=get_all))
	working_time._holiday_category_by_list(
		"SYN-COMPANY", [_dict(name="SYN-EMP", holiday_list=None)], [],
		date(2026, 9, 1), date(2026, 9, 30), date(2025, 9, 7), date(2026, 10, 4),
	)
	assert queried["holiday_date"] == ["between", [date(2025, 9, 7), date(2026, 12, 31) + timedelta(days=7)]]


def _leave_rule():
	from frappe import _dict

	return _dict(
		name="SYN-WT-RULE", company="SYN-COMPANY", casual_leave_type="SYN-CASUAL",
		casual_days_per_year=10, casual_carry_forward=0, sick_leave_type=None,
		annual_leave_type=None,
	)


def test_direct_leave_allocation_without_policy_assignment_is_accepted(monkeypatch):
	from frappe import _dict

	def get_all(doctype, filters=None, **kwargs):
		if doctype == "Leave Allocation":
			return [_dict(
				employee="SYN-EMP", leave_type="SYN-CASUAL", from_date=date(2026, 1, 1),
				to_date=date(2026, 12, 31), new_leaves_allocated=10,
				total_leaves_allocated=10, carry_forward=0,
			)]
		return []

	monkeypatch.setattr(working_time.frappe, "get_all", get_all)
	assert working_time._leave_policy_findings(
		["SYN-EMP"], [_leave_rule()], date(2026, 9, 1), date(2026, 9, 30)
	).get("SYN-EMP", []) == []


def test_direct_leave_allocation_amount_and_period_are_checked(monkeypatch):
	from frappe import _dict

	rows = [_dict(
		employee="SYN-EMP", leave_type="SYN-CASUAL", from_date=date(2026, 1, 1),
		to_date=date(2026, 12, 31), new_leaves_allocated=8,
		total_leaves_allocated=8, carry_forward=0,
	)]
	monkeypatch.setattr(working_time.frappe, "get_all", lambda doctype, **kwargs: rows if doctype == "Leave Allocation" else [])
	findings = working_time._leave_policy_findings(
		["SYN-EMP"], [_leave_rule()], date(2026, 9, 1), date(2026, 9, 30)
	)
	assert "LEAVE_ALLOCATION_MISMATCH" in _codes(findings["SYN-EMP"])
	rows[0].to_date = date(2026, 8, 31)
	findings = working_time._leave_policy_findings(
		["SYN-EMP"], [_leave_rule()], date(2026, 9, 1), date(2026, 9, 30)
	)
	assert "LEAVE_ALLOCATION_REVIEW_REQUIRED" in _codes(findings["SYN-EMP"])


def test_leave_policy_assignment_path_still_covers_required_type(monkeypatch):
	from frappe import _dict

	def get_all(doctype, filters=None, **kwargs):
		if doctype == "Leave Policy Assignment":
			return [_dict(employee="SYN-EMP", leave_policy="SYN-POLICY", effective_from=date(2026, 1, 1), effective_to=date(2026, 12, 31), carry_forward=0)]
		if doctype == "Leave Policy Detail":
			return [_dict(parent="SYN-POLICY", leave_type="SYN-CASUAL", annual_allocation=10)]
		return []

	monkeypatch.setattr(working_time.frappe, "get_all", get_all)
	assert working_time._leave_policy_findings(
		["SYN-EMP"], [_leave_rule()], date(2026, 9, 1), date(2026, 9, 30)
	).get("SYN-EMP", []) == []


def _patch_overtime_salary_validation(monkeypatch, expected_amounts=None, duplicate=False):
	from frappe import _dict

	db = _dict(
		get_value=lambda *args, **kwargs: _dict(
			docstatus=1, employee="SYN-EMP", company="SYN-COMPANY", end_date=date(2026, 9, 30)
		),
		get_single_value=lambda *args, **kwargs: 2,
		exists=lambda *args, **kwargs: duplicate,
	)
	def throw(message, exception):
		raise exception(message)
	monkeypatch.setattr(working_time, "frappe", _dict(
		session=_dict(user="synthetic-approver"),
		get_roles=lambda *args, **kwargs: ["Workforce Payroll Approver"],
		db=db,
		get_doc=lambda *args, **kwargs: _dict(
			get_overtime_component_amounts=lambda: expected_amounts or {"Synthetic OT": 125.5}
		),
		throw=throw,
		PermissionError=working_time.frappe.PermissionError,
	))
	monkeypatch.setattr(working_time, "flt", lambda value, precision=None: round(float(value or 0), precision) if precision is not None else float(value or 0))
	monkeypatch.setattr(working_time, "assert_company_access", lambda *args, **kwargs: None)


def test_native_overtime_additional_salary_amount_and_component_are_verified(monkeypatch):
	from frappe import _dict

	_patch_overtime_salary_validation(monkeypatch)
	doc = _dict(
		ref_doctype="Overtime Slip", ref_docname="SYN-OT", employee="SYN-EMP",
		company="SYN-COMPANY", payroll_date=date(2026, 9, 30), salary_component="Synthetic OT", amount=125.5,
	)
	working_time.validate_overtime_generated_additional_salary(doc)
	doc.amount = 999
	with pytest.raises(working_time.frappe.PermissionError):
		working_time.validate_overtime_generated_additional_salary(doc)
	doc.amount, doc.salary_component = 125.5, "Wrong Component"
	with pytest.raises(working_time.frappe.PermissionError):
		working_time.validate_overtime_generated_additional_salary(doc)


def test_duplicate_overtime_additional_salary_is_denied(monkeypatch):
	from frappe import _dict

	_patch_overtime_salary_validation(monkeypatch, duplicate=True)
	doc = _dict(
		ref_doctype="Overtime Slip", ref_docname="SYN-OT", employee="SYN-EMP",
		company="SYN-COMPANY", payroll_date=date(2026, 9, 30), salary_component="Synthetic OT", amount=125.5,
	)
	with pytest.raises(working_time.frappe.PermissionError):
		working_time.validate_overtime_generated_additional_salary(doc)
