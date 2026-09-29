# Persona access foundation — 2026-09-25

## Scope and starting point

This slice started from `feat/financial-report-scope` at
`f1bf90c5e41ee7c1b6f6bacaccb8f994d4493467` and created the stacked branch
`feat/persona-access-foundation`. It establishes repeatable site-backed tests
for native Frappe Users, Roles, User Permissions, Employee links, reports and
the existing `tradexcel-hr` Workspace. It does not add an identity, persona or
ACL DocType/table, and does not provision real users.

## Installed Frappe behavior

The tests exercise the installed Frappe v16.34.0 runtime. `frappe.has_permission`,
`frappe.get_list`, direct document permission checks and the Desk report and
Workspace endpoints remain the authorities. Populated Company, Branch and
Department User Permissions combine as native query constraints; the combined
Branch-A + Department-B fixture returns no Employee when no record matches
both. With no Company User Permission, Frappe does not infer company scope from
a Tradexcel role. Staging has strict User Permissions disabled, so blank link
values continue to follow framework-native matching; this is a company data
and configuration/UAT decision, not changed here.

The public `tradexcel-hr` Workspace has no role restriction and is therefore
listed for users allowed into the Tradexcel HR module. `get_desktop_page`
filters DocType shortcuts using read permission and Report shortcuts using
report-role visibility; a Report shortcut can still be visible when its
referenced DocType denies the actual endpoint. Number Cards and charts apply
their own permissions. This is navigation filtering, not a replacement for
endpoint authorization.

## Synthetic persona contract

`tradex_hr/tests/persona_uat.py` defines a reusable test-only harness. It makes
unique System Users with native Has Role children and Company/Branch/Department
User Permissions, optionally links a synthetic Employee through `Employee.user_id`,
and explicitly deletes and verifies only its marker-owned records. Integration
tests cover all 15 Tradexcel roles, two Companies, multiple Branches and
Departments, Company-only and unscoped users, combined scope, linked/unlinked
Workers, and selected dual-role combinations. No native HR Manager or System
Manager role is used by the personas; System Manager is only a control where
needed by existing tests.

Observed access contract (all scope comes from native User Permissions):

| Persona | Allowed job boundary proven | Key denied boundary proven |
|---|---|---|
| Owner/Director | Employee and payroll read; company overview | No scope is inferred; explicit Company permissions bound rows |
| HR Manager | Employee create, Transfer submit, Separation create, SSA draft | SSA submission denied; payroll report access is separately role-gated |
| HR/Attendance Officer | Attendance write and attendance reports | Employee Checkin create and Salary Slip read denied |
| Factory Supervisor | Field Duty create and Attendance read | Salary Slip and financial reports denied |
| Branch Manager | Employee/Attendance read within native scope | Cross-Branch rows and Salary Slip denied |
| Department Manager | Employee/Attendance read within native scope | Cross-Department rows and Salary Slip denied |
| Payroll Manager | SSA preparation, Payroll Entry/Salary Slip submission | Attendance mutation denied |
| Payroll Approver | SSA and Payroll Entry approval | Salary Slip submit denied; maker/checker guards remain in native lifecycle tests |
| Finance/Accounts Officer | Salary Slip read and Full & Final submit | Salary Slip write denied |
| Compliance Auditor | Salary read and wage-floor review read | Salary write denied |
| Device/IT Administrator | Biometric Device write | Employee write and Salary Slip read denied |
| Attendance Correction Approver | Attendance Request submit | Salary Slip read denied |
| Leave Approver | Leave Application submit and scoped read-only Leave Allocation evidence | Allocation create/export/print denied |
| Import Reviewer | Employee biometric review write | Employee write denied |
| Employee/Worker, unlinked | No broad HR record access | Employee, Checkin, Allocation and Salary Slip denied |
| Employee/Worker + native Employee, linked | Own Employee, Checkin, Attendance Request and Leave Application paths | Other Employee/document access denied by Employee User Permission; no management reports |

The native Employee role supplies a DocType-level Salary Slip read permission,
but the linked Employee User Permission must still scope individual records.
This is not permission to see company payroll. The tests check both the
DocType permission and direct/list row boundaries.

## Report and action evidence

