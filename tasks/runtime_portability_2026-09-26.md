# Runtime portability and source inventory — 2026-09-26

Parent: accepted attendance branch `feat/bulk-attendance-corrections` at
`5d30ce89d1d96532cbf10847d226a23559ec0afd` (draft PR #28). Work branch:
`refactor/runtime-portability`. The isolated site has Frappe 16.34.0,
ERPNext 16.35.0, HRMS 16.19.0 and tradex_hr 0.1.0 on MariaDB
`127.0.0.1:3307`. Accepted full-suite baseline: 585 passed, 0 skipped.

## Source/runtime audit

`git ls-files` yielded 390 tracked files. The tracked inventory is
`tasks/sol_tracked_source_inventory_2026-09-26.txt`. The source scan parsed
Python/JSON/YAML, enumerated whitelist decorators and searched mutation,
permission, queue, direct SQL, external HTTP, hardcoded company/currency and
absolute-path sites. The source audit is a triage inventory, not a claim that
every endpoint has completed adversarial site-backed UAT; phase H owns that
verification.

The v16 bench has no `sync/` directory. Payroll and biometric worker source
is versioned in this app. The bridge is a separate clean checkout at
`2cb9c50e2af2c0b995cd3e7d75185b98487d58e2`; no bridge source, database
or secrets were copied here. Its current authenticated configuration endpoint
stores a bridge profile but does not apply terminal settings, so physical
device UAT remains open. The old app bridge contract was stale and is updated.

## Caller and hazard classification

| Source | Classification before change | Evidence and outcome |
| --- | --- | --- |
| `payroll_setup.py` | Dormant one-off migration utility | Repository-wide caller search found no importer. It contained hardcoded wage/company/classification, direct Employee mutation, submitted SSA creation, `ignore_permissions` and commit. Removed from the importable package; never executed. |
| `salary_excel.py` | Dormant one-off salary importer | No production caller. It embedded old company/source paths and could write salary authority. Removed; never executed. |
| `salary_setup.py` and `salary_setup.yaml` | Explicit historical company migration utility/spec | Not called by generic install after this change. Kept so historical provenance is visible, but the helper now requires an explicit currency. It must never be run against real staging data without a separate reviewed migration. |
| `branch_setup.py` | Active `after_migrate` metadata and business-data mutation | Kept only neutral Branch custom fields. Removed hardcoded TCL/EFL rename, address and hierarchy writes. Cleared the old company default in metadata. Existing Branch records are untouched. |
| `install.py` | Active install/migrate and dashboard convergence | Removed automatic historic pay-basis seeding and two company-specific Number Cards. Standard migration removes those app-owned cards. No Employee, wage or SSA is manufactured by generic install. |
| `field_attendance_service.py` | Active field-duty allowance path | Removed BDT fallback; Company currency must be configured. No amount or pay-basis rule changed. |
| `biometric/worker.py` | Active packaged worker | Removed old-bench/Windows SQLite and guessed device defaults. Persistent state and site must be explicit; HTTP bridge is default when no SQLite path is configured. No device was contacted in this audit. |
| `tradex_hr.bundle.js` custom rail | Active legacy navigation | Left for phase F, where native Workspace parity and browser behavior can be measured first. |
| `bulk_fix.py` | Active Employee-data mutation | Left for bulk closure phase D; this phase does not alter another workflow's security contract. |

Tradexcel branding remains. Historical task notes and the explicit salary
specification retain company names as historical data, not generic runtime
defaults. README and AGENTS status were corrected without rewriting the old
September 18 snapshot.

## Staging migration and data preservation

Before migration, read `BACKUPS.md` and took `bench --site
hrms-v16.localhost backup --with-files` at 2026-09-26 01:27:50 Asia/Dhaka,
prefix `20260926_012737-hrms-v16_localhost-`. Database gzip and public/private
tar listings passed. Exact sizes and SHA-256 are recorded in `BACKUPS.md`.
Ran standard `bench --site hrms-v16.localhost migrate` and `clear-cache`;
both succeeded. No manual metadata SQL was used. The migration emitted two
expected missing-source warnings for deleted legacy Number Card JSON, then
the app installer removed their installed records. The canonical Workspace
remains installed. The Branch Company custom-field default is blank.

Read-only before/after digests of selected business fields matched exactly:
242 Employees, 5 Branches and 227 Salary Structure Assignments. No real
record in those three categories was changed. Other real-data categories
were not asserted by those digests.

## Tests and remaining proof

Focused portability/pay-basis/worker/dashboard tests: **35 passed**. Full
Tradexcel suite: **593 passed, 0 skipped**, 64 warnings in 445.43 seconds,
above the accepted 585-pass baseline. `compileall` passed, 61 app JSON files
parsed, and `git diff --check` passed. The added focused tests created no
synthetic database records; the full suite uses its existing explicit fixture
cleanup. Fresh neutral-site install has not yet been executed; phase
K owns an isolated clean-install rehearsal. Source tests enforce no automatic
company-specific Branch or salary seeding and no reintroduced importable
one-off payroll helpers. Physical bridge operation, browser UAT and production
restore remain unproven.
