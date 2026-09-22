from types import SimpleNamespace

from tradex_hr.tradexcel_hr import daily_wage_input


def test_attendance_units_use_native_statuses_and_half_day_setting(monkeypatch):
    monkeypatch.setattr(daily_wage_input, "_half_day_fraction", lambda: 0.5)
    monkeypatch.setattr(daily_wage_input, "_leave_type_map", lambda _names: {})

    result = daily_wage_input._attendance_units([
        {"attendance_date": "2026-09-01", "status": "Present"},
        {"attendance_date": "2026-09-02", "status": "Work From Home"},
        {"attendance_date": "2026-09-03", "status": "Half Day", "half_day_status": "Absent"},
        {"attendance_date": "2026-09-04", "status": "Absent"},
    ])

    assert result["status"] == "READY"
    assert result["payable_units"] == 2.5


def test_on_leave_requires_native_leave_type(monkeypatch):
    monkeypatch.setattr(daily_wage_input, "_half_day_fraction", lambda: 0.5)
    monkeypatch.setattr(daily_wage_input, "_leave_type_map", lambda _names: {})

    result = daily_wage_input._attendance_units([
        {"attendance_date": "2026-09-01", "status": "On Leave", "leave_type": "Missing"},
    ])

    assert result["status"] == "UNRESOLVED"


def test_daily_input_has_no_raw_checkin_dependency():
    import inspect

    assert "_checkin_records" not in inspect.getsource(daily_wage_input)


def test_daily_rate_comes_from_resolved_assignment_not_policy(monkeypatch):
    monkeypatch.setattr(daily_wage_input, "resolve_pay_basis", lambda *_args: {
        "status": "Daily Wage", "employee": "EMP-1", "assignment": "SSA-1",
        "salary_structure": "Safe Daily", "base": 350,
    })
    monkeypatch.setattr(daily_wage_input, "resolve_daily_rate", lambda result: {
        "status": "READY", "employee": "EMP-1", "rate": result["base"], "assignment": "SSA-1",
    })
    fake_db = SimpleNamespace(get_value=lambda *args, **kwargs: {
        "date_of_joining": None, "relieving_date": None,
    } if kwargs.get("as_dict") else None)
    monkeypatch.setattr(daily_wage_input, "frappe", SimpleNamespace(
        get_all=lambda *args, **kwargs: [], db=fake_db,
    ))
    monkeypatch.setattr(daily_wage_input, "_attendance_units", lambda _rows: {
        "status": "READY", "payable_units": 10, "attendance_count": 10,
    })
    monkeypatch.setattr(daily_wage_input, "payment_day_component_findings", lambda _rows: [])

    result = daily_wage_input.calculate_daily_wage_input("EMP-1", "2026-09-01", "2026-09-30")

    assert result["amount"] == 3500
