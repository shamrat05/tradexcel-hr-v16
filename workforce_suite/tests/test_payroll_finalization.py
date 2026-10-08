import os
from types import SimpleNamespace

import frappe
import pytest

from workforce_suite.workforce_suite import company_context, payroll_finalization


def _entry(status="Submitted"):
    return frappe._dict(
        name="PE-TEST",
        company="COMPANY_A",
        start_date="2026-09-01",
        end_date="2026-09-30",
        posting_date="2026-09-30",
        docstatus=1,
        workflow_state=payroll_finalization.APPROVED_STATE,
        status=status,
        salary_slips_created=1,
        custom_workforce_run_key="TRAD-TEST",
        employees=[frappe._dict(employee=name) for name in ("EMP-1", "EMP-2", "EMP-3")],
        error_message="",
    )


def _install_reconciliation(monkeypatch, entry, slips, journal_entries):
    monkeypatch.setattr(company_context, "assert_company_access", lambda *_args, **_kwargs: entry.company)

    def get_all(doctype, **_kwargs):
        if doctype == "Salary Slip":
            return slips
        if doctype == "Journal Entry":
            return journal_entries
        raise AssertionError(doctype)

    monkeypatch.setattr(payroll_finalization, "frappe", SimpleNamespace(
        get_all=get_all,
        get_precision=lambda *_args, **_kwargs: 2,
        has_permission=lambda *_args, **_kwargs: True,
        throw=lambda message, exc=None, **_kwargs: (_ for _ in ()).throw(
            (exc or RuntimeError)(str(message))
        ),
        PermissionError=PermissionError,
        local=SimpleNamespace(),
    ))


def _slip(name, employee, docstatus, journal_entry=None, company="COMPANY_A", start_date="2026-09-01"):
    return frappe._dict(
        name=name, employee=employee, docstatus=docstatus, company=company,
        start_date=start_date, end_date="2026-09-30", journal_entry=journal_entry,
    )


def _je(name, debit=100, credit=100, company="COMPANY_A", docstatus=1):
    return frappe._dict(
        name=name, total_debit=debit, total_credit=credit,
        company=company, docstatus=docstatus, posting_date="2026-09-30",
    )


def test_accrual_reconciliation_accepts_multiple_native_journals(monkeypatch):
    entry = _entry()
    slips = [
        _slip("SS-1", "EMP-1", 1, "JE-1"),
        _slip("SS-2", "EMP-2", 1, "JE-1"),
        _slip("SS-3", "EMP-3", 1, "JE-2"),
    ]
    _install_reconciliation(monkeypatch, entry, slips, [_je("JE-1"), _je("JE-2")])

    result = payroll_finalization.inspect_payroll_accrual_reconciliation(entry)

    assert result["status"] == "READY"
    assert result["ready"] is True
    assert result["submitted_slip_count"] == 3
    assert result["draft_slip_count"] == 0
    assert result["journal_entry_count"] == 2


def test_partial_native_submission_is_retryable_only_with_valid_accrual(monkeypatch):
    entry = _entry()
    slips = [
        _slip("SS-1", "EMP-1", 1, "JE-1"),
        _slip("SS-2", "EMP-2", 1, "JE-1"),
        _slip("SS-3", "EMP-3", 0),
    ]
    _install_reconciliation(monkeypatch, entry, slips, [_je("JE-1")])

    result = payroll_finalization.inspect_payroll_accrual_reconciliation(entry)

    assert result["status"] == "PARTIAL_SUBMISSION"
    assert result["safe_to_retry"] is True
    assert result["submitted_slip_count"] == 2
    assert result["draft_slip_count"] == 1


