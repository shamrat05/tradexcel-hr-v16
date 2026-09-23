from datetime import date
import os

import frappe
import pytest

from tradex_hr.tradexcel_hr.statutory_benefits import _evaluate_employee


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


def _rule(**overrides):
	values = {
		"name": "TEST-BENEFIT-RULE",
		"company": "TCL",
		"branch": "Factory",
		"legal_regime": "Bangladesh Labour Act",
		"benefit_type": "Provident Fund",
		"applicability": "Applicable",
		"effective_from": "2026-01-01",
		"effective_to": None,
		"pf_trigger_status": "Written Demand Received",
		"policy_reference": None,
		"policy_effective_from": None,
		"policy_effective_to": None,
		"employee_component": "Employee PF",
		"employer_component": "Employer PF",
	}
	values.update(overrides)
	return frappe._dict(values)


def _enrollment(**overrides):
	values = {
		"name": "TEST-BENEFIT-ENROLLMENT",
		"employee": "EMP-TEST",
		"rule_set": "TEST-BENEFIT-RULE",
		"benefit_type": "Provident Fund",
		"participation_status": "Enrolled",
		"effective_from": "2026-01-01",
		"effective_to": None,
	}
	values.update(overrides)
	return frappe._dict(values)


def _check(rules, enrollments=None, start="2026-09-01", end="2026-09-30"):
	return _evaluate_employee(
		"EMP-TEST",
		frappe._dict(company="TCL", branch="Factory"),
		date.fromisoformat(start),
		date.fromisoformat(end),
		rules,
		enrollments or [],
	)


def test_no_approved_benefit_rule_is_informational_not_false_compliance_or_block():
	result = _check([])
	assert result["status"] == "READY"
	assert result["findings"][0]["code"] == "BENEFIT_RULE_REVIEW_REQUIRED"
	assert result["findings"][0]["severity"] == "info"


def test_reviewed_pf_not_triggered_does_not_require_enrollment():
	result = _check([_rule(applicability="Not Applicable", pf_trigger_status="Not Triggered")])
	assert result["status"] == "READY"
	assert result["benefits"][0]["status"] == "NOT_APPLICABLE"


def test_applicable_pf_without_enrollment_blocks():
	result = _check([_rule()])
	assert result["status"] == "NEEDS_ATTENTION"
	assert result["benefits"][0]["status"] == "BENEFIT_ENROLLMENT_REQUIRED"


def test_pf_enrollment_fails_closed_on_native_employer_accrual_gap():
	result = _check([_rule()], [_enrollment()])
	assert result["status"] == "NEEDS_ATTENTION"
	assert result["benefits"][0]["status"] == "STATUTORY_BENEFIT_ACCOUNTING_PATH_REVIEW_REQUIRED"


def test_progoti_opt_out_is_explicit_and_does_not_create_employer_contribution():
	result = _check(
		[_rule(benefit_type="Progoti Pension", pf_trigger_status=None)],
		[_enrollment(benefit_type="Progoti Pension", participation_status="Opted Out in Writing")],
	)
	assert result["status"] == "READY"
	assert result["benefits"][0]["status"] == "PROGOTI_OPTED_OUT"


def test_group_insurance_uses_policy_and_employee_coverage_without_payroll_money():
	rule = _rule(
		benefit_type="Group Insurance", pf_trigger_status=None,
		policy_reference="SYNTHETIC-POLICY", policy_effective_from="2026-01-01",
		policy_effective_to="2026-12-31", employee_component=None, employer_component=None,
	)
	enrollment = _enrollment(
		benefit_type="Group Insurance", participation_status="Enrolled",
	)
	result = _check([rule], [enrollment])
	assert result["status"] == "READY"
	assert result["benefits"][0]["status"] == "READY"


def test_mid_period_rule_change_fails_closed():
	result = _check([_rule(effective_from="2026-09-15")])
	assert result["status"] == "NEEDS_ATTENTION"
	assert result["benefits"][0]["status"] == "BENEFIT_MID_PERIOD_CHANGE"



def test_enrollment_starting_mid_period_requires_explicit_timing_review():
	result = _check(
		[_rule()],
		[_enrollment(effective_from="2026-09-15")],
	)
	assert result["status"] == "NEEDS_ATTENTION"
	assert result["benefits"][0]["status"] == "BENEFIT_MID_PERIOD_CHANGE"


def test_enrollment_ending_mid_period_requires_explicit_timing_review():
	result = _check(
		[_rule()],
		[_enrollment(effective_from="2026-01-01", effective_to="2026-09-10")],
	)
	assert result["status"] == "NEEDS_ATTENTION"
	assert result["benefits"][0]["status"] == "BENEFIT_MID_PERIOD_CHANGE"


def test_batch_evaluator_accepts_native_employee_dictionary_rows():
    result = _evaluate_employee(
        "EMP-DICT",
        {"company": "TCL", "branch": "Factory"},
        date(2026, 9, 1),
        date(2026, 9, 30),
        [],
        [],
    )
    assert result["company"] == "TCL"
    assert result["status"] == "READY"
