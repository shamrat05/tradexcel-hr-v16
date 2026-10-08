# v16 report and navigation runtime audit — 2026-09-22

## Scope

Staging only: `hrms-v16.localhost` on `localhost:8001`. The v15 site and any production database were not changed.

## Findings

The five app-owned Python reports are file-backed standard Script Reports:

- Daily Attendance Summary
- Workforce Salary Coverage Board
- Biometric ID Audit
- Employee Data Gaps
- Workforce Anomaly Radar

Their JSON definitions already had `is_standard: "Yes"`, but the installer was rewriting four of them as custom records and creating Daily Attendance Summary as custom. In v16, a custom Script Report is executed as a Server Script. Server Scripts are disabled by default, so those reports returned `ServerScriptNotEnabled`/HTTP 403 instead of loading their bundled `execute()` functions.

The installer now repairs only these known Workforce-owned records by reloading their file-backed definitions. It skips standard Script Reports during custom-report reconciliation, so future migrations do not demote them again. Other Query Reports remain custom and editable.

The Playwright sweep also found one invalid navigation route: `Calendar/Leave Application`. It is now `leave-application/view/calendar`, the native HRMS v16 route. The app rail was being emptied when Frappe replaced a page shell; the rail is now idempotent and rebuilds after route changes. The unused blank desktop shell reservation is hidden while the app rail is enabled, without affecting mobile.

## Permission review

Frappe v16 treats an empty Report role table as unrestricted. The five app-owned standard reports now carry explicit role allow-lists in their JSON definitions. Employee and Employee Self Service were removed from Daily Attendance Summary; salary coverage is limited to payroll/finance/HR leadership and audit roles; attendance, data-gap, biometric, and anomaly reports are limited to their corresponding HR, device, compliance, and leadership roles. The migration reloads these standard definitions so role-table drift self-heals without converting them to custom reports.

The navigation repair uses the Frappe route-change event and a guarded idempotent render that tolerates Frappe's incomplete route state during boot. No permanent timer or document-wide observer is used.

## Validation contract

After the staging app is updated from this branch:

1. All five report records must return `is_standard=Yes`, `module=Workforce Suite`, and `report_type=Script Report`.
2. Each report route must load without HTTP 403 or `ServerScriptNotEnabled`.
3. The leave calendar route must resolve to `/desk/leave-application/view/calendar/default`.
4. The Workforce rail must contain grouped items on the workspace and on list, form, report, attendance, and payroll routes.
5. The page must not gain horizontal overflow at the tested desktop viewport.
6. Socket.IO 404s from `bench serve` are test-server noise: `bench serve` does not run the Socket.IO process. Production must use the full bench process manager/supervisor.

## Safety

The repair is deliberately allow-listed. If a report with one of these names is owned by another module, migration stops instead of deleting it. A database backup is taken before the staging migration.

## Final staging result

- Backup: `sites/hrms-v16.localhost/private/backups/20260922_142154-hrms-v16_localhost-database.sql.gz` plus public/private file archives.
- All five app-owned Python reports now return `is_standard=Yes`, `module=Workforce Suite`, `report_type=Script Report`.
- Playwright sweep: 44/44 unique Workforce rail routes passed; 0 navigation errors, 0 page error surfaces, 0 non-Socket.IO HTTP errors, and 0 horizontal-overflow findings at 1440px.
- Rail persistence: 9 groups and 49 links were present after direct navigation to workspace, list, and leave-calendar pages.
- Runtime report calls returned HTTP 200 for Workforce Anomaly Radar, Employee Data Gaps, Biometric ID Audit, Daily Attendance Summary, and Workforce Salary Coverage Board.
- The three required-filter menu reports now open with safe current-date/current-month and user-default-company parameters; their runtime calls also returned HTTP 200.
- Live Has Role rows are explicit for all five reports; none has an empty role list and none includes Employee or Employee Self Service.
- Final minimal-navigation browser sweep: 44/44 routes passed with 9 groups/49 links, no page errors, no non-Socket.IO HTTP errors, no overflow, and no polling/observer repair machinery.
- The dashboard route is `workforce-suite` (`/desk/workforce-suite`). The `workspace/workforce-suite` builder route is intentionally not used by navigation links.
- `bench serve` still emits Socket.IO 404 polling noise because it is only the web process. That is not a page failure; a full `bench start`/supervisor deployment supplies the Socket.IO process.

## Addendum — report filter incident, 2026-09-23

### Root cause

The two failing reports were still database-backed Query Reports, but their definitions were versioned in workforce_suite/install.py. The problem was not missing JSON alone. Query Report SQL interpolates the request filter mapping directly; a missing SQL placeholder raises a driver error before the query reaches MariaDB. The original direct-open probe with empty filters reproduced this for all seven Workforce Query Reports.

The navigation rail already assigns frappe.route_options to the destination options or null. The source and currently served bundle agree, so the rail was not changed. A real browser route transition was not exercised in this follow-up because Chrome DevTools was unavailable and browser launch was blocked by the environment.

### Fix

- Payroll Register, Leave Balance Board, and Daily Attendance Board are now file-backed standard Script Reports. Their Python execute() functions normalize date/company filters, require a real Company default or selection, and check company access before raw SQL.
- Their old Query Report definitions were removed from the install-time custom report registry. Otherwise ensure_reports() would recreate them after the standard report reload and undo the promotion.
- The other four reports remain Query Reports. A narrow supported override_whitelisted_methods wrapper supplies only unambiguous current-user Company/date defaults and raises a clean ValidationError if a placeholder is absent and cannot be chosen safely.
- Explicit empty optional filter values (for example an empty Branch) remain valid. Only absent or null placeholder keys are rejected.
- No payroll calculation, attendance, leave, or company data was changed.

### Staging verification

- bench --site hrms-v16.localhost migrate: exit 0; after_migrate ran normally.
- bench build --app workforce_suite: passed with the bench-required Node 24.15.0; rebuilt JS hash workforce_suite.bundle.TAYVRSUG.js.
- All seven DB records have the intended report type and Workforce Suite module ownership; the promoted three are Script Report / Standard.
- On a disposable restore copy over HTTP, direct empty-filter calls to the three Script Reports returned HTTP 200. Empty filters to the four Query Reports returned HTTP 417 ValidationError for ambiguous required placeholders, with no KeyError. Requests using each report's complete filter set, including explicitly empty optional filters, returned HTTP 200.
- Browser route sequence and observed browser request payloads remain unverified. The server-side endpoint behavior and filter contracts were verified directly.

\r\n