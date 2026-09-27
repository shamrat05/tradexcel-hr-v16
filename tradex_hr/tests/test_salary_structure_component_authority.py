import os

import frappe
import pytest

from tradex_hr.tradexcel_hr import daily_wage_input
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
    ("disabled", "must be enabled"),
    ("payment_days", "must not depend on payment days"),
    ("formula", "must not calculate a separate formula amount"),
    ("amount", "must have a zero structure amount"),
    ("missing", "does not exist"),
    ("monthly_component", "Monthly Salary structures must not set"),
])
def test_invalid_daily_component_authority_fails_closed(monkeypatch, case, message):
    component_type = "Deduction" if case == "deduction" else "Earning"
    disabled = 1 if case == "disabled" else 0
    monkeypatch.setattr(
        frappe.db, "get_value",
        lambda doctype, name, fields=None, **kwargs: (
            None if case == "missing" else frappe._dict(type=component_type, disabled=disabled)
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


def test_disabled_daily_component_blocks_runtime_and_calculation_until_reenabled(monkeypatch):
    component_state = {"type": "Earning", "disabled": 1}
    monkeypatch.setattr(
        daily_wage_input,
        "resolve_pay_basis",
        lambda *_args, **_kwargs: {
            "status": "Daily Wage",
            "employee": "EMP-SYNTH",
            "assignment": "SSA-SYNTH",
            "salary_structure": "Synthetic Structure",
            "base": 450,
            "daily_wage_component": COMPONENT,
        },
    )
    monkeypatch.setattr(
        daily_wage_input,
        "resolve_daily_rate",
        lambda result: {
            "status": "READY",
            "employee": "EMP-SYNTH",
            "rate": result["base"],
            "assignment": "SSA-SYNTH",
        },
    )
    monkeypatch.setattr(
        daily_wage_input.frappe,
        "get_all",
        lambda doctype, *args, **kwargs: (
            [{
                "salary_component": COMPONENT,
                "formula": "",
                "amount": 0,
                "amount_based_on_formula": 0,
                "depends_on_payment_days": 0,
            }]
            if doctype == "Salary Detail"
            else []
        ),
    )
    monkeypatch.setattr(
        daily_wage_input.frappe.db,
        "get_value",
        lambda doctype, name, fields=None, **kwargs: (
            {"date_of_joining": None, "relieving_date": None, "company": "TCL", "branch": None, "department": None}
            if doctype == "Employee" and kwargs.get("as_dict")
            else frappe._dict(component_state)
            if doctype == "Salary Component"
            else None
        ),
    )
    monkeypatch.setattr(
        daily_wage_input,
        "_native_attendance_units",
        lambda *_args, **_kwargs: {"status": "READY", "payable_units": 8, "native": True},
    )

    # 1. Component disabled after structure submission blocks runtime inspection
    inspected = daily_wage_input.inspect_daily_wage_structure("EMP-SYNTH", "2026-09-01")
    assert inspected["status"] == "BLOCKED_UNSAFE_STRUCTURE"
    assert "disabled" in inspected["reason"]

    # 2. Calculation with disabled component fails closed without producing payable money
    calc = daily_wage_input.calculate_daily_wage_input("EMP-SYNTH", "2026-09-01", "2026-09-30")
    assert calc["status"] == "BLOCKED_UNSAFE_STRUCTURE"
    assert "amount" not in calc
    assert "disabled" in calc["reason"]

    # 3. Re-enabling component restores READY status and calculation
    component_state["disabled"] = 0
    inspected_re = daily_wage_input.inspect_daily_wage_structure("EMP-SYNTH", "2026-09-01")
    assert inspected_re["status"] == "READY"
    assert inspected_re["salary_component"] == COMPONENT

    calc_re = daily_wage_input.calculate_daily_wage_input("EMP-SYNTH", "2026-09-01", "2026-09-30")
    assert calc_re["status"] == "READY"
    assert calc_re["amount"] == 3600.0
    assert calc_re["salary_component"] == COMPONENT


def test_post_submit_disablement_and_reenablement_real_db():
    company = frappe.db.get_single_value("Global Defaults", "default_company") or "Tradexcel Ceramics Ltd."
    comp_name = f"Synth FDR {frappe.generate_hash(6)}"
    abbr = f"SF{frappe.generate_hash(3).upper()}"
    struct_name = f"Synth DW Struct {frappe.generate_hash(6)}"
    comp = None
    struct = None
    try:
        comp = frappe.get_doc({
            "doctype": "Salary Component",
            "salary_component": comp_name,
            "salary_component_abbr": abbr,
            "type": "Earning",
            "disabled": 0,
            "depends_on_payment_days": 0,
        }).insert(ignore_permissions=True)

        struct = frappe.get_doc({
            "doctype": "Salary Structure",
            "name": struct_name,
            "company": company,
            "currency": "BDT",
            "payroll_frequency": "Monthly",
            "is_active": "Yes",
            "custom_tradex_pay_basis": "Daily Wage",
            "custom_tradex_daily_wage_component": comp.name,
            "earnings": [{
                "salary_component": comp.name,
                "amount": 0,
                "depends_on_payment_days": 0,
                "amount_based_on_formula": 0,
                "formula": "",
            }],
        }).insert(ignore_permissions=True)
        struct.submit()

        basis = {
            "status": "Daily Wage",
            "employee": "EMP-SYNTH",
            "salary_structure": struct.name,
            "daily_wage_component": comp.name,
        }

        # 1. Post-submit disablement
        comp.disabled = 1
        comp.save(ignore_permissions=True)

        res = daily_wage_input._inspect_daily_wage_structure(basis)
        assert res["status"] == "BLOCKED_UNSAFE_STRUCTURE"
        assert "disabled" in res["reason"]

        # Authoring validation with disabled component fails closed
        authoring_doc = _structure(component=comp.name, earnings=[{
            "salary_component": comp.name, "amount": 0, "depends_on_payment_days": 0,
            "amount_based_on_formula": 0, "formula": "",
        }])
        with pytest.raises(frappe.ValidationError, match="must be enabled"):
            validation.validate_salary_structure(authoring_doc)

        # 2. Re-enable component restores READY
        comp.disabled = 0
        comp.save(ignore_permissions=True)

        res_reenabled = daily_wage_input._inspect_daily_wage_structure(basis)
        assert res_reenabled["status"] == "READY"
        assert res_reenabled["salary_component"] == comp.name
    finally:
        if struct and frappe.db.exists("Salary Structure", struct.name):
            doc = frappe.get_doc("Salary Structure", struct.name)
            if doc.docstatus == 1:
                doc.cancel()
            doc.delete()
        if comp and frappe.db.exists("Salary Component", comp.name):
            frappe.delete_doc("Salary Component", comp.name, force=True)
        frappe.db.commit()

        assert not frappe.db.exists("Salary Structure", struct_name)
        assert not frappe.db.exists("Salary Component", comp_name)
