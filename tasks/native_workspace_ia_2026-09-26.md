# Native Workspace navigation — 2026-09-26

Parent PR #35, `feat/action-board`, `257fa90fccf815c7d3b5698f20e4dd0acbf94b6f`.
Accepted baseline: 607 passed, 0 skipped. Status: COMPLETE; broader workflow/browser UAT remains.

Installed Frappe `boot.get_sidebar_items`, `WorkspaceSidebar` and
`DeskViews.is_item_allowed` already filter each native DocType/Page/Report/
Workspace link. Native sidebar JS resolves the current entity to a sidebar,
keeps it while navigating its records and hides empty sections. No replacement
navigation engine is needed.

Current site already has a non-standard `Workforce Suite` Workspace Sidebar with
41 items, no app ownership and a Home link to `workforce-suite`. It is not maintained
by current installer source. The custom rail ignores persona permissions and
its CSS hides the native desktop sidebar. Its separate theme and app-tile IIFEs
must remain intact.

Source inspection also found `Shift Assignments` targeting native Shift Schedule
Assignment, while ordinary assignments created by the secured tool are native
Shift Assignment. This is a navigation mismatch, not a shift-controller change.

Plan: converge the existing native sidebar from versioned navigation metadata,
using current native targets and native per-item permission filtering. Prove
persona/route parity, then remove only rail JS/CSS. No DocPerm expansion, new
Workspace, business mutation, custom ACL or new rail.

Tests, backup/migration, asset build and full-suite acceptance are pending.

Baseline sidebar target audit found **zero nonexistent targets**, but the 41-item
record had no source ownership and omitted later workflows. The Shift Assignments
label/target mismatch is confirmed in Workspace source. No claim of a nonexistent
Shift Schedule Assignment DocType is made.

## Native route parity

Employee, Checkin, Attendance/Request, Shift, Leave, Payroll, recruitment,
separation, compliance and device targets use native Sidebar Link items.
Calendar remains the native Leave Application view selector. Notifications and
assigned ToDos remain native Desk functions; Role/Workflow setup remains native
administrator search, rather than being advertised to every HR operator.
Duplicate rail aliases (Directory/Employees, Anomalies/Action Queue and
Home/Overview/Setup) converge on their one native target. Mobile evidence review
also has the permission-scoped Action Board drill-through.

No new permissions are granted by this change. Section Breaks in the native boot
payload are not proof of visible empty headings: installed sidebar JS suppresses
empty groups. Browser layout/keyboard/mobile UAT remains separate evidence.

The first migration caught a fresh-install ordering defect: the sidebar's Home
Link was saved before the canonical Workspace existed after orphan cleanup.
Fixed by saving Workspace before sidebar and aligning bundled Workspace name to
`workforce-suite`. Retried standard migration after another verified backup; no
manual metadata SQL. Backups: `20260926_183119-hrms-v16_localhost-` and
`20260926_183319-hrms-v16_localhost-` (exact sizes/hashes in BACKUPS.md).

Persona execution reproduced two navigation-only inconsistencies:
- Device Admin saw Biometric ID Audit in native allowed reports but its Employee
  `report` permission rejected execution. Removed that Report-role row. Employee
  select-only scope remains unchanged; no broad Employee/report grant was added.
- Department Manager and attendance/leave approvers had native HR permissions but
  no custom app DocType permission, so native module gating hid their home.
  The cross-module home now uses explicit native Workspace roles and no Module
  restriction, with `app=workforce_suite`. Sidebar metadata remains app/module-owned.
  This grants no target permission and does not bypass Company scope. Worker and
  import-only users use their native surfaces rather than the management home.

## Native boot results

```json
{"attendance_correction_approver": {"home": true, "links": 6}, "attendance_officer": {"home": true, "links": 25}, "branch_manager": {"home": true, "links": 14}, "compliance": {"home": true, "links": 47}, "department_manager": {"home": true, "links": 12}, "device_admin": {"home": true, "links": 4}, "factory_supervisor": {"home": true, "links": 13}, "finance": {"home": true, "links": 16}, "hr_manager": {"home": true, "links": 63}, "import_reviewer": {"home": false, "links": 2}, "leave_approver": {"home": true, "links": 5}, "owner": {"home": true, "links": 48}, "payroll_approver": {"home": true, "links": 18}, "payroll_manager": {"home": true, "links": 28}, "worker": {"home": false, "links": 1}}
```

All visible reports passed `get_report_doc`; every DocType link passed native read permission.
Every intended management persona loaded the native Action Board block. Worker/import-only
users had no management home. Focused integration/static regression: 19 passed;
rail-removal/theme/app-tile/report-default tests: 6 passed. Node 24 syntax/build passed.
Full suite and final cleanup pending.

## Final validation

Full local suite: **609 passed, 0 skipped**, 82 warnings, 796.41 seconds.
Compileall, all 61 tracked app JSON files and `git diff --check` passed.
Node 24 syntax/build passed. The six old rail-specific tests were replaced with
native navigation/theme/app-tile contracts; two native integration tests were
added, not silently removed.

## Browser-discovered block rendering defect

Isolated Playwright/Chromium was made available without adding app/bench runtime
dependencies. Synthetic HR Manager and Department Manager authenticated and
loaded the native Workspace, but zero Action Board widgets rendered. Installed
`workspace/blocks/block.js:Block.make` matches layout `custom_block_name` against
child `label`; the previous source used different strings. Backend payload
presence did not detect this defect. Aligned the native child label with the
layout key and added a source/installed regression. No custom renderer or core
patch. The first full suite (609 passed) predates this fix; final rerun required.

Browser retest after the label fix **passed**: synthetic HR Manager and Department
Manager rendered one Action Board; Worker had no management home/block. At both
1440px and 390px: native sidebar present, zero custom rail, zero page errors,
zero document horizontal overflow. Temporary identities/password file cleaned.
This is a limited navigation/rendering smoke, not complete workflow/export/device UAT.
Final label migration backup: `20260926_233132-hrms-v16_localhost-`.

Final acceptance after the rendering fix: **25 focused passed; 609 full passed,
0 skipped**, 82 warnings, 464.52 seconds. Compile/61 JSON/diff checks and Node24
build passed. Synthetic SOLNAV and prior campaign markers: Users, Has Role, User
Permissions, Contacts, Notification Settings, Employees and linked operational
records all zero; pending queue empty. No real business records changed.
