"""Read-only readiness for reviewed PF, Progoti, and group-insurance setup."""

from __future__ import annotations

from datetime import date

import frappe
from frappe import _
from frappe.model.base_document import get_controller
from frappe.utils import getdate

from tradex_hr.tradexcel_hr.company_context import assert_company_access


BENEFIT_TYPES = ("Provident Fund", "Progoti Pension", "Group Insurance")


@frappe.whitelist()
def inspect_statutory_benefit_readiness(employee: str, from_date: str | date, to_date: str | date) -> dict:
	"""Inspect one employee's approved participation; never create payroll money."""
	employee_data = frappe.db.get_value("Employee", employee, ["company", "branch"], as_dict=True)
	if not employee_data:
		frappe.throw(_("Employee not found."))
	assert_company_access(employee_data.company, require_explicit_scope=True)
	frappe.get_doc("Employee", employee).check_permission("read")
	return _inspect_employee(employee, employee_data, getdate(from_date), getdate(to_date))


def prepare_statutory_benefit_context(company: str, from_date: str | date, to_date: str | date, employees) -> dict[str, dict]:
	"""Batch-load company rules/enrollments for payroll; do not issue N+1 queries."""
	start, end = getdate(from_date), getdate(to_date)
	if isinstance(employees, dict):
		employee_rows = list(employees.values())
	else:
		employee_rows = list(employees or [])
	rows_by_name = {
		(row.get("name") if isinstance(row, dict) else row.name): row
		for row in employee_rows
	}
	ids = list(rows_by_name)
	if not ids:
		return {}

	rules = frappe.get_all(
		"Tradexcel Statutory Benefit Rule Set",
		filters={"company": company, "docstatus": 1, "effective_from": ["<=", end]},
		or_filters=[["Tradexcel Statutory Benefit Rule Set", "effective_to", "is", "not set"], ["Tradexcel Statutory Benefit Rule Set", "effective_to", ">=", start]],
		fields=["name", "company", "branch", "legal_regime", "benefit_type", "applicability", "effective_from", "effective_to", "pf_trigger_status", "policy_reference", "policy_effective_from", "policy_effective_to", "employee_component", "employer_component"],
	)
	enrollments = frappe.get_all(
		"Tradexcel Statutory Benefit Enrollment",
		filters={"company": company, "employee": ["in", ids], "docstatus": 1, "effective_from": ["<=", end]},
		or_filters=[["Tradexcel Statutory Benefit Enrollment", "effective_to", "is", "not set"], ["Tradexcel Statutory Benefit Enrollment", "effective_to", ">=", start]],
		fields=["name", "employee", "company", "branch", "benefit_type", "rule_set", "participation_status", "effective_from", "effective_to"],
	)
	by_employee = {employee: [] for employee in ids}
	for enrollment in enrollments:
		by_employee.setdefault(enrollment.employee, []).append(enrollment)

	return {
		employee: _evaluate_employee(
			employee,
			row,
			start,
			end,
			rules,
			by_employee.get(employee, []),
		)
		for employee, row in rows_by_name.items()
	}


def native_employer_contribution_accounting_supported() -> bool:
	"""Detect the installed Payroll Entry accrual capability without version strings."""
	controller = get_controller("Payroll Entry")
	accrual = getattr(controller, "make_accrual_jv_entry", None)
	employer_method = getattr(controller, "make_employer_contribution_jv_entry", None)
	function = getattr(accrual, "__func__", accrual)
	code = getattr(function, "__code__", None)
	return callable(employer_method) and code is not None and "make_employer_contribution_jv_entry" in code.co_names


