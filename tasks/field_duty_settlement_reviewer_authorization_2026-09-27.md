# Field-duty settlement reviewer authorization — 2026-09-27

Correction branch `fix/mobile-review-settlement-actor` is stacked on PR #45
(`fix/mobile-evidence-final-boundaries`).

## Reproduced defect

The flagged mobile OUT review endpoint accepted scoped Tradexcel HR Manager,
HR/Attendance Officer, and Branch Manager users and queued
`settle_field_duty_allowance` under the reviewer actor. Before the correction,
all three real site-backed synthetic flows failed when the queued function ran:
the settlement check recognized only Administrator, the linked Employee, or
Tradexcel Attendance Correction Approver, then rejected the other legitimate
reviewers through the employee-self check.

## Correction

`MOBILE_REVIEW_ROLES` is now defined once beside `SUPERVISOR_ROLES` and is used
by both review authorization and settlement authorization. Settlement allows
Administrator, the linked Employee, or a current member of this review-role set
whose Employee scope still includes the duty's Employee. Scope is recalculated
when the queued function executes. No role or DocPerm was added; settlement
calculation and Additional Salary behavior are unchanged.

## Evidence

The synthetic integration regression runs mobile OUT → Flagged/Pending → scoped
review approval → captured enqueue → queued settlement as the same actor, with
`allowance_mode = None`. It covers HR Manager, HR/Attendance Officer, and
Branch Manager. Each succeeds with “No automatic allowance”; an unrelated
Payroll Manager, an out-of-Branch reviewer, and a reviewer whose Branch scope
changes after approval are denied. The linked Employee's trusted OUT path
continues to settle without creating money. Existing actor-bound job tests
continue to cover lost/invalid job actors and unrelated Frappe jobs.

Focused result: 62 passed across field attendance, mobile boundary, release
security, and background-job safety suites. Full result: 669 passed, 0 skipped.
Compileall, all 61 tracked JSON files, and `git diff --check` passed. No
metadata changed; migration and backup were not required. Synthetic fixtures
use native cleanup and assert zero leftovers.
