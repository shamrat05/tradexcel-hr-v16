"""Synthetic native Leave workflow proof; all records are cleaned in finally."""
import frappe
import pytest


def test_native_maternity_leave_application_creates_native_attendance_and_ledger(monkeypatch):
    from tradex_hr.tests.test_payroll_finalization_integration import (
        _create_employee,
        _create_synthetic_company,
        cleanup_synthetic_finalization_company,
    )

    try:
        old_user = frappe.session.user
    except RuntimeError:
        pytest.skip("Native Leave integration requires an initialized isolated Frappe site.")
    token = frappe.generate_hash(8).upper()[:8]
    company = employee = leave_type = leave_period = allocation = application = None
    try:
        frappe.set_user("Administrator")
        company, _abbr, _payable, _expense, _cost_center, holiday_list = _create_synthetic_company(token, monkeypatch)
        holiday = frappe.get_doc("Holiday List", holiday_list)
        holiday.append("holidays", {"holiday_date": "2026-09-22", "description": "TEST ONLY Maternity Parity"})
        holiday.save(ignore_permissions=True)

        employee = _create_employee(f"Synthetic Maternity Leave {token}", company, holiday_list)
        employee.date_of_joining = "2020-01-01"
        employee.save(ignore_permissions=True)

        leave_type = frappe.get_doc({
            "doctype": "Leave Type",
            "leave_type_name": f"TEST ONLY Maternity Leave {token}",
            "max_leaves_allowed": 120,
            "is_lwp": 0,
            "is_ppl": 0,
            "include_holiday": 1,
            "max_continuous_days_allowed": 120,
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
            "new_leaves_allocated": 120,
        }).insert(ignore_permissions=True)
        allocation.submit()

        application = frappe.get_doc({
            "doctype": "Leave Application",
            "employee": employee.name,
            "company": company,
            "leave_type": leave_type,
            "from_date": "2026-09-21",
            "to_date": "2026-09-23",
            "leave_approver": frappe.session.user,
            "status": "Approved",
        }).insert(ignore_permissions=True)
        application.submit()
        assert application.total_leave_days == 3

        attendance = frappe.get_all(
            "Attendance",
            filters={"employee": employee.name, "attendance_date": ["between", ["2026-09-21", "2026-09-23"]]},
            fields=["attendance_date", "status", "docstatus"],
        )
        assert len(attendance) == 3
        assert all(row.status == "On Leave" and row.docstatus == 1 for row in attendance)
        assert frappe.db.exists("Leave Ledger Entry", {
            "employee": employee.name,
            "leave_type": leave_type,
            "transaction_type": "Leave Application",
            "transaction_name": application.name,
        })
    finally:
        frappe.set_user("Administrator")
        if application and frappe.db.exists("Leave Application", application.name):
            doc = frappe.get_doc("Leave Application", application.name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Leave Application", doc.name, force=True, ignore_permissions=True)
        if allocation and frappe.db.exists("Leave Allocation", allocation.name):
            doc = frappe.get_doc("Leave Allocation", allocation.name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Leave Allocation", doc.name, force=True, ignore_permissions=True)
        if employee:
            for name in frappe.get_all(
                "Attendance", filters={"employee": employee.name}, pluck="name"
            ):
                frappe.delete_doc("Attendance", name, force=True, ignore_permissions=True)
            for name in frappe.get_all(
                "Leave Ledger Entry", filters={"employee": employee.name, "leave_type": leave_type}, pluck="name"
            ):
                frappe.delete_doc("Leave Ledger Entry", name, force=True, ignore_permissions=True)
            frappe.delete_doc("Employee", employee.name, force=True, ignore_permissions=True)
        if leave_period and frappe.db.exists("Leave Period", leave_period):
            frappe.delete_doc("Leave Period", leave_period, force=True, ignore_permissions=True)
        if leave_type and frappe.db.exists("Leave Type", leave_type):
            frappe.delete_doc("Leave Type", leave_type, force=True, ignore_permissions=True)
        if company:
            cleanup_synthetic_finalization_company(company)
        frappe.set_user(old_user)
