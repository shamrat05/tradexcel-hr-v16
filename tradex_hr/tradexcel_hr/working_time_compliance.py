from collections import defaultdict
from datetime import date, datetime, timedelta

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from tradex_hr.tradexcel_hr.company_context import assert_company_access


def _finding(code, message, severity="block"):
	return {"code": code, "message": message, "severity": severity}


def _week_start(day, configured_start):
	weekdays = {name: number for number, name in enumerate(("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"))}
	return day - timedelta(days=(day.weekday() - weekdays.get(configured_start, 0)) % 7)


def _spread_hours(row):
	start, end = row.get("in_time"), row.get("out_time")
	if not start or not end:
		return None
	if not isinstance(start, datetime):
		start = datetime.fromisoformat(str(start))
	if not isinstance(end, datetime):
		end = datetime.fromisoformat(str(end))
	if end < start:
		end += timedelta(days=1)
	return (end - start).total_seconds() / 3600


def evaluate_attendance_compliance(rule, attendance_rows, from_date, to_date):
	"""Check approved Attendance values; never derive time or modify source rows."""
	start, end = getdate(from_date), getdate(to_date)
	first_week = _week_start(start, rule.get("week_start_day"))
	last_week = _week_start(end, rule.get("week_start_day"))
	findings, weekly_hours = [], defaultdict(float)
	for row in attendance_rows:
		day = getdate(row.get("attendance_date"))
		week = _week_start(day, rule.get("week_start_day"))
		if not first_week <= week <= last_week or row.get("status") != "Present":
			continue
		hours = row.get("working_hours")
		if hours is None:
			if start <= day <= end:
				findings.append(_finding("WORKING_TIME_EVIDENCE_REQUIRED", "Present Attendance has no approved working-hours value.", "review"))
			continue
		hours = flt(hours)
		weekly_hours[week] += hours
		if not start <= day <= end:
			continue
		if hours > flt(rule.get("daily_max_hours")):
			findings.append(_finding("DAILY_HOUR_LIMIT_EXCEEDED", f"Attendance on {day} exceeds the approved daily maximum."))
		if hours > flt(rule.get("daily_standard_hours")) and not (flt(row.get("actual_overtime_duration")) > 0 and row.get("overtime_type")):
			findings.append(_finding("OVERTIME_REQUIRED", f"Attendance on {day} exceeds normal hours without native overtime evidence."))
		for requirement in rule.get("break_requirements") or []:
			if hours >= flt(requirement.get("minimum_work_duration")):
				findings.append(_finding("BREAK_EVIDENCE_REVIEW_REQUIRED", f"Break evidence is not recorded for {day}.", "review"))
		spread = _spread_hours(row)
		if spread is None:
			findings.append(_finding("SPREAD_OVER_EVIDENCE_REQUIRED", f"Start and end evidence is incomplete for {day}.", "review"))
		elif rule.get("spread_over_hours") and spread > flt(rule["spread_over_hours"]):
			findings.append(_finding("SPREAD_OVER_LIMIT_EXCEEDED", f"Attendance on {day} exceeds the approved spread-over limit."))
	rows_by_week = defaultdict(list)
	for row in attendance_rows:
		day = getdate(row.get("attendance_date"))
		week = _week_start(day, rule.get("week_start_day"))
		if first_week <= week <= last_week:
			rows_by_week[week].append(row)
	for week, hours in weekly_hours.items():
		week_rows = rows_by_week[week]
		covered_dates = {getdate(row.get("attendance_date")) for row in week_rows}
		weekly_ot = sum(flt(row.get("actual_overtime_duration")) for row in week_rows)
		if hours > flt(rule.get("weekly_max_hours")):
			findings.append(_finding("WEEKLY_HOUR_LIMIT_EXCEEDED", f"Week beginning {week} exceeds the approved weekly maximum."))
		if hours > flt(rule.get("weekly_standard_hours")) and weekly_ot <= 0:
			findings.append(_finding("OVERTIME_REQUIRED", f"Week beginning {week} exceeds normal weekly hours without native overtime evidence."))
		if len(covered_dates) < 7:
			findings.append(_finding("WORKING_TIME_EVIDENCE_REQUIRED", f"Approved Attendance does not cover the full week beginning {week}.", "review"))
	for row in attendance_rows:
		day = getdate(row.get("attendance_date"))
		if not start <= day <= end or row.get("status") != "Present":
			continue
		categories = set(row.get("holiday_categories") or [])
		if row.get("holiday_category"):
			categories.add(row["holiday_category"])
		if "Weekly Rest" in categories:
			findings.append(_finding("COMPENSATORY_REST_REQUIRED", f"Work on the weekly rest date {day} needs reviewed compensatory-rest treatment."))
		if "Festival Holiday" in categories:
			findings.append(_finding("FESTIVAL_HOLIDAY_COMPENSATION_REVIEW_REQUIRED", f"Work on festival holiday {day} needs reviewed compensatory treatment."))
	return _unique_findings(findings)