def _inspect_employee(employee, employee_data, start, end):
	return _evaluate_employee(
		employee,
		employee_data,
		start,
		end,
		frappe.get_all(
			"Tradexcel Statutory Benefit Rule Set",
			filters={"company": employee_data.company, "docstatus": 1, "effective_from": ["<=", end]},
			or_filters=[["Tradexcel Statutory Benefit Rule Set", "effective_to", "is", "not set"], ["Tradexcel Statutory Benefit Rule Set", "effective_to", ">=", start]],
			fields=["name", "company", "branch", "legal_regime", "benefit_type", "applicability", "effective_from", "effective_to", "pf_trigger_status", "policy_reference", "policy_effective_from", "policy_effective_to", "employee_component", "employer_component"],
		),
		frappe.get_all(
			"Tradexcel Statutory Benefit Enrollment",
			filters={"company": employee_data.company, "employee": employee, "docstatus": 1, "effective_from": ["<=", end]},
			or_filters=[["Tradexcel Statutory Benefit Enrollment", "effective_to", "is", "not set"], ["Tradexcel Statutory Benefit Enrollment", "effective_to", ">=", start]],
			fields=["name", "employee", "company", "branch", "benefit_type", "rule_set", "participation_status", "effective_from", "effective_to"],
		),
	)


