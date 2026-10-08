# Shift bulk path convergence — 2026-09-25

## Scope and reproduction

Started from `feat/bulk-salary-authority` at
`549462588542d1d615f47e54220df1439a3e4d4a`; created
`fix/converge-shift-bulk-path`. Frappe 16.34.0, ERPNext 16.35.0, HRMS
16.19.0, Workforce Suite 0.1.0 run on `hrms-v16.localhost` with MariaDB at
`127.0.0.1:3307`.

Before editing, inspected the installed Employee Data Gaps report script and
called its actual `bulk_fix.resolve_gap("No Shift Assignment", ...)` Python
endpoint with one disposable Employee and an installed Shift Type. The call
returned one updated row and created a submitted native Shift Assignment. The
synthetic assignment and Employee were canceled/deleted immediately. No real
Employee or Shift Assignment was involved.

## Why the duplicate route was unsafe and unnecessary

The legacy resolver required broad Employee write plus Shift Assignment create
and submit rights; it did not recheck the selected Employee against the native
Shift Assignment Tool's permission-aware eligible set, did not provide the
Tool's Company/Branch/Department-scoped preview, and offered an optional
automatic Policy Exception clone. Its overlap check skipped any prior submitted
assignment starting on/before the effective date, rather than using the native
Tool/controller's date-window and overlap rules. It had per-row savepoints and
Error Logs but no large-batch queue path.

The native Tool remains canonical. PR #25's extension rechecks selected
Employees against the native eligible Employee set at apply time and again in
queued processing, rejects unsupported actions for Workforce operators, and
retains HRMS overlap validation, partial results and queue behavior.

The old exception clone mixed scheduling with a separate reviewed policy
decision. `Workforce Policy Exception` represents an effective, impact-previewed
exception which requires independent Payroll Approver submission for activation;
the legacy clone fabricated a `preview_signature` and tied the exception to a
Shift Assignment. This slice removes only automatic cloning from the old gap
action. The Policy Exception framework and its explicit approval flow remain.

## Result

`No Shift Assignment` remains in the Employee Data Gaps detection/report. Its
action now opens the installed singleton `Shift Assignment Tool` with optional
Company, Branch, Department and today's Start Date route options. It passes no
Employee IDs; native preview and apply-time validation remain authoritative.
HR Manager, HR/Attendance Officer and native HR User/Manager roles receive the
button in the report UI. DocPerms are unchanged; the native shortcut and tool
permissions remain those established by PR #25.

The report keeps `bulk_fix.resolve_gap` only for separate
Department/Designation/Holiday List field resolvers. The No Shift Assignment
gap is absent from `GAP_RESOLVERS`; its button branch directs users to the
native tool.

Removed `_assign_shifts()`, `_clone_exception()` and the now-unused clone field
constant/imports from `bulk_fix.py`. `resolve_gap()` returns the clear message
“Use Bulk Shift Assignment for this gap.” for the retired route. Department,
Designation and Holiday List resolvers remain unchanged.

Frappe 16.34 `frappe.desk.query_report.get_script()` loads the report's bundled
`workforce_suite/report/employee_data_gaps/employee_data_gaps.js` first when it
exists; `Report.javascript` is only fallback. The install-time copy was an
unused duplicate because this standard report is reloaded from its JSON and
skipped by the custom-report installer. Removed that dead install constant and
registry reference. The JSON fallback never contained the resolver endpoint;
it remains unchanged, and migration is not needed for this Python/JS-only
change. Regression coverage asserts the active bundle routes to the actual
native singleton, does not register the shift gap as an in-place resolver, and
does not pass report-row Employee IDs to the native tool.

## Verification

Added a site-backed synthetic regression proving the retired resolver rejects
the request and leaves no Shift Assignment or Policy Exception. Additional
source/runtime checks verify the Report endpoint uses the bundled script, the
Workspace shortcut targets the installed `Shift Assignment Tool`, and the
button supplies no Employee IDs. The existing native bulk Shift integration
continues to cover Branch/Department/Company tampering, queue revalidation,
unsupported actions, partial results and operator Workspace access.

Focused report, resolver, Workspace and native Shift Tool tests passed:
**25 passed**. The complete Workforce suite passed: **575 passed, 0 failed,
0 skipped**. Python `compileall`, parsing all 62 app JSON files, Node 24.15.0
syntax checking, Node 24.15.0 `bench build --app workforce_suite`, and
`git diff --check` passed. Asset build emitted only the existing Browserslist
database age warning.

The before-change reproduction's submitted Shift Assignment and synthetic
Employee were explicitly canceled/deleted. The post-change regression test
also cleans any assignment/Policy Exception attached to its synthetic Employee
in `finally`. A read-only marker check after the full suite found zero
synthetic Employees, related Shift Assignments, related Policy Exceptions or
synthetic Error Logs. No migration, backup, role change or permission change
was required.
