"""Wage-floor comparisons use explicit rules and native full-period values."""
from __future__ import annotations

from datetime import date
import os

import frappe
import pytest

from workforce_suite.workforce_suite import wage_floor


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


def _configured(monkeypatch, amounts, floors=None, total=11900):
	start, end = date(2026, 9, 1), date(2026, 9, 30)
	rule_summary = frappe._dict({
		"name": "RULE-TEST", "branch": "", "effective_from": start, "effective_to": None,
		"annual_increment_review_required": 0,
	})
	classification = frappe._dict({
		"name": "CLASS-TEST", "effective_from": start, "effective_to": None,
		"branch": "", "coverage_decision": "Covered", "rule_set": "RULE-TEST",
		"worker_category": "Worker", "gazette_grade": "Grade 6", "location_category": "A",
	})
	component_rows = []
	for key, component in (("BASIC", "Basic"), ("HOUSE", "House"), ("MEDICAL", "Medical"), ("TRANSPORT", "Transport"), ("FOOD", "Food")):
		component_rows.append(frappe._dict({
			"floor_type": "Component", "worker_category": "Worker", "gazette_grade": "Grade 6",
			"location_category": "A", "rate_basis": "Monthly", "component_key": key,
			"salary_component": component, "include_in_total_floor": 1,
			"minimum_amount": (floors or {}).get(component, amounts[component]),
		}))
	component_rows.append(frappe._dict({
		"floor_type": "Total", "worker_category": "Worker", "gazette_grade": "Grade 6",
		"location_category": "A", "rate_basis": "Monthly", "component_key": "TOTAL",
		"salary_component": None, "include_in_total_floor": 0, "minimum_amount": total,
	}))
	rule = frappe._dict({"name": "RULE-TEST", "currency": "BDT", "floor_rows": component_rows})
	evaluated = frappe._dict({
		"earnings": [
			frappe._dict({"salary_component": name, "default_amount": amount,
				"statistical_component": 0, "accrual_component": 0, "do_not_include_in_total": 0})
			for name, amount in amounts.items()
		] + [frappe._dict({
			"salary_component": "Overtime", "default_amount": 5000,
			"statistical_component": 0, "accrual_component": 0, "do_not_include_in_total": 0,
		})],
	})
	assignment = frappe._dict({"name": "SSA-TEST", "get_evaluated_components": lambda: evaluated})
	context = {
		"rules": [rule_summary],
		"classifications_by_employee": {"EMP-TEST": [classification]},
	}
	monkeypatch.setattr(wage_floor, "resolve_pay_basis", lambda *_: {
		"status": "Monthly Salary", "assignment": "SSA-TEST", "salary_structure": "STRUCT-TEST",
	})
	monkeypatch.setattr(wage_floor.frappe.db, "get_value", lambda *_args, **_kwargs: "BDT")
	monkeypatch.setattr(wage_floor.frappe, "get_cached_doc", lambda doctype, _name: assignment if doctype == "Salary Structure Assignment" else rule)
	return context, start, end


def test_component_floor_passes_at_exact_values_and_ignores_overtime(monkeypatch):
	amounts = {"Basic": 6000, "House": 3000, "Medical": 1000, "Transport": 600, "Food": 1300}
	context, start, end = _configured(monkeypatch, amounts)

	result = wage_floor.inspect_wage_floor_for_employee(
		"EMP-TEST", start, end, context=context,
		employee_data=frappe._dict({"company": "COMPANY_A", "branch": ""}),
		pay_basis={"status": "Monthly Salary", "assignment": "SSA-TEST", "salary_structure": "STRUCT-TEST"},
	)

	assert result["status"] == "READY"
	assert result["total_package"] == 11900
	assert result["component_values"] == amounts


def test_component_floor_blocks_even_when_total_and_overtime_exceed_floor(monkeypatch):
	amounts = {"Basic": 5500, "House": 3500, "Medical": 1000, "Transport": 600, "Food": 1300}
	context, start, end = _configured(monkeypatch, amounts, floors={"Basic": 6000})

	result = wage_floor.inspect_wage_floor_for_employee(
		"EMP-TEST", start, end, context=context,
		employee_data=frappe._dict({"company": "COMPANY_A", "branch": ""}),
		pay_basis={"status": "Monthly Salary", "assignment": "SSA-TEST", "salary_structure": "STRUCT-TEST"},
	)

	assert result["status"] == "WAGE_FLOOR_BELOW_MINIMUM"
	assert any(f["code"] == "WAGE_COMPONENT_BELOW_MINIMUM" and f["component"] == "BASIC" for f in result["findings"])


def test_total_floor_blocks_when_every_component_floor_passes(monkeypatch):
	amounts = {"Basic": 6000, "House": 3000, "Medical": 1000, "Transport": 600, "Food": 1300}
	context, start, end = _configured(monkeypatch, amounts, total=12000)

	result = wage_floor.inspect_wage_floor_for_employee(
		"EMP-TEST", start, end, context=context,
		employee_data=frappe._dict({"company": "COMPANY_A", "branch": ""}),
		pay_basis={"status": "Monthly Salary", "assignment": "SSA-TEST", "salary_structure": "STRUCT-TEST"},
	)

	assert result["status"] == "WAGE_FLOOR_BELOW_MINIMUM"
	assert [finding["code"] for finding in result["findings"]] == ["WAGE_TOTAL_BELOW_MINIMUM"]


