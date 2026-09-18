import pytest

from tradex_hr.tradexcel_hr.component_exceptions import (
    ComponentRuleConflict,
    apply_component_rules,
    expand_scope,
    resolve_component,
    scope_match,
)


EMPLOYEE = {
    "name": "E1", "company": "TCL", "branch": "TCL Factory",
    "department": "Loading - TCL", "designation": "Worker",
}


def rule(name, action, component="Recreation Allowance", **scope):
    base = {
        "name": name, "company": "TCL", "salary_component": component,
        "component_action": action, "effective_from": "2026-09-01",
    }
    base.update(scope)
    return base


def test_scope_match_branch_department_employee():
    assert scope_match(EMPLOYEE, rule("r", "Exclude", branch_scope=["TCL Factory", "Sub Branch"]))
    assert not scope_match(EMPLOYEE, rule("r", "Exclude", branch_scope=["Tradexcel Headquarters"]))
    assert scope_match(EMPLOYEE, rule("r", "Exclude", department_scope=["Loading - TCL"]))
    assert scope_match(EMPLOYEE, rule("r", "Exclude", employee="E1"))
    assert not scope_match(EMPLOYEE, rule("r", "Exclude", employee="E2"))
    assert not scope_match(EMPLOYEE, rule("r", "Exclude", designation="Manager"))


def test_expand_scope_includes_self_and_descendants():
    assert expand_scope("A", {"A": {"B", "C"}, "B": {"D"}}) == ["A", "B", "C"]
    assert expand_scope(None, {}) is None


def test_employee_override_beats_department_scope():
    rules = [
        rule("dept", "Exclude", department_scope=["Loading - TCL"]),
        rule("person", "Include", employee="E1"),
    ]
    decision = resolve_component(EMPLOYEE, "2026-09-10", rules, "Recreation Allowance")
    assert decision["name"] == "person"


def test_exclude_removes_and_override_changes_amount():
    earnings = [
        {"salary_component": "Basic Salary", "amount": 100},
        {"salary_component": "Recreation Allowance", "amount": 50},
    ]
    excluded = apply_component_rules(earnings, EMPLOYEE, "2026-09-10", [rule("r", "Exclude")])
    assert [row["salary_component"] for row in excluded] == ["Basic Salary"]
    overridden = apply_component_rules(
        earnings, EMPLOYEE, "2026-09-10", [rule("r", "Override Amount", component_amount=75)]
    )
    assert overridden[1]["amount"] == 75
    assert earnings[1]["amount"] == 50  # input untouched


def test_effective_window_and_case_insensitive_component():
    active = rule("r", "Exclude")
    assert resolve_component(EMPLOYEE, "2026-08-31", [active], "Recreation Allowance") is None
    expired = rule("r", "Exclude", effective_to="2026-09-05")
    assert resolve_component(EMPLOYEE, "2026-09-10", [expired], "recreation allowance") is None
    assert resolve_component(EMPLOYEE, "2026-09-10", [active], "recreation allowance") is not None


def test_conflicting_same_rank_actions_raise():
    rules = [
        rule("a", "Exclude", department_scope=["Loading - TCL"]),
        rule("b", "Include", department_scope=["Loading - TCL"]),
    ]
    with pytest.raises(ComponentRuleConflict):
        resolve_component(EMPLOYEE, "2026-09-10", rules, "Recreation Allowance")


def test_narrower_scope_wins_over_wider_scope():
    rules = [
        rule("branch", "Exclude", branch_scope=["TCL Factory"]),
        rule("department", "Include", department_scope=["Loading - TCL"]),
    ]
    decision = resolve_component(EMPLOYEE, "2026-09-10", rules, "Recreation Allowance")
    assert decision["name"] == "department"