def evaluate_rolling_weekly_average(rule, attendance_rows, period_start):
	"""Check 52 complete historical weeks; unknown history remains review-only."""
	if not rule.get("weekly_average_max_hours"):
		return []
	week_end = _week_start(getdate(period_start), rule.get("week_start_day")) - timedelta(days=1)
	window_start = week_end - timedelta(days=363)
	rows_by_week = defaultdict(list)
	for row in attendance_rows:
		day = getdate(row.get("attendance_date"))
		if window_start <= day <= week_end:
			rows_by_week[_week_start(day, rule.get("week_start_day"))].append(row)
	last_week = _week_start(week_end, rule.get("week_start_day"))
	weeks = [last_week - timedelta(days=7 * index) for index in reversed(range(52))]
	weekly_totals = []
	for week in weeks:
		rows = rows_by_week.get(week, [])
		if len({getdate(row.get("attendance_date")) for row in rows}) < 7 or any(
			row.get("status") == "Present" and row.get("working_hours") is None for row in rows
		):
			return [_finding("WEEKLY_AVERAGE_HISTORY_INSUFFICIENT", "A complete 52-week approved Attendance history is not available.", "review")]
		weekly_totals.append(sum(
			flt(row.get("working_hours"))
			for row in rows
			if row.get("status") == "Present" and row.get("working_hours") is not None
		))
	average = sum(weekly_totals) / len(weekly_totals)
	if average > flt(rule.get("weekly_average_max_hours")):
		return [_finding("WEEKLY_AVERAGE_LIMIT_EXCEEDED", "The rolling 52-week average exceeds the approved weekly average maximum.")]
	return []


def evaluate_leave_configuration(requirements, native_leave_types):
	findings = []
	for requirement in requirements or []:
		name = requirement.get("leave_type")
		leave_type = native_leave_types.get(name)
		category = requirement.get("leave_category") or "LEAVE"
		code = f"{category.upper()}_LEAVE_CONFIGURATION_MISMATCH"
		if not leave_type:
			findings.append(_finding("LEAVE_POLICY_CONFIGURATION_REQUIRED", f"The mapped native {category} Leave Type is missing."))
			continue
		if (
			flt(leave_type.get("max_leaves_allowed")) != flt(requirement.get("annual_entitlement_days"))
			or bool(leave_type.get("is_lwp")) == bool(requirement.get("paid"))
			or bool(leave_type.get("is_carry_forward")) != bool(requirement.get("carry_forward"))
		):
			findings.append(_finding(code, f"Native {category} Leave Type settings do not match the approved rule."))
		if category == "Annual" and not requirement.get("native_accrual_parity_reviewed"):
			findings.append(_finding("ANNUAL_LEAVE_ACCRUAL_REVIEW_REQUIRED", "Native annual-leave accrual has not been reviewed as equivalent to the approved legal accrual.", "review"))
		if category == "Sick" and requirement.get("medical_evidence_required"):
			findings.append(_finding("SICK_LEAVE_EVIDENCE_REVIEW_REQUIRED", "Native Leave Type does not verify registered medical evidence; review leave evidence controls.", "review"))
	return _unique_findings(findings)



