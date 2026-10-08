# Native Employee-linked record scope — 2026-09-26

## Why this correction precedes the Action Board

Parent: `fix/legacy-report-boundaries` (PR #33). Native approval queues must be
safe independently of any dashboard or report. Synthetic native-list and
`has_permission` / document `check_permission` probes reproduced these gaps:

| Record | Scoped persona | Before correction |
| --- | --- | --- |
| Attendance Request | Attendance Correction Approver, Company + Branch + Department | Other Branch returned/read; other Department denied |
| Employee Checkin | HR Manager and Device/IT Administrator | Other Branch, Department and Company returned/read |
| Salary Structure Assignment | HR Manager | Other Branch returned/read; other Department denied |
| Attendance | HR Manager | All tested outside-scope rows already denied; unchanged |

The installed Attendance Request and SSA do not have a Branch Link on which
native User Permissions could operate. Checkin does not carry all Employee
scope Links either. Native Link-field matching is not automatically transitive
through the Employee Link. Report filtering did not protect these native lists
or known-name retrieval. Only synthetic records were inspected in these probes.

## Supported native correction

`report_scope.py` now supplies one native Employee Query Builder subquery and
additive `permission_query_conditions` / `has_permission` hooks for the three
reproduced record types. Native target DocPerms and HRMS hooks remain in force.
The query uses `ignore_permissions=False`, the actual caller, and native
User Permission matching. It introduces no ACL or identity records and no core
modification. The direct-document hook resolves the Employee with the same
caller. Guest and disabled users fail closed. Native Administrator control
remains available. Empty Branch/Department behavior continues to follow the
site's `apply_strict_user_permissions` setting.

Device/IT Administrator receives only Employee **select**, not read/create/
write/report/export. This supports scoped Employee identity in its existing
Checkin troubleshooting permission. Tests require Employee form retrieval,
compensation/bank fields, SSA and Salary Slip to remain inaccessible. The
existing biometric mapping mutation API is not broadened by this change.

Installed source inspected: `frappe/permissions.py` (`has_permission`,
`has_controller_permissions`), `frappe/model/db_query.py`
(`get_permission_query_conditions`), `frappe/database/query.py` (permission-aware
Query Builder), `frappe/model/meta.py` (`get_permitted_fieldnames`), and native
HRMS Attendance Request / SSA / Checkin metadata. Raw `frappe.get_doc` loads a
server-side object; client retrieval and `check_permission` enforce access.

## Fixture corrections

Linking a synthetic Employee saves its User and triggers native Contact update.
The harness now makes that setup-only side effect synchronous, just as its User
creation already did; this prevents queued Contact work racing explicit cleanup.
An empty harness must not issue `IN []` identity queries: native filtering may
match blank identity fields. Empty identity categories are now skipped and a
regression verifies this. No unrelated Contacts were deleted.

## Convergence and validation

Fresh backup `20260926_173459-hrms-v16_localhost-` verified (gzip and both file
archives, sizes/hashes in BACKUPS.md). Standard `bench migrate` and `clear-cache`
completed for the select-only Custom DocPerm and hook convergence. No manual
metadata SQL. No frontend assets changed.

Initial site-backed scope test passed across HR, correction approver, payroll,
native HR User, device, linked/unlinked Worker and disabled-user cases. Normal
create/write denial, explicit-user checks, API retrieval, blank-Link semantics
and empty-harness cleanup are included in the final regression.

Final acceptance:
- Focused native/report/persona/bulk/lifecycle regression: **23 passed**, 26 warnings.
- Full `env/bin/python -m pytest apps/workforce_suite/workforce_suite/tests -q
  --disable-warnings --tb=short`: **604 passed, 0 failed, 0 skipped**, 77 warnings,
  422.06 seconds. Previous accepted count: 602; two new tests, none removed.
- Bench Python compileall, all **61** tracked JSON files, and `git diff --check`
  passed. No JS changes, so no asset build.
- Explicit test teardown checks every tracked Checkin, Request and SSA name.
  Final marker audit found **zero** SOLLINK/SOLPROBE Users, User Permissions,
  Has Role, Contact, Notification Settings and Employees. Existing campaign
  SOLRPT/SOLPAGE/SOLDG/SOLDI/PUAT/BULKATT/BULKAPP/BULKSSA markers were zero too.
- Full diff reviewed: no secrets, real identifiers, core edits, payroll
  calculation, broad salary grants or duplicate ACL. Local staging evidence;
  GitHub CI was not configured on the parent.

Correction accepted; create the stacked draft PR on #33. Action Board work can
now resume. Broader security review remains a separate campaign phase.

Production and real User/User Permission/Employee/payroll/attendance data remain
untouched. Browser UAT remains separate. Wider Employee-linked records and
explicit sharing behavior belong to the campaign's security pass.