def test_missing_component_mapping_and_daily_conversion_fail_closed(monkeypatch):
	amounts = {"Basic": 6000, "House": 3000, "Medical": 1000, "Transport": 600, "Food": 1300}
	context, start, end = _configured(monkeypatch, amounts)
	context["classifications_by_employee"]["EMP-TEST"][0].location_category = "Missing"
	missing_row = wage_floor.inspect_wage_floor_for_employee(
		"EMP-TEST", start, end, context=context,
		employee_data=frappe._dict({"company": "COMPANY_A", "branch": ""}),
		pay_basis={"status": "Monthly Salary", "assignment": "SSA-TEST", "salary_structure": "STRUCT-TEST"},
	)
	assert missing_row["status"] == "WAGE_FLOOR_RULE_REVIEW_REQUIRED"

	context, start, end = _configured(monkeypatch, amounts)
	daily = wage_floor.inspect_wage_floor_for_employee(
		"EMP-TEST", start, end, context=context,
		employee_data=frappe._dict({"company": "COMPANY_A", "branch": ""}),
		pay_basis={"status": "Daily Wage", "assignment": "SSA-TEST", "salary_structure": "STRUCT-TEST"},
	)
	assert daily["status"] == "WAGE_RATE_CONVERSION_REVIEW_REQUIRED"


def test_period_with_no_approved_scope_is_not_called_compliant(monkeypatch):
	result = wage_floor.inspect_wage_floor_for_employee(
		"EMP-TEST", date(2026, 9, 1), date(2026, 9, 30),
		context={"rules": [], "classifications_by_employee": {}},
		employee_data=frappe._dict({"company": "COMPANY_A", "branch": ""}),
	)

	assert result["status"] == "NOT_IN_CONFIGURED_SCOPE"


def test_mid_period_rule_change_is_reviewed(monkeypatch):
	context, start, end = _configured(
		monkeypatch,
		{"Basic": 6000, "House": 3000, "Medical": 1000, "Transport": 600, "Food": 1300},
	)
	context["rules"][0].effective_from = date(2026, 9, 15)
	result = wage_floor.inspect_wage_floor_for_employee(
		"EMP-TEST", start, end, context=context,
		employee_data=frappe._dict({"company": "COMPANY_A", "branch": ""}),
	)
	assert result["status"] == "WAGE_FLOOR_MID_PERIOD_CHANGE"


def test_outside_scope_decision_is_bound_to_exact_rule_version(monkeypatch):
	context, start, end = _configured(
		monkeypatch,
		{"Basic": 6000, "House": 3000, "Medical": 1000, "Transport": 600, "Food": 1300},
	)
	classification = context["classifications_by_employee"]["EMP-TEST"][0]
	classification.coverage_decision = "Reviewed Outside Scope"
	classification.worker_category = None
	classification.gazette_grade = None
	classification.location_category = None

	accepted = wage_floor.inspect_wage_floor_for_employee(
		"EMP-TEST", start, end, context=context,
		employee_data=frappe._dict({"company": "COMPANY_A", "branch": ""}),
	)
	assert accepted["status"] == "REVIEWED_OUTSIDE_SCOPE"

	context["rules"][0].name = "RULE-NEW-VERSION"
	review_required = wage_floor.inspect_wage_floor_for_employee(
		"EMP-TEST", start, end, context=context,
		employee_data=frappe._dict({"company": "COMPANY_A", "branch": ""}),
	)
	assert review_required["status"] == "WAGE_CLASSIFICATION_REQUIRED"


def test_historical_classification_keeps_its_establishment_after_transfer(monkeypatch):
	context, _start, _end = _configured(
		monkeypatch,
		{"Basic": 6000, "House": 3000, "Medical": 1000, "Transport": 600, "Food": 1300},
	)
	start, end = date(2026, 8, 1), date(2026, 8, 31)
	rule = context["rules"][0]
	rule.branch = "Old Factory"
	rule.effective_from = start
	classification = context["classifications_by_employee"]["EMP-TEST"][0]
	classification.branch = "Old Factory"
	classification.effective_from = start

	result = wage_floor.inspect_wage_floor_for_employee(
		"EMP-TEST", start, end, context=context,
		employee_data=frappe._dict({"company": "COMPANY_A", "branch": "New Factory"}),
		pay_basis={"status": "Monthly Salary", "assignment": "SSA-TEST", "salary_structure": "STRUCT-TEST"},
	)
	assert result["status"] == "READY"


def test_current_period_requires_review_after_establishment_transfer(monkeypatch):
	context, start, end = _configured(
		monkeypatch,
		{"Basic": 6000, "House": 3000, "Medical": 1000, "Transport": 600, "Food": 1300},
	)
	classification = context["classifications_by_employee"]["EMP-TEST"][0]
	classification.branch = "Old Factory"
	rule = context["rules"][0]
	rule.branch = "Old Factory"

	result = wage_floor.inspect_wage_floor_for_employee(
		"EMP-TEST", start, end, context=context,
		employee_data=frappe._dict({"company": "COMPANY_A", "branch": "New Factory"}),
	)
	assert result["status"] == "WAGE_CLASSIFICATION_REQUIRED"
