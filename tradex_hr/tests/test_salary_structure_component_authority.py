import os

import frappe
import pytest

from tradex_hr.tradexcel_hr import salary_structure_validation as validation


COMPONENT = "Factory Day Rate"


@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(
        site=os.environ.get("FRAPPE_TEST_SITE", "hrms-v16.localhost"),
        sites_path=os.environ.get("FRAPPE_TEST_SITES_PATH", "/home/sanchita/frappe-bench-v16/sites"),
        force=True,
    )
    frappe.connect()
    yield
    frappe.destroy()


def _structure(*, basis="Daily Wage", component=COMPONENT, earnings=None):
    return frappe._dict(
        custom_tradex_pay_basis=basis,
        custom_tradex_daily_wage_component=component,
        earnings=[frappe._dict(row) for row in (earnings if earnings is not None else [{
            "salary_component": COMPONENT,
            "amount": 0,
            "depends_on_payment_days": 0,
            "amount_based_on_formula": 0,
            "formula": "",
        }])],
    )


def test_daily_component_must_be_neutral_and_other_earnings_are_allowed(monkeypatch):
    monkeypatch.setattr(
        frappe.db, "get_value",
        lambda doctype, name, fields, **kwargs: frappe._dict(type="Earning", disabled=0),
    )
    doc = _structure(earnings=[
        {"salary_component": COMPONENT, "amount": 0, "depends_on_payment_days": 0,
         "amount_based_on_formula": 0, "formula": ""},
        {"salary_component": "Factory Overtime", "amount": 0, "depends_on_payment_days": 0,
         "amount_based_on_formula": 1, "formula": "approved_overtime_amount"},
    ])

    validation.validate_salary_structure(doc)


def test_salary_structure_metadata_is_source_owned_and_not_editable_after_submit():
    field = frappe.get_meta("Salary Structure").get_field("custom_tradex_daily_wage_component")
    assert field.fieldtype == "Link"
    assert field.options == "Salary Component"
    assert field.default in (None, "")
    assert not field.allow_on_submit
    assert field.depends_on == 'eval:doc.custom_tradex_pay_basis=="Daily Wage"'


@pytest.mark.parametrize("case, message", [
    ("blank", "Select the Daily Wage Salary Component"),
    ("not_in_earnings", "must appear exactly once"),
    ("duplicate", "must appear exactly once"),
    ("deduction", "must be an Earning"),
    ("payment_days", "must not depend on payment days"),
    ("formula", "must not calculate a separate formula amount"),
    ("amount", "must have a zero structure amount"),
    ("missing", "does not exist"),
    ("monthly_component", "Monthly Salary structures must not set"),
])
def test_invalid_daily_component_authority_fails_closed(monkeypatch, case, message):
    component_type = "Deduction" if case == "deduction" else "Earning"
    monkeypatch.setattr(
        frappe.db, "get_value",
        lambda doctype, name, fields, **kwargs: (
            None if case == "missing" else frappe._dict(type=component_type, disabled=0)
        ),
    )
    rows = [{
        "salary_component": COMPONENT, "amount": 0, "depends_on_payment_days": 0,
        "amount_based_on_formula": 0, "formula": "",
    }]
    component = COMPONENT
    basis = "Daily Wage"
    if case == "blank":
        component = None
    elif case == "not_in_earnings":
        rows = [{**rows[0], "salary_component": "Other Earning"}]
    elif case == "duplicate":
        rows = [rows[0], dict(rows[0])]
    elif case == "payment_days":
        rows[0]["depends_on_payment_days"] = 1
    elif case == "formula":
        rows[0]["amount_based_on_formula"] = 1
        rows[0]["formula"] = "base * 0.5"
    elif case == "amount":
        rows[0]["amount"] = 1
    elif case == "monthly_component":
        basis = "Monthly Salary"

    with pytest.raises(frappe.ValidationError, match=message):
        validation.validate_salary_structure(_structure(basis=basis, component=component, earnings=rows))