def evaluate_festival_holiday_calendar(required_days, categorized_days, year):
	if required_days is None:
		return []
	actual = sum(1 for day, categories in categorized_days if getdate(day).year == year and "Festival Holiday" in categories)
	if actual < int(required_days):
		return [_finding(
			"FESTIVAL_HOLIDAY_CONFIGURATION_MISMATCH",
			f"Holiday List has {actual} explicitly classified festival days in {year}; the approved rule requires at least {int(required_days)}.",
		)]
	return []



def evaluate_weekly_rest_calendar(required_days, categorized_days, from_date, to_date, week_start_day):
	"""Check explicit native weekly-off rows for every week touched by the period."""
	if not required_days:
		return []
	if flt(required_days) % 1:
		return [_finding(
			"WEEKLY_REST_CONFIGURATION_REVIEW_REQUIRED",
			"The native Holiday List records whole-day weekly rest only; review fractional weekly-rest requirements.",
		)]
	rest_dates = {
		getdate(day)
		for day, categories in categorized_days
		if "Weekly Rest" in categories
	}
	start, end = getdate(from_date), getdate(to_date)
	week = _week_start(start, week_start_day)
	findings = []
	while week <= end:
		count = sum(1 for day in rest_dates if week <= day <= week + timedelta(days=6))
		if count < int(required_days):
			findings.append(_finding(
				"WEEKLY_REST_CONFIGURATION_MISMATCH",
				f"Holiday List has {count} weekly-rest days in the week beginning {week}; the approved rule requires {int(required_days)}.",
			))
		week += timedelta(days=7)
	return findings


def evaluate_overtime_configuration(rule, overtime_type):
	if not overtime_type:
		return [_finding("OVERTIME_CONFIGURATION_REQUIRED", "The mapped native Overtime Type is missing.")]
	findings = []
	if overtime_type.get("overtime_calculation_method") == "Fixed Hourly Rate":
		findings.append(_finding(
			"FIXED_OT_RATE_LEGAL_REVIEW_REQUIRED",
			"Fixed hourly OT is not supported for covered employees until its statutory wage basis and amount are represented in an approved rule.",
		))
	multiplier_mismatch = flt(overtime_type.get("standard_multiplier")) != flt(rule.get("overtime_multiplier"))
	if rule.get("weekend_multiplier") is not None:
		multiplier_mismatch = multiplier_mismatch or flt(overtime_type.get("weekend_multiplier")) != flt(rule.get("weekend_multiplier"))
		multiplier_mismatch = multiplier_mismatch or not bool(overtime_type.get("applicable_for_weekend"))
	if rule.get("festival_multiplier") is not None:
		multiplier_mismatch = multiplier_mismatch or flt(overtime_type.get("public_holiday_multiplier")) != flt(rule.get("festival_multiplier"))
		multiplier_mismatch = multiplier_mismatch or not bool(overtime_type.get("applicable_for_public_holiday"))
	if multiplier_mismatch:
		findings.append(_finding("OVERTIME_RATE_CONFIGURATION_MISMATCH", "Native standard, weekly-rest, or festival multiplier differs from the approved rule."))
	legal_components = {row.get("salary_component") for row in rule.get("overtime_components") or [] if row.get("salary_component")}
	native_rows = overtime_type.get("applicable_salary_component") or []
	native_components = {
		row.get("salary_component") if isinstance(row, dict) else row
		for row in native_rows
		if (row.get("salary_component") if isinstance(row, dict) else row)
	}
	if legal_components != native_components:
		findings.append(_finding("OVERTIME_WAGE_BASIS_MISMATCH", "Native Overtime Type salary components differ from the reviewed legal wage basis."))
	return findings


def _unique_findings(findings):
	seen, result = set(), []
	for finding in findings:
		key = (finding["code"], finding["message"])
		if key not in seen:
			seen.add(key)
			result.append(finding)
	return result


