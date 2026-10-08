# Financial payroll reports — 2026-09-25

## Scope and baseline

This slice started from PR #22 head `22105f0754dc12884848ffd466801b49187c68c9`
on `feat/operational-report-scope` and was implemented on the stacked branch
`feat/financial-report-scope`. PR #22 was not changed. The only reports in
scope were Workforce Pay Component Register and Workforce Payroll Variance.

Before conversion, both were System Manager-only Query Reports. Real
`frappe.desk.query_report.run` calls as synthetic custom-role users proved the
safe fail-closed baseline: Owner/Director, HR Manager, Payroll Manager, Payroll
Approver, Finance/Accounts Officer, Compliance Auditor, HR/Attendance Officer,
Factory Supervisor, Branch Manager, Department Manager, and Employee/Worker
were denied. This was an availability gap, not an observed data exposure.

## Native salary dimensions and report policy

Installed HRMS 16.19 Salary Slip metadata/controller contains native
`company`, `branch`, `department`, `designation`, `posting_date`, `start_date`,
and `end_date` fields. The controller documents branch and department on a
Salary Slip as its own payroll-period snapshot rather than the Employee's
current values. A synthetic Salary Slip was submitted for Branch A, then its
Employee was moved to Branch B through native Employee Transfer. Both reports
continued to classify the August salary under the Salary Slip's Branch A
snapshot; cancelling the still-unconsumed synthetic Transfer restored the
Employee to Branch A.

Both reports are Submitted-only. This avoids exposing draft salary figures to
the larger report audience; Payroll Manager/Approver continue to review draft
payroll through the native restricted Payroll Entry/Salary Slip workflow.
Report roles are Owner/Director, HR Manager, Payroll Manager, Payroll
Approver, Finance/Accounts Officer, and Compliance Auditor. Worker,
supervisor, branch/department manager, and HR/Attendance Officer roles are
excluded. Each role also has native Salary Slip read/report permissions. The
Payroll Approver gained only read access to Company, needed by the existing
permission-aware company context guard; Company User Permission still scopes
the report.

## Implementation and security

Both reports are now standard app-owned Script Reports with JSON metadata,
Python execution modules, and JavaScript filters. Pay Component Register reads
actual native Salary Detail earnings/deductions for permission-visible,
submitted Salary Slips; it does not recompute Salary Structure values. Payroll
Variance aggregates native submitted Salary Slip gross, deduction, and net
totals. Full calendar-month filters compare against the preceding full calendar
month. For a partial or non-calendar range, it compares against the immediately
preceding interval with the same number of days. Review reproduced that the old
one-month subtraction could compare a one-day month-end range against a
multi-week prior range; `_previous_period()` now makes this deterministic and
tests full-month, partial-month, and month-end cases. Previous-period slips use
the same permitted Company/Employee population, Salary Slip permissions, and
Branch/Department snapshot filters. Manual filters only narrow that result.

The shared `report_scope.permitted_salary_slips()` uses Frappe's
permission-aware `get_list` for Salary Slip after checking native read/report
permission and the existing permission-aware Employee population. The detail
query is bound to those returned native parent names. Endpoint tests and direct
`execute()` tests cover Company/Employee scope, Branch/Department restrictions,
filter-expansion attempts, excluded roles, submitted-only visibility, native
Salary Detail parity, Salary Slip totals, and historical Branch snapshots.
Period membership continues to use the native Salary Slip `start_date`.

Migration converged all four operational/financial reports to standard Script
Reports. Runtime metadata shows zero Workforce Suite Query Reports. The global
`frappe.desk.query_report.run` override, `report_filters.py`, and the now-unused
`GLOBAL_REPORT_ROLES` constant were removed. No other app-owned Query Report
depends on the wrapper.

## Backup and migration

Before the report metadata migration, read `BACKUPS.md` and ran
`bench --site hrms-v16.localhost backup --with-files` at 2026-09-25 18:36:52
Asia/Dhaka, prefix `20260925_183646-hrms-v16_localhost-`. The database gzip and
both file archives passed integrity checks. Before the additional Company
permission convergence for Payroll Approver, another backup was taken at
18:46:00, prefix `20260925_184554-hrms-v16_localhost-`, with the same checks.
Exact sizes and SHA-256 checksums are recorded in `BACKUPS.md`. Both metadata
convergences used standard `bench --site hrms-v16.localhost migrate` followed
by `clear-cache`; there were no direct database metadata edits. A later
read-only marker audit found four unreferenced Salary Components from older
synthetic test attempts. Their Salary Structure and Salary Slip reference
counts were zero. Before removing them through `frappe.delete_doc`, a fresh
`--with-files` backup was taken at 2026-09-25 19:10:28 Asia/Dhaka, prefix
`20260925_191022-hrms-v16_localhost-`; its database gzip and both archives
passed integrity checks and exact hashes are in `BACKUPS.md`. Test cleanup was
also corrected to delete only its own tokenized Salary Component names and
assert their absence. The site continued using MariaDB at `127.0.0.1:3307`.

## Validation and cleanup

- Fail-closed baseline endpoint checks: all 11 synthetic role personas were
  denied both old reports.
- Focused report/permission/payroll regression batch: 53 passed; the focused
  report/filter suite including full-month, partial-range, and month-end
  comparisons passed 21 tests.
- Full Workforce suite: 570 passed, no skipped tests.
- `compileall`: passed.
- All 63 app JSON files parsed; both report JavaScript files passed Node 24
  syntax checks.
- App assets built using Node 24.15.0.
- `git diff --check`: passed.
- Synthetic payroll fixture explicitly removes its disposable Company, native
  payroll documents, Employees, Users, User Permissions, Departments, and
  synthetic Branches and Salary Components. Post-suite aggregate checks
  returned zero marker matches for Companies, Branches, Departments, Users,
  User Permissions, Employees, Attendance, Payroll Entries, Salary Slips,
  Salary Structure Assignments, Salary Structures, Salary Components, and
  Journal Entries. No real payroll or Employee record was changed.

Remaining evidence includes browser-based export/print UAT and real operator
persona UAT. GitHub has no workflow/status checks configured for the verified
stack head; local test results must not be represented as GitHub CI.
