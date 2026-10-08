# Bulk Attendance Correction Preparation + Approval — 2026-09-26

## Scope and starting point

Implemented on `feat/bulk-attendance-corrections`, starting at `2ebf51b223090a891b42976ea2e036e996ff37fd`, stacked on `fix/converge-shift-bulk-path`. The work adds one-day bulk preparation of native Attendance Requests from the Daily Attendance Board. Native Attendance remains the final payable record. No generic bulk framework or second attendance ledger was added.

Runtime used: Frappe 16.34.0, ERPNext 16.35.0, HRMS 16.19.0, Workforce Suite 0.1.0, staging MariaDB `127.0.0.1:3307`.

## Native behavior relied on

Installed HRMS sources inspected:

- `apps/hrms/hrms/hr/doctype/attendance_request/attendance_request.py`: `validate`, `get_attendance_warnings`, `should_mark_attendance`, `get_attendance_doc`, `on_submit`, `on_cancel`.
- `apps/hrms/hrms/hr/doctype/attendance_request/attendance_request.js` and DocType metadata.
- `apps/hrms/hrms/hr/doctype/attendance/attendance.py` and Attendance DocType metadata.
- `apps/frappe/frappe/desk/doctype/bulk_update/bulk_update.py`: `submit_cancel_or_update_docs`, used by native List View bulk submit.
- `apps/hrms/hrms/hr/doctype/employee_checkin/employee_checkin.py`: Checkins are evidence and not payable Attendance.

Native Attendance Request validates the Employee and date span, resolves shifts, rejects overlapping requests, and produces warnings for holidays, approved leave, unchanged status, or existing Attendance. Submission applies its supported result through native Attendance creation/update. Cancellation cancels Attendance linked by the Request. The custom approver's broad Attendance write permission would be needed for that cancellation path, so Workforce Attendance Correction Approver is submit-only; native HR roles retain native behavior.

## Baseline defect and corrected report semantics

A synthetic source-level reproduction of the prior `COALESCE(a.status, 'Absent')` projection returned `Absent` for both a submitted Absent Attendance and an Employee with no Attendance record. The Script Report now shows actual native status when a record exists and `Not Marked` otherwise. It adds the Attendance link and an explicit state of `Not Marked`, `Draft Attendance`, or `Submitted Attendance`. Synthetic Desk endpoint tests cover all three states, including a Checkin without Attendance.

The report now exposes optional Branch and Department filters. Server-side rows continue to use `permitted_employee_names`; request filters narrow the permitted population.

## Bulk flow and authorization

`workforce_suite/workforce_suite/attendance_corrections.py` exposes two POST APIs: a read-only server preview and a draft preparation action. It accepts only one date and these mappings:

- Present → native reason `On Duty`, not half day.
- Half Day → native reason `On Duty`, `half_day=1`, native `half_day_date` set to the selected day.
- Work From Home → native reason `Work From Home`.

Absent is not offered. A meaningful explanation is required. Checkins are displayed as evidence and never determine the proposed status.

Every selected Employee is rechecked against current permission-aware Company/Branch/Department scope and Employee read permission, status, joining/relieving dates, pending mobile evidence, ambiguous biometric identity, existing Attendance Request, draft Attendance, payroll consumption, and native Attendance Request validation/warnings. Each eligible row inserts one draft native Attendance Request with ordinary permissions and a per-row savepoint. No Attendance is created or changed by maker preparation. Failures are returned in plain language and do not roll back valid rows.

Preview integration cases include out-of-Branch, out-of-Department, cross-Company, future joiner, inactive, relieved, pending mobile evidence, existing request, approved native leave, native holiday, unchanged Present, existing Absent, and missing Attendance. A Holiday List Assignment and approved Leave Application are synthetic and explicitly removed during teardown.

## Maker/checker and native approval

Before the maker/checker guard, Frappe's role union gave a synthetic combined HR Manager + Attendance Correction Approver both create and submit permissions. A site-backed regression temporarily bypasses only the Workforce submit guard on a synthetic draft and proves that native submission succeeds for its owner and creates Attendance. With the guard restored, the same combined user cannot submit its own draft. A separate Attendance Correction Approver can submit, has no create permission, and is rechecked against current employee scope at submit.

