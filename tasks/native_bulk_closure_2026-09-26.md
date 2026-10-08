# Native bulk-domain closure — 2026-09-26

- Parent: `feat/native-overtime-bulk` / PR #31, head `9fbfbdd04c8f86585424f279a835de4f61f291e3`.
- Branch: `refactor/native-bulk-closure`, based on that exact head.
- Scope: retire the duplicate Employee Data Gaps mutation endpoint, correct its
  permission/pay-basis evidence, and record one canonical route per bulk domain.

## Reproduction and source decisions

`bulk_fix.resolve_gap` remained whitelisted for direct Employee department,
designation and holiday-list changes. Department/designation updates were
already blocked by the Employee lifecycle guard; holiday-list mutation was a
second path around native Employee maintenance. No other caller required
`bulk_fix.py`. The Employee Data Gaps bundled JS still called that endpoint,
while its Report JSON contained a stale second JavaScript copy. Both paths were
removed. The report now navigates to the native Shift Assignment Tool, native
Bulk Salary Structure Assignment, native Employee Transfer/Promotion, or
Employee List. The native tools rebuild and validate their own selections.

A synthetic Workforce Suite/Attendance Officer limited to one Company and Branch
could previously receive a synthetic Employee in another Branch from the raw
SQL Employee Data Gaps report. The report now binds Employee IDs resolved by
the existing Frappe permission-aware scope helper. A zero-Employee scope
returns zero rows, and filters only narrow scope. The helper no longer silently
truncates at Frappe's default list page size.

The old report classified pay using Salary Structure names containing “Wage”
and Employee `employment_type`. It now resolves the effective submitted SSA and
the linked Salary Structure's explicit `custom_workforce_pay_basis`; historical
assignment count is informational and same-date conflicts follow the canonical
resolver. Active shift coverage is checked on the report date, not by any
historical assignment.

Installed Frappe Data Import uses target DocType `import` permission and
`Importer.update_record` calls the existing Employee `.save()` validation.
The synthetic direct-update probe was rejected by the lifecycle guard.
Workforce Suite Manager lacks Employee import and Data Import create, so broad
import enablement remains fail-closed. The framework's background deadlock
retry does not carry its initial `user`; review this before delegating Data
Import to custom roles. No real import was run.

## Migration and backup

The Report JSON `javascript` metadata changed, so a fresh staging
`bench backup --with-files` was taken before standard migration. Prefix:
`20260926_070248-hrms-v16_localhost-`. `gzip -t` and public/private `tar -tf`
passed; sizes and full SHA-256 values are in `BACKUPS.md`. Standard
`bench --site hrms-v16.localhost migrate` and `clear-cache` completed. The
installed Report has empty saved JavaScript metadata and the canonical
`workforce-suite` Workspace still exists. No direct Report SQL edit was used.

## Validation

- Employee Data Gaps pure + site integration: **8 passed**.
- Report authorization, Workspace, operational report and company-context
  focused set: **29 passed**.
- Post-migration report-focused set: **16 passed**.
- Final focused set after navigation/filter regression updates: **28 passed**.
- Node 24.15.0 syntax check and `bench build --app workforce_suite`: passed.
- Full suite before the fixture cleanup correction: **597 passed, 0 skipped,
  70 warnings**. Compileall, 61 tracked JSON parses and diff check passed.
- Final synthetic scan found two orphan test-owned Contacts, with zero Users,
  User Permissions, Has Role rows or Employees for the phase markers. Native
  `User.on_update` queued Contact creation outside Frappe test mode, racing
  teardown. The harness now makes only User setup synchronous using the native
  test flag, and asserts Contact and role-child cleanup too. The two confirmed
  orphan synthetic Contacts were removed; a final suite rerun follows the
  harness correction. Runtime User creation behavior is unchanged.
- A broader ancillary-record scan also found 17 orphan Notification Settings
  for the phase's deleted synthetic Users. The old harness had skipped native
  `User.on_trash` to work around the Contact race. Native User teardown is now
  restored, and Notification Settings are included in cleanup assertions. The
  17 confirmed test-owned orphan settings were removed without changing any
  real user configuration.

The first full run found one obsolete test expecting the removed saved Data
Import shortcut (593 passed, 1 failed). That assertion was replaced by the
bundled native Employee List route contract; the final full suite is rerun
after all source changes. Old wage-name/Employment-Type inference tests were
replaced by explicit Monthly/Daily and conflict/unresolved tests, and the
retired shift resolver tests by missing-module/native-navigation assertions.
No test was removed to hide a live authorization failure.

The detailed domain map is `tasks/bulk_operations_contract_2026-09-26.md`.
No custom ledger or generic bulk framework was added. Browser/persona UAT,
real company import delegation and legal configuration remain separate gates.

## Ancillary fixture cleanup follow-up

Native User teardown occasionally reproduced MariaDB Contact snapshot error
1020 (`frappe.QueryDeadlockError`). The test harness now retries that native
teardown up to three times in a fresh transaction; it does not suppress native
cleanup hooks. The final focused report/persona set passed **12 tests**.

A broader scan found 621 orphan Notification Settings and one Contact for old
`persona-puat…@example.test` fixtures. A fresh verified `--with-files` backup
(`20260926_092011-hrms-v16_localhost-`) preceded cleanup. Every settings record
was tied to a nonexistent synthetic User. The Contact's test token, exact
synthetic email and empty links were checked before native deletion. All five
scanned categories (Users, Contacts, Notification Settings, User Permissions,
Has Role) were then zero for that marker. No real account was deleted or
reconfigured. Sizes/hashes are recorded in `BACKUPS.md`.

The next full run reported **593 passed, 4 failed**. Three failures were fixture
teardown `QueueOverloaded` errors: the one-off removal of old orphan settings
had queued native dynamic-link cleanup faster than the worker could drain it.
An attempted SIGINT also interrupted the salary test's database connection,
causing the fourth failure; this run is not acceptance evidence. The worker
subsequently drained all three queues. Nine tracked synthetic SSAs, 16
synthetic Employees and eight synthetic Users from that interrupted test were
removed through native APIs. The native salary-tool singleton was restored
exactly from the pre-test backup through `set_single_value`, with no values
exported. The affected group and full suite are rerun after recovery.

## Acceptance evidence

After queue recovery, the affected attendance/salary group passed **4 tests**
(7 warnings). The final frozen-source full suite passed **597 tests, 0 skipped**
(70 warnings, 738.76 seconds). This exceeds the accepted campaign baseline
and phase C's 595 tests. These are local staging results, not GitHub CI.

Final scans showed zero phase `SOLDG`/`SOLDI` and shared `PUAT` Users, User
Permissions, Has Role, Employees, Contacts and Notification Settings. Older
`BULKATT`/`BULKAPP`/`BULKSSA` fixture orphans were also explicitly removed after
verifying nonexistent synthetic Users, test names/emails and empty Contact
links. Native synchronous deletion avoided background queue flooding. The
pre-cleanup backup is `20260926_092011-hrms-v16_localhost-`.

No app runtime core files, real Users, real Employee/payroll records, company
compensation or legal policy were changed. No PR was merged. The three legacy
report boundaries listed in campaign state require a separate reproduced
correction before Action Board adapters consume their output.
