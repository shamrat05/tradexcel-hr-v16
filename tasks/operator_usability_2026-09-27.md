# Operator usability and focused Bangla guidance — 2026-09-27

Parent: PR #37, `fix/bulk-job-privacy`. Accepted baseline: 613 passed, 0 skipped.
Status: COMPLETE. Native forms, reports, lists and Workspace remain the UI.

## Reproduction and bounded changes

The existing attendance report dialog allowed an old Present preview to return
after the operator changed the action to Work From Home. It then displayed
Create draft requests while the eventual apply payload used the new action.
A controlled execution of the actual bundled report JavaScript reproduced this
without a database mutation. The regression now checks stale responses, changed
inputs without a DOM event, fresh confirmation and repeated clicks during apply.
A preview generation plus input snapshot binds confirmation to the reviewed
payload; the server still independently revalidates permissions and eligibility.
A failed apply returns to Preview rather than leaving an inert confirmation.

The dialog displays its Company/date, reports per-row blocked results, and links
created drafts directly to the native Attendance Request List. It never approves
requests. Native independent approval remains unchanged. Action Board Employee
and payroll-entry findings now have readable, permission-scoped identity/period
labels. No amounts or new calculations are added. Date changes refresh the board;
invalid dates, busy state, keyboard focus and narrow-screen text wrapping have
explicit behavior. No animation or refresh-rate controls were added.

`translations/bn.csv` uses installed Frappe `translate.get_translations_from_csv`.
The catalog targets 28 operator labels/guidance/statuses. Placeholders are tested;
canonical status/reason values stay English and are translated only for display.
Framework translation and language preference remain authoritative. Technical
setup vocabulary and wider readiness explanations are not blanket-translated;
actual staff language review remains UAT.

## Task/device classification

| Persona/work | Device priority and canonical surface |
| --- | --- |
| Attendance officer | PHONE_CRITICAL: daily exceptions and mobile evidence; PHONE_USEFUL: correction drafts; DESKTOP_FIRST: large shift batches. |
| HR Manager | PHONE_USEFUL: joiner/exit blockers, correction review; DESKTOP_FIRST: Employee maintenance, leave entitlement, salary drafts. |
| Attendance/Leave approvers | PHONE_CRITICAL: inspect request, review evidence, approve/deny; native request list/form. |
| Supervisor/Branch/Department managers | PHONE_USEFUL: scoped attendance/shift exceptions; no salary or bulk mutation grants. |
| Worker | PHONE_CRITICAL: attendance capture and own leave/ESS where supported; no management board. |
| Payroll manager/approver | DESKTOP_FIRST: salary authority, payroll readiness, batch review; PHONE_USEFUL: finding triage only. |
| Finance/Compliance | DESKTOP_FIRST: reconciliation, legal evidence/review; PHONE_USEFUL: outstanding-work triage. |
| Owner/Device admin | PHONE_USEFUL: relevant outstanding-work review; DESKTOP_FIRST: policy decisions/device setup. |
| Import reviewer | DESKTOP_FIRST: reviewed import evidence; no new import authority. |

## Validation and deployment

- 18 focused tests passed (11 warnings): operator UI, Action Board/native scope,
  attendance correction integration, maker/checker and native navigation.
- Node 24 syntax and `bench build --app workforce_suite` passed.
- Fresh verified `backup --with-files`: `20260927_001652-hrms-v16_localhost-`.
  Gzip/public/private tar integrity, exact sizes and SHA-256 are in `BACKUPS.md`.
- Standard migrate and cache clear converged the versioned Custom HTML Block
  and Report JSON/bundled JS. No manual metadata SQL.
- Actual Chromium: HR Manager in Bangla, Department Manager and Worker at
  1440/390 pixels; no overflow, custom rail or page errors. Operational board
  available only to intended personas. Date refresh and Shadow DOM keyboard
  focus passed. Native report checkbox selection → preview → draft creation →
  filtered Attendance Request List passed for a synthetic Employee. Exactly one
  draft and zero Attendance records resulted. Browser fixtures explicitly removed.
- Full suite: **616 passed, 0 skipped**, 86 warnings, 474.45 seconds.
  Compileall, 61 JSON parses and diff-check passed. Aggregate synthetic marker
  counts are zero and worker queues are empty. Staff language, export/print and
  physical-phone interaction remain broader release UAT, not claimed here.
