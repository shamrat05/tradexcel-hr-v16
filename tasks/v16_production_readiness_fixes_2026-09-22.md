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