@pytest.mark.parametrize(
    ("slips", "journals", "expected"),
    [
        ([
            _slip("SS-1", "EMP-1", 1, None),
            _slip("SS-2", "EMP-2", 0),
            _slip("SS-3", "EMP-3", 0),
        ], [], "ACCRUAL_MISSING"),
        ([
            _slip("SS-1", "EMP-1", 1, "JE-1"),
            _slip("SS-2", "EMP-2", 0),
            _slip("SS-3", "EMP-3", 0),
        ], [_je("JE-1", debit=100, credit=90)], "ACCRUAL_UNBALANCED"),
        ([
            _slip("SS-1", "EMP-1", 1, "JE-1"),
            _slip("SS-2", "EMP-2", 0),
            _slip("SS-3", "EMP-3", 0),
        ], [_je("JE-1", company="COMPANY_B")], "ACCRUAL_MISSING"),
        ([_slip("SS-1", "EMP-1", 1, "JE-1", start_date="2026-08-01")], [_je("JE-1")], "SLIP_UNIVERSE_MISMATCH"),
        ([_slip("SS-1", "EMP-1", 1, "JE-1"), _slip("SS-2", "EMP-1", 0)], [_je("JE-1")], "SLIP_UNIVERSE_MISMATCH"),
        ([_slip("SS-1", "EMP-1", 1, "JE-1"), _slip("SS-C", "EMP-2", 2)], [_je("JE-1")], "SLIP_UNIVERSE_MISMATCH"),
    ],
)
def test_accrual_findings_block_payment_readiness(monkeypatch, slips, journals, expected):
    entry = _entry()
    _install_reconciliation(monkeypatch, entry, slips, journals)

    result = payroll_finalization.inspect_payroll_accrual_reconciliation(entry)

    assert result["status"] == expected
    assert result["ready"] is False


def test_queued_native_submission_is_in_progress_not_universe_mismatch(monkeypatch):
    entry = _entry(status="Queued")
    slips = [_slip("SS-1", "EMP-1", 1, "JE-1")]
    _install_reconciliation(monkeypatch, entry, slips, [_je("JE-1")])

    result = payroll_finalization.inspect_payroll_accrual_reconciliation(entry)

    assert result["status"] == "SUBMISSION_IN_PROGRESS"
    assert result["missing_employees"] == ["EMP-2", "EMP-3"]
    assert result["ready"] is False


def test_failed_native_job_remains_visible_and_retryable_when_records_are_sound(monkeypatch):
    entry = _entry(status="Failed")
    slips = [_slip("SS-1", "EMP-1", 0), _slip("SS-2", "EMP-2", 0), _slip("SS-3", "EMP-3", 0)]
    _install_reconciliation(monkeypatch, entry, slips, [])

    result = payroll_finalization.inspect_payroll_accrual_reconciliation(entry)

    assert result["status"] == "SUBMISSION_FAILED"
    assert result["safe_to_retry"] is True
    assert result["error_message"] == ""


@pytest.fixture
def frappe_site():
    frappe.init(
        site=os.environ.get("FRAPPE_TEST_SITE", "test_workforce.localhost"),
        sites_path=os.environ.get("FRAPPE_TEST_SITES_PATH", "./sites"),
        force=True,
    )
    frappe.connect()
    yield
    frappe.destroy()


