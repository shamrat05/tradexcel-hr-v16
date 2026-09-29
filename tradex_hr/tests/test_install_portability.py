"""A neutral install must not seed Tradexcel business data."""

from __future__ import annotations

import inspect
from pathlib import Path

import frappe
import pytest

from tradex_hr import branch_setup, field_attendance_setup, install
from tradex_hr.tradexcel_hr import salary_setup


def test_branch_setup_only_converges_company_neutral_fields(monkeypatch):
    calls = []
    monkeypatch.setattr(
        branch_setup, "create_custom_fields",
        lambda fields, **kwargs: calls.append((fields, kwargs)),
    )

    branch_setup.ensure_branch_fields()

    assert len(calls) == 1
    fields, kwargs = calls[0]
    assert kwargs == {"update": True}
    company_field = next(row for row in fields["Branch"] if row["fieldname"] == "company")
    assert company_field["default"] == ""
    assert not any("Tradexcel Ceramics" in str(row) for row in fields["Branch"])


def test_generic_migration_does_not_seed_legacy_salary_or_branch_data():
    source = inspect.getsource(install.after_migrate)
    assert "ensure_branch_fields()" in source
    assert "ensure_branch_hierarchy" not in source
    assert "ensure_pay_basis_metadata" not in source
    assert "setup_payroll_configuration" not in source
    assert "import_assignments" not in source


def test_generic_runtime_has_no_salary_split_or_daily_component_name_authority():
    from tradex_hr.tradexcel_hr import daily_wage_input, native_payroll, payroll_rules

    assert not hasattr(payroll_rules, "DEFAULT_COMPONENTS")
    assert not hasattr(payroll_rules, "calculate_wage")
    assert not hasattr(daily_wage_input, "DEFAULT_COMPONENT")
    assert "DEFAULT_COMPONENT" not in inspect.getsource(native_payroll)
    fields = field_attendance_setup._fields()["Salary Structure"]
    component = next(row for row in fields if row["fieldname"] == "custom_tradex_daily_wage_component")
    assert component["fieldtype"] == "Link"
    assert component["options"] == "Salary Component"
    assert "Daily Wage" in component["depends_on"]
    assert "mandatory_depends_on" in component
    assert "default" not in component
    assert "allow_on_submit" not in component
    setup_source = inspect.getsource(install.after_migrate)
    assert "ensure_salary_setup" not in setup_source


def test_historical_salary_spec_names_its_daily_component_explicitly():
    spec = salary_setup.load_spec()
    daily = next(row for row in spec["structures"] if row["pay_basis"] == "Daily Wage")
    assert daily["daily_wage_component"] == "Daily Wage"


def test_after_migrate_salary_structure_fields_are_source_owned_only(monkeypatch):
    calls = []
    monkeypatch.setattr(field_attendance_setup, "create_custom_fields", lambda fields, **kwargs: calls.append(fields))

    field_attendance_setup.ensure_field_attendance_fields()

    fields = calls[0]["Salary Structure"]
    assert {row["fieldname"] for row in fields} >= {
        "custom_tradex_pay_basis", "custom_tradex_daily_wage_component",
    }
    assert not any(row["fieldname"] == "custom_tradex_daily_wage_component" and row.get("default") for row in fields)


def test_old_one_off_salary_importers_are_not_importable():
    package = Path(__file__).resolve().parents[1] / "tradexcel_hr"
    assert not (package / "salary_excel.py").exists()
    assert not (package / "payroll_setup.py").exists()


def test_explicit_salary_spec_cannot_default_to_a_currency():
    with pytest.raises(frappe.ValidationError, match="needs a currency"):
        salary_setup.ensure_structures({"company": "Synthetic Company", "structures": []}, commit=False)
