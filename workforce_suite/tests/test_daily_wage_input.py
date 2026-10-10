from datetime import date
from types import SimpleNamespace

from workforce_suite.workforce_suite import daily_wage_input


def test_attendance_units_delegate_to_native_salary_slip(monkeypatch):
    from hrms.payroll.doctype.salary_slip import salary_slip as native_salary_slip

    monkeypatch.setattr(daily_wage_input, "_half_day_fraction", lambda: 0.5)
    monkeypatch.setattr(
        daily_wage_input.frappe,
        "get_cached_doc",
        lambda _doctype: SimpleNamespace(
            consider_marked_attendance_on_holidays=0,
            include_holidays_in_total_working_days=0,
        ),
    )

    class FakeSalarySlip:
        def __init__(self, _data):
            pass

        def get_holidays_for_employee(self, _start, _end):
            return []

        def calculate_lwp_ppl_and_absent_days_based_on_attendance(self, *_args):
            return 0, 0

        def get_payment_days(self, _include_holidays):
            return 3

        def get_half_absent_days(self, *_args):
            return 1

    monkeypatch.setattr(native_salary_slip, "SalarySlip", FakeSalarySlip)

    result = daily_wage_input._native_attendance_units("EMP-1", date(2026, 9, 1), date(2026, 9, 3))

    assert result["status"] == "READY"
    assert result["payable_units"] == 2.5


def test_attendance_unit_adapter_uses_native_effective_holiday_flag(monkeypatch):
    from hrms.payroll.doctype.salary_slip import salary_slip as native_salary_slip

    observed = []

    class FakeSalarySlip:
        def __init__(self, _data):
            pass

        def get_holidays_for_employee(self, _start, _end):
            return [date(2026, 9, 2)]

        def calculate_lwp_ppl_and_absent_days_based_on_attendance(self, _holidays, _fraction, consider):
            observed.append(("lwp", consider))
            return 0, 0

        def get_payment_days(self, _include_holidays):
            return 3

        def get_half_absent_days(self, consider, _holidays):
            observed.append(("half", consider))
            return 0

    monkeypatch.setattr(native_salary_slip, "SalarySlip", FakeSalarySlip)
    monkeypatch.setattr(daily_wage_input, "_half_day_fraction", lambda: 0.5)

    for include_holidays in (0, 1):
        for consider_marked in (0, 1):
            observed.clear()
            monkeypatch.setattr(
                daily_wage_input.frappe,
                "get_cached_doc",
                lambda _doctype, include=include_holidays, consider=consider_marked: SimpleNamespace(
                    include_holidays_in_total_working_days=include,
                    consider_marked_attendance_on_holidays=consider,
                ),
            )

            daily_wage_input._native_attendance_units(
                "EMP-1", date(2026, 9, 1), date(2026, 9, 3)
            )

            expected = int(bool(include_holidays and consider_marked))
            assert observed == [("lwp", expected), ("half", expected)]


def test_native_attendance_units_never_infer_from_raw_checkins():
    import inspect

    assert "_checkin_records" not in inspect.getsource(daily_wage_input)


def test_duplicate_insert_recovery_returns_existing(monkeypatch):
    existing = {
        "name": "AS-1",
        "employee": "EMP-1",
        "company": "COMPANY_A",
        "salary_component": "Factory Day Rate",
        "amount": 3500,
        "payroll_date": "2026-09-30",
        "ref_doctype": "Workforce Attendance Period",
        "ref_docname": "ATT-PER-1",
        "docstatus": 1,
        "disabled": 0,
    }
    monkeypatch.setattr(daily_wage_input, "_get_existing_input", lambda _key: existing)

    result = daily_wage_input._recover_duplicate_input(
        "DAILY-WAGE:ATT-PER-1:r1:EMP-1:Factory Day Rate",
        {
            "employee": "EMP-1",
            "company": "COMPANY_A",
            "salary_component": "Factory Day Rate",
            "amount": 3500,
            "payroll_date": "2026-09-30",
            "ref_doctype": "Workforce Attendance Period",
            "ref_docname": "ATT-PER-1",
        },
        submit=True,
        result={"amount": 3500},
    )

    assert result["status"] == "EXISTING"
    assert result["additional_salary"] == "AS-1"