def _evaluate_employee(employee, employee_data, start, end, rules, enrollments):
	findings = []
	benefits = []
	current_or_future = end >= getdate(frappe.utils.today())
	if current_or_future:
		matching = [r for r in rules if not r.branch or r.branch == (employee_data.get("branch") or "")]
	else:
		linked_enrollments = [e for e in enrollments if e.employee == employee]
		linked_rule_names = {e.rule_set for e in linked_enrollments}
		matching = [
			r for r in rules
			if not r.branch or any(e.rule_set == r.name and e.branch == r.branch for e in linked_enrollments)
		]
		if any(r.branch and r.name not in linked_rule_names for r in rules):
			findings.append(_finding("BENEFIT_ESTABLISHMENT_REVIEW_REQUIRED", "Historical establishment cannot be inferred from the Employee's current Branch; verify the benefit enrollment snapshot.", "review"))

	for rule in matching:
		rule_start = getdate(rule.effective_from)
		rule_end = getdate(rule.effective_to) if rule.effective_to else None
		if (rule_start > start and rule_start <= end) or (rule_end and rule_end >= start and rule_end < end):
			benefits.append({"benefit_type": rule.benefit_type, "rule_set": rule.name, "status": "BENEFIT_MID_PERIOD_CHANGE"})
			findings.append(_finding("BENEFIT_MID_PERIOD_CHANGE", f"{rule.benefit_type} rule changes inside this payroll period; review the effective-date treatment."))
			continue
		if rule.applicability == "Not Applicable":
			benefits.append({"benefit_type": rule.benefit_type, "rule_set": rule.name, "status": "NOT_APPLICABLE"})
			continue
		if rule.applicability != "Applicable":
			benefits.append({"benefit_type": rule.benefit_type, "rule_set": rule.name, "status": "BENEFIT_RULE_REVIEW_REQUIRED"})
			findings.append(_finding("BENEFIT_RULE_REVIEW_REQUIRED", f"{rule.benefit_type} legal applicability remains under review.", "review"))
			continue
		if rule.benefit_type == "Provident Fund" and rule.pf_trigger_status == "Not Triggered":
			benefits.append({"benefit_type": rule.benefit_type, "rule_set": rule.name, "status": "PF_NOT_TRIGGERED_REVIEWED"})
			continue
		if rule.benefit_type == "Provident Fund" and rule.pf_trigger_status == "Institutional Progoti Exemption":
			benefits.append({"benefit_type": rule.benefit_type, "rule_set": rule.name, "status": "PF_PROGOTI_EXEMPTION_REVIEW_REQUIRED"})
			findings.append(_finding("PF_PROGOTI_EXEMPTION_REVIEW_REQUIRED", "The reviewed Progoti exemption needs a separate linked rule and employee-level evidence."))
			continue

		if rule.benefit_type == "Group Insurance":
			policy_start = getdate(rule.policy_effective_from) if rule.policy_effective_from else None
			policy_end = getdate(rule.policy_effective_to) if rule.policy_effective_to else None
			policy_changes_mid_period = (policy_start and start < policy_start <= end) or (
				policy_end and start <= policy_end < end
			)
			if policy_changes_mid_period:
				status = "BENEFIT_MID_PERIOD_CHANGE"
				benefits.append({"benefit_type": rule.benefit_type, "rule_set": rule.name, "status": status})
				findings.append(_finding(status, "The group-insurance policy starts or expires inside this period; review coverage explicitly."))
				continue
			if not rule.policy_reference or not policy_start or policy_start > start or (policy_end and policy_end < end):
				benefits.append({"benefit_type": rule.benefit_type, "rule_set": rule.name, "status": "GROUP_INSURANCE_POLICY_REQUIRED"})
				findings.append(_finding("GROUP_INSURANCE_POLICY_REQUIRED", "The approved group insurance policy does not cover this period."))
				continue

		enrollment = next((
			e for e in enrollments
			if e.employee == employee and e.rule_set == rule.name
			and (not rule.branch or e.branch == rule.branch)
			and getdate(e.effective_from) <= start
			and (not e.effective_to or getdate(e.effective_to) >= end)
		), None)
		if not enrollment:
			overlapping_enrollment = any(
				e.employee == employee and e.rule_set == rule.name
				and getdate(e.effective_from) <= end
				and (not e.effective_to or getdate(e.effective_to) >= start)
				for e in enrollments
			)
			if overlapping_enrollment:
				status = "BENEFIT_MID_PERIOD_CHANGE"
				findings.append(_finding(status, f"{rule.benefit_type} participation changes inside this payroll period; review the effective-date treatment."))
			else:
				status = "GROUP_INSURANCE_EMPLOYEE_COVERAGE_REQUIRED" if rule.benefit_type == "Group Insurance" else "BENEFIT_ENROLLMENT_REQUIRED"
				findings.append(_finding(status, f"Approved {rule.benefit_type} applicability needs a reviewed employee participation record."))
			benefits.append({"benefit_type": rule.benefit_type, "rule_set": rule.name, "status": status})
			continue

		participation = enrollment.participation_status
		if participation == "Pending Enrollment":
			status = "BENEFIT_ENROLLMENT_REQUIRED"
			findings.append(_finding(status, f"{rule.benefit_type} enrollment is still pending."))
		elif participation == "Opted Out in Writing" and rule.benefit_type == "Progoti Pension":
			status = "PROGOTI_OPTED_OUT"
		elif participation == "Not Applicable":
			status = "BENEFIT_PARTICIPATION_REVIEW_REQUIRED"
			findings.append(_finding(status, f"An employee-level Not Applicable decision needs legal review for {rule.benefit_type}."))
		else:
			status = "READY"
			if rule.benefit_type in ("Provident Fund", "Progoti Pension"):
				if native_employer_contribution_accounting_supported():
					status = "STATUTORY_BENEFIT_NATIVE_ACCOUNTING_UNVERIFIED"
					message = "The installed Payroll Entry exposes native employer-contribution accrual, but Tradexcel has not verified its complete native payroll/accounting path. Keep participation blocked until that integration is proven."
				else:
					status = "STATUTORY_BENEFIT_ACCOUNTING_PATH_REVIEW_REQUIRED"
					message = "The installed Payroll Entry has no native employer-contribution accrual path; do not start PF/Progoti payroll deductions until a supported native path exists."
				findings.append(_finding(status, message))
		benefits.append({"benefit_type": rule.benefit_type, "rule_set": rule.name, "status": status})

	if not matching:
		findings.append(_finding("BENEFIT_RULE_REVIEW_REQUIRED", "No approved applicable statutory benefit rule is configured for this establishment and period.", "info"))
	status = "NEEDS_ATTENTION" if any(f["severity"] == "blocker" for f in findings) else "READY"
	return {"employee": employee, "company": employee_data.get("company"), "from_date": start, "to_date": end, "status": status, "benefits": benefits, "findings": findings}


def _finding(code, message, severity="blocker"):
	return {"code": code, "message": message, "severity": severity}
