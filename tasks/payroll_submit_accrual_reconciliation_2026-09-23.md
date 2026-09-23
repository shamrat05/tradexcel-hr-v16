# Payroll submission and accrual reconciliation — 2026-09-23

## Scope

Stacked on `feat/payroll-financial-readiness` at `23c55ec`. This phase finalizes
approved managed payroll only through native HRMS
`PayrollEntry.submit_salary_slips()`, then reads the native Salary Slips and
Journal Entries to reconcile the result. It does not create custom accounting
entries, release payment, export bank files, or submit real staging payroll.

The operator path is:

```text
Payroll Readiness → Prepare → Submit for Review → Review → Director Approval
→ Finalize Payroll → Accrual Reconciled
```

Payment remains unavailable for managed Payroll Entries.

## Native lifecycle and safeguards

- Frappe v16's `extend_doctype_class` adds a narrow Payroll Entry preflight.
  Unmanaged Payroll Entries delegate unchanged to HRMS. Managed payroll requires
  an explicitly company-scoped user, a submitted Payroll Entry in
  `Tradexcel Payroll Approved`, completed native draft Salary Slips, reconciled
  prior accruals on retry, and current financial readiness. The method then
  delegates to native `submit_salary_slips()` exactly once.
- HRMS calls `SalarySlip.submit()` inside its batch helper with
  `frappe.flags.via_payroll_entry = True`. Managed direct/API Salary Slip
  submission is rejected unless that native flag is set. The gate checks
  approval and financial readiness again in the worker request. HRMS uses
  `Queued` while processing a batch larger than 30; the guard permits that state
  only from the native helper, while reconciliation continues to report
  `SUBMISSION_IN_PROGRESS`.
- Payroll Manager receives the native Salary Slip `submit` right needed by
  HRMS's own `doc.submit()` call. The app's server-side gate still blocks direct
  managed slip submission. Additional Salary submit rights remain unchanged.
- Retry delegates to HRMS for remaining draft slips. The read-only
  reconciliation accepts multiple native accrual Journal Entries after a
  partial batch and retry. It checks the employee universe, duplicate or
  cancelled slips, company and period, each submitted slip's JE link, JE
  submission/company/posting date, and debit-credit balance. It does not
  reimplement payroll accounting math.
- Payroll Entry's Company cost center is copied during managed preparation,
  matching the field HRMS Desk normally fetches from Company. Financial
  readiness now checks it separately because native HRMS uses it on the
  Payroll Payable accrual line; employee cost-center checks alone did not cover
  that balance-sheet row.
- The native Payroll Entry Desk action is replaced by `Finalize Payroll` or
  `Retry Unsubmitted Salary Slips`, based on server reconciliation. Final,
  partial, failed, queued and accrual problem messages use operator language.
  Managed `Make Bank Entry` stays server-blocked.

## Synthetic native end-to-end proof

The integration fixture creates a disposable company, accounts, cost center,
three employees (two monthly and one Daily Wage), effective Salary Structures
and Assignments, finalized Attendance, and one managed native Payroll Entry.
It submits that Entry through the real workflow, reviews it, completes Director
approval, and proves an individually opened approved Salary Slip still cannot
submit directly.

The real HRMS batch helper then submits employees A and C while a one-time
synthetic validation error leaves employee B draft. Native HRMS creates and
links one accrual JE for A/C. Reconciliation reports `PARTIAL_SUBMISSION` and
allows retry. The retry submits B through the same native Payroll Entry method
and HRMS creates a second native accrual JE. Reconciliation reaches `READY`
with 3 submitted slips, 0 drafts, 0 cancelled slips, and 2 submitted, balanced,
linked JEs. The scenario uses no Employee Checkin records; payroll derives from
the finalized Attendance records and native Salary Slips.

Each native submission call runs under Frappe test mode so HRMS's internal
commit behavior is suppressed. The fixture rolls back, explicitly removes any
synthetic records that survive an upstream commit, and asserts the Company,
Payroll Entry, slips and workflow user are absent.

During the first test attempt, the retry call was accidentally outside test
mode; HRMS committed the isolated fixture. That test company was explicitly
removed before continuing:

