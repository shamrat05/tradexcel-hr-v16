# Role-scoped native Workspace Action Board — 2026-09-26

Parent: `fix/employee-linked-scope`, PR #34,
`031120271a393dae93ff90e0aa48614aafc9f4c6`; accepted full suite 604 passed,
0 skipped. Branch `feat/action-board`. Status: COMPLETE for this engineering phase; real browser UAT remains.

## Existing home and native extension point

The canonical `workforce-suite` Workspace previously led with headcount/punch cards
and overview charts. These were informational, not this user's unresolved work.
No new Workspace, SPA, task ledger or approval database is introduced.

Installed Frappe `desk/desktop.py` filters Workspace `custom_blocks` using native
Has Role rows. `widgets/custom_block_widget.js` loads native Custom HTML Block;
`dom.js:create_shadow_element` supplies a shadow-root `root_element`. The app
converges one source-backed HTML/script/style block through its normal installer.
The existing Workspace now places that block first and removes its overview
card/chart references. Existing shortcuts remain for the navigation phase.
Theme toggle, app-tile routing and the old rail are unchanged in this phase.

## Read-only adapters, not new calculations

`action_board.py` resolves caller Company choices from native Company permission
and the native permitted Employee identity query. It rejects disabled/Guest,
Worker-only and Import-Reviewer-only callers. All data queries re-resolve native
scope; browser filters never authorize access. Device operators use their
select-only Employee identity scope and gain no Employee form or salary access.

Sources reused:
- `inspect_attendance_integrity`: required unmarked Attendance, pending native
  correction requests and quarantined/ambiguous evidence. No punch-to-pay rule.
- Standard Shift Coverage and Employee Data Gaps reports.
- Standard Salary Coverage and Payroll Readiness reports; only intended
  financial roles invoke financial sources. Company-wide readiness that cannot
  run within the user's scope yields a configuration/access notice, not partial
  company totals or a misleading zero.
- Native draft SSA/Overtime queues; independent approvers' own drafts are not
  offered as their approval work. Existing submit guards remain authoritative.
- Existing payment-readiness reconciliation, only for permitted native Payroll
  Entries whose Employee population is fully visible. No amounts are copied
  into board items.
- Native onboarding/separation/F&F queues plus existing Employee joiner/exit/
  settlement readiness for joining/leaving dates in the selected month.
- Native legal review drafts and availability of approved effective configuration
  within the caller's scope. Missing configuration requests applicability review;
  it never decides legal applicability, rates or entitlements.
- Assigned native Leave Applications for Leave Approver, and permitted pending
  biometric enrollments for Device Admin.

Items contain category, severity, title, reason, count, Company, optional Employee,
source and canonical route. Queue routes narrow to exactly the counted native
records; they are navigation, not an ACL. The board does not certify readiness
when empty. Expected configuration errors do not become an all-clear. A denied
company-wide source does not offer a known PermissionError drill-through.

Reports run through their permission-checked native `execute_module` method.
They do not use `execute_script_report`'s timer which can enable prepared-report
metadata after 15 seconds. Source calculations are not duplicated. No writes,
submissions, queue mutations, salary calculations or legal money are added.

## Persona and UI evidence in progress

Initial focused run: 13 passed. Actual synthetic User/Role/User Permission
personas cover all 15 representative roles, with native Company/Branch/Department
scope and crafted cross-scope requests. Four role paths execute actual source
adapters, not only mocked routing. Worker/Import Reviewer are denied; operational
personas do not invoke salary sources. Tests verify draft requests remain draft
and no Attendance/SSA/Salary Slip/Additional Salary side effects.

Final focused acceptance: **25 passed**, 15 warnings. Native Workspace checks
prove the block is visible to HR Manager, Branch Manager and Device Admin;
an unlinked Worker does not have the management Workspace itself. Source and
installed HTML/script/style match. The first test assumed dictionary child rows;
installed Frappe returns native child documents. Another initial assertion
assumed every persona had the Workspace; the Worker is correctly excluded.
Both test assumptions were corrected without broadening permissions.
Disabled-user calls also fail closed. No browser/device PASS is claimed here.

## Migration

Verified fresh backup `20260926_180505-hrms-v16_localhost-`, sizes and SHA-256 in
BACKUPS.md; gzip and both tar integrity checks passed. Standard `bench migrate`
and `clear-cache` completed. No direct metadata SQL or real data reconciliation.

The script gained a guard suppressing denied-source buttons after the first
migration. The parity test detected stale stored script, so a second fresh
verified backup `20260926_181032-hrms-v16_localhost-` preceded standard migration
and cache clear. This is a metadata convergence correction, not a business data
migration. No ad-hoc SQL or manual block edit was used.

Node **24.15.0** syntax check and `bench build --app workforce_suite` passed. Compileall,
all **61** tracked JSON files and diff check passed. Full `env/bin/python -m pytest apps/workforce_suite/workforce_suite/tests -q
--disable-warnings --tb=short`: **607 passed, 0 failed, 0 skipped**, 80 warnings,
429.77 seconds. Three new tests; the old overview-card assertion was replaced by
the new native block contract, not silently deleted.

Tracked native Attendance Requests are explicitly deleted and their names
checked after teardown. Final SOLBOARD (including Workspace personas) counts
were zero for Users, User Permissions, Has Role, Contacts, Notification Settings
and Employees. No synthetic Attendance/SSA/Salary Slip/Additional Salary was
created by the board. Previous campaign marker categories were also zero and
queue audit showed no pending jobs.

Full diff reviewed for secrets, real data, core edits, duplicate ledgers,
company-specific business constants and mutation paths. None introduced.
Publish as a draft stacked on #34; no merge or CI pass is claimed. The next
phase replaces the existing rail with proven native navigation. Browser UAT,
per-record card labels and wider usability/localization are separate remaining
campaign gates.
