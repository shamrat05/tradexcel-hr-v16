"""Synthetic proof of native Leave Encashment and Gratuity in exit settlement."""
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


def test_native_leave_encashment_and_gratuity_feed_fnf(monkeypatch):
    from tradex_hr.tests.test_payroll_finalization_integration import (
        _component,
        _create_assignment,
        _create_employee,
        _create_structure,
        _create_synthetic_company,
        cleanup_synthetic_finalization_company,
    )
    from hrms.payroll.doctype.salary_structure.salary_structure import make_salary_slip

    token = frappe.generate_hash(8).upper()[:8]
    company = None
    employee = None
    component = None
    structure = None
    assignment = None
    salary_slip = None
    leave_type = None
    leave_period = None
    allocation = None
    encashment = None
    encashment_salary = None
    rule = None
    gratuity = None
    fnf = None
    old_user = frappe.session.user
    old_in_test = getattr(frappe, "in_test", False)
    old_local_in_test = getattr(frappe.local.flags, "in_test", False)
    try:
        frappe.set_user("Administrator")
        company, _abbr, payable, expense, cost_center, holiday_list = _create_synthetic_company(token, monkeypatch)
        component = _component(f"Exit Benefit Earnings {token}", f"EB{token[:3]}", company, expense)
        structure = _create_structure(
            f"Exit Benefit Structure {token}", company, "BDT", "Monthly Salary", component.name, 30000,
            depends_on_payment_days=1,
        )
        employee = _create_employee(f"Exit Benefits {token}", company, holiday_list)
        employee.date_of_joining = "2020-01-01"
        employee.relieving_date = "2026-09-20"
        employee.status = "Left"
        employee.save(ignore_permissions=True)
        assignment = _create_assignment(
            employee.name, company, "BDT", payable, structure.name, 30000, cost_center,
            from_date="2026-01-01", leave_encashment_amount_per_day=100,
        )

        # Use native Salary Slip calculation as Gratuity's source; all values/rules below
        # are synthetic integration fixtures and do not represent Bangladesh law.
        salary_slip = make_salary_slip(
            structure.name, employee=employee.name, posting_date="2026-09-20"
        )
        salary_slip.start_date = "2026-09-01"
        salary_slip.end_date = "2026-09-30"
        salary_slip.payroll_frequency = "Monthly"
        salary_slip.insert(ignore_permissions=True)
        salary_slip.submit()
        assert salary_slip.docstatus == 1
        assert salary_slip.get("earnings")

        leave_type = frappe.get_doc({
            "doctype": "Leave Type",
            "leave_type_name": f"Synthetic Exit Leave {token}",
            "max_leaves_allowed": 10,
            "allow_encashment": 1,
            "max_encashable_leaves": 2,
            "earning_component": component.name,
        }).insert(ignore_permissions=True).name
        leave_period = frappe.get_doc({
            "doctype": "Leave Period",
            "from_date": "2026-01-01",
            "to_date": "2026-12-31",
            "is_active": 1,
            "company": company,
        }).insert(ignore_permissions=True).name
        allocation = frappe.get_doc({
            "doctype": "Leave Allocation",
            "employee": employee.name,
            "company": company,
            "leave_type": leave_type,
            "leave_period": leave_period,
            "from_date": "2026-01-01",
            "to_date": "2026-12-31",
            "new_leaves_allocated": 4,
        }).insert(ignore_permissions=True)
        allocation.submit()
        encashment = frappe.get_doc({
            "doctype": "Leave Encashment",
            "employee": employee.name,
            "company": company,
            "leave_type": leave_type,
            "leave_period": leave_period,
            "encashment_date": "2026-09-20",
            "posting_date": "2026-09-20",
            "currency": "BDT",
        }).insert(ignore_permissions=True)
        assert employee.status == "Left"  # native validate_active_employee rejects Inactive, not Left
        assert encashment.actual_encashable_days == 2
        assert encashment.encashment_days == 2
        assert encashment.encashment_amount == 200
        encashment.submit()
        assert encashment.docstatus == 1
        encashment_salary = frappe.db.get_value("Additional Salary", {"ref_doctype": "Leave Encashment", "ref_docname": encashment.name}, "name")
        assert encashment_salary
        assert frappe.db.get_value("Additional Salary", encashment_salary, "amount") == 200

        rule = frappe.get_doc({
            "doctype": "Gratuity Rule",
            "name": f"TEST ONLY Synthetic Exit Rule {token}",
            "calculate_gratuity_amount_based_on": "Current Slab",
            "work_experience_calculation_function": "Take Exact Completed Years",
            "total_working_days_per_year": 365,
            "minimum_year_for_gratuity": 0,
            "applicable_earnings_component": [{"salary_component": component.name}],
            "gratuity_rule_slabs": [{
                "from_year": 0,
                "to_year": 0,
                "fraction_of_applicable_earnings": 0.1,
            }],
        }).insert(ignore_permissions=True)
        gratuity = frappe.get_doc({
            "doctype": "Gratuity",
            "employee": employee.name,
            "gratuity_rule": rule.name,
            "pay_via_salary_slip": 0,
            "expense_account": expense,
            "payable_account": payable,
            "mode_of_payment": "Cash",
            "cost_center": cost_center,
            "posting_date": "2026-09-20",
        }).insert(ignore_permissions=True)
        assert gratuity.amount > 0
        gratuity.submit()
        assert gratuity.docstatus == 1

        # Native F&F rows can point to the native benefit documents and load their
        # native account/amount values without a Tradexcel calculation.
        from hrms.hr.doctype.full_and_final_statement.full_and_final_statement import get_account_and_amount
        assert get_account_and_amount("Gratuity", gratuity.name, company) == [payable, gratuity.amount]
        assert get_account_and_amount("Leave Encashment", encashment.name, company) == [payable, 200]
        fnf = frappe.get_doc({
            "doctype": "Full and Final Statement",
            "employee": employee.name,
            "company": company,
            "transaction_date": "2026-09-20",
        }).insert(ignore_permissions=True)
        for doctype, name, amount in (
            ("Gratuity", gratuity.name, gratuity.amount),
            ("Leave Encashment", encashment.name, 200),
        ):
            fnf.append("payables", {
                "component": doctype,
                "reference_document_type": doctype,
                "reference_document": name,
                "account": payable,
                "amount": amount,
                "status": "Settled",
            })
        fnf.save(ignore_permissions=True)
        assert {row.reference_document for row in fnf.payables} >= {gratuity.name, encashment.name}
        assert employee.status == "Left"
    finally:
        frappe.set_user("Administrator")
        if fnf and frappe.db.exists("Full and Final Statement", fnf.name):
            frappe.delete_doc("Full and Final Statement", fnf.name, force=True, ignore_permissions=True)
        if gratuity and frappe.db.exists("Gratuity", gratuity.name):
            doc = frappe.get_doc("Gratuity", gratuity.name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Gratuity", doc.name, force=True, ignore_permissions=True)
        if encashment_salary and frappe.db.exists("Additional Salary", encashment_salary):
            doc = frappe.get_doc("Additional Salary", encashment_salary)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Additional Salary", doc.name, force=True, ignore_permissions=True)
        if encashment and frappe.db.exists("Leave Encashment", encashment.name):
            doc = frappe.get_doc("Leave Encashment", encashment.name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Leave Encashment", doc.name, force=True, ignore_permissions=True)
        if allocation and frappe.db.exists("Leave Allocation", allocation.name):
            doc = frappe.get_doc("Leave Allocation", allocation.name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Leave Allocation", doc.name, force=True, ignore_permissions=True)
        if employee:
            for name in frappe.get_all("Leave Ledger Entry", filters={"employee": employee.name, "leave_type": leave_type}, pluck="name"):
                frappe.delete_doc("Leave Ledger Entry", name, force=True, ignore_permissions=True)
        if leave_period and frappe.db.exists("Leave Period", leave_period):
            frappe.delete_doc("Leave Period", leave_period, force=True, ignore_permissions=True)
        if leave_type and frappe.db.exists("Leave Type", leave_type):
            frappe.delete_doc("Leave Type", leave_type, force=True, ignore_permissions=True)
        if rule and frappe.db.exists("Gratuity Rule", rule.name):
            frappe.delete_doc("Gratuity Rule", rule.name, force=True, ignore_permissions=True)
        if salary_slip and frappe.db.exists("Salary Slip", salary_slip.name):
            doc = frappe.get_doc("Salary Slip", salary_slip.name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Salary Slip", doc.name, force=True, ignore_permissions=True)
        if company:
            cleanup_synthetic_finalization_company(company)
        frappe.in_test = old_in_test
        frappe.local.flags.in_test = old_local_in_test
        frappe.set_user(old_user)