@frappe.whitelist()
def inspect_working_time_compliance(company, from_date, to_date, employee_ids=None):
	"""Read-only review of approved legal scope and native Attendance/Leave/OT records."""
	assert_company_access(company, require_explicit_scope=True)
	start, end = getdate(from_date), getdate(to_date)
	if end < start:
		frappe.throw(_("To Date must be on or after From Date."))
	if not frappe.db.exists("DocType", "Tradexcel Working Time Rule Set"):
		return {"company": company, "status": "READY", "findings": [_finding("WORKING_TIME_RULE_REQUIRED", "No approved working-time rule is configured.", "info")], "employees": []}

	rules = frappe.get_all(
		"Tradexcel Working Time Rule Set",
		filters={"company": company, "docstatus": 1, "effective_from": ("<=", end)},
		or_filters=[["effective_to", "is", "not set"], ["effective_to", ">=", start]],
		fields=["name", "company", "branch", "legal_regime", "effective_from", "effective_to", "week_start_day"],
	)
	if not rules:
		return {"company": company, "status": "READY", "findings": [_finding("WORKING_TIME_RULE_REQUIRED", "No approved working-time rule covers this period; confirm legal scope before activation.", "info")], "employees": []}

	employee_filters = {"company": company, "date_of_joining": ("<=", end)}
	if employee_ids:
		employee_ids = list(dict.fromkeys(employee_ids))
		employee_filters["name"] = ["in", employee_ids]
	employees = frappe.get_all(
		"Employee", filters=employee_filters,
		fields=["name", "company", "branch", "holiday_list", "date_of_joining", "relieving_date", "status"],
	)
	employees = [e for e in employees if not e.relieving_date or getdate(e.relieving_date) >= start]
	if employee_ids and {e.name for e in employees} != set(employee_ids):
		frappe.throw(_("One or more selected Employees are outside the authorized Company or period."))
	if not employees:
		return {"company": company, "status": "READY", "findings": [], "employees": []}

	by_employee = {e.name: e for e in employees}
	classifications = frappe.get_all(
		"Tradexcel Working Time Classification",
		filters={"company": company, "employee": ["in", list(by_employee)], "docstatus": 1, "effective_from": ("<=", end)},
		or_filters=[["effective_to", "is", "not set"], ["effective_to", ">=", start]],
		fields=["name", "employee", "company", "branch", "rule_set", "coverage_decision", "effective_from", "effective_to"],
	)
	by_classification = defaultdict(list)
	for classification in classifications:
		by_classification[classification.employee].append(classification)

	attendance_start = min(_week_start(start, rule.week_start_day) for rule in rules)
	if any(rule.weekly_average_max_hours for rule in rules):
		attendance_start = min(attendance_start, start - timedelta(days=365))
	attendance_end = max(_week_start(end, rule.week_start_day) + timedelta(days=6) for rule in rules)
	attendance = frappe.get_all(
		"Attendance",
		filters={"company": company, "employee": ["in", list(by_employee)], "docstatus": 1,
			"attendance_date": ["between", [attendance_start, attendance_end]]},
		fields=["name", "employee", "attendance_date", "status", "working_hours", "standard_working_hours",
			"actual_overtime_duration", "overtime_type", "in_time", "out_time", "shift"],
	)
	attendance_by_employee = defaultdict(list)
	holiday_scope = _holiday_category_by_list(company, employees, attendance, start, end)
	for row in attendance:
		attendance_by_employee[row.employee].append(row)

	active_rules = {rule.name: frappe.get_doc("Tradexcel Working Time Rule Set", rule.name) for rule in rules}
	native_configs = _load_native_configs(active_rules.values())
	leave_findings_by_rule = {}
	for rule_name, rule_doc in active_rules.items():
		employees_for_rule = [
			c.employee for c in classifications
			if c.rule_set == rule_name and c.employee in by_employee
		]
		leave_findings_by_rule[rule_name] = _leave_policy_findings(
			employees_for_rule, [rule_doc], start, end
		)
	findings, employee_results = [], []
	for employee, employee_data in by_employee.items():
		available = [r for r in active_rules.values() if not r.branch or (employee_data.branch and r.branch == employee_data.branch)]
		matches = [c for c in by_classification.get(employee, []) if getdate(c.effective_from) <= start and (not c.effective_to or getdate(c.effective_to) >= end)]
		if len(matches) > 1:
			items = [_finding("WORKING_TIME_CLASSIFICATION_CONFLICT", "Multiple approved working-time classifications cover this period.")]
		elif not matches:
			if available or any(not r.branch for r in active_rules.values()) or end < getdate(today()):
				items = [_finding("WORKING_TIME_CLASSIFICATION_REQUIRED", "Review this Employee's legal working-time coverage and establishment.")]
			else:
				items = [_finding(
					"WORKING_TIME_RULE_REQUIRED",
					"No approved Working Time Rule Set covers this establishment; confirm legal scope before activation.",
					"info",
				)]
		else:
			classification = matches[0]
			if classification.coverage_decision == "Reviewed Outside Scope":
				continue
			rule = active_rules.get(classification.rule_set)
			if not rule or (rule.branch and rule.branch != classification.branch):
				items = [_finding("WORKING_TIME_RULE_REQUIRED", "The classification's exact approved rule does not cover this period and establishment.")]
			elif getdate(classification.effective_from) > start or (classification.effective_to and getdate(classification.effective_to) < end):
				items = [_finding("WORKING_TIME_CLASSIFICATION_CHANGE_REVIEW_REQUIRED", "Legal working-time coverage changes inside this period.")]
			else:
				items = evaluate_attendance_compliance(rule.as_dict(), attendance_by_employee.get(employee, []), start, end)
				items.extend(evaluate_rolling_weekly_average(rule.as_dict(), attendance_by_employee.get(employee, []), start))
				holiday_list = holiday_scope["employee_lists"].get(employee)
				categorized_days = [
					(day, categories)
					for (parent, day), categories in holiday_scope["by_list_date"].items()
					if parent == holiday_list
				]
				items.extend(evaluate_weekly_rest_calendar(
					rule.weekly_rest_days, categorized_days, start, end, rule.week_start_day
				))
				if flt(rule.festival_holidays_per_year) > 0:
					for year in range(start.year, end.year + 1):
						items.extend(evaluate_festival_holiday_calendar(rule.festival_holidays_per_year, categorized_days, year))
				if not attendance_by_employee.get(employee):
					items.append(_finding("WORKING_TIME_EVIDENCE_REQUIRED", "No submitted Attendance exists for this Employee and period."))
				items.extend(_inspect_leave_and_overtime(rule, native_configs))
				items.extend(leave_findings_by_rule.get(rule.name, {}).get(employee, []))
		items = _unique_findings(items)
		findings.extend(items)
		employee_results.append({"employee": employee, "status": "NEEDS_ATTENTION" if any(x["severity"] == "block" for x in items) else "REVIEW" if items else "READY", "findings": items})

	return {
		"company": company, "from_date": str(start), "to_date": str(end),
		"status": "NEEDS_ATTENTION" if any(x["severity"] == "block" for x in findings) else "READY",
		"checked": len(employee_results), "findings": _unique_findings(findings), "employees": employee_results,
	}


