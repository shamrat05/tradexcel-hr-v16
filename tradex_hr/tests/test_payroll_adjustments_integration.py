from __future__ import annotations

import os

import frappe
import pytest


@pytest.fixture(scope="module", autouse=True)
def frappe_site():
    frappe.init(
        site=os.environ.get("FRAPPE_TEST_SITE", "hrms-v16.localhost"),
        sites_path=os.environ.get("FRAPPE_TEST_SITES_PATH", "/home/sanchita/frappe-bench-v16/sites"),
        force=True,
    )
    frappe.connect()
    yield
    frappe.destroy()


def _create_period(company, year):
    return frappe.get_doc({
        "doctype": "Payroll Period",
        "name": f"Adjustment Test {year} {frappe.generate_hash(6)}",
        "company": company,
        "start_date": f"{year}-01-01",
        "end_date": f"{year}-12-31",
    }).insert(ignore_permissions=True)


def _create_assignment(employee, company, currency, payable, structure, base, cost_center, from_date):
    assignment = frappe.get_doc({
        "doctype": "Salary Structure Assignment",
        "employee": employee,
        "company": company,
        "currency": currency,
        "salary_structure": structure,
        "from_date": from_date,
        "base": base,
        "payroll_payable_account": payable,
        "payroll_cost_centers": [{"cost_center": cost_center, "percentage": 100}],
    }).insert(ignore_permissions=True)
    assignment.submit()
    return assignment


def _submit_slip(structure, employee, posting_date):
    from hrms.payroll.doctype.salary_structure.salary_structure import make_salary_slip

    slip = make_salary_slip(structure, employee=employee, posting_date=posting_date)
    slip.save()
    slip.submit()
    return slip


