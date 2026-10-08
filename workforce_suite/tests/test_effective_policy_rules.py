from datetime import date, datetime

import pytest
import frappe

from workforce_suite.workforce_suite.effective_policy_rules import (
    RuleConflict,
    preview_change,
    resolve_values,
    validate_rule,
)
from workforce_suite.workforce_suite.payroll_policy import resolve_policy


EMPLOYEE = {
    "name": "EMP-1",
    "company": "COMPANY_A",
    "branch": "Factory",
    "department": "Loading",
    "designation": "Operator",
    "date_of_joining": "2021-09-01",
}


def rule(name, field, value, **scope):
    return {
        "name": name,
        "field_name": field,
        "value": value,
        "company": "COMPANY_A",
        "effective_from": "2026-09-01",
        **scope,
    }


def test_employee_exception_wins_and_other_fields_inherit():
    rules = [
        rule("factory", "daily_wage", 350, branch="Factory"),
        rule("personal", "daily_wage", 400, employee="EMP-1"),
        rule("break", "break_minutes", 0, branch="Factory"),
    ]
    result = resolve_values(EMPLOYEE, date(2026, 9, 17), rules)
    assert result["daily_wage"]["value"] == 400
    assert result["daily_wage"]["rule"] == "personal"
    assert result["break_minutes"]["value"] == 0


def test_designation_and_department_conflict_instead_of_arbitrary_rank():
    rules = [
        rule("designation", "daily_wage", 400, designation="Operator"),
        rule("department", "daily_wage", 350, department="Loading"),
    ]
    with pytest.raises(RuleConflict, match="daily_wage"):
        resolve_values(EMPLOYEE, date(2026, 9, 17), rules)


def test_tenure_is_condition_and_more_restrictive_threshold_wins():
    rules = [
        rule("four-years", "daily_wage", 375, min_tenure_months=48),
        rule("five-years", "daily_wage", 400, min_tenure_months=60),
    ]
    newer_hire = {**EMPLOYEE, "date_of_joining": "2021-10-01"}
    assert resolve_values(newer_hire, date(2026, 9, 17), rules)["daily_wage"]["value"] == 375
    assert resolve_values(EMPLOYEE, date(2026, 9, 17), rules)["daily_wage"]["value"] == 400


def test_narrower_department_but_lower_tenure_is_incomparable():
    rules = [
        rule("department", "daily_wage", 400, department="Loading"),
        rule("veteran", "daily_wage", 375, min_tenure_months=60),
    ]
    with pytest.raises(RuleConflict):
        resolve_values(EMPLOYEE, date(2026, 9, 17), rules)


def test_effective_window_and_later_version_same_scope():
    rules = [
        rule("old", "daily_wage", 350, branch="Factory"),
        rule("new", "daily_wage", 375, branch="Factory", effective_from="2026-09-17"),
        rule("expired", "break_minutes", 0, effective_to="2026-09-16"),
    ]
    assert resolve_values(EMPLOYEE, date(2026, 9, 16), rules)["daily_wage"]["value"] == 350
    result = resolve_values(EMPLOYEE, date(2026, 9, 17), rules)
    assert result["daily_wage"]["value"] == 375
    assert "break_minutes" not in result


def test_different_companies_and_future_rules_do_not_apply():
    rules = [
        rule("other", "daily_wage", 500, company="COMPANY_B"),
        rule("future", "daily_wage", 400, effective_from="2026-09-18"),
    ]
    assert resolve_values(EMPLOYEE, date(2026, 9, 17), rules) == {}


def test_equal_rank_different_values_are_blocked():
    rules = [rule("a", "daily_wage", 350), rule("b", "daily_wage", 400)]
    with pytest.raises(RuleConflict):
        resolve_values(EMPLOYEE, date(2026, 9, 17), rules)


def test_employee_category_limits_rule_and_datetime_input_is_safe():
    rules = [rule("workers", "daily_wage", 350, employee_category="Worker")]
    staff = {**EMPLOYEE, "employment_type": "Employee"}
    worker = {**EMPLOYEE, "employment_type": "Worker"}
    assert resolve_values(staff, datetime(2026, 9, 17, 9), rules) == {}
    assert resolve_values(worker, datetime(2026, 9, 17, 9), rules)["daily_wage"]["value"] == 350


