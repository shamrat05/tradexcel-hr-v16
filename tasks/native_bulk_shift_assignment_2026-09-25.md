# Native bulk Shift Assignment slice — 2026-09-25

## Scope and starting point

Started from `feat/persona-access-foundation` at `e78bdf6ee88717992e0b74bfa57e1cf1fed2facc`; implementation branch is `feat/native-bulk-shift-assignment`. This slice enables the installed HRMS Shift Assignment Tool for two scheduling personas and closes the selected-Employee authorization gap. It does not add a Tradexcel bulk engine or shift ledger.

Runtime was Frappe 16.34.0, ERPNext 16.35.0, HRMS 16.19.0, Tradexcel HR 0.1.0, with staging MariaDB at `127.0.0.1:3307`.

## Installed native behavior inspected

Installed sources inspected:

- `apps/hrms/hrms/hr/doctype/shift_assignment_tool/shift_assignment_tool.py`
- `apps/hrms/hrms/hr/doctype/shift_assignment_tool/shift_assignment_tool.js`
- `apps/hrms/hrms/hr/doctype/shift_assignment_tool/shift_assignment_tool.json`
- `apps/hrms/hrms/hr/doctype/shift_assignment/shift_assignment.py`
- `apps/hrms/hrms/hr/doctype/shift_schedule_assignment/shift_schedule_assignment.py`
- `apps/hrms/hrms/hr/doctype/shift_request/shift_request.py`
- Frappe `frappe/utils/background_jobs.py` for queued-user restoration.

The native tool already provides Company/Branch/Department/Designation/Grade/Employment Type and advanced Employee filters, active/joining/relieving-date checks, overlapping assignment exclusion and configurable multiple-shift timing checks, a selectable Employee preview with Employee/name/Branch/Department/default shift, confirmation before applying, native Shift Assignment create+submit, per-Employee savepoints, per-Employee success/failure reporting, Error Logs, realtime completion, and queueing above 30 Employees. The 30-row synchronous path and 31-row queued path are preserved. HRMS resolves Shift Type overlap timings, including overnight intervals, in its native query/controller. No duplicate implementation was added.

## Reproduced authorization behavior

A synthetic native HR User with Company A, Branch A, and Department A User Permissions saw only its permitted Employee in native preview. The installed unextended controller nevertheless accepted a manually supplied Employee from another Branch in the same Company and Department and created a submitted native Shift Assignment. That assignment was canceled and deleted as synthetic cleanup. This is the reproduced gap.

A manually supplied Employee from Company B did not produce an assignment under the native HR User because native Company User Permission/controller validation rejected it. The new Tradexcel check independently rejects cross-Company, out-of-Branch, and out-of-Department selected IDs before writes. Preview is recalculated again inside `_bulk_assign`, so the native queued method rechecks current scope at execution under Frappe's queued user context.

The native tool's Process Shift Requests preview can expose draft request rows without a Shift Request read grant. Tradexcel operators are therefore denied that action server-side, and the UI exposes only Assign Shift to them. Assign Shift Schedule is likewise denied. Native HR User/HR Manager behavior remains delegated to HRMS.

## Access and implementation

Only `Tradexcel HR Manager` and `Tradexcel HR/Attendance Officer` receive the native tool access needed for Assign Shift:

- Shift Assignment Tool: read.
- Shift Assignment: read/create/write/submit.
- Shift Type and Shift Location: read.
- No cancel/delete/export/print/import grants were added.

`tradex_hr/tradexcel_hr/shift_assignment_tool.py` is a narrow Frappe `extend_doctype_class` mixin. It validates the selected IDs against the native eligible-Employee preview before calling native `bulk_assign`, and revalidates in native `_bulk_assign` for queued jobs. It calls `super()` for native processing and leaves savepoint, overlap, creation, submission, queue, and partial-result semantics intact. Custom roles may only choose Assign Shift; the two other native actions remain unavailable. The client script narrows the action selector for those roles; backend validation remains authoritative. No HRMS/Frappe source was edited.

The existing “Bulk Shift Assignment” Workspace shortcut is visible to HR Manager and HR/Attendance Officer and absent for Factory Supervisor, Branch Manager, Department Manager, and Worker after standard permission convergence.

## Test evidence

Site-backed integration uses the existing `SyntheticPersonaHarness` and actual Frappe document-method endpoint. It proves:

- HR Manager and HR/Attendance Officer preview in-scope eligible Employees; HR Manager's combined Branch+Department scope and Attendance Officer's Branch-only scope are respected.
- Company, Branch, and Department manual filters cannot widen the permitted Employee set.
- inactive, relieved, future-joining, and already-overlapping Employees are excluded; an earlier non-overlapping assignment and default-shift-only Employee remain visible.
- factory supervisor, branch manager, department manager, and Worker cannot access the tool or call preview/apply methods.
- valid apply creates a submitted native Shift Assignment with the intended Company and Shift Type.
- replay is rejected by native overlap behavior without a duplicate.
- a simulated failure after native insert+submit rolls back that Employee at the native savepoint, while another Employee succeeds and native realtime partial results identify both outcomes.
- 30 selected IDs use native synchronous processing; 31 invoke native queueing. The queued method rejects after the user's Department permission changes between enqueue and execution.
- native HR User retains its unextended tool behavior.
- no synthetic Attendance, Checkin, Salary Slip, or SSA is created.
- native HRMS Shift Request list exposure is blocked for the Tradexcel roles.

The focused Tradexcel integration batch passed 39 tests. The standalone HRMS test module was attempted through raw pytest collection but requires the Frappe test bootstrap (`new_doc_templates` was unavailable during collection); the site integration directly exercised installed native methods instead. No separate HRMS core test harness was run.

## Migration and cleanup

A `bench backup --with-files` restore point was recorded before migration in `BACKUPS.md`: prefix `20260925_205430-hrms-v16_localhost-`, taken 2026-09-25 20:54:37 Asia/Dhaka. Database gzip and public/private tar checks passed. The standard `bench --site hrms-v16.localhost migrate` and `clear-cache` commands converged Custom DocPerm records; no direct metadata SQL was used.

Integration fixture cleanup explicitly removes its synthetic Users/User Permissions, Employees, Shift Assignments, Shift Request, Shift Types, and exact test Error Logs; restores `HR Settings.allow_multiple_shift_assignments`; then verifies cleanup. Real records are not selected or modified.

## Remaining boundary

Supported for these Tradexcel roles: native Assign Shift only. Assign Shift Schedule and Process Shift Requests remain unavailable until their specific DocType permissions and selected-record scoping are separately justified and proven. This slice completes only the Shift Assignment portion of Step 23; it does not complete other bulk domains. No browser/manual persona UAT or production deployment was performed.