def _load_native_configs(rules):
	rules = list(rules)
	overtime_names = {rule.overtime_type for rule in rules if rule.overtime_type}
	leave_names = {
		name for rule in rules
		for name in (rule.casual_leave_type, rule.sick_leave_type, rule.annual_leave_type)
		if name
	}
	overtime_types = {}
	if overtime_names:
		overtime_types = {
			row.name: row for row in frappe.get_all(
				"Overtime Type",
				filters={"name": ["in", sorted(overtime_names)]},
				fields=["name", "standard_multiplier", "weekend_multiplier", "public_holiday_multiplier",
					"applicable_for_weekend", "applicable_for_public_holiday", "overtime_calculation_method"],
			)
		}
		component_rows = frappe.get_all(
			"Overtime Salary Component",
			filters={"parent": ["in", sorted(overtime_names)], "parenttype": "Overtime Type", "parentfield": "applicable_salary_component"},
			fields=["parent", "salary_component"],
		)
		for row in component_rows:
			overtime_types[row.parent].setdefault("applicable_salary_component", []).append({"salary_component": row.salary_component})
	leave_types = {}
	if leave_names:
		leave_types = {
			row.name: row.as_dict() for row in frappe.get_all(
				"Leave Type",
				filters={"name": ["in", sorted(leave_names)]},
				fields=["name", "max_leaves_allowed", "is_lwp", "is_carry_forward"],
			)
		}
	return {"overtime_types": overtime_types, "leave_types": leave_types}


