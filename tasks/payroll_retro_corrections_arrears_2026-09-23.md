# Payroll Corrections and Arrears — 2026-09-23

## Scope and invariant

This branch adds guarded use of native HRMS v16 Payroll Correction and Arrear documents. It does not change submitted historical Salary Slips, recalculate tax, or create a second adjustment ledger.

- Submitted Salary Slips and consumed Daily Wage inputs remain historical payroll truth.
- LWP reversals use native Payroll Correction; retroactive positive salary differences use native Arrear.
- Retroactive reductions stop for an HR/Finance decision. No automatic recovery is generated.
- Adjustments create native Additional Salary with native ref_doctype / ref_docname provenance for a later payroll.
- Daily Wage retroactive changes remain a review-only decision; reopening a consumed Attendance Period is blocked.

## Safeguards

- Payroll Correction source must be submitted and match employee, company, and selected Payroll Period; its dates must belong to that period. LWP reversal cannot exceed the native eligible days.
- Both document types require an authorized, company-scoped HR/Payroll maker. Approval is a separate Payroll Approver workflow transition with self-approval disabled. Employee/Worker has no create authority.
- Approval revalidates the document. The target payroll date must follow source history and must not already be covered by completed payroll.
- Arrear source slips are limited to the selected employee, company, and Payroll Period date range. HRMS still previews and calculates the arrear.
- Cancelling an unconsumed adjustment cancels its linked Additional Salary. If a later submitted Salary Slip consumed it, cancellation is blocked and history remains intact.
- Daily Wage Attendance Periods consumed by a Salary Slip now direct operators to post-payroll adjustment review instead of incorrectly naming LWP Payroll Correction.

## Native integration evidence

A synthetic company integration test created and cleaned up native records. It proved:

1. A native submitted Salary Slip with LWP → Payroll Correction → submitted Additional Salary with source provenance → a later native Salary Slip consumes the adjustment. The historical source slip amount remains unchanged.
2. A retroactive higher Salary Structure → an in-period historical slip candidate only (a later out-of-period slip was present) → native Arrear → native Additional Salary → a later native Salary Slip consumes the adjustment.
3. A lower retroactive component result is rejected during native Arrear validation with RETRO_OVERPAYMENT_DECISION_REQUIRED; no Additional Salary is created.
4. Native cancellation is blocked after consumption. Before consumption, cancelling the parent cancels its generated Additional Salary.

Test artifacts use a disposable Tradexcel Finalization Test <token> company and are explicitly cleaned; cleanup verifies the company and company-linked records are gone. The new test reads Payroll Settings and skips if the site is not already configured with Payroll Based On Leave.

Unit tests cover cross-employee/company/period rejection, future-target blocking, explicit company scope, maker self-approval, independent approver validation, Daily Wage review status, Arrear source bounds, and no automatic recovery.

## Staging evidence and deployment limit

Read-only staging inspection recorded 0 Payroll Corrections, 0 Arrears, 0 linked Additional Salary records, 0 Payroll Periods, and no Salary Components enabled for arrears. Payroll Settings is based on Leave. No real employee or financial configuration was changed.

The staging backup index records the verified hrms-v16.localhost backup taken at 2026-09-23 17:10 Dhaka time before further synthetic cleanup. Its database archive passed gzip -t; Full SHA-256: `d16474ca660a1c3599ca26409eb2080bec0ed5f7b152dade359721a9e9393f19`; BACKUPS.md records its abbreviated prefix. No migration was run. The custom workflow fields and workflows therefore still require standard bench migrate verification on an isolated/release environment before deployment; no manual metadata convergence is claimed.

## Verification

- Focused correction, cancellation, permission, approval-transition, Daily Wage control, and native integration tests: 32 passed, with 2 upstream Frappe deprecation warnings.
- Full Tradexcel app suite: 371 passed, 2 skipped, 14 upstream Frappe deprecation warnings.
- compileall passed; Node syntax check passed; git diff --check passed.
- Workflow schema/UI was not migrated into staging, so the Desk workflow transition remains a release verification gate. The approver role/action policy is covered by tests, and the installed Frappe submit/save ordering was checked directly.
- No production site was touched. No real staging Salary Slip, Additional Salary, Arrear, Payroll Correction, accrual Journal Entry, or payment entry was submitted or created.
