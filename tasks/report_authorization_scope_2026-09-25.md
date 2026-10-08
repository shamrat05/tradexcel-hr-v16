# Report authorization scope — 2026-09-25

## Scope and starting point

Branch `fix/report-authorization-scope` was created from PR #20's verified
`feat/employee-lifecycle` head `8a8303cc3d274535224a61fa78754eed458a5cb0`.
This slice covers the two company-wide attendance/leave boards, Salary Coverage
Board's pay-basis display, Company read access needed by scoped report users,
and the Worker native-record grants reproduced below. It changes no native
ledger and no real User, Employee, Attendance, Leave, or payroll record.

## Installed Frappe permission findings

Source inspected in the bench's Frappe 16.34.0, ERPNext 16.35.0, and HRMS
16.19.0:

- `frappe/core/doctype/report/report.py`, `Report.is_permitted()`: an empty
  Report role list returns allowed. `frappe/desk/query_report.py`,
  `get_report_doc()` still checks `frappe.has_permission(ref_doctype, "report")`.
- `frappe/model/db_query.py`, `DBQuery.build_match_conditions()` and
  `add_user_permissions()`: `get_list` applies role permissions, linked-field
  User Permissions, and permission-query hooks. A raw `frappe.db.sql()` call in
  a Script Report does not use these conditions.
- `frappe/core/doctype/user_permission/user_permission.py`,
  `get_user_permissions()`, and the `DBQuery.add_user_permissions()` source
  show User Permissions are applied to matching Link fields; Company permission
  does not traverse an Employee link. With
  `apply_strict_user_permissions` disabled, an empty link value is admitted by
  Frappe's match condition. Tests observed this for unassigned Branch/Department
  rows; no alternative scope semantics were introduced here.
- `frappe/client.py`, `get()`: normal document retrieval calls
  `doc.check_permission()`. Low-level Python `frappe.get_doc()` alone is a
  trusted fetch and does not authorize access.
- `erpnext/setup/doctype/employee/employee.py`, `update_user_permissions()` and
  `update_user()`: linking a User to Employee provisions native Employee and
  Company User Permissions and the native Employee role. That native path
  scopes Employee-linked records to the linked Employee. It is retained.

## Reproduced behavior and implementation

The baseline JSON for Daily Attendance Board and Leave Balance Board had
`roles: []`; their SQL only constrained Company. The pre-fix SQL shape was
replayed with synthetic records: a Branch Manager's company-only attendance
and check-in query returned the synthetic Employee in another Branch, and a
linked Worker raw Leave Allocation query returned another Employee's
allocation. The native permission-aware Worker `get_list` remained own-record
only. The two Report source files and the installed empty-role semantics show
why the old report endpoint admitted an otherwise permitted caller. The
post-fix tests use the real `frappe.desk.query_report.run` endpoint.

Before the Worker DocPerm change, an unlinked synthetic
`Workforce Employee/Worker` with only a Company User Permission could list both
synthetic employees' `Employee Checkin`, `Leave Allocation`, and
`Leave Application` rows. Company permission is not transitive across the
Employee Link. This was reproduced in site tests before role setup convergence.

The fix adds `workforce_suite/workforce_suite/report_scope.py`. It calls Company access
validation, resolves Employee IDs with native `frappe.get_list()` under the
caller, then applies optional Branch/Department filters as narrowing constraints.
Each Script Report binds that tuple into its SQL; an empty permitted set returns
zero rows. Desk filters cannot expand scope, and direct `execute()` calls use
the same boundary.

- Daily Attendance Board now has explicit roles: Owner/Director, HR Manager,
  HR/Attendance Officer, Factory Supervisor, Branch Manager, Department
  Manager, Attendance Correction Approver, and Compliance Auditor.
- Leave Balance Board has explicit roles: Owner/Director, HR Manager,
  HR/Attendance Officer, Factory Supervisor, Branch Manager, Department
  Manager, and Compliance Auditor. Employee/Worker is excluded from both.
- Company read-only DocPerms were added for report-operating custom roles that
  need the existing Company context check. Company User Permissions continue to
  constrain each user's visible Company; no Company write/create rights were
  added.
