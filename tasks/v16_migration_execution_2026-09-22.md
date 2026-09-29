# Tradexcel HR v16 staging migration — 2026-09-22

## Scope and safety

- Branch: `feature/hrms-v16-hr-only` (local canonical app repository).
- Production/current site `hrms.localhost` was not migrated or written.
- Staging bench: `/home/sanchita/frappe-bench-v16`.
- Staging site: `hrms-v16.localhost`.
- Staging MariaDB: separate database on port `3307`.
- The isolated bench default site is set to `hrms-v16.localhost`, so
  `http://localhost:8001/app/tradexcel-hr` resolves to this staging site.
- A fresh source backup was taken before migration and recorded in `BACKUPS.md`.

## Runtime installed

| App | Version | Branch |
|---|---:|---|
| Frappe | 16.34.0 | version-16 |
| ERPNext | 16.35.0 | version-16 |
| Frappe HRMS | 16.19.0 | version-16 |
| tradex_hr | 0.1.0 | feature/hrms-v16-hr-only |

Frappe HRMS v16 declares ERPNext v16 as a required Frappe dependency. ERPNext is
therefore installed in the bench even though the user-facing navigation is HR-only;
removing ERPNext would make HRMS unsupported.

## Source backup

- Database backup: `20260922_121725-hrms_localhost-database.sql.gz`
- Database SHA-256: `8e62a570fe6a6c430a95b6c8ed7c2f5682c8c2ce9bf2cb4c2d09b30c60d5146f`
- `gzip -t` passed.
- Public/private file archives were restored into staging.

The Bench restore wrapper did not populate the isolated database, so the same
verified dump was imported directly through the staging site's configured DB
credentials. The source backup remains unchanged.

## Data verification after restore and v16 migration

| DocType | Rows |
|---|---:|
| Employee | 242 |
| Employee Checkin | 22,302 |
| Attendance | 16,077 |
| Salary Slip | 0 |
| Salary Structure Assignment | 227 |
| Leave Application | 7 |
| Leave Allocation | 1,190 |
| Shift Assignment | 237 |
| Tradexcel Biometric Device | 2 |
| Tradexcel Employee Biometric | 221 |

The zero Salary Slip count matches the source site at backup time; the migration
did not invent or recreate payroll slips.

## v16 fixes included

1. App-owned reports, number cards and dashboard charts are custom records, not
   Frappe standard records. This avoids the v16 runtime rejection “Cannot edit a
   standard report/chart”. Existing app-owned legacy standard reports are safely
   converted during migration; records owned by another module are not deleted.
2. Report roles are normalized into child rows before document construction.
3. The title-named `Tradexcel HR` workspace is retired. Only the canonical public
   `tradexcel-hr` workspace remains.
4. A persistent grouped HR navigation rail is included in the Desk bundle:
   248px expanded, 64px icon-only collapsed, active route highlighting, keyboard
   buttons, accessible labels, and grouped Home/People/Time/Leave/Payroll/
   Operations/Devices/Analytics/Administration links.

## Validation

- v16 asset build passed with Node 24.15.0.
- Custom app v16 non-site-mutating tests: **130 passed, 6 skipped**.
- JavaScript syntax check passed with Node 24.
- Focused dashboard/navigation tests passed.
- Staging Desk login and `/app/tradexcel-hr` returned HTTP 200 and loaded the
  hashed `tradex_hr` JS/CSS assets.
- Chrome DevTools MCP is not configured in this environment, so screenshot,
  computed-style and accessibility-tree checks remain a manual staging step.

## Remaining gates before any production cutover

1. Push the local branch to the private GitHub app repository after GitHub
   credentials are available; it has not been pushed from this session.
2. Repair the legacy integration-test fixture that points to the obsolete
   Desktop mirror (`/mnt/c/Users/Sanchita/Desktop/hrms.localhost/logs`), then run
   the integration suite against an explicitly selected staging site.
3. Perform manual browser checks at laptop width: expanded/collapsed rail,
   workspace, list, report, form and payroll routes; verify no console errors.
4. Reconcile payroll/leave business rules and test a draft-only payroll cycle in
   staging before production cutover.
5. Take a new production backup immediately before any eventual v16 cutover.

## Addendum — PR #7 migration and queue proof, 2026-09-23

### Deployment preflight

Before a staging migration:

1. Confirm the exact site is hrms-v16.localhost and the bench is /home/sanchita/frappe-bench-v16.
2. Record the app branch and commit; confirm the production site is not selected.
3. Take a fresh backup with files and record archive checksums.
4. Verify the database gzip and both file archives before relying on the backup.
5. Inspect the default/short/long queues by site and job type; confirm a healthy normal worker before migration.
6. Check free disk space and keep the source commit recorded with the migration result.

Frappe v16 queues delete_dynamic_links jobs during document cleanup. Do not patch Frappe, make cleanup synchronous in Tradexcel, or clear Redis queues to force migration success. Worker availability is an operational prerequisite.

### Queue diagnosis

The earlier staging backlog contained 567 queued jobs: 556 default-queue delete_dynamic_links jobs and 11 long-queue search-index jobs, all attributed to hrms-v16.localhost. No other site was represented. A normal bench worker processed them; no Redis jobs were deleted manually. Subsequent migrations also queued the expected site-scoped search-index work. At final inspection bench show-pending-jobs reported no pending jobs.

### Final PR #7 staging migration

- Branch: feat/payroll-readiness-operator-flow, based on PR #7 head 8aff25f325756aee116aa7a89d6385b478e3893a before these changes.
- Fresh pre-migration backup: 20260923_081458-hrms-v16_localhost.
- Database SHA-256: f6b47e03a7a78b0796e5c81d5ca5ef8423e1580e6748bc2daedb87425fe62a44.
- Public files SHA-256: 407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532.
- Private files SHA-256: 7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe.
- Config SHA-256: 904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73.
- gzip -t and tar archive listings passed.
- Standard bench migrate exited 0 and executed after_migrate. No direct ensure_* calls or manual metadata convergence were used.
- clear-cache exited 0. bench build --app tradex_hr passed with Node 24.15.0.

### Restore rehearsal

A disposable site, payroll-migration-check-20260923.localhost, was restored from the verified staging backup using the bench restore path and migrated with standard bench migrate. Workers were running during migration. The app metadata smoke check passed: the three promoted reports load as Standard Script Reports in Tradexcel HR; the remaining four stay custom Query Reports. The report API smoke checks are recorded in ui_report_runtime_audit_2026-09-22.md. No production site was touched, and no salary slip or accounting entry was submitted or created by this rehearsal.

Status: STANDARD BENCH MIGRATE = PROVEN on staging and the disposable restored site. This is deployment rehearsal evidence, not production approval.

\r\n