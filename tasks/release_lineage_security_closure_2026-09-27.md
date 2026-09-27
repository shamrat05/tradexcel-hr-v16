# Release lineage and mobile evidence correction — 2026-09-27

## Starting truth and lineage

Clean `test/release-readiness-contract` at
`9173b5aaa5e9e6cee7daa23ce3c88b7f519138e3` (#42); Frappe 16.34.0,
ERPNext 16.35.0, HRMS 16.19.0, app 0.1.0; MariaDB 127.0.0.1:3307.
Correction branch `fix/release-lineage-security-closure` descends directly from
#42. No reset/rebase/cherry-pick or changes to historical branches.

PR #3 is not an ancestor; merge-base with #42 is PR #2
`69461cf6c96153a99291ae798f58cbf4d98c15a8`. Its security requirements were
selectively ported into current source, preserving later Employee scope, privacy,
neutral currency, consumed-history and report work. PR #43 is the draft
bookkeeping PR for the existing seven payroll-P0 commits, base
`fix/v16-production-readiness`, head `fix/payroll-p0-safety`. It adds no commits.
PR #1 is independent docs; eventual runtime order is #2 → #43 → #4 … #42 →
this correction. Old #3 is superseded semantically; do not blindly merge it later.

## Pre-fix reproduction

Five temporary baseline tests passed against unchanged #42 before edits:
6-hour-old events were Trusted; missing device time could fall back to canonical
time; 100-hour-old events under Flag were accepted as Flagged; naive browser
strings were accepted; no approve/reject endpoints existed. A captured timestamp
could select historical policy; Pending lacked native skip_auto_attendance.
A synthetic Attendance Officer created a native Attendance Request, then lost
that role and gained Attendance Correction Approver: the same owner submitted
successfully. The global actor hook rejected an unrelated job without a user.
These are reproduced defects, not hypothetical requirements.

## Timing and security policy

Mobile API strings require Z or an explicit +/-HH:MM offset. Aware values convert
to Frappe system timezone before becoming MariaDB naive Datetime; internal naive
Python datetimes remain site-local. The receipt-time policy decides integrity.
Default trust window is five minutes (0–1440). Maximum age defaults to 72 hours
(1–720) and is a hard bound in both directions. Outside trust but inside maximum:
Flag quarantines, Block rejects. Missing captured time is never Trusted.

Captured time, receipt time, skew and original integrity reason remain stored.
Flagged evidence has Pending, Time Review Required and skip_auto_attendance=1.
The installed native `ShiftType.get_employee_checkins` selects skip_auto_attendance=0;
Pending also blocks the existing bulk Attendance Correction preview. It cannot
settle Field Duty allowance. Checkins remain evidence, never a parallel ledger.

Approval loads the exact stored receipt-policy record, separately resolves the
event-time business policy, and reruns duty/GPS/location/shift/selfie/face checks
with combined stricter evidence requirements. It retains receipt-policy identity
and the original timing reason. Today's policy cannot replace it. Rejection
keeps native skip=1. Approval releases skip=0. Opposite final decisions cannot
be replayed; same-decision retries are idempotent. Both actions require POST,
explicit review role, native Checkin read permission, native permitted Employee
scope and a meaningful reason. Native comments plus reviewer/time/reason provide
history. Normal save cannot relabel Mobile to Manual to release quarantine.

Review role candidates are System Manager, Owner/Director, HR Manager,
HR/Attendance Officer, Factory/Branch/Department managers and Attendance
Correction Approver; actual native Checkin read + Employee scope must also pass.
Only the custom Correction Approver receives new DocPerm bits: read/select.
No new Checkin create/write/delete/export/print permission is granted.
Approved OUT Field Duty evidence may enqueue existing allowance settlement only
after commit. Settlement rechecks actor scope and unreleased evidence.

Offline IndexedDB cleanup drops selfie Blob and personal payload on success,
server rejection, expiry and next startup/visibility/flush opportunity. Only
sync ID/time and non-sensitive error/retry state remain for rejected/expired
entries. Network failures inside the age limit retain retry evidence. No promise
of wall-clock deletion while the browser is closed. Executed JS tests use the
production functions with an in-memory storage boundary; physical browser/device
lifecycle UAT is still required.

## Attendance ownership and background jobs

Non-Administrator custom Attendance Correction Approver cannot submit a request
whose owner is that user, regardless of current maker-role membership. Independent
scoped approvers continue through native submission; existing scope and consumed
payroll guards remain unchanged. Native-only HR-role behavior is unchanged.

Installed Frappe `execute_job` retry drops its user argument. The hook now
matches only actor-bound HR mutation methods; unrelated jobs immediately return.
For matched jobs, original job user must be present, enabled and equal to session;
method identity must agree. A kwargs requested_by value is not accepted as proof.
Native execution-time scope/state checks and private per-user completion remain.

Exact methods are enumerated and resolved against installed callables in
`test_actor_bound_methods_match_installed_callable_names`:
- ShiftAssignmentTool / TradexcelShiftAssignmentToolMixin: `_bulk_assign`,
  `_bulk_process_shift_requests`.
- BulkSalaryStructureAssignment / TradexcelBulkSalaryStructureAssignmentMixin:
  `_bulk_assign_structure`; custom `_bulk_prepare_drafts`.
- `tradex_hr.tradexcel_hr.overtime_bulk._prepare_now`.
- `tradex_hr.tradexcel_hr.field_attendance_service.settle_field_duty_allowance`.
- `hrms.payroll.doctype.payroll_entry.payroll_entry`:
  `create_salary_slips_for_employees`, `submit_salary_slips_for_employees`.
- `hrms.hr.doctype.overtime_slip.overtime_slip`:
  `create_overtime_slips_for_employees`, `submit_overtime_slips_for_employees`.
- Native `run_doc_method`, `execute_action`, List `_bulk_action`, and Data Import
  `start_import` only for explicit HR DocTypes/app-owned Tradexcel DocTypes;
  Data Import uses the native reference_doctype. Unrelated ToDo/accounting/setup
  wrappers are not denied by this hook. Installed Leave Control Panel is
  synchronous; existing extension revalidates selection without a new queue.

An actual harmless Frappe retry executed twice without Tradexcel denial. Installed
outer job-context cleanup can still raise AttributeError after recursive retry;
this unrelated framework defect was not patched or disguised as a successful job.

## Schema, source and migration

Before migration, staging had a trust-window SQL column without current metadata
and old review fields left by historical work. That was not source completeness.
Policy JSON, custom-field setup, review Desk JS, hooks and service endpoints are
now versioned; no real approved Policy row was updated to populate the new field.
Null legacy trust-window values use the five-minute runtime default. Obsolete
SQL columns are not destructively dropped.

Verified backup `20260927_133159-hrms-v16_localhost-` includes gzip, public/private
archives and config JSON; sizes and SHA-256 are in BACKUPS.md. Standard bench
migrate and clear-cache passed. No direct metadata SQL. Clean source-only install
on disposable `closure-neutral-20260927.localhost` (isolated 3307) passed security
smoke, 13 standard reports and neutral zero-business-data assertions. The site
was dropped through native bench after proof; no real site was restored over.

## External release gates

#42 runs 36283160723 (3ec045d...) and 36283208413 (9173b5...) both failed before
any steps. GitHub's current annotation confirms billing/spending restriction.
Phase K remains BLOCKED. ERPNext banking/yarn.lock drift, real configuration,
physical device/staff UAT, parallel payroll and recovery/cutover remain external.
No billing settings, framework files, production or real business records changed.

## Validation and final handoff

First full run: **652 passed, 0 skipped** (101 warnings, 492.70 seconds).
A final least-privilege review reduced the new Checkin permission to read/select;
backup `20260927_134711-hrms-v16_localhost-` was verified before a second standard
migration. No real role assignments or business records changed. Final validation
below runs against that narrower installed permission. Git/GitHub
own the final commit SHA; this note does not embed its own commit hash.


Final focused commands used bench `env/bin/python -m pytest` with `-q
--disable-warnings --tb=short`, targeting:
`test_field_attendance_service`, `test_mobile_page_assets`,
`test_release_security_closure`, `test_attendance_corrections`,
`test_bulk_attendance_corrections_integration`, `test_persona_access_integration`,
`test_security_privacy_integration`, `test_bulk_execution_safety`,
`test_native_bulk_shift_assignment_integration`,
`test_native_bulk_leave_control_integration`, `test_bulk_salary_authority_integration`,
`test_native_overtime_bulk_integration`: **60 passed**. The final release-security
module including native OUT API → quarantine → scoped review → after-commit
settlement dispatch passed **4 tests**. No artificial allowance rate was needed.
Pure CI subset: **11 passed**. Source checks: 238 Python files, 61 JSON files,
30 JavaScript files; Node 24.15.0 syntax and `bench build --app tradex_hr` passed.
Compileall and `git diff --check` passed. Staging release smoke passed again after
final migration. The first full suite passed 652; a final full run includes the
additional OUT API integration test and narrowed installed reviewer permission.

Both #42 failure annotations were queried directly and report the same account
payment/spending-limit problem; the diagnosis is current API evidence, not only
a remembered local explanation. No action was rerun to evade it.


## Final accepted validation

**653 passed, 0 skipped**, 103 warnings, 496.49 seconds, using:
`env/bin/python -m pytest apps/tradex_hr/tradex_hr/tests -q --disable-warnings --tb=short`
from the v16 bench. Baseline was 629; no security regression was deleted to pass.
Actual 31-row isolated native RQ execution and changed-scope rejection passed as
part of that full suite. Final compileall, all JSON/JS source checks, asset build,
diff-check and installed release smoke passed.

Final explicit cleanup: zero correction/review/actor/queue synthetic Users,
Has Role children, User Permissions, Employees, Checkins, Attendance/Requests,
Field Duties, policies, SSA, Salary Slips, Additional Salary and Leave Allocation
markers; fixture-specific native integrations verify their own dependency cleanup.
Disposable site/database was dropped normally; archived directory removed.
Nineteen queued setup jobs were removed only when their stored site matched that
disposable site; repeat cleanup found zero. Dedicated live-worker test deletes
its own jobs/queue. No real staging queue was cleared. Read-only audit found zero
legacy Mobile Pending Checkins with skip_auto_attendance=0. Final installed
Correction Approver Checkin permission is read/select; create/write/delete/
export/print are all zero.

Frappe and HRMS checkouts remain clean. ERPNext's pre-existing banking/yarn.lock
change remains untouched. Local staging DB/Redis/web/Socket.IO are running;
HTTP 200 verified. Production, real Users/User Permissions/Employees/Checkins/
Attendance/payroll/accounting and approved business/legal values remain unchanged.