def _inspect_leave_and_overtime(rule, native_configs):
	findings = []
	if rule.overtime_type:
		findings.extend(evaluate_overtime_configuration(rule.as_dict(), native_configs["overtime_types"].get(rule.overtime_type)))

	requirements = []
	for category, type_field, days_field in (
		("Casual", "casual_leave_type", "casual_days_per_year"),
		("Sick", "sick_leave_type", "sick_days_per_year"),
	):
		if rule.get(type_field) and rule.get(days_field) is not None:
			requirements.append({
				"leave_category": category,
				"leave_type": rule.get(type_field),
				"annual_entitlement_days": rule.get(days_field),
				"paid": rule.get(f"{category.lower()}_paid"),
				"carry_forward": rule.get(f"{category.lower()}_carry_forward"),
			})
	findings.extend(evaluate_leave_configuration(requirements, native_configs["leave_types"]))
	if rule.annual_leave_type:
		annual_type = native_configs["leave_types"].get(rule.annual_leave_type)
		if not rule.native_annual_leave_parity_reviewed:
			findings.append(_finding("ANNUAL_LEAVE_ACCRUAL_REVIEW_REQUIRED", "Native annual-leave accrual is not confirmed as equivalent to the approved days-worked accrual.", "review"))
		elif not annual_type or bool(annual_type.get("is_lwp")) != (not bool(rule.annual_paid)) or bool(annual_type.get("is_carry_forward")) != bool(rule.annual_carry_forward):
			findings.append(_finding("ANNUAL_LEAVE_CONFIGURATION_MISMATCH", "Native annual-leave type differs from the approved paid/carry-forward settings."))
	if rule.sick_medical_evidence_required and rule.sick_leave_type:
		findings.append(_finding("SICK_LEAVE_EVIDENCE_REVIEW_REQUIRED", "Native Leave Application does not verify registered medical evidence.", "review"))
	return findings



def _holiday_category_by_list(company, employees, attendance, start, end):
	"""Batch-load native Holiday rows and retain weekly-rest plus festival tags."""
	company_default = frappe.db.get_value("Company", company, "default_holiday_list")
	employee_lists = {row.name: row.holiday_list or company_default for row in employees}
	shift_names = {row.shift for row in attendance if row.shift}
	shift_lists = {
		row.name: row.holiday_list
		for row in frappe.get_all(
			"Shift Type", filters={"name": ["in", sorted(shift_names)]}, fields=["name", "holiday_list"]
		)
	} if shift_names else {}
	employee_shift_lists = defaultdict(set)
	for row in attendance:
		if shift_lists.get(row.shift):
			employee_shift_lists[row.employee].add(shift_lists[row.shift])
	for employee, holiday_lists in employee_shift_lists.items():
		employee_lists[employee] = next(iter(holiday_lists)) if len(holiday_lists) == 1 else None
	list_names = set(employee_lists.values()) | set(shift_lists.values())
	list_names.discard(None)
	list_names.discard("")
	if not list_names:
		return {"employee_lists": employee_lists, "by_list_date": {}}
	holiday_start = date(start.year, 1, 1) - timedelta(days=7)
	holiday_end = date(end.year, 12, 31) + timedelta(days=7)
	holiday_rows = frappe.get_all(
		"Holiday",
		filters={
			"parent": ["in", sorted(list_names)],
			"parenttype": "Holiday List",
			"holiday_date": ["between", [holiday_start, holiday_end]],
		},
		fields=["parent", "holiday_date", "weekly_off", "custom_tradex_holiday_category"],
	)
	by_list_date = defaultdict(set)
	for holiday in holiday_rows:
		day = getdate(holiday.holiday_date)
		if holiday.weekly_off:
			by_list_date[(holiday.parent, day)].add("Weekly Rest")
		if holiday.custom_tradex_holiday_category:
			by_list_date[(holiday.parent, day)].add(holiday.custom_tradex_holiday_category)
	for row in attendance:
		day = getdate(row.attendance_date)
		holiday_list = shift_lists.get(row.shift) or employee_lists.get(row.employee)
		row["holiday_categories"] = by_list_date.get((holiday_list, day), set())
	return {"employee_lists": employee_lists, "by_list_date": by_list_date}


