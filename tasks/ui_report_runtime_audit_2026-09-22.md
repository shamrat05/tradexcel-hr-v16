# v16 report and navigation runtime audit — 2026-09-22

## Scope

Staging only: `hrms-v16.localhost` on `localhost:8001`. The v15 site and any production database were not changed.

## Findings

The five app-owned Python reports are file-backed standard Script Reports:

- Daily Attendance Summary
- Tradexcel Salary Coverage Board
- Biometric ID Audit
- Employee Data Gaps
- Workforce Anomaly Radar

Their JSON definitions already had `is_standard: "Yes"`, but the installer was rewriting four of them as custom records and creating Daily Attendance Summary as custom. In v16, a custom Script Report is executed as a Server Script. Server Scripts are disabled by default, so those reports returned `ServerScriptNotEnabled`/HTTP 403 instead of loading their bundled `execute()` functions.

The installer now repairs only these known Tradexcel-owned records by reloading their file-backed definitions. It skips standard Script Reports during custom-report reconciliation, so future migrations do not demote them again. Other Query Reports remain custom and editable.

The Playwright sweep also found one invalid navigation route: `Calendar/Leave Application`. It is now `leave-application/view/calendar`, the native HRMS v16 route. The app rail was being emptied when Frappe replaced a page shell; the rail is now idempotent and rebuilds after route changes. The unused blank desktop shell reservation is hidden while the app rail is enabled, without affecting mobile.

## Permission review

Frappe v16 treats an empty Report role table as unrestricted. The five app-owned standard reports now carry explicit role allow-lists in their JSON definitions. Employee and Employee Self Service were removed from Daily Attendance Summary; salary coverage is limited to payroll/finance/HR leadership and audit roles; attendance, data-gap, biometric, and anomaly reports are limited to their corresponding HR, device, compliance, and leadership roles. The migration reloads these standard definitions so role-table drift self-heals without converting them to custom reports.

The navigation repair uses the Frappe route-change event and a guarded idempotent render that tolerates Frappe's incomplete route state during boot. No permanent timer or document-wide observer is used.

## Validation contract

After the staging app is updated from this branch:

1. All five report records must return `is_standard=Yes`, `module=Tradexcel HR`, and `report_type=Script Report`.
2. Each report route must load without HTTP 403 or `ServerScriptNotEnabled`.
3. The leave calendar route must resolve to `/desk/leave-application/view/calendar/default`.
4. The Tradexcel rail must contain grouped items on the workspace and on list, form, report, attendance, and payroll routes.
5. The page must not gain horizontal overflow at the tested desktop viewport.
6. Socket.IO 404s from `bench serve` are test-server noise: `bench serve` does not run the Socket.IO process. Production must use the full bench process manager/supervisor.

## Safety

The repair is deliberately allow-listed. If a report with one of these names is owned by another module, migration stops instead of deleting it. A database backup is taken before the staging migration.

## Final staging result

- Backup: `sites/hrms-v16.localhost/private/backups/20260922_142154-hrms-v16_localhost-database.sql.gz` plus public/private file archives.
- All five app-owned Python reports now return `is_standard=Yes`, `module=Tradexcel HR`, `report_type=Script Report`.
- Playwright sweep: 44/44 unique Tradexcel rail routes passed; 0 navigation errors, 0 page error surfaces, 0 non-Socket.IO HTTP errors, and 0 horizontal-overflow findings at 1440px.
- Rail persistence: 9 groups and 49 links were present after direct navigation to workspace, list, and leave-calendar pages.
- Runtime report calls returned HTTP 200 for Workforce Anomaly Radar, Employee Data Gaps, Biometric ID Audit, Daily Attendance Summary, and Tradexcel Salary Coverage Board.
- The three required-filter menu reports now open with safe current-date/current-month and user-default-company parameters; their runtime calls also returned HTTP 200.
- Live Has Role rows are explicit for all five reports; none has an empty role list and none includes Employee or Employee Self Service.
- Final minimal-navigation browser sweep: 44/44 routes passed with 9 groups/49 links, no page errors, no non-Socket.IO HTTP errors, no overflow, and no polling/observer repair machinery.
- `bench serve` still emits Socket.IO 404 polling noise because it is only the web process. That is not a page failure; a full `bench start`/supervisor deployment supplies the Socket.IO process.
