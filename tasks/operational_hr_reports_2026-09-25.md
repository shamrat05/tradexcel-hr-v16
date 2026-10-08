# Operational HR reports — 2026-09-25

## Scope and starting point

Starting PR #21 head: `7577ce2671d7dcbe37bfa94fa7af2816cb16e4c1` on
`fix/report-authorization-scope`. Work is on the stacked branch
`feat/operational-report-scope`. PR #21 remains unchanged. This slice converts
only `Workforce Shift Coverage` and `Workforce Joiners and Leavers`; the salary-
sensitive `Workforce Pay Component Register` and `Workforce Payroll Variance`
remain fail-closed Query Reports.

## Baseline reproduced

Before migration, both reports were Query Reports restricted to `System Manager`.
Seven synthetic custom-role users—HR Manager, HR/Attendance Officer, Factory
Supervisor, Branch Manager, Department Manager, Compliance Auditor, and
Employee/Worker—were each denied both reports through
`frappe.desk.query_report.run`. No native HR role was added. This was a safe,
fail-closed availability limitation, not a data exposure.

## Report implementation

Both reports are now standard file-backed Script Reports with Python modules,
JSON metadata, and version-controlled JavaScript filters:

- `Workforce Shift Coverage`: explicit audience Owner/Director, HR Manager,
  HR/Attendance Officer, Factory Supervisor, Branch Manager, Department
  Manager, and Compliance Auditor.
- `Workforce Joiners and Leavers`: explicit audience Owner/Director, HR Manager,
  HR/Attendance Officer, Branch Manager, Department Manager, and Compliance
  Auditor.

Employee/Worker and payroll/finance roles are excluded. Both use Employee as
`ref_doctype`, so Frappe's report permission check is against the Employee
permissions already provisioned for these personas. Shift Coverage reads
Employee `default_shift` and submitted native Shift Assignment; Joiners and
Leavers reads Employee `date_of_joining` and `relieving_date`. No ledger or
native DocPerm grant was added.

Both Script Reports call the existing
`workforce_suite.workforce_suite.report_scope.permitted_employee_names()` before running
SQL. The permitted names are also bound as SQL parameters. Optional Company,
Branch, Department, date, and coverage filters only narrow the result. Empty
Employee scope returns the report's columns with zero rows. Direct `execute()`
uses the same scope as Desk execution. The Employee link column provides
native-record drill-through.

Shift coverage still distinguishes submitted active assignments, overlap,
missing coverage, and Employee default-shift-only coverage. The user-facing
labels are `Multiple active assignments — review`, `Assigned`,
`No shift assigned — review`, and `Default shift only`. The filter options retain
`All`, `Overlap`, `Missing`, `Assigned`, and `Default only`.

Joiner/leaver rows are events from canonical Employee dates. Both events are
returned when both dates fall in the requested range; records outside the
range are omitted.

## Permission semantics and site-backed evidence

Installed source/runtime is Frappe 16.34.0, ERPNext 16.35.0, and HRMS 16.19.0.
Context7's v16 Report documentation agrees with installed runtime behavior:
standard reports execute the bundled Python module; the report's role table is
enforced; standard reports keep roles from their JSON definition. Site-backed
tests exercised `frappe.desk.query_report.run` as scoped synthetic users without
native HR User, HR Manager, or System Manager roles.

The integration fixture covers synthetic COMPANY_A/COMPANY_B Employees across two
Branches/Departments, active and default shifts, missing coverage, and multiple
submitted overlapping native Shift Assignments. It verifies HR Manager and
HR/Attendance Officer access to both reports, Factory Supervisor access to Shift
Coverage but not Joiners/Leavers, Branch and Department manager scope, combined
Branch+Department permissions, Compliance Auditor read access, company
isolation, manually supplied out-of-scope filters, and Worker denial. The HR
Manager ran both reports; the HR/Attendance Officer ran Joiners and Leavers;
the Factory Supervisor ran Shift Coverage and was denied Joiners and Leavers.
Direct Python execution is also tested under scoped users, including zero-result
scope.

The staging site's `apply_strict_user_permissions` remains disabled. Native
Frappe User Permission matching admits blank Branch/Department Link values. The
synthetic Branch-scoped user therefore sees an otherwise in-company Employee
whose Branch is blank, and a Department-scoped user sees an Employee whose
Department is blank. The report preserves this native behavior. A requested
specific Branch/Department still narrows to exact matches. This remains a
company data-quality and security-UAT decision; strict permissions were not
enabled globally.

## Installer convergence and query-report wrapper

The app installer removes the two reports from the app's custom Query Report
map and includes their names in `STANDARD_SCRIPT_REPORT_NAMES`. During normal
migration `ensure_standard_script_reports()` deletes an app-owned non-standard
record and reloads the bundled report JSON. This staging migration converted
both installed records from Query Report to standard Script Report with
`module = Workforce Suite`, `ref_doctype = Employee`, explicit roles, and no saved
Query SQL. The conversion was performed only through normal `bench migrate`;
there was no direct SQL metadata edit.

Before conversion four Workforce Query Reports depended on
`workforce_suite.report_filters.run`. The installed app now has exactly two Query
Reports: `Workforce Pay Component Register` and `Workforce Payroll Variance`.
The global override remains registered for those reports and is unchanged in
behavior; it does not normalize the two Script Reports. Removing or narrowing
the global override remains future cleanup for the financial-report slice.

## Backup and migration

Before migration, read `BACKUPS.md` and ran
`bench --site hrms-v16.localhost backup --with-files` at
2026-09-25 17:54:24 Asia/Dhaka. Prefix:
`20260925_175417-hrms-v16_localhost-`. Database `gzip -t` and public/private
`tar -tf` checks passed. Sizes and SHA-256 values are recorded in `BACKUPS.md`.
The site DB endpoint remained `127.0.0.1:3307`. Standard
`bench --site hrms-v16.localhost migrate` and `bench --site hrms-v16.localhost
clear-cache` were run. Installed Report metadata was read back after migration
to verify conversion and the remaining two Query Reports.

## Validation and cleanup

- Focused report/security batch: `34 passed, 2 skipped`.
- Full Workforce suite: `567 passed, 2 skipped`.
- `compileall`: passed.
- All 61 app JSON files parsed.
- `git diff --check`: passed.
- App assets built with documented Node 24.15.0 runtime.
- Synthetic User, User Permission, Employee, Shift Type, and Shift Assignment
  markers all returned zero after tests. The test restores the original
  `HR Settings.allow_multiple_shift_assignments` value in `finally`.

No real Employee, User, User Permission, Shift Assignment, Attendance, Leave,
or payroll data was changed by the synthetic integration fixture.
