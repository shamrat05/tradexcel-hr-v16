"""Read-only payment readiness for managed native Payroll Entries.

Salary Slip payment snapshots remain authoritative for the approved period.
Actual payment accounting and bank matching are delegated to HRMS/ERPNext.
"""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from tradex_hr.tradexcel_hr.company_context import assert_company_access
from tradex_hr.tradexcel_hr.payroll_finalization import inspect_payroll_accrual_reconciliation

MANAGED_RUN_FIELD = "custom_tradex_run_key"
PAYMENT_MODE_REVIEW = "PAYMENT_MODE_REVIEW_REQUIRED"
MIXED_MODE_REVIEW = "MIXED_PAYMENT_MODE_REVIEW_REQUIRED"


def _mode_findings(slips: list[dict]) -> tuple[dict[str, int], list[dict]]:
    counts: dict[str, int] = {}
    for slip in slips:
        mode = (slip.get("mode_of_payment") or "").strip()
        counts[mode or "<blank>"] = counts.get(mode or "<blank>", 0) + 1

    blockers = []
    if not slips:
        blockers.append({"code": PAYMENT_MODE_REVIEW, "reason": _("No payable Salary Slips were found.")})
    elif len(counts) > 1:
        blockers.append({
            "code": MIXED_MODE_REVIEW,
            "reason": _("This Payroll Entry has more than one payment mode. Review the payment batch with Finance."),
        })
    else:
        mode = next(iter(counts))
        if mode not in {"Bank", "Cash"}:
            blockers.append({
                "code": PAYMENT_MODE_REVIEW,
                "reason": _("Salary payment mode is blank or unsupported. Settle this with Finance before payment."),
            })
    return counts, blockers


def _payment_account_findings(entry, expected_type: str) -> list[dict]:
    findings = []
    account_name = entry.get("payment_account")
    if not account_name:
        return [{
            "code": "PAYMENT_ACCOUNT_MISSING",
            "reason": _("Select a payment account on Payroll Entry."),
        }]

    account = frappe.db.get_value(
        "Account",
        account_name,
        ["company", "is_group", "disabled", "account_type", "account_currency"],
        as_dict=True,
    )
    if not account:
        return [{
            "code": "PAYMENT_ACCOUNT_INVALID",
            "reason": _("The selected payment account no longer exists."),
        }]

    currency = entry.get("currency") or frappe.get_cached_value("Company", entry.company, "default_currency")
    valid = (
        account.company == entry.company
        and not account.is_group
        and not account.disabled
        and account.account_type == expected_type
        and (not account.account_currency or account.account_currency == currency)
    )
    if not valid:
        findings.append({
            "code": "PAYMENT_ACCOUNT_INVALID",
            "reason": _("The payment account must be an enabled {0} account in {1} with compatible currency.").format(
                expected_type, entry.company
            ),
        })

    if expected_type == "Bank":
        bank_account_name = entry.get("bank_account")
        bank_account = frappe.db.get_value(
            "Bank Account",
            bank_account_name,
            ["account", "company", "is_company_account", "disabled", "bank_account_no"],
            as_dict=True,
        ) if bank_account_name else None
        if not bank_account or (
            bank_account.account != account_name
            or bank_account.company != entry.company
            or not bank_account.is_company_account
            or bank_account.disabled
            or not bank_account.bank_account_no
        ):
            findings.append({
                "code": "PAYMENT_BANK_ACCOUNT_INVALID",
                "reason": _("Choose an enabled company Bank Account linked to this payment account and company."),
            })
    return findings


def _linked_payment_entries(payroll_entry: str) -> tuple[list, list]:
    references = frappe.get_all(
        "Journal Entry Account",
        filters={"reference_type": "Payroll Entry", "reference_name": payroll_entry},
        pluck="parent",
        distinct=True,
    )
    active, cancelled = [], []
    for name in sorted(set(references)):
        je = frappe.get_doc("Journal Entry", name)
        if je.voucher_type not in {"Bank Entry", "Cash Entry"}:
            continue
        (cancelled if je.docstatus == 2 else active).append(je)
    return active, cancelled


