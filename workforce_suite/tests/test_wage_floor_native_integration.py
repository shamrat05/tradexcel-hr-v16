"""Exercise wage-floor evaluation through native HRMS salary structures."""
from __future__ import annotations

from datetime import date
import os

import frappe
import pytest


@pytest.fixture(scope="module", autouse=True)
def frappe_site():
	frappe.init(
		site=os.environ.get("FRAPPE_TEST_SITE", "test_workforce.localhost"),
		sites_path=os.environ.get("FRAPPE_TEST_SITES_PATH", "./sites"),
		force=True,
	)
	frappe.connect()
	yield
	frappe.destroy()


def test_native_assignment_full_period_amounts_feed_wage_floor(monkeypatch):
	from workforce_suite.tests.test_payroll_finalization_integration import (
		_component,
		_create_assignment,
		_create_employee,
		_create_scoped_user,
		_create_synthetic_company,
		cleanup_synthetic_finalization_company,
	)
	from workforce_suite.workforce_suite import wage_floor

	token = frappe.generate_hash(8).upper()[:8]
	company = None
	components = []
	draft_rule = None
	approved_rule = None
	classification_doc = None
	old_user = frappe.session.user
	try:
		frappe.set_user("Administrator")
		company, abbreviation, payable, expense, cost_center, holiday_list = _create_synthetic_company(token, monkeypatch)
		from workforce_suite.role_setup import ensure_workforce_roles
		ensure_workforce_roles()
		hr_user = _create_scoped_user("Workforce Suite Manager", company, token)
		director = _create_scoped_user("Workforce Owner/Director", company, token)
		assert frappe.has_permission("Workforce Wage Floor Rule Set", "create", user=hr_user)
		assert not frappe.has_permission("Workforce Wage Floor Rule Set", "submit", user=hr_user)
		assert frappe.has_permission("Workforce Wage Floor Rule Set", "submit", user=director)
		assert frappe.has_permission("Workforce Wage Floor Classification", "submit", user=director)
		employee = _create_employee(f"Wage Test {token}", company, holiday_list)
		amounts = {"Basic": 12000, "House": 6000, "Medical": 1000, "Transport": 1000}
		for index, (label, amount) in enumerate(amounts.items()):
			components.append(_component(f"{label} Wage Test {token}", f"W{token[:3]}{index}", company, expense))
		structure = frappe.get_doc({
			"doctype": "Salary Structure",
			"name": f"Wage Test Structure {token}",
			"company": company,
			"currency": "BDT",
			"payroll_frequency": "Monthly",
			"is_active": "Yes",
			"custom_workforce_pay_basis": "Monthly Salary",
			"earnings": [
				{"salary_component": component.name, "amount": amounts[label]}
				for label, component in zip(amounts, components)
			],
		}).insert(ignore_permissions=True)
		structure.submit()
		assignment = _create_assignment(
			employee.name, company, "BDT", payable, structure.name, 20000, cost_center,
			from_date="2026-09-01",
		)

		# A government proposal is source evidence for review, never an active rule.
		frappe.set_user("Administrator")
		draft_rule = frappe.get_doc({
			"doctype": "Workforce Wage Floor Rule Set",
			"title": f"Synthetic Draft Proposal {token} (not law)",
			"company": company,
			"jurisdiction": "Bangladesh",
			"legal_regime": "Bangladesh Labour Act",
			"industry_sector": "Synthetic test sector; not a real classification",
			"establishment_reference": "Synthetic test establishment only",
			"currency": "BDT",
			"effective_from": "2026-09-01",
			"legal_review_notes": "Synthetic test record; it has no legal authority.",
			"sources": [{
				"source_title": "Synthetic test proposal (not law)",
				"authority_status": "Draft Recommendation",
				"issuing_authority": "Synthetic test issuer",
				"notification_number": "TEST-DRAFT",
				"publication_date": "2026-08-14",
				"effective_date": "2026-09-01",
				"section_reference": "TEST ONLY",
				"official_reference": "https://example.test/not-a-law",
			}],
			"floor_rows": [
				{
					"worker_category": "Worker", "gazette_grade": "Synthetic Grade 6",
					"location_category": "Synthetic Location", "rate_basis": "Monthly",
					"floor_type": "Component", "component_key": f"TEST-{index}",
					"salary_component": component.name, "include_in_total_floor": 1,
					"minimum_amount": amounts[label],
				}
				for index, (label, component) in enumerate(zip(amounts, components))
			] + [{
				"worker_category": "Worker", "gazette_grade": "Synthetic Grade 6",
				"location_category": "Synthetic Location", "rate_basis": "Monthly",
				"floor_type": "Total", "component_key": "TOTAL",
				"include_in_total_floor": 0, "minimum_amount": 20000,
			}],
		}).insert(ignore_permissions=True)
		assert type(draft_rule).__name__ == "WorkforceWageFloorRuleSet"
		assert draft_rule.sources[0].authority_status == "Draft Recommendation"
		with pytest.raises(frappe.ValidationError, match="Final Gazette"):
			draft_rule.before_submit()
		with pytest.raises(frappe.ValidationError, match="Final Gazette"):
			draft_rule.submit()
		assert frappe.db.get_value(draft_rule.doctype, draft_rule.name, "docstatus") == 0
		draft_rule.append("sources", {
			"source_title": "Synthetic older final gazette (not law)",
			"authority_status": "Final Gazette",
			"issuing_authority": "Synthetic test issuer",
			"notification_number": "TEST-FINAL",
			"publication_date": "2020-01-01",
			"effective_date": "2020-01-01",
			"section_reference": "TEST ONLY",
			"official_reference": "https://example.test/not-a-law",
		})
		with pytest.raises(frappe.ValidationError, match="Every source"):
			draft_rule.before_submit()
		frappe.delete_doc(draft_rule.doctype, draft_rule.name, force=True, ignore_permissions=True)
		draft_rule = None

		# This is HRMS's own formula/value evaluator. It returns default_amount
		# before Salary Slip payment-day proration; no Workforce salary formula runs.
		evaluated = assignment.get_evaluated_components()
		full_period = {row.salary_component: float(row.default_amount) for row in evaluated.earnings}
		assert sorted(full_period.values()) == [1000.0, 1000.0, 6000.0, 12000.0]

		component_rows = []
		for key, label in (("BASIC", "Basic"), ("HOUSE", "House"), ("MEDICAL", "Medical"), ("TRANSPORT", "Transport")):
			component = next(row for row in components if row.salary_component.startswith(label))
			component_rows.append(frappe._dict({
				"floor_type": "Component", "component_key": key,
				"worker_category": "Worker", "gazette_grade": "Synthetic Grade 6",
				"location_category": "Synthetic Location", "rate_basis": "Monthly",
				"salary_component": component.name, "include_in_total_floor": 1,
				"minimum_amount": amounts[label],
			}))
		component_rows.append(frappe._dict({
			"floor_type": "Total", "component_key": "TOTAL", "worker_category": "Worker",
			"gazette_grade": "Synthetic Grade 6", "location_category": "Synthetic Location",
			"rate_basis": "Monthly", "salary_component": None,
			"include_in_total_floor": 0, "minimum_amount": 20000,
		}))
		classification = frappe._dict({
			"name": "SYNTHETIC-CLASSIFICATION", "effective_from": date(2026, 9, 1),
			"effective_to": None, "branch": "", "coverage_decision": "Covered",
			"rule_set": "SYNTHETIC-RULE", "worker_category": "Worker",
			"gazette_grade": "Synthetic Grade 6", "location_category": "Synthetic Location",
		})
		rule_summary = frappe._dict({
			"name": "SYNTHETIC-RULE", "branch": "", "effective_from": date(2026, 9, 1),
			"effective_to": None, "annual_increment_review_required": 0,
		})
		rule = frappe._dict({"name": "SYNTHETIC-RULE", "currency": "BDT", "floor_rows": component_rows})
		get_cached_doc = frappe.get_cached_doc
		monkeypatch.setattr(
			wage_floor.frappe,
			"get_cached_doc",
			lambda doctype, name: rule if doctype == "Workforce Wage Floor Rule Set" else get_cached_doc(doctype, name),
		)
		result = wage_floor.inspect_wage_floor_for_employee(
			employee.name,
			date(2026, 9, 1),
			date(2026, 9, 30),
			context={"rules": [rule_summary], "classifications_by_employee": {employee.name: [classification]}},
			employee_data={"company": company, "branch": ""},
			pay_basis={"status": "Monthly Salary", "assignment": assignment.name, "salary_structure": structure.name},
		)
		assert result["status"] == "READY", result
		assert result["component_values"] == full_period
		assert result["total_package"] == 20000

		# A synthetic final source/rule tests actual maker-checker and persistence.
		frappe.set_user(hr_user)
		approved_rule = frappe.get_doc({
			"doctype": "Workforce Wage Floor Rule Set",
			"title": f"Synthetic wage floor rule {token} (not law)",
			"company": company,
			"jurisdiction": "Bangladesh",
			"legal_regime": "Bangladesh Labour Act",
			"industry_sector": f"Synthetic test sector {token}",
			"establishment_reference": "Synthetic test establishment only",
			"currency": "BDT",
			"effective_from": "2026-09-01",
			"legal_review_notes": "Synthetic test values and source. Not an operative legal rule.",
			"sources": [{
				"source_title": "Synthetic final notification (not law)",
				"authority_status": "Final Gazette",
				"issuing_authority": "Synthetic test issuer",
				"notification_number": f"TEST-FINAL-{token}",
				"publication_date": "2026-08-01",
				"effective_date": "2026-09-01",
				"section_reference": "TEST ONLY",
				"official_reference": "https://example.test/synthetic-only",
			}],
			"floor_rows": [
				{
					"worker_category": "Worker", "gazette_grade": "Synthetic Grade 6",
					"location_category": "Synthetic Location", "rate_basis": "Monthly",
					"floor_type": "Component", "component_key": f"TEST-{index}",
					"salary_component": component.name, "include_in_total_floor": 1,
					"minimum_amount": amounts[label],
				}
				for index, (label, component) in enumerate(zip(amounts, components))
			] + [{
				"worker_category": "Worker", "gazette_grade": "Synthetic Grade 6",
				"location_category": "Synthetic Location", "rate_basis": "Monthly",
				"floor_type": "Total", "component_key": "TOTAL",
				"include_in_total_floor": 0, "minimum_amount": 20000,
			}],
		})
		assert frappe.session.user == hr_user
		assert frappe.db.exists("User Permission", {"user": hr_user, "allow": "Company", "for_value": company})
		assert wage_floor.wage_floor_has_permission(approved_rule, "create", user=hr_user) is True
		assert frappe.has_permission(approved_rule.doctype, "create", doc=approved_rule)
		approved_rule.insert()
		with pytest.raises(frappe.PermissionError):
			approved_rule.submit()
		frappe.set_user(director)
		approved_rule.reload().submit()
		assert approved_rule.reviewed_by == director

		frappe.set_user(hr_user)
		classification_doc = frappe.get_doc({
			"doctype": "Workforce Wage Floor Classification",
			"employee": employee.name,
			"company": company,
			"coverage_decision": "Covered",
			"rule_set": approved_rule.name,
			"worker_category": "Worker",
			"gazette_grade": "Synthetic Grade 6",
			"location_category": "Synthetic Location",
			"effective_from": "2026-09-01",
			"legal_review_notes": "Synthetic test classification only; not a real legal decision.",
		}).insert()
		with pytest.raises(frappe.PermissionError):
			classification_doc.submit()
		frappe.set_user(director)
		classification_doc.reload().submit()
		assert classification_doc.reviewed_by == director

		# The persisted immutable versions drive the same native component check.
		monkeypatch.setattr(wage_floor.frappe, "get_cached_doc", get_cached_doc)
		frappe.set_user("Administrator")
		persisted_context = wage_floor.prepare_wage_floor_context(
			company, date(2026, 9, 1), date(2026, 9, 30), [employee.name],
		)
		persisted_result = wage_floor.inspect_wage_floor_for_employee(
			employee.name,
			date(2026, 9, 1),
			date(2026, 9, 30),
			context=persisted_context,
			employee_data={"company": company, "branch": ""},
			pay_basis={"status": "Monthly Salary", "assignment": assignment.name, "salary_structure": structure.name},
		)
		assert persisted_result["status"] == "READY", persisted_result
		assert persisted_result["rule_set"] == approved_rule.name
		assert persisted_result["classification"] == classification_doc.name
	finally:
		frappe.set_user("Administrator")
		if classification_doc and frappe.db.exists(classification_doc.doctype, classification_doc.name):
			classification_doc.reload()
			if classification_doc.docstatus == 1:
				classification_doc.cancel()
			frappe.delete_doc(classification_doc.doctype, classification_doc.name, force=True, ignore_permissions=True)
		if approved_rule and frappe.db.exists(approved_rule.doctype, approved_rule.name):
			approved_rule.reload()
			if approved_rule.docstatus == 1:
				approved_rule.cancel()
			frappe.delete_doc(approved_rule.doctype, approved_rule.name, force=True, ignore_permissions=True)
		if draft_rule and frappe.db.exists(draft_rule.doctype, draft_rule.name):
			frappe.delete_doc(draft_rule.doctype, draft_rule.name, force=True, ignore_permissions=True)
		if company:
			cleanup_synthetic_finalization_company(company)
		frappe.set_user(old_user)


