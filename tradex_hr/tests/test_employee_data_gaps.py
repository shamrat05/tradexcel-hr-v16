from tradex_hr.tradexcel_hr.report.employee_data_gaps.employee_data_gaps import employee_gaps


WAGE_STRUCTURE = "TCL Factory Daily Wage Worker Structure"
STAFF_STRUCTURE = "TCL Source Staff Monthly Salary Structure"
WAGE_STRUCTURES = {WAGE_STRUCTURE}
AS_OF = "2026-09-17"
FUTURE_DATE = "2026-12-05"


def employee(**overrides):
    base = {
        "name": "HR-EMP-0001",
        "employee_number": "TCL-0001",
        "department": "Loading - TCL",
        "designation": "Worker",
        "employment_type": "Worker",
        "date_of_joining": "2026-01-01",
        "date_of_birth": "1990-01-01",
        "holiday_list": "Tradex Holidays 2026",
    }
    base.update(overrides)
    return base


def gaps_for(employee_data, structure=WAGE_STRUCTURE, punches=0, assignments=1):
    return employee_gaps(employee_data, structure, WAGE_STRUCTURES, punches,
                         assignment_count=assignments, as_of=AS_OF)


def test_clean_worker_has_no_gaps():
    assert gaps_for(employee(), punches=10) == []


def test_missing_master_data_is_flagged():
    result = gaps_for(employee(department=None, employee_number="", designation=None,
                               date_of_birth=None, holiday_list=None))
    assert result == ["no_department", "no_employee_number", "no_designation",
                      "no_date_of_birth", "no_holiday_list"]


def test_missing_active_assignment_is_flagged():
    assert gaps_for(employee(employment_type="Full-time"), structure=None) == ["no_active_assignment"]


def test_multiple_active_assignments_are_flagged():
    assert gaps_for(employee(), assignments=2) == ["duplicate_active_assignments"]


def test_latest_wage_structure_on_non_worker_is_flagged():
    assert gaps_for(employee(employment_type="Full-time")) == ["wage_structure_not_worker"]


def test_worker_without_wage_structure_is_flagged():
    assert gaps_for(employee(), structure=STAFF_STRUCTURE) == ["worker_without_wage_structure"]


def test_future_joining_date_only_flagged_with_punches():
    future = employee(date_of_joining=FUTURE_DATE)
    assert "future_doj_with_punches" not in gaps_for(future)
    assert "future_doj_with_punches" in gaps_for(future, punches=112)