def test_native_payroll_entry_extension_preflights_and_queues_over_30(frappe_site, monkeypatch):
    from hrms.payroll.doctype.payroll_entry.payroll_entry import submit_salary_slips_for_employees
    from workforce_suite.workforce_suite.payroll_finalization import PayrollEntryFinalizationMixin

    from frappe.model.base_document import get_controller
    controller = get_controller("Payroll Entry")
    assert issubclass(controller, PayrollEntryFinalizationMixin)

    entry = controller({"doctype": "Payroll Entry"})
    entry.name = "PE-QUEUED-TEST"
    entry.company = "Example Company A"
    entry.custom_workforce_run_key = "TRAD-QUEUED-TEST"
    entry.docstatus = 1
    entry.workflow_state = payroll_finalization.APPROVED_STATE
    entry.status = "Submitted"
    entry.salary_slips_created = 1
    entry.employees = [frappe._dict(employee=f"EMP-{i}") for i in range(31)]
    entry.check_permission = lambda *_args, **_kwargs: None
    entry.get_sal_slip_list = lambda **_kwargs: [(f"SS-{i}",) for i in range(31)]
    db_updates = []
    entry.db_set = lambda *args, **kwargs: db_updates.append((args, kwargs))
    queued = []
    monkeypatch.setattr(frappe, "enqueue", lambda method, *args, **kwargs: queued.append((method, args, kwargs)))
    monkeypatch.setattr(frappe, "msgprint", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(company_context, "assert_company_access", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(payroll_finalization, "inspect_payroll_accrual_reconciliation", lambda *_: {
        "status": "NOT_FINALIZED", "safe_to_retry": True, "draft_slip_count": 31,
        "submitted_slip_count": 0,
    })
    monkeypatch.setattr(payroll_finalization, "_cache_financial_readiness", lambda *_args, **_kwargs: {
        "status": "READY", "blockers": [],
    })

    entry.submit_salary_slips()

    assert db_updates == [(("status", "Queued"), {})]
    assert len(queued) == 1
    assert queued[0][0] is submit_salary_slips_for_employees
    assert len(queued[0][2]["salary_slips"]) == 31


def test_managed_bank_entry_requires_ready_payment_phase(frappe_site, monkeypatch):
    from frappe.model.base_document import get_controller
    from workforce_suite.workforce_suite import payment_readiness

    entry = get_controller("Payroll Entry")({"doctype": "Payroll Entry"})
    entry.company = "Example Company A"
    entry.docstatus = 1
    entry.workflow_state = "Workforce Payroll Approved"
    entry.custom_workforce_run_key = "TRAD-MANAGED-TEST"
    entry.check_permission = lambda *_args, **_kwargs: None
    monkeypatch.setattr(company_context, "assert_company_access", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(payment_readiness, "inspect_payroll_payment_readiness", lambda *_args, **_kwargs: {
        "status": "ACCRUAL_NOT_READY",
        "blockers": [{"reason": "accrual is not ready"}],
    })

    with pytest.raises(frappe.ValidationError, match="Payroll payment is blocked: accrual is not ready"):
        entry.make_bank_entry()


def test_unapproved_managed_payroll_entry_cannot_finalize(frappe_site, monkeypatch):
    from frappe.model.base_document import get_controller
    from workforce_suite.workforce_suite import payroll_finalization

    entry = get_controller("Payroll Entry")({"doctype": "Payroll Entry"})
    entry.company = "Example Company A"
    entry.custom_workforce_run_key = "TRAD-UNAPPROVED-TEST"
    entry.docstatus = 1
    entry.workflow_state = "Workforce Payroll Pending Review"
    entry.check_permission = lambda *_args, **_kwargs: None
    monkeypatch.setattr(company_context, "assert_company_access", lambda *_args, **_kwargs: None)

    with pytest.raises(frappe.ValidationError, match="Only an approved Payroll Entry"):
        entry.submit_salary_slips()


def test_blocked_financial_readiness_prevents_native_batch_delegation(frappe_site, monkeypatch):
    from frappe.model.base_document import get_controller
    from workforce_suite.workforce_suite import payroll_finalization

    entry = get_controller("Payroll Entry")({"doctype": "Payroll Entry"})
    entry.name = "PE-BLOCKED-FINALIZE-TEST"
    entry.company = "Example Company A"
    entry.custom_workforce_run_key = "TRAD-BLOCKED-FINALIZE-TEST"
    entry.docstatus = 1
    entry.workflow_state = payroll_finalization.APPROVED_STATE
    entry.status = "Submitted"
    entry.salary_slips_created = 1
    entry.check_permission = lambda *_args, **_kwargs: None
    monkeypatch.setattr(company_context, "assert_company_access", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(payroll_finalization, "inspect_payroll_accrual_reconciliation", lambda *_args: {
        "status": "NOT_FINALIZED", "safe_to_retry": True,
        "draft_slip_count": 1, "submitted_slip_count": 0,
    })
    monkeypatch.setattr(payroll_finalization, "_cache_financial_readiness", lambda *_args, **_kwargs: {
        "status": "BLOCKED", "blockers": [{"reason": "missing account"}],
    })

    with pytest.raises(frappe.ValidationError, match="missing account"):
        entry.submit_salary_slips()


def test_company_scope_denial_precedes_managed_finalization(frappe_site, monkeypatch):
    from frappe.model.base_document import get_controller
    from workforce_suite.workforce_suite import payroll_finalization

    entry = get_controller("Payroll Entry")({"doctype": "Payroll Entry"})
    entry.company = "COMPANY_B"
    entry.custom_workforce_run_key = "TRAD-OUT-OF-SCOPE-TEST"
    entry.check_permission = lambda *_args, **_kwargs: None

    def deny(company, **_kwargs):
        assert company == "COMPANY_B"
        frappe.throw("Company access denied", frappe.PermissionError)

    monkeypatch.setattr(company_context, "assert_company_access", deny)
    monkeypatch.setattr(payroll_finalization, "inspect_payroll_accrual_reconciliation", lambda *_args: (
        pytest.fail("out-of-scope finalization must stop before record inspection")
    ))

    with pytest.raises(frappe.PermissionError, match="Company access denied"):
        entry.submit_salary_slips()