def _leave_policy_findings(employee_ids, rules, from_date, to_date):
	"""Check native Leave Policy Assignment coverage without creating allocations."""
	requirements_by_type = defaultdict(set)
	for rule in rules:
		for field in ("casual_leave_type", "sick_leave_type", "annual_leave_type"):
			if rule.get(field):
				requirements_by_type[rule.get(field)].add(rule.name)
	if not requirements_by_type or not employee_ids:
		return {}
	assignments = frappe.get_all(
		"Leave Policy Assignment",
		filters={"employee": ["in", employee_ids], "company": rules[0].company, "docstatus": 1, "effective_from": ["<=", to_date]},
		or_filters=[["effective_to", "is", "not set"], ["effective_to", ">=", from_date]],
		fields=["employee", "leave_policy", "effective_from", "effective_to"],
	)
	policy_names = list({row.leave_policy for row in assignments if row.leave_policy})
	policy_details = frappe.get_all(
		"Leave Policy Detail",
		filters={"parent": ["in", policy_names], "parenttype": "Leave Policy", "parentfield": "leave_policy_details"},
		fields=["parent", "leave_type"],
	) if policy_names else []
	leave_types_by_policy = defaultdict(set)
	for row in policy_details:
		leave_types_by_policy[row.parent].add(row.leave_type)
	assigned = defaultdict(set)
	for row in assignments:
		if getdate(row.effective_from) <= getdate(from_date) and (
			not row.effective_to or getdate(row.effective_to) >= getdate(to_date)
		):
			assigned[row.employee].update(leave_types_by_policy.get(row.leave_policy, set()))
	result = defaultdict(list)
	for employee in employee_ids:
		for leave_type in requirements_by_type:
			if leave_type not in assigned.get(employee, set()):
				result[employee].append(_finding(
					"LEAVE_POLICY_CONFIGURATION_REQUIRED",
					f"Employee has no effective native Leave Policy Assignment for mapped Leave Type {leave_type}.",
				))
	return result


def working_time_query_conditions(user=None):
	user = user or frappe.session.user
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return ""
	companies = frappe.get_all("User Permission", filters={"user": user, "allow": "Company"}, pluck="for_value")
	if not companies:
		return "1=0"
	values = ", ".join(frappe.db.escape(company) for company in sorted(set(companies)))
	return "company in (" + values + ")"


def working_time_has_permission(doc, ptype=None, user=None, **_kwargs):
	user = user or frappe.session.user
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return True
	return bool(
		doc and doc.company and frappe.db.exists(
			"User Permission", {"user": user, "allow": "Company", "for_value": doc.company}
		)
	)