def _payment_entry_identity_issue(entry, journal_entry, expected_mode: str) -> str | None:
    """Check the native JE identity/shape without recalculating payroll accounting."""
    expected_voucher = {"Bank": "Bank Entry", "Cash": "Cash Entry"}.get(expected_mode)
    if not expected_voucher:
        return _("The payroll payment mode is not supported.")
    if journal_entry.company != entry.company:
        return _("The linked payment Journal Entry belongs to a different company.")
    if journal_entry.docstatus not in {0, 1}:
        return _("The linked payment Journal Entry is not active.")
    if journal_entry.voucher_type != expected_voucher:
        return _("The linked Journal Entry type does not match the payroll payment mode.")

    rows = journal_entry.get("accounts") or []
    payment_rows = [
        row for row in rows
        if row.get("account") == entry.get("payment_account") and flt(row.get("credit")) > 0
    ]
    if not payment_rows or any(flt(row.get("debit")) > 0 for row in payment_rows):
        return _("The Journal Entry has no valid credit to the selected payroll payment account.")
    if expected_mode == "Bank" and any(
        row.get("bank_account") != entry.get("bank_account") for row in payment_rows
    ):
        return _("The Journal Entry uses a different company Bank Account.")

    payroll_refs = [row for row in rows if row.get("reference_type") == "Payroll Entry"]
    if any(row.get("reference_name") != entry.name for row in payroll_refs):
        return _("The Journal Entry also references a different Payroll Entry.")
    payable_rows = [
        row for row in payroll_refs
        if row.get("reference_name") == entry.name
        and row.get("account") == entry.get("payroll_payable_account")
        and flt(row.get("debit")) > 0
        and flt(row.get("credit")) <= 0
    ]
    if not payable_rows:
        return _("The Journal Entry has no payroll-payable debit linked to this Payroll Entry.")

    if journal_entry.docstatus == 1:
        precision = frappe.get_precision("Journal Entry", "total_debit") or 2
        tolerance = 10 ** (-int(precision))
        if abs(flt(journal_entry.total_debit) - flt(journal_entry.total_credit)) >= tolerance:
            return _("The submitted payment Journal Entry is not balanced.")
    return None


def _bank_reconciled(je) -> tuple[bool, list[dict]]:
    allocations = frappe.get_all(
        "Bank Transaction Payments",
        filters={"payment_document": "Journal Entry", "payment_entry": je.name},
        fields=["parent", "clearance_date"],
    )
    transactions = []
    for allocation in allocations:
        transaction = frappe.db.get_value(
            "Bank Transaction",
            allocation.parent,
            ["docstatus", "status"],
            as_dict=True,
        )
        if transaction and transaction.docstatus == 1 and transaction.status == "Reconciled":
            transactions.append({
                "name": allocation.parent,
                "status": transaction.status,
                "clearance_date": allocation.clearance_date,
            })
    return bool(je.clearance_date and transactions), transactions