def test_native_correction_and_arrear_create_future_period_adjustments(monkeypatch):
    from tradex_hr.tests.test_payroll_finalization_integration import (
        _component,
        _create_employee,
        _create_structure,
        _create_synthetic_company,
        cleanup_synthetic_finalization_company,
    )

    token = frappe.generate_hash(8)[:8].upper()
    company_name = f"Tradexcel Finalization Test {token}"
    old_user = frappe.session.user
    company = None

    try:
        frappe.set_user("Administrator")
        company, _abbr, payable, expense, cost_center, holiday_list = _create_synthetic_company(
            token, monkeypatch
        )
        payroll_basis = frappe.db.get_single_value("Payroll Settings", "payroll_based_on")
        if payroll_basis != "Leave":
            pytest.skip("native LWP correction fixture requires Payroll Settings based on Leave")
        period_2026 = _create_period(company, 2026)
        _create_period(company, 2027)
        frappe.get_doc({
            "doctype": "Fiscal Year",
            "year": f"Finalization Test FY {token} 2025",
            "year_start_date": "2025-01-01",
            "year_end_date": "2025-12-31",
            "companies": [{"company": company}],
        }).insert(ignore_permissions=True)
        frappe.get_doc({
            "doctype": "Fiscal Year",
            "year": f"Finalization Test FY {token} 2027",
            "year_start_date": "2027-01-01",
            "year_end_date": "2027-12-31",
            "companies": [{"company": company}],
        }).insert(ignore_permissions=True)

        component = _component(f"Correction Basic {token}", f"CB{token[:3]}", company, expense)
        frappe.db.set_value("Salary Component", component.name, "arrear_component", 1)

        correction_employee = _create_employee(f"Correction {token}", company, holiday_list)
        correction_structure = _create_structure(
            f"Correction Structure {token}", company, "BDT", "Monthly Salary", component.name, 30000
        )
        _create_assignment(
            correction_employee.name, company, "BDT", payable, correction_structure.name,
            30000, cost_center, "2025-01-01",
        )

        leave_type = frappe.get_doc({
            "doctype": "Leave Type",
            "leave_type_name": f"Codex Adjustment Test LWP {token}",
            "is_lwp": 1,
            "include_holiday": 1,
        }).insert(ignore_permissions=True)
        leave = frappe.get_doc({
            "doctype": "Leave Application",
            "employee": correction_employee.name,
            "leave_type": leave_type.name,
            "from_date": "2026-01-05",
            "to_date": "2026-01-05",
            "company": company,
            "status": "Approved",
            "leave_approver": "Administrator",
        }).insert(ignore_permissions=True)
        leave.submit()

        source_slip = _submit_slip(correction_structure.name, correction_employee.name, "2026-01-01")
        assert source_slip.leave_without_pay > 0
        original_source_amount = source_slip.gross_pay
        correction = frappe.get_doc({
            "doctype": "Payroll Correction",
            "employee": correction_employee.name,
            "company": company,
            "payroll_period": period_2026.name,
            "payroll_date": "2027-01-01",
            "days_to_reverse": 1,
            "month_for_lwp_reversal": "January",
            "salary_slip_reference": source_slip.name,
        }).insert(ignore_permissions=True)
        correction.submit()

        correction_inputs = frappe.get_all(
            "Additional Salary",
            filters={"ref_doctype": "Payroll Correction", "ref_docname": correction.name, "docstatus": 1},
            fields=["name", "amount"],
        )
        assert correction_inputs and all(row.amount > 0 for row in correction_inputs)
        correction_input_names = {row.name for row in correction_inputs}

        correction_target_slip = _submit_slip(
            correction_structure.name, correction_employee.name, "2027-01-01"
        )
        assert any(row.additional_salary in correction_input_names for row in correction_target_slip.earnings)
        assert source_slip.reload().gross_pay == original_source_amount
        correction.workflow_state = "Tradexcel Adjustment Cancelled"
        with pytest.raises(frappe.ValidationError, match="ADJUSTMENT_ALREADY_CONSUMED"):
            correction.cancel()
        assert frappe.db.get_value("Payroll Correction", correction.name, "docstatus") == 1
        assert frappe.db.get_value("Additional Salary", correction_inputs[0].name, "docstatus") == 1

        february_leave = frappe.get_doc({
            "doctype": "Leave Application",
            "employee": correction_employee.name,
            "leave_type": leave_type.name,
            "from_date": "2026-02-05",
            "to_date": "2026-02-05",
            "company": company,
            "status": "Approved",
            "leave_approver": "Administrator",
        }).insert(ignore_permissions=True)
        february_leave.submit()
        february_source = _submit_slip(
            correction_structure.name, correction_employee.name, "2026-02-01"
        )
        unconsumed_correction = frappe.get_doc({
            "doctype": "Payroll Correction",
            "employee": correction_employee.name,
            "company": company,
            "payroll_period": period_2026.name,
            "payroll_date": "2027-02-01",
            "days_to_reverse": 1,
            "month_for_lwp_reversal": "February",
            "salary_slip_reference": february_source.name,
        }).insert(ignore_permissions=True)
        unconsumed_correction.submit()
        unconsumed_inputs = frappe.get_all(
            "Additional Salary",
            filters={
                "ref_doctype": "Payroll Correction",
                "ref_docname": unconsumed_correction.name,
                "docstatus": 1,
            },
            fields=["name"],
        )
        assert unconsumed_inputs
        unconsumed_correction.workflow_state = "Tradexcel Adjustment Cancelled"
        unconsumed_correction.cancel()
        assert frappe.db.get_value(
            "Payroll Correction", unconsumed_correction.name, "docstatus"
        ) == 2
        assert all(
            frappe.db.get_value("Additional Salary", row.name, "docstatus") == 2
            for row in unconsumed_inputs
        )

        arrear_employee = _create_employee(f"Arrear {token}", company, holiday_list)
        old_structure = _create_structure(
            f"Old Arrear Structure {token}", company, "BDT", "Monthly Salary", component.name, 30000
        )
        _create_assignment(
            arrear_employee.name, company, "BDT", payable, old_structure.name,
            30000, cost_center, "2025-01-01",
        )
        old_slip = _submit_slip(old_structure.name, arrear_employee.name, "2026-01-01")
        new_structure = _create_structure(
            f"Raised Arrear Structure {token}", company, "BDT", "Monthly Salary", component.name, 36000
        )
        _create_assignment(
            arrear_employee.name, company, "BDT", payable, new_structure.name,
            36000, cost_center, "2026-01-01",
        )
        future_slip = _submit_slip(new_structure.name, arrear_employee.name, "2027-01-01")

        arrear = frappe.get_doc({
            "doctype": "Arrear",
            "employee": arrear_employee.name,
            "company": company,
            "payroll_period": period_2026.name,
            "salary_structure": new_structure.name,
            "arrear_start_date": "2026-01-01",
            "payroll_date": "2027-02-01",
        })
        candidates = arrear.get_existing_salary_slips()
        assert [row.name for row in candidates] == [old_slip.name]
        arrear.insert(ignore_permissions=True)
        arrear.submit()

        arrear_inputs = frappe.get_all(
            "Additional Salary",
            filters={"ref_doctype": "Arrear", "ref_docname": arrear.name, "docstatus": 1},
            fields=["name", "amount"],
        )
        assert arrear_inputs and all(row.amount > 0 for row in arrear_inputs)
        arrear_input_names = {row.name for row in arrear_inputs}
        arrear_target_slip = _submit_slip(new_structure.name, arrear_employee.name, "2027-02-01")
        assert any(row.additional_salary in arrear_input_names for row in arrear_target_slip.earnings)
        arrear.workflow_state = "Tradexcel Adjustment Cancelled"
        with pytest.raises(frappe.ValidationError, match="ADJUSTMENT_ALREADY_CONSUMED"):
            arrear.cancel()
        assert frappe.db.get_value("Arrear", arrear.name, "docstatus") == 1
        assert frappe.db.get_value("Additional Salary", arrear_inputs[0].name, "docstatus") == 1

        unconsumed_arrear_employee = _create_employee(
            f"Unconsumed Arrear {token}", company, holiday_list
        )
        unconsumed_old_structure = _create_structure(
            f"Unconsumed Old Structure {token}", company, "BDT", "Monthly Salary",
            component.name, 30000
        )
        _create_assignment(
            unconsumed_arrear_employee.name, company, "BDT", payable,
            unconsumed_old_structure.name, 30000, cost_center, "2025-01-01",
        )
        _submit_slip(
            unconsumed_old_structure.name, unconsumed_arrear_employee.name, "2026-01-01"
        )
        unconsumed_new_structure = _create_structure(
            f"Unconsumed New Structure {token}", company, "BDT", "Monthly Salary",
            component.name, 36000
        )
        _create_assignment(
            unconsumed_arrear_employee.name, company, "BDT", payable,
            unconsumed_new_structure.name, 36000, cost_center, "2026-01-01",
        )
        unconsumed_arrear = frappe.get_doc({
            "doctype": "Arrear",
            "employee": unconsumed_arrear_employee.name,
            "company": company,
            "payroll_period": period_2026.name,
            "salary_structure": unconsumed_new_structure.name,
            "arrear_start_date": "2026-01-01",
            "payroll_date": "2027-04-01",
        }).insert(ignore_permissions=True)
        unconsumed_arrear.submit()
        unconsumed_arrear_inputs = frappe.get_all(
            "Additional Salary",
            filters={
                "ref_doctype": "Arrear",
                "ref_docname": unconsumed_arrear.name,
                "docstatus": 1,
            },
            fields=["name"],
        )
        assert unconsumed_arrear_inputs
        unconsumed_arrear.workflow_state = "Tradexcel Adjustment Cancelled"
        unconsumed_arrear.cancel()
        assert frappe.db.get_value("Arrear", unconsumed_arrear.name, "docstatus") == 2
        assert all(
            frappe.db.get_value("Additional Salary", row.name, "docstatus") == 2
            for row in unconsumed_arrear_inputs
        )

        _submit_slip(new_structure.name, arrear_employee.name, "2026-03-01")
        reduced_structure = _create_structure(
            f"Reduced Arrear Structure {token}", company, "BDT", "Monthly Salary", component.name, 25000
        )
        _create_assignment(
            arrear_employee.name, company, "BDT", payable, reduced_structure.name,
            25000, cost_center, "2026-03-01",
        )
        reduced_arrear = frappe.get_doc({
            "doctype": "Arrear",
            "employee": arrear_employee.name,
            "company": company,
            "payroll_period": period_2026.name,
            "salary_structure": reduced_structure.name,
            "arrear_start_date": "2026-03-01",
            "payroll_date": "2027-03-01",
        })
        with pytest.raises(frappe.ValidationError, match="RETRO_OVERPAYMENT_DECISION_REQUIRED"):
            reduced_arrear.insert(ignore_permissions=True)
        assert not frappe.get_all(
            "Additional Salary",
            filters={"ref_doctype": "Arrear", "ref_docname": reduced_arrear.name},
            pluck="name",
        )
    finally:
        if company or frappe.db.exists("Company", company_name):
            cleanup_synthetic_finalization_company(company_name)
        frappe.set_user(old_user)