def validate_overtime_slip_before_submit(doc, method=None):
	"""Gate native OT money creation on reviewed, finalized Attendance and an independent approver."""
	user = frappe.session.user
	if user != "Administrator":
		if "Tradexcel Payroll Approver" not in frappe.get_roles(user):
			frappe.throw(_("Only a Tradexcel Payroll Approver can submit a monetary Overtime Slip."), frappe.PermissionError)
		if doc.owner == user:
			frappe.throw(_("The Overtime Slip maker cannot approve their own monetary OT."), frappe.PermissionError)
	assert_company_access(doc.company, require_explicit_scope=True)
	if not (doc.employee and doc.start_date and doc.end_date and doc.get("overtime_details")):
		frappe.throw(_("Employee, date range, and native Attendance detail are required before OT submission."))
	if getdate(doc.start_date) > getdate(doc.end_date):
		frappe.throw(_("Overtime Slip end date must not precede its start date."))

	attendance_names = {row.reference_document for row in doc.overtime_details if row.reference_document}
	if len(attendance_names) != len(doc.overtime_details):
		frappe.throw(_("Every Overtime Slip row must reference submitted native Attendance."))
	attendance_rows = frappe.get_all(
		"Attendance",
		filters={"name": ["in", list(attendance_names)], "employee": doc.employee, "company": doc.company, "docstatus": 1},
		fields=["name", "attendance_date", "actual_overtime_duration", "overtime_type"],
	)
	attendance_by_name = {row.name: row for row in attendance_rows}
	if len(attendance_by_name) != len(attendance_names):
		frappe.throw(_("Overtime Slip rows must reference submitted Attendance for the same Employee and Company."))
	for detail in doc.overtime_details:
		attendance_row = attendance_by_name[detail.reference_document]
		if (
			getdate(detail.date) != getdate(attendance_row.attendance_date)
			or detail.overtime_type != attendance_row.overtime_type
			or flt(detail.overtime_duration) != flt(attendance_row.actual_overtime_duration)
		):
			frappe.throw(_("Overtime Slip detail differs from its approved Attendance overtime evidence."))

	periods = frappe.get_all(
		"Tradexcel Attendance Period",
		filters={
			"company": doc.company, "status": "Finalized",
			"from_date": ["<=", doc.start_date], "to_date": [">=", doc.end_date],
		},
		fields=["name", "from_date", "to_date", "attendance_hash"],
	)
	if len(periods) != 1:
		frappe.throw(_("Overtime Slip dates must belong to one finalized Tradexcel Attendance Period."), title=_("OVERTIME_ATTENDANCE_NOT_FINAL"))
	from tradex_hr.tradexcel_hr.attendance_payroll_boundary import current_attendance_period_hash
	period = periods[0]
	if current_attendance_period_hash(doc.company, period.from_date, period.to_date) != period.attendance_hash:
		frappe.throw(_("Attendance changed after period finalization. Review and finalize it again."), title=_("OVERTIME_ATTENDANCE_NOT_FINAL"))

	from tradex_hr.tradexcel_hr.payroll_adjustments import _target_payroll_has_started
	if _target_payroll_has_started(doc.employee, doc.company, doc.end_date):
		frappe.throw(_("The target payroll has started. Route this OT through post-payroll adjustment review."), title=_("OVERTIME_TARGET_PAYROLL_ALREADY_STARTED"))
	result = inspect_working_time_compliance(doc.company, doc.start_date, doc.end_date, employee_ids=[doc.employee])
	employee_result = next(iter(result.get("employees", [])), None)
	blocks = [
		item for item in (employee_result or {}).get("findings", [])
		if item["severity"] == "block"
	]
	if blocks:
		frappe.throw(_("Working-time review blocks Overtime Slip submission: {0}").format("; ".join(x["code"] for x in blocks[:8])))



def validate_overtime_generated_additional_salary(doc, method=None):
	"""Verify that approver-submitted Additional Salary has a native approved source."""
	if frappe.session.user == "Administrator" or "Tradexcel Payroll Approver" not in frappe.get_roles():
		return

	if doc.ref_doctype == "Overtime Slip" and doc.ref_docname:
		slip = frappe.db.get_value(
			"Overtime Slip", doc.ref_docname, ["docstatus", "employee", "company", "end_date"], as_dict=True
		)
		valid = (
			slip and slip.docstatus == 1 and slip.employee == doc.employee and slip.company == doc.company
			and getdate(slip.end_date) == getdate(doc.payroll_date)
		)
	elif doc.ref_doctype in {"Payroll Correction", "Arrear"} and doc.ref_docname:
		if not frappe.db.exists("DocType", doc.ref_doctype) or not frappe.db.exists(doc.ref_doctype, doc.ref_docname):
			valid = False
		else:
			source = frappe.get_doc(doc.ref_doctype, doc.ref_docname)
			component_amount = sum(
				flt(row.amount)
				for field in ("earning_arrears", "deduction_arrears")
				for row in source.get(field) or []
				if row.salary_component == doc.salary_component
			)
			valid = (
				source.docstatus == 1 and source.employee == doc.employee and source.company == doc.company
				and getdate(source.payroll_date) == getdate(doc.payroll_date)
				and component_amount > 0 and flt(doc.amount) == flt(component_amount)
			)
	else:
		valid = False

	if not valid:
		frappe.throw(_("Payroll Approvers may submit Additional Salary only from a matching submitted native Overtime Slip, Payroll Correction, or Arrear."), frappe.PermissionError)
	assert_company_access(doc.company, require_explicit_scope=True)
