"""Read-only statutory wage-floor checks over native salary assignments."""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate

from workforce_suite.workforce_suite.company_context import assert_company_access
from workforce_suite.workforce_suite.pay_basis import DAILY, MONTHLY, resolve_pay_basis


PASS_STATUSES = {"READY", "NOT_IN_CONFIGURED_SCOPE", "REVIEWED_OUTSIDE_SCOPE"}
WAGE_FLOOR_DOCTYPES = {
	"Workforce Wage Floor Rule Set",
	"Workforce Wage Floor Classification",
}


def _overlaps(start, end, row_start, row_end) -> bool:
	return getdate(row_start) <= end and (not row_end or getdate(row_end) >= start)


def prepare_wage_floor_context(company: str, start_date, end_date, employee_ids: list[str]):
	"""Batch-load scoped rules and approved classifications once per payroll run."""
	start, end = getdate(start_date), getdate(end_date)
	rules = frappe.get_all(
		"Workforce Wage Floor Rule Set",
		filters={"company": company, "docstatus": 1},
		fields=["name", "branch", "currency", "effective_from", "effective_to", "annual_increment_review_required"],
	)
	rules = [row for row in rules if _overlaps(start, end, row.effective_from, row.effective_to)]
	classifications = []
	if employee_ids:
		classifications = frappe.get_all(
			"Workforce Wage Floor Classification",
			filters={"company": company, "employee": ["in", employee_ids], "docstatus": 1},
			fields=["name", "employee", "company", "branch", "coverage_decision", "rule_set", "worker_category", "gazette_grade", "location_category", "effective_from", "effective_to"],
		)
	return {
		"company": company,
		"start": start,
		"end": end,
		"rules": rules,
		"classifications": classifications,
		"classifications_by_employee": _group_by_employee(classifications),
	}


def _group_by_employee(rows):
	grouped = {}
	for row in rows:
		grouped.setdefault(row.employee, []).append(row)
	return grouped


def _result(status: str, *, findings=None, **details):
	return {"status": status, "findings": findings or [], **details}


def _finding(code: str, message: str, severity="blocker", **details):
	return {"code": code, "message": _(message), "severity": severity, **details}


