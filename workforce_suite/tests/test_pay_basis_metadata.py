from types import SimpleNamespace

import frappe
import pytest

from workforce_suite.workforce_suite import salary_setup


def _metadata_fakes(monkeypatch, current, linked, component=None):
    writes = []
    fake_db = SimpleNamespace(
        exists=lambda *_args: True,
        count=lambda *_args: linked,
        set_value=lambda *args, **kwargs: writes.append((args, kwargs)),
    )
    fake_frappe = SimpleNamespace(
        ValidationError=frappe.ValidationError,
        db=fake_db,
        get_meta=lambda _doctype: SimpleNamespace(has_field=lambda _field: True),
        get_doc=lambda *_args: SimpleNamespace(
            custom_workforce_pay_basis=current,
            custom_workforce_daily_wage_component=component,
            get=lambda field: component if field == "custom_workforce_daily_wage_component" else None,
        ),
    )
    monkeypatch.setattr(salary_setup, "frappe", fake_frappe)
    return writes


def test_submitted_structure_cannot_reinterpret_historical_pay_basis(monkeypatch):
    writes = _metadata_fakes(monkeypatch, "Monthly Salary", linked=2)

    with pytest.raises(frappe.ValidationError, match="Create a new Salary Structure"):
        salary_setup.ensure_pay_basis_metadata(
            {"structures": [{"name": "Example Monthly", "pay_basis": "Daily Wage"}]}
        )

    assert writes == []


def test_blank_metadata_is_seeded_once_even_for_existing_assignments(monkeypatch):
    writes = _metadata_fakes(monkeypatch, None, linked=2)

    result = salary_setup.ensure_pay_basis_metadata(
        {"structures": [{"name": "Example Monthly", "pay_basis": "Monthly Salary"}]}
    )

    assert "  UPDATE pay basis Example Monthly: Monthly Salary" in result
    assert len(writes) == 1


def test_matching_metadata_is_idempotent(monkeypatch):
    writes = _metadata_fakes(monkeypatch, "Monthly Salary", linked=2)

    result = salary_setup.ensure_pay_basis_metadata(
        {"structures": [{"name": "Example Monthly", "pay_basis": "Monthly Salary"}]}
    )

    assert result == ["  ok     pay basis Example Monthly = Monthly Salary"]
    assert writes == []


def test_historical_utility_will_not_change_daily_component_on_linked_structure(monkeypatch):
    writes = _metadata_fakes(monkeypatch, "Daily Wage", linked=1)

    with pytest.raises(frappe.ValidationError, match="Cannot change Daily Wage Salary Component"):
        salary_setup.ensure_pay_basis_metadata({
            "structures": [{
                "name": "Example Daily Wage", "pay_basis": "Daily Wage",
                "daily_wage_component": "Daily Wage",
            }],
        })

    assert writes == []
