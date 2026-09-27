# Accounting reconciliation closure — 2026-09-27

Parent PR #39 (`4ddffbe99d97eccc133295b952edcfde1a534a4f`). Branch
`feat/accounting-reconciliation`. Existing native accounting remains canonical.

## Audit and reproduction

Existing services already expose missing/duplicate/wrong-company/wrong-period
Salary Slips, draft/partial/failed accrual, cancelled or missing accrual Journals,
unbalanced Journals, payment-mode/account/bank-snapshot blockers, missing,
duplicate, cancelled or invalid payment Journals, bank reconciliation state,
withheld-salary review, correction/arrear provenance and F&F settlement evidence.
F&F validates its native payable/receivable/accounting rows. No second report,
accounting ledger, salary engine or legal calculation is needed.

A real synthetic native payroll fixture reproduced one missing exception:
a balanced **half-sized draft Bank Entry** still returned `PAYMENT_ENTRY_DRAFT`
and was eligible for native retry reuse. Before-fix fixture passed and explicitly
printed that state. The fixture restored its original draft amounts before
continuing normal submission/reconciliation; no real vouchers were used.

## Change

Payment readiness now compares the native payment's referenced payroll-payable
debits against payroll-payable credits in the submitted accrual Journal Entries
linked by the selected submitted Salary Slips. All amounts use native company-
currency `debit`/`credit` at Journal Entry Account precision. Multiple accruals
from partial submission/retry are aggregated exactly once. No Salary Structure
formula or statutory amount is recalculated.

Missing source references, underpayment and overpayment produce
`PAYMENT_AMOUNT_REVIEW_REQUIRED`, with source voucher names, expected payable,
actual payable and difference. An intentionally partial payment remains a Finance
review; it is not falsely described as the completed payroll settlement. The
existing native payment-retry gate respects this blocker. No Journal Entry or
submitted history is automatically changed or cancelled.

When a shared accrual contains withheld salaries, native Employee party rows may
identify the payable subset. A pooled accrual without that evidence stays review-
required; net pay is not used to guess its allocation. The existing explicit
withheld-payment review gate remains.

Company/User Permission and full Payroll Entry Employee-population access are
checked before reconciliation. Existing financial audience and native voucher
links remain. Bank details are not added to returned data.

## Evidence and limits

The durable native fixture now verifies half-payment detection, blocked retry,
restored valid draft, native submission, actual Bank Transaction reconciliation,
and native Cash path. Unit cases cover under/over/exact payment, company-currency
amounts, missing accrual references and pooled/Employee-wise withholding.

No metadata, schema or JS changed: no migration, backup or asset build needed.
This is accounting-evidence closure, not certification of real company account
mappings, tax, bank details, cash receipt, statutory contributions or actual
payments. Existing accrual gates prove source/voucher integrity; this change does
not reconstruct historical expense-account allocation using today's mutable
Salary Component/Cost Center configuration. Finance must approve those mappings.

Final test and cleanup results follow below.

Validation: before-fix synthetic reproduction **1 passed**; native payment plus
focused readiness **34 passed**, broader accounting/separation **74 passed**.
Final full suite **627 passed, 0 skipped** (96 warnings, 468.22 seconds). The first
full run exposed a unit fixture's dependency on warmed DocType precision metadata;
its mocked DB now supplies deterministic precision. No production code workaround
was added. Compileall, 61 JSON parses and diff check passed. Native fixture cleanup
removed its payroll, Journal Entries, Bank Transactions and related synthetic
records; 16-prefix identity/linked-record audit was zero.