- The Employee/Worker custom DocPerms for Employee Checkin, Attendance Request,
  Leave Application, and Leave Allocation are now empty. A linked employee
  retains native Employee-role access to own Checkin, Attendance, and Leave
  Application records. Direct Leave Allocation browsing remains unavailable;
  native leave application/balance behavior is unchanged.
- Salary Coverage Board now uses `resolve_pay_basis(employee, as_of_date)` for
  the effective submitted SSA and linked Structure's explicit pay basis. Its
  Assignment Status remains separate. Monthly, Daily, missing basis, missing
  assignment, and company mismatch are not inferred from Employment Type,
  Branch, or structure names.

## Site-backed evidence

Synthetic scoped personas exercised actual report runs: HR Manager,
HR/Attendance Officer, Factory Supervisor, Branch Manager, Department Manager,
Compliance Auditor, linked Employee/Worker, unlinked Employee/Worker, and
Company-A/Company-B users. Tests cover Company isolation, Branch and Department
isolation, combined restrictions, caller-supplied narrowing filters, worker
report denial, direct Script Report execution, and Company-scoped auditor/HR
results. Underlying Employee, Employee Checkin, Attendance, Leave Allocation,
and Leave Application checks use `has_permission`, `get_list`, document
permission checks, and `frappe.client.get()` by known synthetic document name.
Low-level `get_doc()` is verified to be a fetch that still fails its subsequent
permission check for another Employee's record.

Salary Coverage parity tests create synthetic monthly, daily, missing-basis,
and no-assignment records. Monthly and Daily results match the canonical
resolver at the same date even when Employment Type contradicts pay basis.

The report metadata and Company/Worker DocPerm convergence required site
migration. Before migration, `BACKUPS.md` was read and three fresh
`bench --site hrms-v16.localhost backup --with-files` backups were taken as
permission/metadata changes were staged. The database gzip and public/private
tar archives passed integrity checks for each backup. Prefixes and full hashes
are recorded in `BACKUPS.md`. Only standard `bench ... migrate` and
`bench ... clear-cache` were used; no manual SQL metadata convergence occurred.
The site remained configured for `127.0.0.1:3307`.

Focused report/security batch: `42 passed, 2 skipped`. The first complete run
found one obsolete report-source assertion expecting `Source Salary Pending`;
it was replaced with assertions for canonical pay-basis resolution and removal
of legacy inference. Corrected focused report tests: `5 passed`. Final clean
Workforce suite: `566 passed, 2 skipped`. Python compileall, all 58 app JSON
files, and `git diff --check` pass. No JS/assets changed.

After the suite, zero test-marker Users, User Permissions, Employees,
Attendance, Checkins, Leave Allocations, Leave Applications, Salary Structures,
or SSAs remained.

## Deliberately unchanged / future work

- The four app-owned raw Query Reports remain System Manager-only:
  Joiners and Leavers, Pay Component Register, Payroll Variance, and Shift
  Coverage.
- `hooks.py` still overrides `frappe.desk.query_report.run` with
  `workforce_suite.report_filters.run`. Runtime audit found exactly those four
  app-owned Query Reports; `normalise_query_report_filters()` checks for
  `report_type == "Query Report"` and provides safe defaults/clear errors.
  Script Reports do not use this wrapper. Keep it until the remaining Query
  Reports are converted or no longer require normalization; the global hook is
  an upgrade-coupling item for that future reports slice.
- `workforce_suite/workforce_suite/payroll_setup.py` functions
  `classify_employees()`, `ensure_factory_assignments()`, and
  `setup_payroll_configuration()` have no callers outside that module and are
  not hooked or whitelisted. They include an Employment Type derivation, a
  hard-coded `base=350`, SSA submission, and commit. They were not executed or
  changed; remove or quarantine them in a separately reviewed cleanup slice.
- Empty Employee Branch/Department values follow installed Frappe's permissive
  User Permission behavior when strict permissions are disabled. Company data
  reconciliation and the policy decision about strict User Permissions remain
  configuration/UAT work; report code follows the current native semantics.