def test_historical_branch_classification_and_source_effective_dates(monkeypatch):
	"""Historical scopes follow the reviewed Rule Set, not today's Employee Branch."""
	from workforce_suite.tests.test_payroll_finalization_integration import (
		_component,
		_create_employee,
		_create_scoped_user,
		_create_synthetic_company,
		cleanup_synthetic_finalization_company,
	)

	token = frappe.generate_hash(8).upper()[:8]
	company = None
	rules = []
	classification = None
	branches = []
	components = []
	old_user = frappe.session.user
	try:
		frappe.set_user("Administrator")
		company, _abbr, _payable, expense, _cost_center, holiday_list = _create_synthetic_company(token, monkeypatch)
		old_branch = f"Wage Old {token}"
		new_branch = f"Wage New {token}"
		for branch in (old_branch, new_branch):
			frappe.get_doc({"doctype": "Branch", "branch": branch, "company": company}).insert(ignore_permissions=True)
			branches.append(branch)

		employee = _create_employee(f"Historical Wage Test {token}", company, holiday_list)
		frappe.db.set_value("Employee", employee.name, "branch", new_branch)
		components.extend(
			_component(f"{label} History Test {token}", f"H{token[:3]}{index}", company, expense)
			for index, label in enumerate(("Basic", "House", "Medical", "Transport"))
		)

		def make_rule(title, branch, effective_from, source_dates):
			doc = frappe.get_doc({
				"doctype": "Workforce Wage Floor Rule Set",
				"title": f"{title} {token}",
				"company": company,
				"branch": branch,
				"jurisdiction": "Bangladesh",
			"legal_regime": "Bangladesh Labour Act",
				"industry_sector": f"Synthetic historical sector {token}",
				"establishment_reference": "Synthetic test establishment only",
				"currency": "BDT",
				"effective_from": effective_from,
				"effective_to": "2026-06-30" if effective_from <= "2026-06-30" else None,
				"legal_review_notes": "Synthetic test only; not an operative wage rule.",
				"sources": [{
					"source_title": f"Synthetic source {index} {token}",
					"authority_status": "Final Gazette",
					"issuing_authority": "Synthetic test issuer",
					"notification_number": f"TEST-{token}-{index}",
					"publication_date": "2026-01-01",
					"effective_date": source_date,
					"section_reference": "TEST ONLY",
					"official_reference": "https://example.test/synthetic-only",
				} for index, source_date in enumerate(source_dates)],
				"floor_rows": [{
					"worker_category": "Worker", "gazette_grade": "Synthetic Grade",
					"location_category": "Synthetic Location", "rate_basis": "Monthly",
					"floor_type": "Component", "component_key": f"TEST-{index}",
					"salary_component": component.name, "include_in_total_floor": 1,
					"minimum_amount": 1000,
				} for index, component in enumerate(components)] + [{
					"worker_category": "Worker", "gazette_grade": "Synthetic Grade",
					"location_category": "Synthetic Location", "rate_basis": "Monthly",
					"floor_type": "Total", "component_key": "TOTAL",
					"include_in_total_floor": 0, "minimum_amount": 4000,
				}],
			})
			doc.insert(ignore_permissions=True)
			rules.append(doc)
			return doc

		# A final source effective in October cannot authorize a September rule.
		bad_rule = make_rule("Bad source date", "", "2026-09-01", ["2026-01-01", "2026-10-01"])
		director = _create_scoped_user("Workforce Owner/Director", company, token)
		frappe.set_user(director)
		with pytest.raises(frappe.ValidationError, match="effective date"):
			bad_rule.submit()
		assert bad_rule.reload().docstatus == 0
		frappe.delete_doc(bad_rule.doctype, bad_rule.name, force=True, ignore_permissions=True)
		rules.remove(bad_rule)

		# A later supporting source sets the earliest permissible rule start.
		frappe.set_user("Administrator")
		old_rule = make_rule("Historical old establishment", old_branch, "2026-06-01", ["2020-01-01", "2026-06-01"])
		new_rule = make_rule("Historical other establishment", new_branch, "2026-06-01", ["2026-06-01"])
		hr_user = _create_scoped_user("Workforce Suite Manager", company, token)
		frappe.set_user(hr_user)
		frappe.set_user(director)
		old_rule.reload().submit()
		new_rule.submit()

		frappe.set_user(hr_user)
		classification = frappe.get_doc({
			"doctype": "Workforce Wage Floor Classification",
			"employee": employee.name,
			"company": company,
			"branch": old_branch,
			"coverage_decision": "Covered",
			"rule_set": old_rule.name,
			"worker_category": "Worker",
			"gazette_grade": "Synthetic Grade",
			"location_category": "Synthetic Location",
			"effective_from": "2026-06-01",
			"effective_to": "2026-06-30",
			"legal_review_notes": "Synthetic historical branch snapshot only.",
		}).insert()
		frappe.set_user(director)
		classification.reload().submit()
		assert classification.docstatus == 1

		# The same branch cannot be paired with a Rule Set scoped elsewhere.
		frappe.set_user(hr_user)
		with pytest.raises(frappe.ValidationError, match="match the Employee"):
			frappe.get_doc({
				"doctype": "Workforce Wage Floor Classification",
				"employee": employee.name,
				"company": company,
				"branch": old_branch,
				"coverage_decision": "Covered",
				"rule_set": new_rule.name,
				"worker_category": "Worker",
				"gazette_grade": "Synthetic Grade",
				"location_category": "Synthetic Location",
				"effective_from": "2026-07-01",
				"effective_to": "2026-07-31",
				"legal_review_notes": "Synthetic mismatch test only.",
			}).insert()

		# A historical Branch owned by another Company remains invalid.
		foreign_branch = frappe.db.get_value("Branch", {"company": "Example Company B"}, "name")
		assert foreign_branch
		with pytest.raises(frappe.ValidationError, match="belong to the Employee's Company"):
			frappe.get_doc({
				"doctype": "Workforce Wage Floor Classification",
				"employee": employee.name,
				"company": company,
				"branch": foreign_branch,
				"coverage_decision": "Covered",
				"rule_set": old_rule.name,
				"worker_category": "Worker",
				"gazette_grade": "Synthetic Grade",
				"location_category": "Synthetic Location",
				"effective_from": "2026-06-01",
				"effective_to": "2026-06-30",
				"legal_review_notes": "Synthetic cross-company branch test only.",
			}).insert()

		# A future classification cannot retain the Employee's old establishment.
		with pytest.raises(frappe.ValidationError, match="current Employee Branch"):
			frappe.get_doc({
				"doctype": "Workforce Wage Floor Classification",
				"employee": employee.name,
				"company": company,
				"branch": old_branch,
				"coverage_decision": "Covered",
				"rule_set": old_rule.name,
				"worker_category": "Worker",
				"gazette_grade": "Synthetic Grade",
				"location_category": "Synthetic Location",
				"effective_from": "2026-10-01",
				"effective_to": "2026-10-31",
				"legal_review_notes": "Synthetic stale current branch test only.",
			}).insert()
	finally:
		frappe.set_user("Administrator")
		if classification and frappe.db.exists(classification.doctype, classification.name):
			classification.reload()
			if classification.docstatus == 1:
				classification.cancel()
			frappe.delete_doc(classification.doctype, classification.name, force=True, ignore_permissions=True)
		for rule in rules:
			if frappe.db.exists(rule.doctype, rule.name):
				rule.reload()
				if rule.docstatus == 1:
					rule.cancel()
				frappe.delete_doc(rule.doctype, rule.name, force=True, ignore_permissions=True)
		for branch in branches:
			if frappe.db.exists("Branch", branch):
				frappe.delete_doc("Branch", branch, force=True, ignore_permissions=True)
		for component in components:
			if frappe.db.exists("Salary Component", component.name):
				frappe.delete_doc("Salary Component", component.name, force=True, ignore_permissions=True)
		if company:
			cleanup_synthetic_finalization_company(company)
		frappe.set_user(old_user)
