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
- Approval revalidates the document. The target payroll date follows source history and is rejected once a non-cancelled Salary Slip overlaps that date, or a managed Payroll Entry has started salary-slip creation / is queued for the target employee. An untouched draft Payroll Entry remains eligible because native Salary Slips have not begun processing.
- Arrear source slips are limited to the selected employee, company, and Payroll Period date range. HRMS still previews and calculates the arrear.
- Cancelling an unconsumed adjustment cancels its linked Additional Salary. If a later submitted Salary Slip consumed it, cancellation is blocked and history remains intact.
- Daily Wage Attendance Periods consumed by a Salary Slip now direct operators to post-payroll adjustment review instead of incorrectly naming LWP Payroll Correction.

## Native integration evidence

A synthetic company integration test created and cleaned up native records. It proved:

1. A native submitted Salary Slip with LWP → Payroll Correction → submitted Additional Salary with source provenance → a later native Salary Slip consumes the adjustment. The historical source slip amount remains unchanged.
2. A retroactive higher Salary Structure → an in-period historical slip candidate only (a later out-of-period slip was present) → native Arrear → native Additional Salary → a later native Salary Slip consumes the adjustment.
3. A lower retroactive component result is rejected during native Arrear validation with RETRO_OVERPAYMENT_DECISION_REQUIRED; no Additional Salary is created.
4. Native cancellation is blocked after consumption. Before consumption, cancelling the parent cancels its generated Additional Salary.

Test artifacts use a disposable Workforce Finalization Test <token> company and are explicitly cleaned; cleanup verifies the company and company-linked records are gone. The new test reads Payroll Settings and skips if the site is not already configured with Payroll Based On Leave.

Unit tests cover cross-employee/company/period rejection, future-target blocking, explicit company scope, maker self-approval, independent approver validation, Daily Wage review status, Arrear source bounds, and no automatic recovery.

## Staging evidence and migration

Staging was inspected read-only before migration; no real employee or financial configuration was changed. The pre-migration workflow probe found no queued jobs and four failed `delete_dynamic_links` jobs, all for `hrms-v16.localhost` after deleted Salary Structure Assignments. A normal default worker reprocessed those jobs successfully. `bench doctor` then reported one worker online and no remaining site jobs.

Fresh `--with-files` backups were verified and are indexed in `BACKUPS.md` (18:20, 18:32, 18:37, 18:39, and 18:46 Dhaka). Standard `bench migrate` completed after each permission change; `after_migrate` completed. No direct `ensure_*()` calls, manual metadata convergence, queue deletion, or core patch was used. The 18:46 backup database SHA-256 is `1e7797d321840954892588ec126ca08990dc6070e852009541550ba3c66e5a88`.

The synthetic integration test's `finally` cleanup removed its company-linked documents and test users. Direct post-suite query confirmed zero Arrear rows; suite cleanup checks passed. A pre-existing staging Additional Salary record remains outside these test artifacts. No real employee or financial configuration was changed.

## Verification

- Focused correction, target-timing, role-safety, accrual-component and native workflow integration: 43 passed, 6 upstream deprecation warnings.
- Full Workforce app suite: 383 passed, 2 skipped, 18 upstream deprecation warnings.
- compileall passed; `node --check` passed; `git diff --check` passed.
- Native Frappe `apply_workflow` was exercised with disposable users: maker submitted for approval, self-approval was denied, an out-of-company approver was denied, and the same-company Payroll Approver completed native Arrear approval and created native Additional Salary.
- The approver receives only Salary Slip read/create and company-scoped Employee/Salary Structure read access required by native HRMS preview mapping. Salary Slip write, cancel, delete, and submit remain denied.
- Desk/browser visual verification remains a release gate; server workflow behavior is proven.
- No production site was touched. No real staging Salary Slip, Additional Salary, Arrear, Payroll Correction, accrual Journal Entry, or payment entry was submitted or created.
