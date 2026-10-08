# Native leave bulk security and entitlement scope — 2026-09-26

Parent: `refactor/runtime-portability` at
`bba1daa126594b04f3f03442c87fe340aa6cb924` (draft PR #29). Branch:
`feat/native-bulk-leave-control`. The isolated staging site uses HRMS 16.19.0.
No real Leave records, Employees, User Permissions, or company entitlement
configuration were changed.

## Installed HRMS behavior and reproduced gap

Installed source: `hrms/hr/doctype/leave_control_panel/leave_control_panel.py`
and its JS/JSON/native tests; `leave_allocation.py` and
`leave_policy_assignment.py` remain the controllers. `get_employees()` uses
permission-aware `frappe.get_list("Employee")`, excludes inactive Employees
and existing submitted allocations, and respects Company/Branch/Department
User Permissions in preview. Its `allocate_leave(employees)` accepted an
arbitrary POSTed Employee list and dispatched to per-Employee native creation
and submission without reusing the preview scope.

A synthetic native HR User restricted to Company A, Branch A and Department A
had an out-of-Branch Employee omitted from preview. Direct Desk document-method
POST nonetheless created a **submitted** native Leave Allocation for that
Employee. An in-scope Employee succeeded; the out-of-Department and
cross-Company attempts failed through downstream native permissions. The
native preview also included synthetic Employees whose joining date was after
the allocation range or whose relieving date preceded it; native apply
submitted allocations for both. These reproductions used disposable Leave
Type/Employees and were explicitly cleaned, including Leave Ledger Entries.
The native latest-period method also returned an active Company-B Leave Period
to a Company-A-scoped caller. A crafted Company-A policy-mode request using
that Company-B period then submitted both a Leave Policy Assignment and Leave
Allocation for a Company-A synthetic Employee. A separate crafted request
using a DRAFT Leave Policy did the same. These probe records were explicitly
cancelled and deleted.

## Narrow extension and role audience

`extend_doctype_class` adds a small Leave Control Panel mixin. On apply it
validates native mandatory fields, re-resolves the current permission-aware
native preview population and rejects any selected Employee outside it before
calling `super().allocate_leave()`. The preview is additionally narrowed by
employment-date intersection: a future joiner after the requested end or an
Employee relieved before the requested start is excluded. All actual Leave
Allocation/Leave Policy Assignment validation, submission, ledger entries,
savepoints, partial failure reporting and realtime behavior remain HRMS code.
There is no second leave ledger or custom bulk page.
Company and active Leave Period are checked server-side against native User
Permissions; period Company must match the selected Company. Policy mode
requires a readable submitted Leave Policy. The latest-period lookup checks
Company access before invoking HRMS. Native HR users without Company read
DocPerm retain native tool access through Frappe's User Permission evaluation;
pure Workforce Suite Managers need explicit Company scope.
An additional `before_submit` hook on native Leave Policy Assignment prevents
the same draft-policy bypass through the direct per-record API. It leaves the
native assignment and allocation documents authoritative and adds no approval
record.

Workforce Suite Manager is the sole custom entitlement administrator for this
tool. The minimum extra native permissions are Leave Control Panel read;
Leave Allocation submit on top of existing draft rights; Leave Policy
Assignment read/create/write/submit; and select/read on Leave Policy, Leave
Period and Leave Type. Leave Approver retains individual Leave Application
approval and read-only balance evidence; Attendance Officer, managers and
Worker do not gain bulk entitlement mutation. Synthetic native HR User and
combined native/custom HR User keep native successful actions, now with the
same tamper boundary. Workspace `Bulk Leave Allocation` visibility follows
the native tool permission; no navigation redesign was made.

Direct allocation and submitted-policy modes both remain native. The only
amount in the test is a disposable **one-day synthetic fixture**, never a
real policy default. Real leave period, policy and entitlement decisions are
company configuration gates. Existing submitted allocation is excluded on
repeat; native overlap validation remains authoritative. A simulated failure
of one eligible Employee left another eligible Employee's submitted native
allocation intact and no partial failed allocation. No Salary Slip,
Additional Salary or Payroll Entry was created. The native tool is synchronous;
there is no queue path to revalidate. Its installed `frappe.get_list` preview
uses Frappe's default page length of 20; operator filtering and volume UAT
remain necessary before promising one-click coverage of a large roster.

## Migration, tests, cleanup and limits

Before DocPerm/hook migration, `BACKUPS.md` was read and a full-files backup
was taken at 2026-09-26 01:43:48 Asia/Dhaka with prefix
`20260926_014339-hrms-v16_localhost-`. Database gzip and both file archives
passed integrity checks; exact sizes and SHA-256 are in `BACKUPS.md`. Standard
`bench --site hrms-v16.localhost migrate` and `clear-cache` succeeded. No
direct metadata SQL was used.

Focused native leave integration: 1 passed. The broader persona, role,
company, report and working-time suite passed 40 tests before the last
Company/period/policy checks. The final serial full Workforce suite passed
**594 tests, 0 skipped, 66 warnings**. A prior overlapping site-backed run
had one `tabSeries` deadlock in an unrelated separation test; that test passed
alone and the subsequent exclusive full run passed. Python compileall, all
61 app JSON files, and `git diff --check` passed. No app JS changed, so no
asset build was needed. Synthetic test teardown
explicitly cancels/deletes allocations, policy assignments, policy, period,
Leave Type, Error Logs, Users, User Permissions and Employees; linked Leave
Ledger Entries were verified absent. Read-only marker scans returned zero
synthetic Users, Employees, Leave Types and Leave Policies after the test.

Physical browser operation, real company leave configuration and large-roster
preview UAT remain separate gates. No Bangladesh leave entitlement was
inferred or configured.