def inspect_wage_floor_for_employee(employee: str, start_date, end_date, context=None, employee_data=None, pay_basis=None):
	"""Resolve one employee against approved scope and native SSA-evaluated earnings."""
	start, end = getdate(start_date), getdate(end_date)
	if start > end:
		frappe.throw(_("Wage-floor period dates are invalid."))
	if employee_data is None:
		employee_data = frappe.db.get_value("Employee", employee, ["company", "branch"], as_dict=True)
	if not employee_data:
		frappe.throw(_("Employee not found."))
	company = employee_data.get("company")
	branch = employee_data.get("branch") or ""
	if context is None:
		context = prepare_wage_floor_context(company, start, end, [employee])

	all_classifications = context["classifications_by_employee"].get(employee, [])
	period_classifications = [row for row in all_classifications if _overlaps(start, end, row.effective_from, row.effective_to)]
	if len(period_classifications) > 1:
		return _result("WAGE_CLASSIFICATION_CONFLICT", findings=[_finding("WAGE_CLASSIFICATION_CONFLICT", "Employee wage classifications overlap for this payroll period.")])
	classification = period_classifications[0] if period_classifications else None
	classification_branch = (classification.branch or "") if classification else branch
	if classification and (classification.branch or "") != branch and end >= getdate(frappe.utils.today()):
		return _result("WAGE_CLASSIFICATION_REQUIRED", findings=[_finding("WAGE_CLASSIFICATION_REQUIRED", "The Employee's establishment changed; review wage classification for the current payroll period.")], classification=classification.name)
	rules = [row for row in context["rules"] if not row.branch or row.branch == classification_branch]
	partial_rules = [row for row in rules if not (getdate(row.effective_from) <= start and (not row.effective_to or getdate(row.effective_to) >= end))]
	active_rules = [row for row in rules if getdate(row.effective_from) <= start and (not row.effective_to or getdate(row.effective_to) >= end)]
	if partial_rules:
		return _result("WAGE_FLOOR_MID_PERIOD_CHANGE", findings=[_finding("WAGE_FLOOR_MID_PERIOD_CHANGE", "An approved wage-floor rule changes during this payroll period.")])
	if not rules:
		return _result("NOT_IN_CONFIGURED_SCOPE", findings=[_finding("WAGE_FLOOR_SCOPE_NOT_CONFIGURED", "No approved wage-floor scope applies to this establishment and payroll period.", "info")])
	if len(active_rules) != 1:
		return _result("WAGE_FLOOR_RULE_CONFLICT", findings=[_finding("WAGE_FLOOR_RULE_CONFLICT", "More than one approved wage-floor rule may apply, or no rule covers the complete payroll period.")])
	rule_summary = active_rules[0]

	if not period_classifications:
		return _result("WAGE_CLASSIFICATION_REQUIRED", findings=[_finding("WAGE_CLASSIFICATION_REQUIRED", "This approved wage-floor scope needs an independently reviewed employee coverage decision.")], rule_set=rule_summary.name)
	classification = period_classifications[0]
	if not (getdate(classification.effective_from) <= start and (not classification.effective_to or getdate(classification.effective_to) >= end)):
		return _result("WAGE_FLOOR_MID_PERIOD_CHANGE", findings=[_finding("WAGE_FLOOR_MID_PERIOD_CHANGE", "Employee wage classification changes during this payroll period.")], classification=classification.name, rule_set=rule_summary.name)
	if classification.rule_set != rule_summary.name:
		return _result("WAGE_CLASSIFICATION_REQUIRED", findings=[_finding("WAGE_CLASSIFICATION_REQUIRED", "Re-review this employee against the exact wage-floor rule effective for the period.")], classification=classification.name, rule_set=rule_summary.name)
	if classification.coverage_decision == "Reviewed Outside Scope":
		return _result("REVIEWED_OUTSIDE_SCOPE", findings=[_finding("REVIEWED_OUTSIDE_SCOPE", "An independent reviewer recorded this Employee as outside the configured wage-floor population.", "info")], classification=classification.name)
	if classification.coverage_decision != "Covered":
		return _result("WAGE_CLASSIFICATION_CONFLICT", findings=[_finding("WAGE_CLASSIFICATION_CONFLICT", "The employee classification is not bound to the exact wage-floor Rule Set effective for this period.")], classification=classification.name, rule_set=rule_summary.name)
	if rule_summary.annual_increment_review_required:
		return _result("STATUTORY_INCREMENT_REVIEW_REQUIRED", findings=[_finding("STATUTORY_INCREMENT_REVIEW_REQUIRED", "The approved source requires an annual increment decision that is not calculated automatically.")], classification=classification.name, rule_set=rule_summary.name)
	if (classification.worker_category or "").strip().casefold() == "apprentice":
		return _result("APPRENTICE_PERIOD_REVIEW_REQUIRED", findings=[_finding("APPRENTICE_PERIOD_REVIEW_REQUIRED", "Apprentice wage periods need a reviewed duration rule; this check does not extend an apprentice rate automatically.")], classification=classification.name, rule_set=rule_summary.name)

	rule = frappe.get_cached_doc("Workforce Wage Floor Rule Set", rule_summary.name)
	matching = [row for row in rule.floor_rows if row.worker_category == classification.worker_category and row.gazette_grade == classification.gazette_grade and row.location_category == classification.location_category]
	if not matching:
		return _result("WAGE_FLOOR_RULE_REVIEW_REQUIRED", findings=[_finding("WAGE_FLOOR_RULE_REVIEW_REQUIRED", "No approved wage-floor rows match the reviewed category, grade, and location.")], classification=classification.name, rule_set=rule.name)

	basis = pay_basis or resolve_pay_basis(employee, start, end)
	if basis.get("status") not in {MONTHLY, DAILY}:
		return _result("WAGE_RATE_CONVERSION_REVIEW_REQUIRED", findings=[_finding("WAGE_RATE_CONVERSION_REVIEW_REQUIRED", "The native Salary Structure pay basis is unresolved for this wage-floor rule.")], classification=classification.name, rule_set=rule.name)
	expected_rate_basis = "Monthly" if basis["status"] == MONTHLY else "Daily"
	matching_rates = {row.rate_basis for row in matching}
	if matching_rates != {expected_rate_basis}:
		return _result("WAGE_RATE_CONVERSION_REVIEW_REQUIRED", findings=[_finding("WAGE_RATE_CONVERSION_REVIEW_REQUIRED", "The approved wage rate uses a different time basis; no monthly/daily conversion is inferred.")], classification=classification.name, rule_set=rule.name)
	structure_currency = frappe.db.get_value("Salary Structure", basis.get("salary_structure"), "currency")
	if structure_currency != rule.currency:
		return _result("WAGE_CURRENCY_REVIEW_REQUIRED", findings=[_finding("WAGE_CURRENCY_REVIEW_REQUIRED", "The Salary Structure and wage-floor Rule Set currencies do not match.")], classification=classification.name, rule_set=rule.name)

	try:
		assignment = frappe.get_cached_doc("Salary Structure Assignment", basis["assignment"])
		evaluated = assignment.get_evaluated_components()
	except Exception:
		return _result("WAGE_SALARY_STRUCTURE_REVIEW_REQUIRED", findings=[_finding("WAGE_SALARY_STRUCTURE_REVIEW_REQUIRED", "Native Salary Structure component evaluation needs review.")], classification=classification.name, rule_set=rule.name)
	earnings = {row.salary_component: flt(row.default_amount) for row in evaluated.earnings if not row.statistical_component and not row.accrual_component and not row.do_not_include_in_total}
	component_rows = [row for row in matching if row.floor_type == "Component"]
	total_row = next(row for row in matching if row.floor_type == "Total")
	missing = [row.salary_component for row in component_rows if row.salary_component not in earnings]
	if missing:
		return _result("WAGE_COMPONENT_MAPPING_REQUIRED", findings=[_finding("WAGE_COMPONENT_MAPPING_REQUIRED", "The approved wage-component mapping is missing from the evaluated Salary Structure.", components=missing)], classification=classification.name, rule_set=rule.name)

	values = {row.salary_component: earnings[row.salary_component] for row in component_rows}
	findings = []
	for row in component_rows:
		actual = values[row.salary_component]
		if actual < flt(row.minimum_amount):
			findings.append(_finding("WAGE_COMPONENT_BELOW_MINIMUM", "A mapped fixed wage component is below its approved component floor.", component=row.component_key, salary_component=row.salary_component, configured=actual, required=flt(row.minimum_amount), difference=flt(row.minimum_amount) - actual))
	package_total = sum(values[row.salary_component] for row in component_rows if row.include_in_total_floor)
	if package_total < flt(total_row.minimum_amount):
		findings.append(_finding("WAGE_TOTAL_BELOW_MINIMUM", "Mapped contractual wage components are below the approved total floor.", configured=package_total, required=flt(total_row.minimum_amount), difference=flt(total_row.minimum_amount) - package_total))
	if findings:
		return _result("WAGE_FLOOR_BELOW_MINIMUM", findings=findings, classification=classification.name, rule_set=rule.name, salary_assignment=assignment.name, salary_structure=basis["salary_structure"], component_values=values, total_package=package_total)
	return _result("READY", findings=[], classification=classification.name, rule_set=rule.name, salary_assignment=assignment.name, salary_structure=basis["salary_structure"], component_values=values, total_package=package_total, required_total=flt(total_row.minimum_amount))


@frappe.whitelist()
def inspect_wage_floor_readiness(employee: str, from_date, to_date) -> dict:
	company = frappe.db.get_value("Employee", employee, "company")
	if not company:
		frappe.throw(_("Employee not found."))
	assert_company_access(company, require_explicit_scope=True)
	return inspect_wage_floor_for_employee(employee, from_date, to_date)


def wage_floor_query_conditions(user=None):
	user = user or frappe.session.user
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return ""
	companies = frappe.get_all(
		"User Permission",
		filters={"user": user, "allow": "Company"},
		pluck="for_value",
	)
	if not companies:
		return "1=0"
	values = ", ".join(frappe.db.escape(company) for company in sorted(set(companies)))
	return "company in (" + values + ")"


def wage_floor_has_permission(doc, ptype=None, user=None, **_kwargs):
	user = user or frappe.session.user
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return True
	if doc.doctype not in WAGE_FLOOR_DOCTYPES:
		return True
	if not doc.company or not frappe.db.exists(
		"User Permission", {"user": user, "allow": "Company", "for_value": doc.company}
	):
		return False
	return True
