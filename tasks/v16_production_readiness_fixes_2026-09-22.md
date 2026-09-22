# v16 production-readiness fixes — 2026-09-22

Scope: feature branch `fix/v16-production-readiness`, staging site
`hrms-v16.localhost` only. The v15 site and any production database were not
changed.

## Implemented

- Company-sensitive reports now resolve an explicit company or the current
  user's Frappe default. There is no silent fallback to Tradexcel Ceramics
  Ltd. EFL remains a separate legal company; TCL Head Office and TCL Factory
  remain branches under TCL.
- The four company-required Script Reports validate Company read permission
  before their raw SQL runs.
- The seven native Query Reports were exercised through Frappe's real
  `frappe.desk.query_report.run()` path with JSON-style filters. They remain
  native Query Reports; no unnecessary Script Report conversion was made.
- The Tradexcel HR Desktop tile is normalized to `/desk/tradexcel-hr` in the
  current tab without changing Frappe core or other external links.
- HR rail report links now pass initial filters through native
  `frappe.route_options`; query strings are no longer embedded into the route
  path and URL-encoded as part of the report name.
- Mobile attendance now has a browser IndexedDB queue. Check-in/out events,
  GPS evidence, and selfie blobs survive a temporary network outage and replay
  with the original idempotent `sync_id`. Server-rejected events remain visible
  as needing HR attention instead of retrying forever. A page reload reflects
  the latest pending local event, preventing a duplicate punch; a queued OUT
  event cannot expose another checkout action.
- Offline mobile attendance now uses the captured event time as the canonical
  `Employee Checkin.time` for shift/date resolution and stores server receipt
  time separately. Attendance policies configure a maximum offline age,
  future-clock tolerance, and whether suspicious timestamps are flagged or
  blocked. This prevents delayed replay from silently becoming the receipt
  time while retaining an auditable clock-skew signal.
- Staging face matching was configured with the OpenCV YuNet + SFace adapter.
  Models are site-local and not committed to Git:

  ```text
  face_detection_yunet_2023mar.onnx
  SHA-256 8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4

  face_recognition_sface_2021dec.onnx
  SHA-256 0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79
  ```

  The supplied staging photo matched itself successfully at score `1.0`.

## Verification

- Before the staging migration, a full site backup was taken and gzip-verified:
  `20260922_164856-hrms-v16_localhost-database.sql.gz` (3,248,003 bytes,
  SHA-256 first 16 `9d45b229d7caf76f`). The complete backup set is indexed in
  `BACKUPS.md`.
- Focused tests: `11 passed` before the rail regression extension.
- Full v16 suite against `hrms-v16.localhost`: `158 passed, 2 skipped`.
- After offline-time hardening and schema migration: `162 passed, 2 skipped`.
- Before that staging schema migration, the complete site backup
  `20260922_203730-hrms-v16_localhost-*` was created and the database dump was
  gzip-verified. Its database SHA-256 first 16 is `f95eae64b85d7c99`; the full
  set is indexed in `BACKUPS.md`.
- Operational-report fixtures default to the v16 site/bench while retaining
  `FRAPPE_TEST_SITE` and `FRAPPE_TEST_SITES_PATH` overrides. The endpoint test
  covers all seven Query Reports, preventing a silent fallback to the old v15
  site from hiding report regressions.
- Python compilation passed.
- JavaScript syntax checks passed for the navigation and mobile page.
- Staging assets rebuilt successfully with Node 24 (`bench build --app
  tradex_hr`) and the staging cache was cleared. The installed system Node 20
  is below the Frappe v16 engine requirement, so the build used an isolated
  Node 24 runner and did not change the system Node installation.
- All five app-owned Script Reports are present on staging as standard Script
  Reports with module `Tradexcel HR`.

## Still configuration-owned before go-live

- An Administrator must assign the fifteen Tradexcel roles to real named
  users. No user identities were invented or granted access by this change.
- Each non-admin user's Company User Permission must be tested for TCL or EFL.
- Contabo must serve the mobile page over HTTPS before GPS/camera testing in
  the field. Localhost is a secure-context exception.