def inspect_payroll_payment_readiness(payroll_entry, *, for_withheld_salaries: bool = False) -> dict:
    """Inspect payment setup and native payment/reconciliation records, without writing."""
    entry = frappe.get_doc("Payroll Entry", payroll_entry) if isinstance(payroll_entry, str) else payroll_entry
    entry.check_permission("read")
    assert_company_access(entry.company, require_explicit_scope=True)

    if not entry.get(MANAGED_RUN_FIELD):
        return {
            "status": "PAYROLL_NOT_MANAGED",
            "payroll_entry": entry.name,
            "company": entry.company,
            "blockers": [{"code": "PAYROLL_NOT_MANAGED", "reason": _("This Payroll Entry is not managed by Payroll Readiness.")}],
            "warnings": [],
        }

    accrual = inspect_payroll_accrual_reconciliation(entry)
    if accrual.get("status") != "READY":
        return {
            "status": "ACCRUAL_NOT_READY",
            "payroll_entry": entry.name,
            "company": entry.company,
            "accrual_status": accrual.get("status"),
            "blockers": [{
                "code": "ACCRUAL_NOT_READY",
                "reason": _("Payroll accrual must reconcile before payment can be prepared."),
            }],
            "warnings": [],
        }

    if for_withheld_salaries:
        return {
            "status": "WITHHELD_PAYMENT_REVIEW_REQUIRED",
            "payroll_entry": entry.name,
            "company": entry.company,
            "accrual_status": accrual.get("status"),
            "blockers": [{
                "code": "WITHHELD_PAYMENT_REVIEW_REQUIRED",
                "reason": _("Native withheld-salary payments need a separate Finance review before preparation."),
            }],
            "warnings": [],
        }

    fields = ["name", "employee", "net_pay", "mode_of_payment", "bank_name", "bank_account_no", "status"]
    slips = frappe.get_all(
        "Salary Slip",
        filters={"payroll_entry": entry.name, "docstatus": 1},
        fields=fields,
        order_by="employee",
    )
    withheld_slips = [slip for slip in slips if slip.get("status") == "Withheld"]
    payment_slips = [
        slip for slip in slips
        if (slip.get("status") == "Withheld") == bool(for_withheld_salaries)
    ]
    mode_counts, blockers = _mode_findings(payment_slips)
    mode = next(iter(mode_counts)) if len(mode_counts) == 1 else None

    warnings = []
    bank_mode_slips = [slip for slip in payment_slips if slip.get("mode_of_payment") == "Bank"]
    if bank_mode_slips:
        employees = frappe.get_all(
            "Employee",
            filters={"name": ["in", [slip.get("employee") for slip in bank_mode_slips]]},
            fields=["name", "salary_mode", "bank_name", "bank_ac_no"],
        )
        current_by_employee = {employee.get("name"): employee for employee in employees}
        changed = []
        missing = []
        for slip in bank_mode_slips:
            if not slip.get("bank_name") or not slip.get("bank_account_no"):
                missing.append(slip.get("employee"))
                continue
            employee = current_by_employee.get(slip.get("employee"))
            if employee and (
                employee.get("salary_mode") != slip.get("mode_of_payment")
                or employee.get("bank_name") != slip.get("bank_name")
                or employee.get("bank_ac_no") != slip.get("bank_account_no")
            ):
                changed.append(slip.get("employee"))
        if missing:
            blockers.append({
                "code": "PAYMENT_BANK_DETAILS_MISSING",
                "reason": _("Bank payment details are missing from {0} approved Salary Slip snapshots.").format(len(missing)),
                "employees": missing,
            })
        if changed:
            warnings.append({
                "code": "BANK_DETAILS_CHANGED_AFTER_PAYROLL",
                "reason": _("Current Employee bank details differ from the approved Salary Slip snapshot for {0} employee(s). The snapshot remains in effect.").format(len(changed)),
                "employees": changed,
            })

    if mode in {"Bank", "Cash"}:
        blockers.extend(_payment_account_findings(entry, "Bank" if mode == "Bank" else "Cash"))

    active_entries, cancelled_entries = _linked_payment_entries(entry.name)
    payment_entry = None
    bank_transactions = []
    if len(active_entries) > 1:
        blockers.append({
            "code": "PAYMENT_ENTRY_AMBIGUOUS",
            "reason": _("More than one active payment Journal Entry is linked to this Payroll Entry."),
        })
        status = "PAYMENT_ENTRY_AMBIGUOUS"
    elif cancelled_entries and not active_entries:
        blockers.append({
            "code": "PAYMENT_ENTRY_CANCELLED",
            "reason": _("A linked payment Journal Entry was cancelled. Review with Finance before creating another."),
        })
        status = "PAYMENT_ENTRY_CANCELLED"
    elif active_entries:
        payment_entry = active_entries[0]
        identity_issue = _payment_entry_identity_issue(entry, payment_entry, mode)
        if identity_issue:
            blockers.append({
                "code": "PAYMENT_ENTRY_INVALID",
                "reason": _("A linked Journal Entry is not a valid native payroll payment: {0}").format(identity_issue),
            })
            status = "PAYMENT_ENTRY_INVALID"
        elif payment_entry.docstatus == 0:
            status = "PAYMENT_ENTRY_DRAFT"
        elif payment_entry.voucher_type == "Cash Entry":
            status = "CASH_PAYMENT_ACCOUNTING_POSTED"
        else:
            reconciled, bank_transactions = _bank_reconciled(payment_entry)
            status = "BANK_RECONCILED" if reconciled else "AWAITING_BANK_RECONCILIATION"
    else:
        status = "READY_TO_PREPARE_PAYMENT" if not blockers else blockers[0]["code"]

    return {
        "status": status,
        "payroll_entry": entry.name,
        "company": entry.company,
        "accrual_status": accrual.get("status"),
        "employee_count": len(payment_slips),
        "withheld_employee_count": len(withheld_slips),
        "payment_mode": mode,
        "payment_mode_counts": mode_counts,
        "payment_account": entry.get("payment_account"),
        "payment_journal_entry": payment_entry.name if payment_entry else None,
        "payment_journal_entry_docstatus": payment_entry.docstatus if payment_entry else None,
        "payment_journal_entry_type": payment_entry.voucher_type if payment_entry else None,
        "payment_journal_entry_amount": (
            payment_entry.total_credit if payment_entry and payment_entry.docstatus == 1
            else None
        ),
        "clearance_date": payment_entry.clearance_date if payment_entry else None,
        "bank_transactions": bank_transactions,
        "payment_status": status,
        "blockers": blockers,
        "warnings": warnings,
        "net_pay_reference_total": sum(flt(slip.get("net_pay")) for slip in payment_slips),
    }


@frappe.whitelist()
def get_payroll_payment_readiness(payroll_entry: str):
    return inspect_payroll_payment_readiness(payroll_entry)
