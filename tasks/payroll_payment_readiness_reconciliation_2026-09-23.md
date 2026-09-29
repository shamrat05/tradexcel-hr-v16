# Payroll Payment Readiness and Reconciliation — 2026-09-23

## Scope

This branch adds read-only payment readiness for managed Payroll Entries and delegates payment accounting and bank reconciliation to native HRMS/ERPNext documents. It does not add a payment ledger, bank export, or custom accounting calculations.

Flow:

1. A director-approved managed Payroll Entry must pass accrual reconciliation.
2. The operator checks payment readiness against submitted Salary Slip payment snapshots and the Payroll Entry payment account.
3. Payroll Manager prepares one native draft Bank Entry or Cash Entry through `PayrollEntry.make_bank_entry()`.
4. Finance reviews and submits the native Journal Entry.
5. Bank payments remain pending until native Bank Transaction reconciliation sets Journal Entry `clearance_date`. Cash is reported as accounting-posted, not bank-reconciled.

## Native behavior and safeguards

- HRMS uses one Payroll Entry `payment_account` for a payment batch. Mixed Bank/Cash/other employee snapshots fail closed for Finance review; no custom split is attempted.
- Employee payment mode, bank name, and bank account number on the submitted Salary Slip are authoritative for this payroll. Changed current Employee details create a warning and never replace that snapshot.
- Bank mode requires snapshot bank name/account number plus a same-company, enabled company Bank Account linked to an enabled Bank Account type GL account.
- Cash mode requires a same-company enabled Cash account and no Bank Account.
- Blank, Cheque, and unknown modes require review until a supported native workflow is selected.
- Withheld slips are separated using native Salary Slip `status == "Withheld"`, matching HRMS's native `get_salary_slip_details()` filter.
- Linked Bank/Cash Journal Entries are reused only after validating company, voucher type, selected payment-account credit, the selected Bank Account for Bank mode, and one or more Payroll Payable debit rows referencing this Payroll Entry. A submitted entry must balance. Multiple active entries and a cancelled-only payment entry block retries.
- Withheld-salary payment requests stop for Finance review. Native v16 exposes no stable structured marker separate from translated user_remark text for classifying the release entry, so the app does not parse English remarks.
- Native Bank Transaction allocations, Reconciled status, and Journal Entry `clearance_date` are used to report bank reconciliation. A submitted payment Journal Entry alone is not called paid.
- Full employee/company account numbers are not returned in the readiness response.

The Payroll Manager can prepare the native draft using existing Payroll Entry write authority after the managed workflow and readiness checks. An Accounts role reviews/submits the Journal Entry using native Accounts permissions. No payment entry is auto-submitted.

## Read-only staging evidence

Site: `hrms-v16.localhost`, company: `Tradexcel Ceramics Ltd.`

- 240 currently Active Employee records: 208 Cash, 2 Bank, 30 blank; 0 Cheque.
- Both Bank-mode employees have `bank_name`; both lack `bank_ac_no`.
- There are no submitted Salary Slips for this company, so there are no real period snapshots to inspect.
- Payroll Settings employee-wise accounting is disabled.
- No Salary Withholding records or active withholding cycle were found.
- Company default payment-account fields contain values, but the site has no company Bank Account records; the Bank Account link therefore needs Finance review.
- No real payment, Bank/Cash Entry, or Bank Transaction was created.

These are present-day Employee counts, not a payroll-period population. Previously recorded attendance, salary structure, SSA, tax, payable-account, and component-mapping blockers remain unchanged. This work did not modify them.

## Verification

- Payment readiness tests cover accrual gating, Bank/Cash/unknown/mixed modes, missing snapshot data, account company/type/currency checks, required linked company Bank Account, changed Employee bank details, explicit company scope, native payment Journal Entry identity/shape, and withheld-payment review.
- Synthetic native integration covers partial Salary Slip submission and retry, native accrual Journal Entries, native Bank Entry draft and idempotent retry before/after posting, submission by a scoped ERPNext Accounts User, native Bank Transaction reconciliation and `clearance_date`, plus a submitted native Cash Entry that reports `CASH_PAYMENT_ACCOUNTING_POSTED` without fabricating a bank match. All synthetic entries are removed during explicit cleanup.
- Integration cleanup explicitly removes the synthetic Bank Transaction, Journal Entries, GL Entries, Bank Account, Bank, accounts, employee, attendance, and payroll records; assertions verify the synthetic Company and its GL records are gone.
- Real queued worker E2E (>30 employees) remains a pre-production release gate.
