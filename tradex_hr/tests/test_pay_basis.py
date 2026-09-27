from datetime import date

from tradex_hr.tradexcel_hr import pay_basis


def _resolver(monkeypatch, rows, bases):
    def get_all(_doctype, filters, **_kwargs):
        if filters.get("from_date") == [">", date(2026, 9, 1)]:
            return [row for row in rows if date(2026, 9, 1) <= row["from_date"] <= date(2026, 9, 30)]
        return [row for row in rows if row["from_date"] <= date(2026, 9, 1)]

    class FakeFrappe:
        class db:
            @staticmethod
            def get_value(*_args, **_kwargs):
                return None

    FakeFrappe.get_all = staticmethod(get_all)
    monkeypatch.setattr(pay_basis, "frappe", FakeFrappe)
    monkeypatch.setattr(pay_basis, "_structure_configuration", lambda name: bases.get(name, {}))


def test_worker_employment_type_does_not_override_monthly_structure(monkeypatch):
    rows = [{"name": "SSA-1", "from_date": date(2026, 1, 1), "salary_structure": "Monthly", "base": 20000}]
    _resolver(monkeypatch, rows, {"Monthly": {"pay_basis": "Monthly Salary"}})

    result = pay_basis.resolve_pay_basis("EMP-1", date(2026, 9, 1), date(2026, 9, 30))

    assert result["status"] == pay_basis.MONTHLY


def test_staff_can_have_explicit_daily_structure(monkeypatch):
    rows = [{"name": "SSA-2", "from_date": date(2026, 1, 1), "salary_structure": "Daily", "base": 350}]
    _resolver(monkeypatch, rows, {"Daily": {"pay_basis": "Daily Wage", "daily_wage_component": "Factory Day Rate"}})

    result = pay_basis.resolve_pay_basis("EMP-2", date(2026, 9, 1), date(2026, 9, 30))

    assert result["status"] == pay_basis.DAILY
    assert result["daily_wage_component"] == "Factory Day Rate"
    assert pay_basis.resolve_daily_rate(result) == {
        "status": "READY", "employee": "EMP-2", "rate": 350.0, "assignment": "SSA-2"
    }


def test_daily_structure_without_configured_component_fails_closed(monkeypatch):
    rows = [{"name": "SSA-2A", "from_date": date(2026, 1, 1), "salary_structure": "Daily", "base": 425}]
    _resolver(monkeypatch, rows, {"Daily": {"pay_basis": "Daily Wage", "daily_wage_component": None}})

    result = pay_basis.resolve_pay_basis("EMP-2A", date(2026, 9, 1), date(2026, 9, 30))

    assert result["status"] == pay_basis.UNRESOLVED
    assert "no configured Daily Wage Salary Component" in result["reason"]


def test_missing_structure_metadata_is_unresolved(monkeypatch):
    rows = [{"name": "SSA-3", "from_date": date(2026, 1, 1), "salary_structure": "Unlabelled", "base": 350}]
    _resolver(monkeypatch, rows, {"Unlabelled": {"pay_basis": None}})

    result = pay_basis.resolve_pay_basis("EMP-3", date(2026, 9, 1), date(2026, 9, 30))

    assert result["status"] == pay_basis.UNRESOLVED
    assert pay_basis.resolve_daily_rate(result)["status"] == pay_basis.UNRESOLVED


def test_mid_period_assignment_is_explicit_not_silently_selected(monkeypatch):
    rows = [
        {"name": "SSA-JAN", "from_date": date(2026, 1, 1), "salary_structure": "Monthly", "base": 20000},
        {"name": "SSA-SEP", "from_date": date(2026, 9, 15), "salary_structure": "Daily", "base": 350},
    ]
    _resolver(monkeypatch, rows, {
        "Monthly": {"pay_basis": "Monthly Salary"},
        "Daily": {"pay_basis": "Daily Wage", "daily_wage_component": "Factory Day Rate"},
    })

    result = pay_basis.resolve_pay_basis("EMP-4", date(2026, 9, 1), date(2026, 9, 30))

    assert result["status"] == pay_basis.MID_PERIOD_CHANGE
    assert result["later_assignments"] == ["SSA-SEP"]


def test_same_effective_date_is_conflict(monkeypatch):
    rows = [
        {"name": "SSA-A", "from_date": date(2026, 1, 1), "salary_structure": "Monthly", "base": 20000},
        {"name": "SSA-B", "from_date": date(2026, 1, 1), "salary_structure": "Daily", "base": 350},
    ]
    _resolver(monkeypatch, rows, {
        "Monthly": {"pay_basis": "Monthly Salary"},
        "Daily": {"pay_basis": "Daily Wage", "daily_wage_component": "Factory Day Rate"},
    })

    result = pay_basis.resolve_pay_basis("EMP-5", date(2026, 9, 1), date(2026, 9, 30))

    assert result["status"] == pay_basis.CONFLICT


def test_daily_rate_requires_positive_assignment_base(monkeypatch):
    rows = [{"name": "SSA-6", "from_date": date(2026, 1, 1), "salary_structure": "Daily", "base": 0}]
    _resolver(monkeypatch, rows, {"Daily": {"pay_basis": "Daily Wage", "daily_wage_component": "Factory Day Rate"}})

    result = pay_basis.resolve_pay_basis("EMP-6", date(2026, 9, 1), date(2026, 9, 30))

    assert pay_basis.resolve_daily_rate(result)["status"] == "BLOCKED_MISSING_BASE"

def test_first_assignment_on_joining_date_is_applicable_to_partial_month(monkeypatch):
    rows = [{
        "name": "SSA-JOIN",
        "from_date": date(2026, 9, 15),
        "salary_structure": "Monthly",
        "base": 30000,
    }]

    def get_all(_doctype, filters, **_kwargs):
        operator, boundary = filters["from_date"]
        if operator == "<=":
            return [row for row in rows if row["from_date"] <= boundary]
        return [row for row in rows if row["from_date"] > boundary]

    class FakeFrappe:

        class db:
            @staticmethod
            def get_value(doctype, employee, field):
                return date(2026, 9, 15) if (
                    doctype, employee, field
                ) == ("Employee", "EMP-JOIN", "date_of_joining") else None

    FakeFrappe.get_all = staticmethod(get_all)
    monkeypatch.setattr(pay_basis, "frappe", FakeFrappe)
    monkeypatch.setattr(pay_basis, "_structure_configuration", lambda name: {"pay_basis": "Monthly Salary"})

    result = pay_basis.resolve_pay_basis(
        "EMP-JOIN", date(2026, 9, 1), date(2026, 9, 30)
    )

    assert result["status"] == pay_basis.MONTHLY
    assert result["from_date"] == date(2026, 9, 15)
