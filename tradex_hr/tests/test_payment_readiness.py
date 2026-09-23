"""Payment readiness safeguards and native Payroll Entry delegation."""
from __future__ import annotations

import os

import frappe
import pytest

from tradex_hr.tradexcel_hr import payment_readiness
from tradex_hr.tradexcel_hr.payroll_finalization import PayrollEntryFinalizationMixin


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


def test_payment_modes_require_one_known_native_mode():
    counts, blockers = payment_readiness._mode_findings([
        {"mode_of_payment": "Bank"}, {"mode_of_payment": "Cash"},
    ])
    assert counts == {"Bank": 1, "Cash": 1}
    assert blockers[0]["code"] == payment_readiness.MIXED_MODE_REVIEW

    for unsupported in ("", "Cheque", "Wallet"):
        _counts, blockers = payment_readiness._mode_findings([{"mode_of_payment": unsupported}])
        assert blockers[0]["code"] == payment_readiness.PAYMENT_MODE_REVIEW


def test_payment_readiness_stops_when_accrual_is_not_ready(monkeypatch):
    entry = frappe._dict({
        "name": "PE-PARTIAL",
        "company": "Tradexcel Ceramics Ltd.",
        "custom_tradex_run_key": "RUN-1",
    })
    entry.check_permission = lambda *_args: None
    monkeypatch.setattr(payment_readiness, "assert_company_access", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(payment_readiness, "inspect_payroll_accrual_reconciliation", lambda *_args: {
        "status": "PARTIAL_SUBMISSION",
    })
    monkeypatch.setattr(frappe, "get_all", lambda *_args, **_kwargs: pytest.fail("must stop before reading slips"))

    result = payment_readiness.inspect_payroll_payment_readiness(entry)
    assert result["status"] == "ACCRUAL_NOT_READY"
    assert result["accrual_status"] == "PARTIAL_SUBMISSION"


def _payment_result(monkeypatch, *, mode, slips=None, employee=None, bank_account=None, active_entries=None, cancelled_entries=None):
    entry = frappe._dict({
        "name": "PE-PAYMENT-TEST",
        "company": "Tradexcel Ceramics Ltd.",
        "currency": "BDT",
        "custom_tradex_run_key": "RUN-1",
        "payment_account": "PAYMENT-ACCOUNT",
        "bank_account": "COMPANY-BANK-ACCOUNT",
    })
    entry.check_permission = lambda *_args: None

    monkeypatch.setattr(payment_readiness, "assert_company_access", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(payment_readiness, "inspect_payroll_accrual_reconciliation", lambda *_args: {
        "status": "READY",
        "submitted_slip_count": len(slips or []),
    })

    def get_all(doctype, **_kwargs):
        if doctype == "Salary Slip":
            return slips or []
        if doctype == "Employee":
            return [employee] if employee else []
        if doctype == "Journal Entry Account":
            return []
        raise AssertionError(f"unexpected doctype {doctype}")

    monkeypatch.setattr(frappe, "get_all", get_all)
    if active_entries is not None or cancelled_entries is not None:
        monkeypatch.setattr(
            payment_readiness,
            "_linked_payment_entries",
            lambda *_args, **_kwargs: (active_entries or [], cancelled_entries or []),
        )
        monkeypatch.setattr(payment_readiness, "_bank_reconciled", lambda *_args: (False, []))

    def get_value(doctype, name, fields, **kwargs):
        if doctype == "Account":
            return frappe._dict({
                "company": "Tradexcel Ceramics Ltd.",
                "is_group": 0,
                "disabled": 0,
                "account_type": "Bank" if mode == "Bank" else "Cash",
                "account_currency": "BDT",
            })
        if doctype == "Bank Account":
            return bank_account
        raise AssertionError(f"unexpected doctype {doctype}")

    monkeypatch.setattr(frappe.db, "get_value", get_value)
    return payment_readiness.inspect_payroll_payment_readiness(entry)


def test_bank_mode_missing_snapshot_account_blocks(monkeypatch):
    result = _payment_result(
        monkeypatch,
        mode="Bank",
        slips=[{
            "name": "SS-1", "employee": "EMP-1", "net_pay": 100,
            "mode_of_payment": "Bank", "bank_name": "Test Bank", "bank_account_no": "",
            "salary_withholding": None,
        }],
        employee=frappe._dict(name="EMP-1", salary_mode="Bank", bank_name="Test Bank", bank_ac_no="9988"),
        bank_account=frappe._dict(
            account="PAYMENT-ACCOUNT", company="Tradexcel Ceramics Ltd.",
            is_company_account=1, disabled=0, bank_account_no="BANK-001",
        ),
    )
    assert result["status"] == "PAYMENT_BANK_DETAILS_MISSING"
    assert result["blockers"][0]["employees"] == ["EMP-1"]


def test_cash_mode_does_not_require_bank_account(monkeypatch):
    result = _payment_result(
        monkeypatch,
        mode="Cash",
        slips=[{
            "name": "SS-1", "employee": "EMP-1", "net_pay": 100,
            "mode_of_payment": "Cash", "bank_name": "", "bank_account_no": "",
            "salary_withholding": None,
        }],
    )
    assert result["status"] == "READY_TO_PREPARE_PAYMENT"
    assert result["payment_mode"] == "Cash"
    assert result["bank_transactions"] == []


def test_changed_employee_bank_details_are_warning_and_snapshot_is_not_returned(monkeypatch):
    snapshot_number = "SNAPSHOT-12345678"
    result = _payment_result(
        monkeypatch,
        mode="Bank",
        slips=[{
            "name": "SS-1", "employee": "EMP-1", "net_pay": 100,
            "mode_of_payment": "Bank", "bank_name": "Test Bank",
            "bank_account_no": snapshot_number, "salary_withholding": None,
        }],
        employee=frappe._dict(
            name="EMP-1", salary_mode="Bank", bank_name="Test Bank", bank_ac_no="CURRENT-87654321"
        ),
        bank_account=frappe._dict(
            account="PAYMENT-ACCOUNT", company="Tradexcel Ceramics Ltd.",
            is_company_account=1, disabled=0, bank_account_no="COMPANY-ACCOUNT-1",
        ),
    )
    assert result["status"] == "READY_TO_PREPARE_PAYMENT"
    assert result["warnings"][0]["code"] == "BANK_DETAILS_CHANGED_AFTER_PAYROLL"
    assert snapshot_number not in repr(result)
    assert "CURRENT-87654321" not in repr(result)


@pytest.mark.parametrize("invalid_account", [
    {"company": "EFL"},
    {"is_group": 1},
    {"disabled": 1},
    {"account_type": "Bank"},
    {"account_currency": "USD"},
])
def test_payment_account_must_be_enabled_correct_type_and_company(monkeypatch, invalid_account):
    account = frappe._dict(
        company="TCL", is_group=0, disabled=0, account_type="Cash", account_currency="BDT"
    )
    account.update(invalid_account)
    entry = frappe._dict(company="TCL", payment_account="A", bank_account=None, currency="BDT")
    monkeypatch.setattr(
        frappe.db,
        "get_value",
        lambda doctype, *_args, **_kwargs: account if doctype == "Account" else None,
    )
    findings = payment_readiness._payment_account_findings(entry, "Cash")
    assert [finding["code"] for finding in findings] == ["PAYMENT_ACCOUNT_INVALID"]


class _NativePayrollEntry:
    def __init__(self):
        self.calls = 0

    def make_bank_entry(self, *args, **kwargs):
        self.calls += 1
        return frappe._dict(name="JE-NATIVE")


class _ManagedPayrollEntry(PayrollEntryFinalizationMixin, _NativePayrollEntry):
    def __init__(self):
        super().__init__()
        self.company = "Tradexcel Ceramics Ltd."
        self.docstatus = 1
        self.workflow_state = "Tradexcel Payroll Approved"

    def get(self, fieldname):
        return "RUN-1" if fieldname == "custom_tradex_run_key" else None

    def check_permission(self, _ptype):
        return None


def test_native_make_bank_entry_runs_only_when_payment_readiness_is_ready(monkeypatch):
    entry = _ManagedPayrollEntry()
    monkeypatch.setattr(
        "tradex_hr.tradexcel_hr.company_context.assert_company_access",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(payment_readiness, "inspect_payroll_payment_readiness", lambda *_args, **_kwargs: {
        "status": "READY_TO_PREPARE_PAYMENT", "blockers": [],
    })
    result = entry.make_bank_entry()
    assert result.name == "JE-NATIVE"
    assert entry.calls == 1


def test_native_make_bank_entry_is_blocked_when_payment_readiness_fails(monkeypatch):
    entry = _ManagedPayrollEntry()
    monkeypatch.setattr(
        "tradex_hr.tradexcel_hr.company_context.assert_company_access",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(payment_readiness, "inspect_payroll_payment_readiness", lambda *_args, **_kwargs: {
        "status": "ACCRUAL_NOT_READY",
        "blockers": [{"reason": "accrual not ready"}],
    })
    with pytest.raises(frappe.ValidationError, match="Payroll payment is blocked: accrual not ready"):
        entry.make_bank_entry()
    assert entry.calls == 0


def test_existing_native_payment_entry_is_reused_on_retry(monkeypatch):
    entry = _ManagedPayrollEntry()
    existing = frappe._dict(name="JE-EXISTING")
    monkeypatch.setattr(
        "tradex_hr.tradexcel_hr.company_context.assert_company_access",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(payment_readiness, "inspect_payroll_payment_readiness", lambda *_args, **_kwargs: {
        "status": "PAYMENT_ENTRY_DRAFT",
        "payment_journal_entry": existing.name,
        "blockers": [],
    })
    monkeypatch.setattr(frappe, "get_doc", lambda *_args, **_kwargs: existing)
    result = entry.make_bank_entry()
    assert result.name == existing.name
    assert entry.calls == 0



def test_payment_bank_requires_linked_company_bank_account(monkeypatch):
    result = _payment_result(
        monkeypatch,
        mode="Bank",
        slips=[{
            "name": "SS-1", "employee": "EMP-1", "net_pay": 100,
            "mode_of_payment": "Bank", "bank_name": "Test Bank",
            "bank_account_no": "12345678", "status": "Submitted",
        }],
        bank_account=None,
    )
    assert result["status"] == "PAYMENT_BANK_ACCOUNT_INVALID"
    assert any(item["code"] == "PAYMENT_BANK_ACCOUNT_INVALID" for item in result["blockers"])


def test_withheld_salary_slips_are_separate_from_normal_payment_batch(monkeypatch):
    slips = [
        {
            "name": "SS-NORMAL", "employee": "EMP-1", "net_pay": 100,
            "mode_of_payment": "Cash", "status": "Submitted",
        },
        {
            "name": "SS-WITHHELD", "employee": "EMP-2", "net_pay": 200,
            "mode_of_payment": "Bank", "status": "Withheld",
        },
    ]
    result = _payment_result(monkeypatch, mode="Cash", slips=slips)
    assert result["employee_count"] == 1
    assert result["withheld_employee_count"] == 1
    assert result["payment_mode"] == "Cash"
    assert result["payment_mode_counts"] == {"Cash": 1}


def test_payment_readiness_requires_explicit_company_scope(monkeypatch):
    calls = []
    monkeypatch.setattr(payment_readiness, "assert_company_access", lambda company, **kwargs: calls.append((company, kwargs)))
    entry = frappe._dict(name="PE-1", company="TCL", custom_tradex_run_key="RUN-1")
    entry.check_permission = lambda ptype: None
    monkeypatch.setattr(payment_readiness, "inspect_payroll_accrual_reconciliation", lambda *_args: {
        "status": "PARTIAL_SUBMISSION",
    })
    result = payment_readiness.inspect_payroll_payment_readiness(entry)
    assert result["status"] == "ACCRUAL_NOT_READY"
    assert calls == [("TCL", {"require_explicit_scope": True})]


def test_linked_payment_entry_from_another_company_is_blocked(monkeypatch):
    foreign_entry = frappe._dict(
        name="JE-FOREIGN", company="EFL", docstatus=0,
        voucher_type="Cash Entry", clearance_date=None,
    )
    result = _payment_result(
        monkeypatch,
        mode="Cash",
        slips=[{
            "name": "SS-1", "employee": "EMP-1", "net_pay": 100,
            "mode_of_payment": "Cash", "status": "Submitted",
        }],
        active_entries=[foreign_entry],
    )
    assert result["status"] == "PAYMENT_ENTRY_INVALID"
    assert result["blockers"][0]["code"] == "PAYMENT_ENTRY_INVALID"


def test_submitted_payment_entry_awaits_bank_reconciliation(monkeypatch):
    posted = frappe._dict(
        name="JE-POSTED", company="Tradexcel Ceramics Ltd.", docstatus=1,
        voucher_type="Bank Entry", clearance_date=None,
    )
    result = _payment_result(
        monkeypatch,
        mode="Cash",
        slips=[{
            "name": "SS-1", "employee": "EMP-1", "net_pay": 100,
            "mode_of_payment": "Cash", "status": "Submitted",
        }],
        active_entries=[posted],
    )
    assert result["status"] == "AWAITING_BANK_RECONCILIATION"
    assert result["payment_journal_entry"] == "JE-POSTED"


def test_multiple_active_payment_entries_are_ambiguous(monkeypatch):
    entries = [
        frappe._dict(name=f"JE-{i}", company="Tradexcel Ceramics Ltd.", docstatus=0,
                     voucher_type="Cash Entry", clearance_date=None)
        for i in (1, 2)
    ]
    result = _payment_result(
        monkeypatch,
        mode="Cash",
        slips=[{
            "name": "SS-1", "employee": "EMP-1", "net_pay": 100,
            "mode_of_payment": "Cash", "status": "Submitted",
        }],
        active_entries=entries,
    )
    assert result["status"] == "PAYMENT_ENTRY_AMBIGUOUS"
    assert result["payment_journal_entry"] is None


def test_cancelled_payment_entry_blocks_duplicate_recreation(monkeypatch):
    cancelled = frappe._dict(
        name="JE-CANCELLED", company="Tradexcel Ceramics Ltd.", docstatus=2,
        voucher_type="Cash Entry", clearance_date=None,
    )
    result = _payment_result(
        monkeypatch,
        mode="Cash",
        slips=[{
            "name": "SS-1", "employee": "EMP-1", "net_pay": 100,
            "mode_of_payment": "Cash", "status": "Submitted",
        }],
        active_entries=[],
        cancelled_entries=[cancelled],
    )
    assert result["status"] == "PAYMENT_ENTRY_CANCELLED"
    assert result["blockers"][0]["code"] == "PAYMENT_ENTRY_CANCELLED"