def test_preview_is_dated_and_flags_submitted_slip_without_mutating_inputs():
    proposed = rule("new", "daily_wage", 400, employee="EMP-1", effective_from="2026-09-16")
    slips = [{"employee": "EMP-1", "name": "SLIP-1", "start_date": "2026-09-01", "end_date": "2026-09-30"}]
    result = preview_change(
        [EMPLOYEE], [], proposed, "2026-09-15", "2026-09-17", slips,
        base_value=lambda employee, day, field: 350,
    )
    assert result["affected_days"] == 2
    assert result["changes"][0]["from_date"] == "2026-09-16"
    assert result["changes"][0]["to_date"] == "2026-09-17"
    assert result["changes"][0]["old_value"] == 350
    assert result["changes"][0]["new_value"] == 400
    assert result["submitted_slips"] == ["SLIP-1"]
    assert "docstatus" not in slips[0]


def test_preview_flags_draft_slip_that_must_be_repriced():
    proposed = rule("new", "daily_wage", 400, employee="EMP-1")
    drafts = [{"employee": "EMP-1", "name": "DRAFT-1",
               "start_date": "2026-09-01", "end_date": "2026-09-30"}]
    result = preview_change([EMPLOYEE], [], proposed, "2026-09-17", "2026-09-17", [],
                            draft_slips=drafts,
                            base_value=lambda employee, day, field: 350)
    assert result["draft_slips"] == ["DRAFT-1"]


def test_preview_rejects_unbounded_long_recalculation():
    with pytest.raises(ValueError, match="366"):
        preview_change([EMPLOYEE], [], rule("new", "daily_wage", 400),
                       "2020-01-01", "2026-09-17", [])


def test_preview_isolates_unrelated_employees_with_existing_conflicts():
    other = {**EMPLOYEE, "name": "EMP-2"}
    conflicting = [
        rule("a", "daily_wage", 350, employee="EMP-2"),
        rule("b", "daily_wage", 400, employee="EMP-2"),
    ]
    result = preview_change([EMPLOYEE, other], conflicting,
                            rule("new", "daily_wage", 425, employee="EMP-1"),
                            "2026-09-17", "2026-09-17", [],
                            base_value=lambda employee, day, field: 350)
    assert result["affected_employees"] == 1


@pytest.mark.parametrize("field,value", [
    ("daily_wage", 0), ("break_minutes", -1), ("break_minutes", 30.5),
    ("overtime_multiplier", 1.5), ("overtime_enabled", 2),
])
def test_rule_validation_rejects_invalid_pay_values(field, value):
    with pytest.raises(ValueError):
        validate_rule(rule("bad", field, value))


def test_rule_validation_requires_reason_and_valid_dates():
    with pytest.raises(ValueError, match="Reason"):
        validate_rule(rule("bad", "daily_wage", 350))
    with pytest.raises(ValueError, match="Effective To"):
        validate_rule(rule("bad", "daily_wage", 350, reason="test",
                           effective_to="2026-08-31"))


def test_resolve_policy_merges_approved_exception_without_changing_base(monkeypatch):
    base = frappe._dict({"name": "base", "pay_basis": "Daily Wage", "daily_wage": 350,
                         "break_minutes": 0, "effective_from": "2026-09-01",
                         "department": None, "branch": "Factory", "modified": "2026-09-01"})
    approved = frappe._dict(rule("approved", "daily_wage", 400, employee="EMP-1",
                                 employee_category="Worker", effective_from="2026-09-17"))

    def get_all(doctype, **kwargs):
        return [base] if doctype == "Workforce Payroll Policy" else [approved]

    monkeypatch.setattr(frappe, "get_all", get_all)
    employee = {**EMPLOYEE, "employment_type": "Worker"}
    before = resolve_policy(employee, "2026-09-16")
    after = resolve_policy(employee, "2026-09-17")
    assert before.daily_wage == 350
    assert after.daily_wage == 400
    assert after.break_minutes == 0
    assert base.daily_wage == 350