def test_daily_input_has_no_raw_checkin_dependency():
    import inspect

    assert "_checkin_records" not in inspect.getsource(daily_wage_input)


def test_daily_rate_comes_from_resolved_assignment_not_policy(monkeypatch):
    monkeypatch.setattr(daily_wage_input, "_attendance_rows", lambda *_args: [])
    monkeypatch.setattr(daily_wage_input, "resolve_pay_basis", lambda *_args: {
        "status": "Daily Wage", "employee": "EMP-1", "assignment": "SSA-1",
        "salary_structure": "Safe Daily", "base": 425,
        "daily_wage_component": "Factory Day Rate",
    })
    monkeypatch.setattr(daily_wage_input, "resolve_daily_rate", lambda result: {
        "status": "READY", "employee": "EMP-1", "rate": result["base"], "assignment": "SSA-1",
    })
    fake_db = SimpleNamespace(get_value=lambda doctype, *args, **kwargs: (
        {"date_of_joining": None, "relieving_date": None}
        if doctype == "Employee" and kwargs.get("as_dict")
        else "Earning" if doctype == "Salary Component" else None
    ))
    monkeypatch.setattr(daily_wage_input, "frappe", SimpleNamespace(
        get_all=lambda doctype, *args, **kwargs: ([{
            "salary_component": "Factory Day Rate", "formula": "", "amount": 0,
            "amount_based_on_formula": 0, "depends_on_payment_days": 0,
        }] if doctype == "Salary Detail" else []), db=fake_db,
    ))
    monkeypatch.setattr(daily_wage_input, "_native_attendance_units", lambda *_args, **_kwargs: {
        "status": "READY", "payable_units": 10, "native": True,
    })

    result = daily_wage_input.calculate_daily_wage_input("EMP-1", "2026-09-01", "2026-09-30")

    assert result["amount"] == 4250
    assert result["salary_component"] == "Factory Day Rate"


def test_disabled_daily_component_blocks_daily_wage_input(monkeypatch):
    monkeypatch.setattr(daily_wage_input, "resolve_pay_basis", lambda *_args: {
        "status": "Daily Wage", "employee": "EMP-1", "assignment": "SSA-1",
        "salary_structure": "Safe Daily", "base": 425,
        "daily_wage_component": "Factory Day Rate",
    })
    monkeypatch.setattr(daily_wage_input, "resolve_daily_rate", lambda result: {
        "status": "READY", "employee": "EMP-1", "rate": result["base"], "assignment": "SSA-1",
    })
    fake_db = SimpleNamespace(get_value=lambda doctype, *args, **kwargs: (
        {"date_of_joining": None, "relieving_date": None}
        if doctype == "Employee" and kwargs.get("as_dict")
        else {"type": "Earning", "disabled": 1} if doctype == "Salary Component" else None
    ))
    monkeypatch.setattr(daily_wage_input, "frappe", SimpleNamespace(
        get_all=lambda doctype, *args, **kwargs: ([{
            "salary_component": "Factory Day Rate", "formula": "", "amount": 0,
            "amount_based_on_formula": 0, "depends_on_payment_days": 0,
        }] if doctype == "Salary Detail" else []), db=fake_db,
    ))
    monkeypatch.setattr(daily_wage_input, "_native_attendance_units", lambda *_args, **_kwargs: {
        "status": "READY", "payable_units": 10, "native": True,
    })

    result = daily_wage_input.calculate_daily_wage_input("EMP-1", "2026-09-01", "2026-09-30")

    assert result["status"] == "BLOCKED_UNSAFE_STRUCTURE"
    assert "amount" not in result
    assert "disabled" in result["reason"]