```text
Tradexcel Finalization Test E9B9B7F09AC8EF40C9E869BBA87C637CCA1A8983AD27CED959580E35
Payroll Entries: 1
Salary Slips remaining at cleanup: 0
Journal Entries: 2
Additional Salary: 1
Attendance: 93
Company after cleanup: absent
```

The test now keeps the retry in test mode and has an explicit scoped cleanup
fallback. The subsequent integration run passed and its own cleanup assertions
passed.

The final artifact audit found that deleting those Companies had left the
cloned Account, Cost Center, and Warehouse masters behind; the first explicit
cleanup had also left synthetic ledger rows for two older committed attempts.
Three exact test-company scopes were cleaned:

```text
Tradexcel Finalization Test 8A81BEE761EB0F5B2523BCE6565B1430725AEDB2260E937A94D96372
Tradexcel Finalization Test 8E55BC27AAE6141540D18BBFD12F4494708D3ED7324838E57F9209D9
Tradexcel Finalization Test E9B9B7F09AC8EF40C9E869BBA87C637CCA1A8983AD27CED959580E35
```

The fixture cleanup now removes records by the unique company link, cancels and
deletes its synthetic payroll documents, removes its GL Entry rows created by
the native accrual/cancellation path, deletes nested company masters deepest
first, and only then removes the Company. It refuses any name outside the
`Tradexcel Finalization Test ` prefix. Post-cleanup staging queries returned
zero matching Companies, Accounts, Cost Centers, and GL Entries. A fresh
end-to-end integration run passed and asserted zero remaining Account, Cost
Center, Warehouse, and GL Entry rows for its test company. The full app suite
also left no synthetic Test Companies or finalization test company artifacts.

## Other verification

- Reconciliation unit tests cover multiple accrual JEs, queued and failed
  states, partial submissions, missing/unbalanced/wrong-company accruals,
  duplicate and cancelled employee slips, and wrong-period slips.
- Native queue tests prove a 31-slip Payroll Entry takes HRMS's queued worker
  route, queued status is not considered final, and the native worker's
  `via_payroll_entry` flag can pass the submission readiness gate.
- Direct managed submit, unapproved Payroll Entry, blocked financial readiness,
  cross-company access, missing payable cost center, and pre-payment blocking
  are covered.
- `make_accrual_jv_entry()` remains upstream HRMS behavior. Tradexcel contains
  no custom Journal Entry creation path.

## Verification record

Focused Phase A/Phase B payroll tests: 81 passed.

Final full app suite: 304 passed, 2 skipped, 13 upstream deprecation warnings.
`compileall`, `node --check`, `bench clear-cache`, and `git diff --check` passed.
The first full suite found three stale expectations after the added company
cost-center field and native Salary Slip submit permission; their fixtures and
assertions were updated before the passing rerun.

PR remains open/unmerged; no production action is part of this change.


## Post-review Salary Slip permission correction

PR #9 review found that granting Salary Slip submit permission to Tradexcel Payroll Manager also allowed a standalone or unmanaged Salary Slip to reach native submission. The server hook now limits users whose submit authority comes only from Tradexcel Payroll Manager or Tradexcel Payroll Approver to an approved, managed Payroll Entry batch. Managed direct submission remains blocked; the native Payroll Entry batch uses Frappe's via_payroll_entry flag and is rechecked for approval and current financial readiness.

Payroll Approver no longer has Salary Slip submit permission. Payroll Manager retains the native submit permission required by HRMS batch submission. Users who also hold another role with an explicit Salary Slip submit DocPerm retain that independent native authority; Administrator and System Manager behavior remains unchanged. The role-only restriction decision is cached for the request so batch processing does not query role permissions per employee.

Regression tests cover standalone and unmanaged Salary Slips for Payroll Manager and Payroll Approver, a native administrative role, an additional native submit role, the real Approver DocPerm, and the existing synthetic managed native batch/partial-retry flow. The >30 employee test proves that HRMS chooses its queued path; a real disposable asynchronous worker end-to-end run remains a pre-production release gate.
