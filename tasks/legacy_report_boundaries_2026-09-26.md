# Older report boundary correction — 2026-09-26

Parent: PR #32, `refactor/native-bulk-closure`,
`4d6c9af81d5d89e9b1d87867bc5bd97c05bf66ed` (597 passed, zero skipped).
Branch: `fix/legacy-report-boundaries`. This is a separate correction on the
current stack; earlier reviewed report PRs are not rewritten.

## Reproduced baseline

Synthetic native Employees, Checkins, a submitted SSA and a draft Salary Slip
were created under scoped Tradexcel roles and explicitly removed afterwards.
No real record values were printed or modified.

- Attendance Officer + Company/Branch/Department permissions: Workforce Anomaly
  Radar returned an out-of-Branch synthetic Employee and a Payroll-category
  finding about that Employee's native Salary Slip.
- Payroll Manager with the same scope: Payroll Register returned the other
  Branch's draft Salary Slip through `frappe.desk.query_report.run`.
- Daily Attendance Summary: the report endpoint filtered the out-of-Branch
  row because installed Frappe `get_filtered_data` checks returned Link
  columns. Direct Python `execute()` still returned it. The report inferred
  `Present` from a raw Checkin and `Absent` from no Attendance/no Checkin.
  Both were reproduced. This distinction prevents overstating endpoint
  exposure where Frappe's column filtering did work.

Installed authority: `frappe/desk/query_report.py:get_report_doc`,
`generate_report_result`, `get_filtered_data`; native `frappe.get_list` applies
User Permissions while SQL/get_all do not. The app's established report-scope
helper remains the only Employee/Salary Slip population mechanism.

## Work in progress

Report execution checks native Report permission even for direct Python calls.
Attendance Summary uses actual Attendance status, separate draft/submitted
state, and submitted `working_hours`; punches remain evidence only. Payroll
Register uses submitted Salary Slips visible through both Employee and Salary
Slip permissions. Radar scopes Employees and only loads financial data for
callers with native salary read/report access. Financial findings use scoped
submitted native slips and permission-visible canonical SSA authority.

The two old punch-to-pay heuristic checks are retired: a raw punch neither
establishes payable days nor justifies repricing salary. Existing attendance,
payroll readiness and reviewed correction routes own those decisions.

Final test, migration, backup and cleanup evidence will be recorded before PR.

## Pagination hypothesis disproved

A native probe with 21 synthetic submitted Salary Slips showed this installed
Frappe returns all 21 through `get_list` without an explicit limit. Its
`DatabaseQuery.execute` defaults `limit_page_length=None`, despite older API
docstrings/Context7 saying 20. No truncation defect was reproduced. The
explicit unlimited scope option and 21-row parity test document completeness;
they are not a claimed performance fix. The earlier Phase D explanation that
implicit pagination necessarily truncated this runtime was too strong.

## Migration and focused evidence

- Focused source/report set: **37 passed**, 4 warnings.
- Post-migration native report/security integration: **22 passed**, 12 warnings.
- Fresh `--with-files` backup: `20260926_101050-hrms-v16_localhost-`,
  taken 2026-09-26 10:11:24 Asia/Dhaka. Database gzip and both file archives
  verified; exact sizes/SHA-256 are in `BACKUPS.md`.
- Standard `bench migrate` and `clear-cache` completed. Both affected Reports
  remain standard Script Reports with empty saved JavaScript; canonical
  `tradexcel-hr` Workspace is present. No direct metadata SQL was used.
- Node 24 syntax and app build passed. Compileall, 61 JSON parses and
  `git diff --check` passed before final full-suite execution.
- Both `SOLRPT` and `SOLPAGE` markers were zero for Users, User Permissions,
  Has Role, Employees, Contacts and Notification Settings after focused tests.

Full-suite acceptance and final cleanup are pending.

## Validation interruption and test isolation

The first full run stopped at **305 passed, 1 failed**: an existing maternity
unit test replaced every `frappe.get_doc` lookup with its Employee fixture,
then called the real clock. With an uncached System Settings document this
attempted to pickle that fake Employee as settings. The test now fixes its
clock explicitly; maternity runtime behavior is unchanged. Its 34-test module
passed afterwards.

The subsequent full run was interrupted by an environment restart, so it is
not acceptance evidence. On resume the old process handle and temporary log
were absent. The documented isolated MariaDB/Redis services were restarted;
versions and `127.0.0.1:3307` were verified again. Read-only checks found zero
SOLRPT, SOLPAGE, SOLDG, SOLDI, PUAT, BULKATT, BULKAPP and BULKSSA fixture records
in the checked identity/Employee categories and no linked operational records.
Installed Report metadata remained converged. The two new integrations plus
the maternity module passed again: **36 passed, 4 warnings**. A fresh complete
run is required before commit.

## Accepted result

The fresh full run completed: **602 passed, 0 failed, 0 skipped**, 74 warnings
in 417.00 seconds. Command from the v16 bench:
`env/bin/python -m pytest apps/tradex_hr/tradex_hr/tests -q --disable-warnings`.
Compileall, all 61 tracked JSON parses, Node 24 syntax and `git diff --check`
also passed. The earlier Node 24 app build and standard migration remain the
applicable evidence; no further asset or metadata changes followed them.

Final aggregate cleanup checks were zero for all eight marker families above:
Users, User Permissions, Has Role, Employees, Contacts and Notification
Settings. The integration fixtures additionally verified every tracked SSA,
Salary Slip, Attendance and Checkin was deleted through native cleanup. No
real Employee, payroll, attendance, User or legal configuration was changed.
The local web service returned HTTP 200 after restart; scheduled business
processing remains off during synthetic engineering tests.

The diff was reviewed for secrets, real identifiers, core modifications,
duplicate authority and unrelated changes. Browser/report print/export UAT
remains for the release phase. GitHub has no workflow checks on the parent;
these results are local staging evidence, not CI.
