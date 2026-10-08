import pytest

from workforce_suite.workforce_suite.report.employee_data_gaps.employee_data_gaps import employee_gaps


AS_OF = "2026-09-17"


def employee(**overrides):
    base = {
        "name": "SYN-EMP-1", "employee_number": "SYN-1",
        "department": "Synthetic Department", "designation": "Synthetic Role",
        "employment_type": "Worker", "date_of_joining": "2026-01-01",
        "date_of_birth": "1990-01-01", "holiday_list": "Synthetic Holidays",
    }
    base.update(overrides)
    return base


def gaps_for(employee_data, structure="SYN-STRUCTURE", basis="Monthly Salary", punches=0):
    return employee_gaps(employee_data, structure, basis, punches, as_of=AS_OF)


@pytest.mark.parametrize("employment_type,basis", [
    ("Worker", "Monthly Salary"), ("Full-time", "Daily Wage"),
])
def test_explicit_structure_basis_wins_over_employment_type(employment_type, basis):
    assert gaps_for(employee(employment_type=employment_type), basis=basis) == []


def test_missing_master_data_is_flagged():
    result = gaps_for(employee(department=None, employee_number="", designation=None,
                               date_of_birth=None, holiday_list=None))
    assert result == ["no_department", "no_employee_number", "no_designation",
                      "no_date_of_birth", "no_holiday_list"]


def test_missing_submitted_assignment_is_flagged():
    assert gaps_for(employee(), structure=None, basis="UNRESOLVED") == ["no_active_assignment"]


@pytest.mark.parametrize("basis,gap", [
    ("CONFLICT", "conflicting_assignments"), ("UNRESOLVED", "pay_basis_unresolved"),
])
def test_conflict_and_missing_explicit_basis_are_distinct(basis, gap):
    assert gaps_for(employee(), basis=basis) == [gap]


def test_missing_current_shift_assignment_remains_an_actionable_gap():
    assert employee_gaps(employee(), "SYN-STRUCTURE", "Monthly Salary", 0,
                         as_of=AS_OF, has_shift_assignment=False) == ["no_shift_assignment"]


def test_future_joining_date_only_flagged_with_punches():
    future = employee(date_of_joining="2026-12-05")
    assert "future_doj_with_punches" not in gaps_for(future)
    assert "future_doj_with_punches" in gaps_for(future, punches=112)
