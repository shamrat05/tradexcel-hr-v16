"""Native Full & Final workflow and exit-access integration proofs."""
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

def test_native_separation_and_fnf_four_eyes_flow_and_native_je_retry(monkeypatch):
    from frappe.model.workflow import apply_workflow
    from tradex_hr.tests.test_payroll_finalization_integration import (
        _create_employee,
        _create_scoped_user,
        _create_synthetic_company,
        cleanup_synthetic_finalization_company,
    )
    from tradex_hr.tradexcel_hr.employee_separation import review_separation_statutory_status
    from tradex_hr import role_setup

    token = frappe.generate_hash(8).upper()[:8]
    company = None
    separation = None
    fnf = None
    foreign_fnf = None
    journal_entry = None
    bank_transaction = None
    employee_user = None
    biometric = None
    device = None
    shared_employee = None
    users = []
    old_user = frappe.session.user
    old_in_test = getattr(frappe, "in_test", False)
    old_local_in_test = getattr(frappe.local.flags, "in_test", False)
    try:
        frappe.set_user("Administrator")
        company, _abbr, _payable, expense, _cost_center, holiday_list = _create_synthetic_company(token, monkeypatch)
        role_setup.ensure_tradex_roles()
        maker = _create_scoped_user("Tradexcel HR Manager", company, token)
        finance = _create_scoped_user("Tradexcel Finance/Accounts Officer", company, token)
        finance_user = frappe.get_doc("User", finance)
        finance_user.append("roles", {"role": "Accounts User"})
        finance_user.save(ignore_permissions=True)
        director = _create_scoped_user("Tradexcel Owner/Director", company, token)
        users.extend((maker, finance, director))
        employee = _create_employee(f"Exit Test {token}", company, holiday_list)
        employee.relieving_date = "2026-09-20"
        employee.resignation_letter_date = "2026-09-01"
        employee.save(ignore_permissions=True)

        frappe.set_user(maker)
        separation = frappe.get_doc({
            "doctype": "Employee Separation",
            "employee": employee.name,
            "company": company,
            "boarding_begins_on": "2026-09-01",
            "custom_tradex_separation_type": "Resignation",
        }).insert()
        separation.submit()
        assert separation.docstatus == 1

        frappe.set_user(director)
        review_separation_statutory_status(separation.name, "Not Applicable", "Synthetic test review; not a legal decision.")

        frappe.set_user(maker)
        from tradex_hr.tradexcel_hr.employee_separation import inspect_full_and_final_readiness
        readiness = inspect_full_and_final_readiness(employee.name)
        assert readiness["native_settlement_hub"] == "Full and Final Statement"
        assert set(readiness["native_outstanding_sources"]) == {"payables", "receivables", "assets"}
        assert all("status" in row for row in readiness["native_outstanding_sources"]["payables"])
        assert any(row["code"] == "NATIVE_SETTLEMENT_ITEMS_PENDING" for row in readiness["findings"])
        finding_codes = {row["code"] for row in readiness["findings"]}
        assert "GRATUITY_RULE_DECISION_REQUIRED" not in finding_codes
        assert "LEAVE_ENCASHMENT_CONFIGURATION_REQUIRED" not in finding_codes
        assert readiness["status"] == "REVIEW_REQUIRED"
        frappe.set_user(director)
        review_separation_statutory_status(separation.name, "Approved", "Synthetic missing-ruleset check; not a legal decision.")
        frappe.set_user(maker)
        approved_readiness = inspect_full_and_final_readiness(employee.name)
        assert "STATUTORY_ENTITLEMENT_RULESET_REQUIRED" in {row["code"] for row in approved_readiness["findings"]}
        frappe.set_user(director)
        review_separation_statutory_status(separation.name, "Not Applicable", "Synthetic test review; not a legal decision.")
        frappe.set_user(maker)
        assert "amount" not in repr(readiness)

        fnf = frappe.get_doc({
            "doctype": "Full and Final Statement",
            "employee": employee.name,
            "company": company,
            "transaction_date": "2026-09-20",
        }).insert()
        with pytest.raises(frappe.ValidationError, match="after the approved Full & Final"):
            fnf.create_journal_entry()
        fnf.workflow_state = "Tradexcel F&F Approved"
        fnf.owner = "another-maker@example.test"
        from tradex_hr.tradexcel_hr.employee_separation import validate_full_and_final_before_submit
        with pytest.raises(frappe.PermissionError, match="Finance authorization"):
            validate_full_and_final_before_submit(fnf)
        fnf.owner = maker
        fnf.workflow_state = None
        fnf.append("payables", {
            "component": "Synthetic test payable",
            "account": expense,
            "amount": 100,
            "reference_document_type": "Employee Advance",
            "status": "Settled",
        })
        for row in fnf.payables + fnf.receivables:
            row.status = "Settled"
            row.reference_document_type = "Employee Advance"
        fnf.save()
        apply_workflow(fnf, "Submit for Finance Review")
        fnf.reload()
        assert fnf.workflow_state == "Tradexcel F&F Pending Finance"
        frappe.set_user("Administrator")
        maker_doc = frappe.get_doc("User", maker)
        maker_doc.append("roles", {"role": "Tradexcel Finance/Accounts Officer"})
        maker_doc.save(ignore_permissions=True)
        frappe.set_user(maker)
        with pytest.raises(frappe.ValidationError, match="Self approval is not allowed"):
            apply_workflow(fnf, "Approve and Submit")

        frappe.set_user(finance)
        apply_workflow(fnf, "Approve and Submit")
        fnf.reload()
        assert fnf.docstatus == 1
        assert fnf.workflow_state == "Tradexcel F&F Approved"

        foreign_fnf = frappe.get_doc({
            "doctype": "Full and Final Statement",
            "employee": employee.name,
            "company": company,
            "transaction_date": "2026-09-20",
        }).insert(ignore_permissions=True)
        foreign_entry = frappe.get_doc({
            "doctype": "Journal Entry", "company": company, "voucher_type": "Bank Entry",
            "posting_date": "2026-09-20",
            "accounts": [
                {"account": expense, "debit_in_account_currency": 100},
                {"account": expense, "credit_in_account_currency": 50,
                 "reference_type": "Full and Final Statement", "reference_name": fnf.name},
                {"account": expense, "credit_in_account_currency": 50,
                 "reference_type": "Full and Final Statement", "reference_name": foreign_fnf.name},
            ],
        }).insert(ignore_permissions=True)
        with pytest.raises(frappe.ValidationError, match="FNF_PAYMENT_ENTRY_INVALID"):
            frappe.get_doc("Full and Final Statement", fnf.name).create_journal_entry()
        frappe.delete_doc("Journal Entry", foreign_entry.name, force=True, ignore_permissions=True)
        frappe.delete_doc("Full and Final Statement", foreign_fnf.name, force=True, ignore_permissions=True)
        foreign_fnf = None
        # A balanced but manually linked Journal Entry with an Expense account
        # in the payment row is not native settlement accounting.
        bad_entry = frappe.get_doc({
            "doctype": "Journal Entry",
            "company": company,
            "voucher_type": "Bank Entry",
            "posting_date": "2026-09-20",
            "accounts": [
                {"account": expense, "debit_in_account_currency": 100},
                {
                    "account": expense,
                    "credit_in_account_currency": 100,
                    "reference_type": "Full and Final Statement",
                    "reference_name": fnf.name,
                },
            ],
        }).insert(ignore_permissions=True)
        with pytest.raises(frappe.ValidationError, match="FNF_PAYMENT_ENTRY_INVALID"):
            frappe.get_doc("Full and Final Statement", fnf.name).create_journal_entry()
        bad_entry.delete(ignore_permissions=True)

        # Shared linked users fail closed; removing the second active link allows
        # the dedicated employee account and biometric mapping to be disabled.
        frappe.set_user("Administrator")
        employee_user = frappe.get_doc({
            "doctype": "User", "email": f"exit-employee-{token}@example.test",
            "first_name": "Synthetic Employee", "user_type": "System User", "enabled": 1,
            "send_welcome_email": 0, "roles": [{"role": "Employee"}],
        }).insert(ignore_permissions=True).name
        employee.reload()
        employee.user_id = employee_user
        employee.save(ignore_permissions=True)
        shared_employee = _create_employee(f"Legacy Shared Link {token}", company, holiday_list)
        # Simulate pre-existing/imported duplicate identity data; native Employee
        # validation correctly rejects creating this through the ordinary form.
        frappe.db.set_value("Employee", shared_employee.name, "user_id", employee_user)
        device = frappe.get_doc({
            "doctype": "Tradexcel Biometric Device", "device_code": f"EXIT-{token}",
            "device_name": f"Synthetic Exit Device {token}", "company": company,
            "device_serial": f"SYN-{token}", "bridge_url": "http://127.0.0.1:9",
        }).insert(ignore_permissions=True).name
        biometric_doc = frappe.get_doc({
            "doctype": "Tradexcel Employee Biometric", "employee": employee.name,
            "device": device, "biometric_id": f"EXIT-{token}",
            "assignment_key": f"EXIT:{token}", "enabled": 1, "enrollment_status": "Enrolled",
        }).insert(ignore_permissions=True)
        biometric = biometric_doc.name

        frappe.set_user(maker)
        from tradex_hr.tradexcel_hr.employee_separation import finalize_employee_exit_access
        with pytest.raises(frappe.ValidationError, match="shared or privileged"):
            finalize_employee_exit_access(employee.name)
        frappe.set_user("Administrator")
        frappe.delete_doc("Employee", shared_employee.name, force=True, ignore_permissions=True)
        shared_employee = None
        frappe.set_user(maker)
        result = finalize_employee_exit_access(employee.name)
        assert result["status"] == "EXIT_ACCESS_FINALIZED"
        assert result["user_disabled"] is True
        assert frappe.db.get_value("Employee", employee.name, "status") == "Left"
        assert frappe.db.get_value("User", employee_user, "enabled") == 0
        assert frappe.db.get_value("Tradexcel Employee Biometric", biometric, "enabled") == 0
        assert frappe.db.get_value("Full and Final Statement", fnf.name, "status") == "Unpaid"
        frappe.set_user(finance)

        from tradex_hr.tests.test_payroll_finalization_integration import (
            _create_synthetic_cash_account,
            _create_synthetic_company_bank_account,
        )
        from tradex_hr.tradexcel_hr.employee_separation import _full_and_final_payment_status
        cash_account = _create_synthetic_cash_account(company, token)
        draft = fnf.create_journal_entry()
        assert draft.doctype == "Journal Entry"
        assert draft.docstatus == 0
        draft.voucher_type = "Cash Entry"
        draft.accounts[-1].account = cash_account
        draft.insert()
        journal_entry = draft.name
        reused = frappe.get_doc("Full and Final Statement", fnf.name).create_journal_entry()
        assert reused.name == journal_entry
        assert reused.docstatus == 0
        assert _full_and_final_payment_status([fnf])["status"] == "PAYMENT_ENTRY_DRAFT"
        assert _full_and_final_payment_status([fnf])["settlement_mode"] == "Cash"
        draft.submit()
        assert _full_and_final_payment_status([fnf])["status"] == "CASH_SETTLEMENT_ACCOUNTING_POSTED"
        fnf.reload()
        assert fnf.status == "Paid"
        draft.cancel()
        frappe.delete_doc("Journal Entry", draft.name, force=True, ignore_permissions=True)
        journal_entry = None

        _bank, bank_gl, bank_account = _create_synthetic_company_bank_account(company, token[:8], token)
        bank_draft = frappe.get_doc("Full and Final Statement", fnf.name).create_journal_entry()
        bank_draft.accounts[-1].account = bank_gl
        bank_draft.cheque_no = f"FNF-{token}"
        bank_draft.cheque_date = "2026-09-20"
        bank_draft.insert()
        journal_entry = bank_draft.name
        bank_draft.submit()
        assert _full_and_final_payment_status([fnf])["status"] == "AWAITING_BANK_RECONCILIATION"
        bank_transaction = frappe.get_doc({
            "doctype": "Bank Transaction",
            "date": "2026-09-20",
            "bank_account": bank_account,
            "currency": "BDT",
            "description": f"Synthetic F&F settlement {token}",
            "withdrawal": bank_draft.total_credit,
        }).insert(ignore_permissions=True)
        bank_transaction.submit()
        from erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool import reconcile_vouchers
        import json
        reconcile_vouchers(bank_transaction.name, json.dumps([{
            "payment_doctype": "Journal Entry",
            "payment_name": bank_draft.name,
            "amount": bank_transaction.unallocated_amount,
        }]))
        final_payment = _full_and_final_payment_status([fnf])
        assert final_payment["status"] == "BANK_RECONCILED", final_payment
        assert frappe.utils.getdate(final_payment["clearance_date"]) == frappe.utils.getdate("2026-09-20")
        fnf.reload()
        assert fnf.status == "Paid"
    finally:
        frappe.set_user("Administrator")
        for doctype, name in (("Tradexcel Employee Biometric", biometric), ("Tradexcel Biometric Device", device)):
            if name and frappe.db.exists(doctype, name):
                frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
        if shared_employee and frappe.db.exists("Employee", shared_employee.name):
            frappe.delete_doc("Employee", shared_employee.name, force=True, ignore_permissions=True)
        if bank_transaction and frappe.db.exists("Bank Transaction", bank_transaction.name):
            bank_doc = frappe.get_doc("Bank Transaction", bank_transaction.name)
            if bank_doc.docstatus == 1:
                bank_doc.cancel()
            frappe.delete_doc("Bank Transaction", bank_doc.name, force=True, ignore_permissions=True)
        for doctype, name in (("Journal Entry", journal_entry), ("Full and Final Statement", getattr(foreign_fnf, "name", None)), ("Full and Final Statement", getattr(fnf, "name", None)),
                              ("Employee Separation", getattr(separation, "name", None))):
            if name and frappe.db.exists(doctype, name):
                doc = frappe.get_doc(doctype, name)
                if doc.docstatus == 1:
                    doc.cancel()
                frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
        for user in users:
            for permission in frappe.get_all("User Permission", filters={"user": user}, pluck="name"):
                frappe.delete_doc("User Permission", permission, force=True, ignore_permissions=True)
        if company:
            cleanup_synthetic_finalization_company(company)
        if employee_user and frappe.db.exists("User", employee_user):
            frappe.delete_doc("User", employee_user, force=True, ignore_permissions=True)
            # The native synthetic-company cleanup commits its own fixture
            # teardown. Persist this separate User deletion too, or Frappe's
            # test transaction can roll it back and leave a disabled test user.
            frappe.db.commit()
        frappe.in_test = old_in_test
        frappe.local.flags.in_test = old_local_in_test
        frappe.set_user(old_user)