The report endpoint matrix checks Daily Attendance Board, Leave Balance Board,
Shift Coverage, Joiners and Leavers, Salary Coverage, Pay Component Register,
Payroll Variance and Payroll Register using `frappe.desk.query_report.run`.
Operational personas can open only reports matching their roles and underlying
DocType grants. Payroll Register, Variance and Pay Component reports deny
Supervisor/Worker; Attendance Board denies unlinked Worker. HR, attendance,
supervisor, branch/department, payroll preparer/approver, Finance, Compliance,
Device, Import and Worker actions are checked using `frappe.has_permission`;
native lifecycle integration tests continue to cover document submission and
maker/checker behavior.

The real report integration surfaced two narrow inconsistencies and they were
fixed:

1. Leave Approver was intentionally on the Leave Balance Board but lacked the
   minimum Company and Employee read context and Leave Allocation read/report
   rights. Those permissions are now read-only and remain User-Permission
   scoped. Export, print, create, write and submit are not granted.
2. Payroll Register had no explicit Report roles, so it appeared as a Workspace
   shortcut to an operational user even though the endpoint denied access via
   Salary Slip permission. It now lists only Owner/Director, HR Manager,
   Payroll Manager, Payroll Approver, Finance/Accounts Officer and Compliance
   Auditor. It excludes Worker, Supervisor, Branch/Department Manager and
   Attendance Officer.

## Workspace audit

The `tradexcel-hr` Workspace remains a public mixed overview/navigation page,
not a role-specific Action Board. In the test payload it has 47 shortcuts;
Frappe removes links that fail its shortcut-level visibility checks. Measured
synthetic persona examples: HR Manager 35 visible / 12 inaccessible, Payroll
Manager 16 / 31, Payroll Approver 10 / 37, Finance 13 / 34, Compliance 33 / 14,
Attendance Officer 21 / 26, Factory Supervisor 12 / 35, Branch Manager 13 / 34,
Device Admin 4 / 43, Import Reviewer 2 / 45. Operational users did not receive
the Payroll-by-Month chart; its native Salary Slip permission hides it. No
salary shortcut is visible to Supervisor or Branch Manager after the explicit
Payroll Register role fix.

Department Manager, Attendance Correction Approver, Leave Approver and Worker
personas cannot open this Workspace because Frappe's module access filter finds
no readable module DocType for their roles. Their underlying scoped/report or
native actions are independently tested. This is a navigation usability gap,
not evidence to grant unrelated permissions. The Workspace still mixes
headcount, attendance and payroll overview cards/charts with a large static
shortcut set; visible cards/shortcuts are informational or navigation, not
user-specific blockers/approvals. A future navigation/Action Board slice should
address this after real persona UAT.

## Separation of duties, mobile and limits

The test fixture checks HR Manager + Payroll Manager, Payroll Manager + Payroll
Approver, and Owner + HR Manager unions. Union-of-roles affects Frappe permission
bits, while server-side maker/checker validation remains the deciding
protection; lifecycle integration coverage verifies self-approval denial.
Operationally, the same account should not be assigned both maker and approver
roles for the same financial flow.

Task-classification for future UAT (not browser evidence): phone-critical:
attendance capture, own leave/attendance requests; phone-useful: supervisor
exceptions and attendance/leave approvals; desktop-first: payroll preparation
and approval, Finance/Full & Final, compliance review, large imports, Employee
master maintenance and device setup. No mobile interface was built or tested
here.

Staging had no enabled non-Administrator System Users before this test, so
real-staff login, browser usability and actual company persona provisioning
remain open. Statutory approvals were not fabricated: their permissions are
tested only at the available role/DocType boundary; applicable rule submissions
require reviewed legal configuration.

## Migration, verification and cleanup

Role/Report metadata convergence required standard site migrations. Before each
metadata migration, a fresh `bench backup --with-files` was taken; database
gzip and public/private tar integrity checks passed. Backup details and exact
SHA-256 values are recorded chronologically in `BACKUPS.md` (most recent
pre-migration prefix: `20260925_195302-hrms-v16_localhost-`). Migration and cache
clear used standard Bench commands; no direct metadata SQL or site credential
change was made.

Focused permission/report/lifecycle tests passed: 12 passed; after the final
Workspace assertion, the persona integration passed 1 passed. The final
complete Tradexcel suite passed: 571 passed, 0 skipped. Python compileall,
parsing all 62 app JSON files and `git diff --check` passed. The persona harness
explicitly cleans synthetic Users, User Permissions and Employees in dependency
order and asserts their absence. A post-suite native Frappe query found zero
matching synthetic Users, Has Role rows, User Permissions or Employees. Existing
integration fixtures clean their own tracked operational records. No real staff
user, Employee, payroll, attendance or leave record was intentionally changed.
