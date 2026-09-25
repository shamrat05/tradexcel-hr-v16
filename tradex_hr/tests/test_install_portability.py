"""A neutral install must not seed Tradexcel business data."""

from __future__ import annotations

import inspect
from pathlib import Path

import frappe
import pytest

from tradex_hr import branch_setup, install
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


def test_old_one_off_salary_importers_are_not_importable():
    package = Path(__file__).resolve().parents[1] / "tradexcel_hr"
    assert not (package / "salary_excel.py").exists()
    assert not (package / "payroll_setup.py").exists()


def test_explicit_salary_spec_cannot_default_to_a_currency():
    with pytest.raises(frappe.ValidationError, match="needs a currency"):
        salary_setup.ensure_structures({"company": "Synthetic Company", "structures": []}, commit=False)