- Face matching remains biometric evidence, not a mathematically perfect
  liveness or identity guarantee. Enable it per policy only after a small
  approved validation set and reference photos are in place.
- Offline selfie Blobs remain in browser IndexedDB until successful replay,
  rejection, expiration processing, or the next application opportunity to
  run cleanup. Production must document device security, retention, and
  clearing procedures before enabling offline selfie capture; the browser
  cannot guarantee wall-clock deletion while the app is never opened.

## Mobile branch freeze

The receipt-time security-policy correction is isolated on
`fix/mobile-offline-time-integrity` and pushed at commit `a83ae92`. Approval
loads the exact policy stored on the quarantined check-in for security
validation; it resolves the event-time policy separately for historical duty,
zone, shift, and evidence semantics. The focused field-attendance test command
was:

```text
cd /home/sanchita/frappe-bench-v16
env/bin/python -m pytest apps/tradex_hr/tradex_hr/tests/test_field_attendance_service.py -q
20 passed
```

Stacked PR: `https://github.com/shamrat05/tradexcel-hr-v16/pull/3`, with base
`fix/v16-production-readiness` and head `fix/mobile-offline-time-integrity`.
It is intentionally not merged. Android airplane-mode E2E was not run because
no ADB device was available; this remains a release gate, not a development
blocker for the next P0.

## Payroll P0 safety slice

Branch: `fix/payroll-p0-safety`, with behavior commit `090ff37`, created from
base commit `69461cf` (`fix/v16-production-readiness`). No production site was
opened, no real payroll was run, and no Salary Slip was submitted.

Caller audit found:

| Caller | Finding | Compatibility action |
| --- | --- | --- |
| `sync/run_payroll.py` | Untracked compatibility shim to the app runner | Kept as a forwarding shim; CLI now requires explicit site context |
| Desktop `run_payroll.bat` | Still invokes the old untracked shim without site arguments | Deliberately not changed in this app-repo commit; it now fails closed and must be pointed explicitly at the v16 bench before operator use |
| `sync/rebuild_tradex.py` | Imports the shim and calls the public runner | Existing-context calls remain valid; an uninitialized call now fails closed instead of selecting the v15 site |
| `sync/smoke_manual_payroll_drafts.py` | Uses draft helpers only | Unchanged; it remains a rollback-only smoke utility |
| `sync/audit_salary_coverage.py` | Uses source-salary helpers for comparison | Preserved; source JSON is audit-only and never a payroll input |
| app tests | Previously covered only `_create_manual_slip` | Added preflight and orchestration regression coverage |

Behavior now enforced:

- `Salary Structure Assignment` is the only source of calculation money.
- Missing assignment, zero base, overlapping assignments, and mid-period
  assignment changes produce explicit blockers; no `latest_by_employee`
  guess remains.
- Existing draft or submitted slips produce `SKIPPED_EXISTING` and are never
  overwritten.
- Rows report `CREATED`, `SKIPPED_EXISTING`, `BLOCKED_*`, `FAILED`, or the
  legacy comparison warning. Savepoints and per-row commits preserve earlier
  successful drafts when a later employee fails.
- The CLI accepts `--site` and `--sites-path` or
  `FRAPPE_SITE`/`FRAPPE_SITES_PATH`; without an existing Frappe context it
  refuses to guess a bench or site.
- The raw `Employee Checkin` daily-wage path is explicitly marked legacy and
  non-production. It was not redesigned in this safety slice; the next P0
  replaces that Checkin-to-money boundary with finalized native Attendance.

Verification on this branch:

```text
cd /home/sanchita/frappe-bench-v16
env/bin/python -m pytest apps/tradex_hr/tradex_hr/tests/test_payroll_safety.py apps/tradex_hr/tradex_hr/tests/test_payroll_draft.py apps/tradex_hr/tradex_hr/tests/test_payroll_rules.py -q
19 passed

env/bin/python -m pytest apps/tradex_hr/tradex_hr/tests -q
168 passed, 2 skipped
```
