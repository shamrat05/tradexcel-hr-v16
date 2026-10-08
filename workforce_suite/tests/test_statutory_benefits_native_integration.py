"""Native benefit-rule/enrollment and accounting-boundary integration tests."""
from __future__ import annotations

import os
import types

import frappe
import pytest


@pytest.fixture(scope="module", autouse=True)
def frappe_site():
	frappe.init(
		site=os.environ.get("FRAPPE_TEST_SITE", "hrms-v16.localhost"),
		sites_path=os.environ.get("FRAPPE_TEST_SITES_PATH", "/home/sanchita/frappe-bench-v16/sites"),
		force=True,
	)
	frappe.connect()
	yield
	frappe.destroy()


def test_company_scoped_approved_benefits_and_native_accounting_boundary(monkeypatch):
	from workforce_suite.role_setup import ensure_workforce_roles
	from workforce_suite.tests.test_payroll_finalization_integration import (
		_create_employee,
		_create_scoped_user,
		_create_synthetic_company,
		cleanup_synthetic_finalization_company,
	)
	from workforce_suite.workforce_suite.statutory_benefits import native_employer_contribution_accounting_supported
	from workforce_suite.workforce_suite.statutory_benefits import inspect_statutory_benefit_readiness

	token = frappe.generate_hash(8).upper()[:8]
	company = None
	rules = []
	enrollments = []
	components = []
	old_user = frappe.session.user
	try:
		frappe.set_user("Administrator")
		company, _abbr, _payable, expense, _cost_center, holiday_list = _create_synthetic_company(token, monkeypatch)
		ensure_workforce_roles()
		hr_user = _create_scoped_user("Workforce Suite Manager", company, token)
		director = _create_scoped_user("Workforce Owner/Director", company, token)
		unscoped_hr = frappe.get_doc({
			"doctype": "User",
			"email": f"unscoped-benefits-{token}@example.test",
			"first_name": "Unscoped benefits HR",
			"enabled": 1,
			"user_type": "System User",
			"send_welcome_email": 0,
			"roles": [{"role": "Workforce Suite Manager"}],
		}).insert(ignore_permissions=True).name
		employee = _create_employee(f"Benefits Test {token}", company, holiday_list)
		assert frappe.has_permission("Workforce Statutory Benefit Rule Set", "create", user=hr_user)
		assert not frappe.has_permission("Workforce Statutory Benefit Rule Set", "submit", user=hr_user)
		assert frappe.has_permission("Workforce Statutory Benefit Rule Set", "submit", user=director)

		for name, abbreviation, component_type in (
			(f"Synthetic PF Employee {token}", f"PE{token[:3]}", "Deduction"),
			(f"Synthetic PF Employer {token}", f"PR{token[:3]}", "Employer Contribution"),
		):
			components.append(frappe.get_doc({
				"doctype": "Salary Component",
				"salary_component": name,
				"salary_component_abbr": abbreviation,
				"type": component_type,
				"accounts": [{"company": company, "account": expense}],
			}).insert(ignore_permissions=True))

		assert not frappe.get_meta("Salary Component").has_field("company")
		# Without a reviewed rule, readiness explains that applicability remains
		# open but does not turn every employee into a false payroll blocker.
		result = inspect_statutory_benefit_readiness(employee.name, "2026-09-01", "2026-09-30")
		assert result["status"] == "READY"
		assert result["findings"][0]["code"] == "BENEFIT_RULE_REVIEW_REQUIRED"

		frappe.set_user(hr_user)
		rule = frappe.get_doc({
			"doctype": "Workforce Statutory Benefit Rule Set",
			"title": f"Synthetic PF trigger {token}",
			"company": company,
			"legal_regime": "Bangladesh Labour Act",
			"benefit_type": "Provident Fund",
			"applicability": "Applicable",
			"effective_from": "2026-01-01",
			"pf_trigger_status": "Written Demand Received",
			"trigger_evidence": "Synthetic written-demand evidence reference only; no real workers or demand.",
			"reviewed_permanent_worker_count": 120,
			"written_demand_worker_count": 80,
			"worker_count_as_of": "2026-01-01",
			"minimum_permanent_workers_required": 100,
			"written_demand_numerator": 2,
			"written_demand_denominator": 3,
			"employee_component": components[0].name,
			"employer_component": components[1].name,
			"legal_review_notes": "Synthetic legal fixture only; no actual PF obligation or plan.",
			"sources": [{
				"source_title": "Synthetic Labour Act PF source",
				"source_type": "Amendment Act",
				"act_or_rule": "SYNTHETIC TEST DATA",
				"section_reference": "TEST ONLY",
				"effective_date": "2026-01-01",
				"official_reference": "https://example.test/synthetic-benefit-source",
			}],
		}).insert()
		rules.append(rule)
		# The trigger is backed by explicit reviewed counts, not Employee rows.
		rule.written_demand_worker_count = 79
		with pytest.raises(frappe.ValidationError):
			rule.validate()
		rule.written_demand_worker_count = 80
		rule.reviewed_permanent_worker_count = 99
		with pytest.raises(frappe.ValidationError):
			rule.validate()
		rule.reviewed_permanent_worker_count = 120
		rule.legal_regime = "Bangladesh EPZ Labour Act"
		with pytest.raises(frappe.ValidationError):
			rule.validate()
		rule.legal_regime = "Bangladesh Labour Act"
		rule.validate()
		with pytest.raises(frappe.PermissionError):
			rule.submit()
		rule.reload()
		assert rule.docstatus == 0
		frappe.set_user(director)
		rule.submit()
		assert rule.docstatus == 1

		# A company-unscoped HR operator is rejected before benefit queries run.
		frappe.set_user(unscoped_hr)
		with pytest.raises(frappe.PermissionError):
			inspect_statutory_benefit_readiness(employee.name, "2026-09-01", "2026-09-30")

		frappe.set_user(hr_user)
		result = inspect_statutory_benefit_readiness(employee.name, "2026-09-01", "2026-09-30")
		assert result["status"] == "NEEDS_ATTENTION"
		assert result["benefits"][0]["status"] == "BENEFIT_ENROLLMENT_REQUIRED"

		enrollment = frappe.get_doc({
			"doctype": "Workforce Statutory Benefit Enrollment",
			"employee": employee.name,
			"company": company,
			"benefit_type": "Provident Fund",
			"rule_set": rule.name,
			"participation_status": "Enrolled",
			"external_reference": f"SYNTHETIC-PF-{token}",
			"participation_evidence": "Synthetic employee participation reference only.",
			"effective_from": "2026-01-01",
			"review_notes": "Synthetic enrollment; not a real employee benefit.",
		}).insert()
		enrollments.append(enrollment)
		with pytest.raises(frappe.PermissionError):
			enrollment.submit()
		enrollment.reload()
		assert enrollment.docstatus == 0
		frappe.set_user(director)
		enrollment.submit()
		result = inspect_statutory_benefit_readiness(employee.name, "2026-09-01", "2026-09-30")
		assert result["benefits"][0]["status"] == "STATUTORY_BENEFIT_ACCOUNTING_PATH_REVIEW_REQUIRED"
		assert f"SYNTHETIC-PF-{token}" not in frappe.as_json(result)

		# This staging bench is still on 16.19.0. A later v16 upgrade must make
		# this capability probe true, then remain blocked until full integration proof.
		assert native_employer_contribution_accounting_supported() is False

		# Execute installed Payroll Entry accrual code with a capture seam.
		frappe.set_user("Administrator")
		payroll_entry = frappe.new_doc("Payroll Entry")
		payroll_entry.company = company
		payroll_entry.start_date = "2026-09-01"
		payroll_entry.end_date = "2026-09-30"
		payroll_entry.posting_date = "2026-09-30"
		component_types = []
		payroll_entry.get_salary_component_total = types.MethodType(
			lambda self, component_type, **kwargs: component_types.append(component_type) or {}, payroll_entry
		)
		payroll_entry.make_accrual_jv_entry([])
		assert component_types == ["earnings", "deductions"]

	finally:
		frappe.set_user("Administrator")
		for enrollment in reversed(enrollments):
			if frappe.db.exists(enrollment.doctype, enrollment.name):
				enrollment.reload()
				if enrollment.docstatus == 1:
					enrollment.cancel()
				frappe.delete_doc(enrollment.doctype, enrollment.name, force=True, ignore_permissions=True)
		for rule in reversed(rules):
			if frappe.db.exists(rule.doctype, rule.name):
				rule.reload()
				if rule.docstatus == 1:
					rule.cancel()
				frappe.delete_doc(rule.doctype, rule.name, force=True, ignore_permissions=True)
		for component in components:
			if frappe.db.exists(component.doctype, component.name):
				frappe.delete_doc(component.doctype, component.name, force=True, ignore_permissions=True)
		for user in (unscoped_hr if "unscoped_hr" in locals() else None, director if "director" in locals() else None, hr_user if "hr_user" in locals() else None):
			if user and frappe.db.exists("User", user):
				frappe.delete_doc("User", user, force=True, ignore_permissions=True)
		if company:
			cleanup_synthetic_finalization_company(company)
		frappe.set_user(old_user)
