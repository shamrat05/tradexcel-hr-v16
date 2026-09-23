"""Native Payroll Entry finalization gates and read-only accrual reconciliation."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

import frappe
from frappe import _
from frappe.utils import cint, getdate


MANAGED_RUN_FIELD = "custom_tradex_run_key"
APPROVED_STATE = "Tradexcel Payroll Approved"


def _payroll_entry(value):
    return frappe.get_doc("Payroll Entry", value) if isinstance(value, str) else value


def inspect_payroll_accrual_reconciliation(payroll_entry):
    """Reconcile actual Salary Slip and Journal Entry records for a managed run."""
    entry = _payroll_entry(payroll_entry)
    from tradex_hr.tradexcel_hr.company_context import assert_company_access

    assert_company_access(entry.company, require_explicit_scope=True)
    if not frappe.has_permission("Payroll Entry", "read", entry):
        frappe.throw(_("You do not have permission to inspect this Payroll Entry."), frappe.PermissionError)
    if not entry.get(MANAGED_RUN_FIELD):
        return {"status": "UNMANAGED_PAYROLL_ENTRY", "ready": False}

    expected = {row.employee for row in entry.get("employees", []) if row.get("employee")}
    slips = frappe.get_all(
        "Salary Slip",
        filters={"payroll_entry": entry.name},
        fields=["name", "employee", "docstatus", "company", "start_date", "end_date", "journal_entry"],
        order_by="employee asc",
    )
    active = [row for row in slips if cint(row.docstatus) != 2]
    drafts = [row for row in active if cint(row.docstatus) == 0]
    submitted = [row for row in active if cint(row.docstatus) == 1]
    cancelled = [row for row in slips if cint(row.docstatus) == 2]

    by_employee = defaultdict(list)
    for slip in active:
        by_employee[slip.employee].append(slip)
    duplicate_employees = sorted(employee for employee, rows in by_employee.items() if len(rows) != 1)
    actual = set(by_employee)
    missing_employees = sorted(expected - actual)
    unexpected_employees = sorted(actual - expected)
    wrong_company = sorted(slip.name for slip in active if slip.company != entry.company)
    wrong_period = sorted(
        slip.name for slip in active
        if getdate(slip.start_date) != getdate(entry.start_date)
        or getdate(slip.end_date) != getdate(entry.end_date)
    )

    linked_names = {slip.journal_entry for slip in submitted if slip.journal_entry}
    journal_entries = frappe.get_all(
        "Journal Entry",
        filters={"name": ["in", sorted(linked_names)]},
        fields=["name", "company", "docstatus", "posting_date", "total_debit", "total_credit"],
    ) if linked_names else []
    journal_by_name = {row.name: row for row in journal_entries}
    missing_accrual_slips = sorted(
        slip.name for slip in submitted
        if not slip.journal_entry or slip.journal_entry not in journal_by_name
    )
    invalid_journal_entries = sorted(
        row.name for row in journal_entries
        if cint(row.docstatus) != 1 or row.company != entry.company
        or getdate(row.posting_date) != getdate(entry.posting_date)
    )
    precision = cint(frappe.get_precision("Journal Entry Account", "debit") or 2)
    tolerance = Decimal(1).scaleb(-precision)
    unbalanced_journal_entries = sorted(
        row.name for row in journal_entries
        if abs(Decimal(str(row.total_debit or 0)) - Decimal(str(row.total_credit or 0))) >= tolerance
    )

    failed = entry.status == "Failed"
    queued = entry.status == "Queued"
    universe_mismatch = bool(
        duplicate_employees or unexpected_employees or wrong_company or wrong_period or cancelled
        or (missing_employees and not (queued or failed))
    )

    if universe_mismatch:
        status = "SLIP_UNIVERSE_MISMATCH"
    elif missing_accrual_slips or invalid_journal_entries:
        status = "ACCRUAL_MISSING"
    elif unbalanced_journal_entries:
        status = "ACCRUAL_UNBALANCED"
    elif failed:
        status = "SUBMISSION_FAILED"
    elif queued:
        status = "SUBMISSION_IN_PROGRESS"
    elif drafts and submitted:
        status = "PARTIAL_SUBMISSION"
    elif drafts or not entry.salary_slips_created:
        status = "NOT_FINALIZED"
    else:
        status = "READY"

    retryable = (
        bool(drafts)
        and not universe_mismatch
        and not missing_accrual_slips
        and not invalid_journal_entries
        and not unbalanced_journal_entries
        and not queued
        and entry.docstatus == 1
        and entry.workflow_state == APPROVED_STATE
        and bool(entry.salary_slips_created)
    )
    return {
        "status": status,
        "ready": status == "READY",
        "safe_to_retry": retryable,
        "payroll_entry": entry.name,
        "company": entry.company,
        "expected_employee_count": len(expected),
        "salary_slip_count": len(slips),
        "submitted_slip_count": len(submitted),
        "draft_slip_count": len(drafts),
        "cancelled_slip_count": len(cancelled),
        "journal_entry_count": len(linked_names),
        "missing_employees": missing_employees,
        "unexpected_employees": unexpected_employees,
        "duplicate_employees": duplicate_employees,
        "wrong_company_slips": wrong_company,
        "wrong_period_slips": wrong_period,
        "missing_accrual_slips": missing_accrual_slips,
        "invalid_journal_entries": invalid_journal_entries,
        "unbalanced_journal_entries": unbalanced_journal_entries,
        "error_message": entry.get("error_message") or "",
    }


def _cache_financial_readiness(entry, *, allow_partial_submission=False):
    from tradex_hr.tradexcel_hr.financial_readiness import inspect_payroll_financial_readiness

    result = inspect_payroll_financial_readiness(
        entry, allow_partial_submission=allow_partial_submission
    )
    cache = getattr(frappe.local, "tradex_financial_readiness", None)
    if cache is None:
        cache = frappe.local.tradex_financial_readiness = {}
    cache[entry.name] = result
    return result


def readiness_for_batch_submission(entry):
    """Revalidate remaining slips; prior accruals must reconcile before retry."""
    submitted = frappe.get_all(
        "Salary Slip",
        filters={"payroll_entry": entry.name, "docstatus": 1},
        fields=["name", "journal_entry"],
    )
    allow_partial = False
    if submitted and any(row.journal_entry for row in submitted):
        reconciliation = inspect_payroll_accrual_reconciliation(entry)
        if not reconciliation.get("safe_to_retry"):
            frappe.throw(
                _("Payroll retry is blocked by accrual reconciliation: {0}.").format(
                    reconciliation["status"]
                )
            )
        allow_partial = True
    elif submitted:
        # No linked accrual exists for an earlier request; the native worker
        # cannot repair that prior submission by creating another batch entry.
        frappe.throw(_("A submitted Salary Slip has no linked native accrual Journal Entry."))

    return _cache_financial_readiness(entry, allow_partial_submission=allow_partial)


def _raise_if_blocked(result):
    if result["status"] == "READY":
        return
    reason = result.get("blockers", [{}])[0].get("reason") if result.get("blockers") else None
    frappe.throw(
        _("Payroll cannot be finalized because financial readiness is blocked: {0}").format(
            reason or _("Review the financial readiness findings.")
        ),
        title=_("Payroll Financial Review Required"),
    )


class PayrollEntryFinalizationMixin:
    """Add preflights while delegating payroll accounting work to native HRMS."""

    @frappe.whitelist(methods=["POST"])
    def submit_salary_slips(self):
        if not self.get(MANAGED_RUN_FIELD):
            return super().submit_salary_slips()

        self.check_permission("write")
        from tradex_hr.tradexcel_hr.company_context import assert_company_access

        assert_company_access(self.company, require_explicit_scope=True)
        if self.docstatus != 1 or self.workflow_state != APPROVED_STATE:
            frappe.throw(_("Only an approved Payroll Entry can finalize Salary Slips."))
        if not self.salary_slips_created or self.status == "Queued":
            frappe.throw(_("Native Salary Slip creation or processing is still in progress."))
        if self.status == "Failed" and not self.salary_slips_created:
            frappe.throw(_("Resolve the Salary Slip creation error before finalizing payroll."))

        reconciliation = inspect_payroll_accrual_reconciliation(self)
        if not reconciliation.get("safe_to_retry") and reconciliation["status"] not in {"NOT_FINALIZED"}:
            frappe.throw(
                _("Payroll cannot be finalized: {0}. Open Payroll Entry and resolve the listed issue.").format(
                    reconciliation["status"]
                )
            )
        if not reconciliation.get("draft_slip_count"):
            frappe.throw(_("No unsubmitted Salary Slips remain in this Payroll Entry."))

        partial = bool(reconciliation.get("submitted_slip_count"))
        _raise_if_blocked(_cache_financial_readiness(self, allow_partial_submission=partial))
        return super().submit_salary_slips()

    @frappe.whitelist(methods=["POST"])
    def make_bank_entry(self, for_withheld_salaries=False, *args, **kwargs):
        if not self.get(MANAGED_RUN_FIELD):
            return super().make_bank_entry(
                for_withheld_salaries=for_withheld_salaries, *args, **kwargs
            )

        self.check_permission("write")
        from tradex_hr.tradexcel_hr.company_context import assert_company_access
        from tradex_hr.tradexcel_hr.payment_readiness import inspect_payroll_payment_readiness

        assert_company_access(self.company, require_explicit_scope=True)
        if self.docstatus != 1 or self.workflow_state != APPROVED_STATE:
            frappe.throw(_("Only Director-approved payroll can prepare a payment entry."))

        readiness = inspect_payroll_payment_readiness(
            self, for_withheld_salaries=bool(for_withheld_salaries)
        )
        if readiness["blockers"]:
            reason = readiness["blockers"][0]["reason"]
            frappe.throw(
                _("Payroll payment is blocked: {0}").format(reason),
                title=_("Payroll Payment Review Required"),
            )

        if readiness["status"] == "READY_TO_PREPARE_PAYMENT":
            return super().make_bank_entry(
                for_withheld_salaries=for_withheld_salaries, *args, **kwargs
            )

        if readiness.get("payment_journal_entry"):
            return frappe.get_doc("Journal Entry", readiness["payment_journal_entry"])

        reason = readiness["blockers"][0]["reason"] if readiness["blockers"] else readiness["status"]
        frappe.throw(_("Payroll payment cannot proceed: {0}").format(reason))


@frappe.whitelist()
def get_payroll_accrual_reconciliation(payroll_entry: str):
    return inspect_payroll_accrual_reconciliation(payroll_entry)
