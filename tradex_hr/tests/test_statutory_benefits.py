from datetime import date
import os

import frappe
import pytest

from tradex_hr.tradexcel_hr import statutory_benefits
from tradex_hr.tradexcel_hr.doctype.tradexcel_statutory_benefit_enrollment import (
	tradexcel_statutory_benefit_enrollment as enrollment_controller,
)
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
		"company": "TCL",
		"branch": "Factory",
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


def test_company_wide_rule_applies_to_branched_employee():
	rule = _rule(
		branch=None,
		benefit_type="Group Insurance",
		pf_trigger_status=None,
		policy_reference="SYNTHETIC-POLICY",
		policy_effective_from="2026-01-01",
		policy_effective_to="2026-12-31",
	)
	result = _check([rule])
	assert result["benefits"][0]["status"] == "GROUP_INSURANCE_EMPLOYEE_COVERAGE_REQUIRED"
	assert result["status"] == "NEEDS_ATTENTION"


def test_branch_specific_rule_does_not_apply_to_another_branch():
	rule = _rule(
		branch="Factory A",
		benefit_type="Group Insurance",
		pf_trigger_status=None,
		policy_reference="SYNTHETIC-POLICY",
		policy_effective_from="2026-01-01",
		policy_effective_to="2026-12-31",
	)
	result = _evaluate_employee(
		"EMP-TEST",
		frappe._dict(company="TCL", branch="Factory B"),
		date(2026, 9, 1), date(2026, 9, 30), [rule], [],
	)
	assert result["benefits"] == []
	assert result["findings"][0]["severity"] == "info"


@pytest.mark.parametrize(
	("policy_from", "policy_to", "expected"),
	[
		("2026-01-01", "2026-12-31", "READY"),
		("2026-10-01", "2026-12-31", "GROUP_INSURANCE_POLICY_REQUIRED"),
		("2026-01-01", "2026-08-31", "GROUP_INSURANCE_POLICY_REQUIRED"),
		("2026-09-15", "2026-12-31", "BENEFIT_MID_PERIOD_CHANGE"),
		("2026-01-01", "2026-09-15", "BENEFIT_MID_PERIOD_CHANGE"),
	],
)
def test_group_insurance_policy_must_cover_entire_payroll_period(policy_from, policy_to, expected):
	rule = _rule(
		benefit_type="Group Insurance",
		pf_trigger_status=None,
		policy_reference="SYNTHETIC-POLICY",
		policy_effective_from=policy_from,
		policy_effective_to=policy_to,
	)
	result = _check([rule], [_enrollment(benefit_type="Group Insurance")])
	assert result["benefits"][0]["status"] == expected


class _LegacyPayrollEntryController:
	def make_accrual_jv_entry(self):
		return None


class _SupportedPayrollEntryController:
	def make_accrual_jv_entry(self):
		self.make_employer_contribution_jv_entry([])

	def make_employer_contribution_jv_entry(self, _rows):
		return None


def test_native_employer_contribution_capability_is_detected_from_controller_shape(monkeypatch):
	monkeypatch.setattr(statutory_benefits, "get_controller", lambda _doctype: _LegacyPayrollEntryController)
	assert statutory_benefits.native_employer_contribution_accounting_supported() is False

	monkeypatch.setattr(statutory_benefits, "get_controller", lambda _doctype: _SupportedPayrollEntryController)
	assert statutory_benefits.native_employer_contribution_accounting_supported() is True


def test_native_capability_without_verified_integration_still_fails_closed(monkeypatch):
	monkeypatch.setattr(statutory_benefits, "native_employer_contribution_accounting_supported", lambda: True)
	result = _check([_rule()], [_enrollment()])
	assert result["benefits"][0]["status"] == "STATUTORY_BENEFIT_NATIVE_ACCOUNTING_UNVERIFIED"
	assert result["status"] == "NEEDS_ATTENTION"


def _validate_enrollment(monkeypatch, *, rule_branch, employee_branch, enrollment_branch, start="2026-01-01", end="2026-12-31", branch_company="TCL"):
	monkeypatch.setattr(enrollment_controller, "assert_company_access", lambda *_args, **_kwargs: None)
	original_get_value = enrollment_controller.frappe.db.get_value

	def get_value(doctype, name, fieldname, **kwargs):
		if doctype == "Employee":
			return frappe._dict(company="TCL", branch=employee_branch)
		if doctype == "Branch":
			return branch_company
		if doctype == "Tradexcel Statutory Benefit Rule Set":
			return frappe._dict(
				docstatus=1,
				company="TCL",
				branch=rule_branch,
				benefit_type="Group Insurance",
				applicability="Applicable",
				effective_from="2026-01-01",
				effective_to="2026-12-31",
			)
		return original_get_value(doctype, name, fieldname, **kwargs)

	monkeypatch.setattr(enrollment_controller.frappe.db, "get_value", get_value)
	monkeypatch.setattr(enrollment_controller.frappe, "get_all", lambda *_args, **_kwargs: [])
	enrollment = enrollment_controller.TradexcelStatutoryBenefitEnrollment.__new__(
		enrollment_controller.TradexcelStatutoryBenefitEnrollment
	)
	for field, value in {
		"doctype": "Tradexcel Statutory Benefit Enrollment",
		"name": "SYNTHETIC-ENROLLMENT",
		"employee": "EMP-TEST",
		"company": "TCL",
		"branch": enrollment_branch,
		"benefit_type": "Group Insurance",
		"rule_set": "SYNTHETIC-RULE",
		"participation_status": "Enrolled",
		"external_reference": "SYNTHETIC-COVERAGE",
		"participation_evidence": "Synthetic evidence",
		"review_notes": "Synthetic enrollment scope test",
		"effective_from": start,
		"effective_to": end,
	}.items():
		setattr(enrollment, field, value)
	enrollment.validate()


def test_company_wide_rule_accepts_current_branch_snapshot(monkeypatch):
	_validate_enrollment(monkeypatch, rule_branch=None, employee_branch="Factory A", enrollment_branch="Factory A")


def test_branch_specific_rule_accepts_same_branch(monkeypatch):
	_validate_enrollment(monkeypatch, rule_branch="Factory A", employee_branch="Factory A", enrollment_branch="Factory A")


def test_branch_specific_rule_rejects_different_enrollment_branch(monkeypatch):
	with pytest.raises(frappe.ValidationError):
		_validate_enrollment(monkeypatch, rule_branch="Factory A", employee_branch="Factory A", enrollment_branch="Factory B")


def test_historical_old_branch_enrollment_survives_employee_transfer(monkeypatch):
	_validate_enrollment(
		monkeypatch, rule_branch=None, employee_branch="Factory B", enrollment_branch="Factory A", end="2026-08-31"
	)


def test_current_enrollment_cannot_retain_old_employee_branch(monkeypatch):
	with pytest.raises(frappe.ValidationError):
		_validate_enrollment(monkeypatch, rule_branch=None, employee_branch="Factory B", enrollment_branch="Factory A")


def test_historical_enrollment_rejects_branch_from_other_company(monkeypatch):
	with pytest.raises(frappe.ValidationError):
		_validate_enrollment(
			monkeypatch, rule_branch=None, employee_branch="Factory B", enrollment_branch="Factory A", end="2026-08-31", branch_company="EFL"
		)