The native List View bulk submit endpoint `frappe.desk.doctype.bulk_update.bulk_update.submit_cancel_or_update_docs` was exercised. It called HRMS `AttendanceRequest.on_submit`, which created one submitted Attendance for a missing date and updated an existing submitted Absent record in place. A synthetic failing Workforce Attendance hook prevented the overwrite before the native submit proceeded, proving the project Attendance validation is not bypassed by HRMS's `db_set` update path.

Custom Attendance Correction Approver cancellation was removed. HRMS cancellation calls native Attendance cancellation, for which granting Attendance write would also expose direct Attendance mutation. Administrator control cancellation proves the native relationship behavior; custom approvers use submit-only review. Cancellation and submission both check for a submitted Salary Slip overlapping the request date.

## Finalization and payroll-consumed history

A synthetic finalized `Workforce Attendance Period` was created with the live attendance hash. After native request approval changed Attendance, the live hash differed while the stored finalized hash remained unchanged. No auto-refresh occurs.

A second site-backed test created a disposable company, Employee, submitted SSA, Salary Structure, and an actual native submitted Salary Slip using HRMS `make_salary_slip` and the normal `submit()` controller path. Against that submitted slip, Attendance Request submission and cancellation both raised the payroll-consumed validation. The Salary Slip remained submitted throughout the assertions, was not changed by the Attendance Request, and was explicitly removed before its dependent synthetic masters. This standalone synthetic slip did not use Payroll Entry or create an accounting accrual; full managed payroll integration is already covered by existing repository tests.

## Backup and migration

Role metadata changed: Attendance Correction Approver now has Employee select/read only, and Attendance Request cancel was removed. `BACKUPS.md` records two verified `bench backup --with-files` archives before the corresponding migration changes, with exact timestamps, sizes, SHA-256 hashes, and verification results. Standard `bench --site hrms-v16.localhost migrate` and `clear-cache` were run after each permission convergence. No manual SQL metadata edits were used. Report Python/JS changes were installed from app source; the report itself did not require custom DocType schema migration.

## Tests and cleanup

Latest final full suite: `585 passed, 0 skipped` (`pytest apps/workforce_suite/workforce_suite/tests -q`). Final focused attendance correction integration: `3 passed`; attendance unit + integration: `10 passed`. The broader focused run also passed 109 relevant attendance, reporting, persona, maternity, mobile/biometric, and boundary tests before the final incremental synthetic holiday/leave additions; the full suite was rerun after those additions.

Python compileall, JSON parsing, `git diff --check`, Node 24 syntax validation, and `bench build --app workforce_suite` passed. The build emitted only the existing outdated Browserslist data notice.

Synthetic cleanup explicitly removes Users, User Permissions, Employees, Attendance Requests, Attendance, Checkins, Attendance Periods, Holiday List Assignments/Lists, Leave Applications, Leave Allocations/Periods, Salary Slips, Salary Structure Assignments, Salary Structures, Salary Components, and the disposable payroll Company. Leave Ledger Entry rows for synthetic Leave Applications/Allocations are asserted absent. Tests use explicit cleanup because native operations can commit.

## Limits still requiring evidence

- The desk dialog was syntax-checked and assets built, but no browser/persona UAT was performed.
- The maker preparation endpoint is synchronous for all batch sizes. One-day rows are individually validated with savepoints; no >30 employee latency/queue execution benchmark was performed, so large-company volume behavior remains unverified. No queue is added in this slice.
- Approved leave and holiday outcomes are exercised with synthetic native records. Pending mobile review is tested; ambiguous biometric mapping has no dedicated synthetic integration case.
- Native HRMS's `include_holidays` field is intentionally not exposed by the bulk dialog. Holiday attendance requires the operator to use the appropriate native process rather than bypassing the default skip.
- Custom Attendance Correction Approver cannot cancel Attendance Requests. A future cancellation design would need a narrowly supported native path that does not grant direct Attendance write.
