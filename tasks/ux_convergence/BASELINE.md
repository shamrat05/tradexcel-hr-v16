# Current UX inventory and measured baseline

TASK-ID: TXUX-260930-001. Audit date: 2026-09-30. Source baseline: `1a194240b7312609f0dbcf4195558a54bddcca8c`. Installed source: Frappe 16.34.0, ERPNext 16.35.0, HRMS 16.19.0. No redesign implemented.

## Evidence boundaries and method

Source audit uses the exact accepted-base worktree. Staging serves the canonical checkout at PR #53 head `830c599b19a6074c58f2a9b37977f336d1fe61d4`. Its diff from the accepted base is only scoped field-page CSS, its asset test and its evidence note. Browser navigation measurements therefore exercise the same navigation/application logic, but visual results are **not an untouched accepted-base theme comparison**. No #53 change is included/cherry-picked in this branch.

Read README/AGENTS/BACKUPS, the latest Workspace/Action Board/operator/performance/release notes and relevant source/tests. Historical figures in those notes are attributed evidence, not fresh staging counts. Context7's v16 navigation guidance recommends curated standard Workspace Sidebar metadata; its mixed develop/v14 snippets were checked against installed source rather than assumed compatible. Codebase-memory discovery tools were not available in this tool session; `rg`/direct source were used. No semantic graph was needed for these documentation-only edits.

Chromium/Playwright uses seven disposable native persona Users from `tradex_hr/tests/persona_uat.py`, native Company/Branch/Department User Permissions, a unique synthetic Branch/Department, one linked synthetic Employee and one DRAFT Attendance Request. Existing Company identity remains private and unchanged. The scope contains only the synthetic Employee. No leave/payroll/device/financial configuration is invented. Navigation/inspection only; no Attendance, payroll, correction apply or submit button is pressed.

Each journey starts from a settled Home at 1365×900 except Employee self-service, which starts on its direct page. Login/reset is harness setup and excluded. Navigation click = opening a route, native group or search selection. Intentional actions additionally include typing, read-only inspection and dismissing an encountered message. Safety/confirmation clicks are separately recorded (none exercised in these read-only journeys). Browser auto-scroll is not counted as an intentional human scroll; these are lower-bound scripted navigation actions, not human effort estimates. Source route alternatives are never converted into invented click counts.

Timed intervals use the same harness waits (650ms after click and 800ms after scenario, plus awaited rendering). They are single-run **automation elapsed time**, not staff completion-time/median/P95 claims. Pilot locator mistakes were corrected and excluded. Reproducible Home and Employee permission modals are application observations; their dismissals remain in final counts. Seven fixture personas were created; six were exercised in browser journeys. The separate Attendance Correction Approver fixture was not browser-exercised.

## Current UI inventory

| Surface | Current source truth / behavior | Persona and audit implication |
| --- | --- | --- |
| Home | `tradex_hr/install.py:workspace_blocks`, `ensure_workspace`; `tradex_hr/tradexcel_hr/workspace/tradexcel_hr/tradexcel_hr.json`. Four headers: Action Board, Operational Snapshot, Pending Work, Common Actions. One Custom HTML Block, three native Number Cards, three Quick Lists, twelve rendered shortcut definitions, zero charts. | Native role/item filtering changes the visible population. Synthetic HR Manager saw eleven Home shortcuts; Run Monthly Payroll was absent. Worker has no management Home. |
| Home source ownership | Bundled Workspace JSON is title-named; installer converges canonical slug `tradexcel-hr`, removes aliases, sets cross-module Home roles and no module gate. 119 shortcut definitions also feed Sidebar. | Changing twelve rendered blocks must not delete advanced catalog definitions. Review dual JSON/installer ownership in 011. |
| Sidebar | `install.py:WORKSPACE_SECTIONS`, `workspace_sidebar_items`, `ensure_workspace_sidebar`. Twelve sections, 120 Link definitions including Home, 12 Section Breaks; native per-user output is smaller. Sections: Employees; Attendance & Shifts; Leave & Holidays; Expenses & Travel; Payroll; Recruitment; Development & Relations; Separation; Compliance; Reports; Setup; Devices. | Existing `Workspace Sidebar` record is app/module-owned, `standard=0`, no `for_user`, saved by installer. Native boot filters each target and JS hides empty sections. No custom rail remains. |
| Action Board backend | `tradex_hr/tradexcel_hr/action_board.py:get_board_context`, `get_action_board`, `_build_board`, `_report_items`, `_queue`, `_people_items`, `_payment_items`. Categories currently include Attendance, Shifts, People, Payroll, Finance, Compliance, Leave, Devices according to roles/data. Severity values include Review/Configuration. | Company/Employee scope is server-resolved; financial sources gated. Worker/import-only denied. Existing inspectors/reports/native drafts are sources; no task-state ledger or new calculations. |
| Action Board presentation | `tradex_hr/public/action_board/home.html`, `home.js`, `home.css`; native Custom HTML Block Shadow DOM. Company + review date + Review work. Cards show category/title/count/context/reason/Open review. Routes use server-supplied native filters. | Severity exists in response but is not separately rendered/grouped by current client. Empty state explicitly does not certify readiness. Failure shows access/retry text; denied sources can still leak native msgprint modals (measured below). |
| Native pending widgets | Open Leave Requests (`status=Open`); Attendance Requests to Review (`docstatus=0`); Draft Expense Claims (`docstatus=0`, `approval_status=Draft`). Snapshot: leave today/month and Expense Claims this month. | Generic permitted drafts/open requests differ from assigned/independent-review work. Widget visibility does not prove the counted population has identical meaning to board findings. |
| Lists | `tradex_hr/public/js/list_scope.js`: nine DocTypes; eight primary date fields; Today/This Week/This Month/Custom Range; Company/Branch/Department/Designation/Employee Link narrowing; Attendance in/out and Checkin time shown as clock time. Existing settings callbacks/formatters composed. | UX filters are never ACL. Clock-only Checkin display can obscure date context; measure before changing. Four buttons per dated list may crowd toolbar; native saved filters are hidden on phone, so replacement needs evidence. |
| Mobile Attendance | `tradex_hr/tradexcel_hr/page/tradexcel_mobile_attendance/`; native custom Page. Policy context, last Checkin, purpose, camera, GPS, IN/OUT, success screen, IndexedDB queue and cleanup/replay. | Self-service server identity and quarantine remain authoritative. Saved-on-device is not server-approved Attendance. Review/rejected status clarity needs 009 evidence. |
| Live Locations | `tradex_hr/tradexcel_hr/page/tradex_live_locations/`; native custom Page. Scoped read API, refresh + 60-second interval, active-duty table, integrity label, OpenStreetMap external link. | No new Page warranted. Existing timer lifecycle/empty/error/status behavior may be measured in later MOBILE owner task; no fix here. |
| Global UI | `tradex_hr/public/js/tradex_hr.bundle.js`: toolbar/page-change theme button uses native `frappe.ui.set_theme` and User switch_theme; same-tab tile rewrite targets only Tradexcel HR desktop icon. | Theme state uses native API but insertion/DOM selectors need upgrade review. Tile DOM rewriting is an upgrade-risk adapter; inspect native Desktop Icon before replacing. |
| Global CSS | `tradex_hr/public/css/tradex_hr.bundle.css`: broad full-width container overrides, 215px layout-side-section cap, navbar 15px padding, `html` stable both-edges scrollbar gutter, hidden navbar brand. | Global scope remains a containment review target. Prior width measurements are historical; they do not prove every native screen. No persistent custom rail/sidebar-hiding rules remain. |

## Exact installed native mechanisms

Paths are relative to the respective installed app root (read-only; not modified):

- Frappe `frappe/desk/doctype/workspace_sidebar/workspace_sidebar.py:WorkspaceSidebar.export_sidebar`: app + standard + developer mode exports app-level `workspace_sidebar/<scrubbed-title>.json`. `frappe/model/sync.py:sync_for` imports app-level sidebar/desktop-icon/group JSON. Installed HRMS itself ships `hrms/workspace_sidebar/` JSON. This supports a curated standard source path; it is not yet a tested migration recommendation for this app's current record.
- Frappe `frappe/boot.py:get_sidebar_items`, `frappe/desk/desk_views.py:DeskViews.is_item_allowed`: native DocType/Page/Report/Workspace permission filtering, per-user private-sidebar overlay; empty sidebars withheld. `frappe/public/js/frappe/ui/sidebar/sidebar.js:resolve_sidebar` preserves current/remembered/app-matching Sidebar and suppresses empty groups.
- Frappe `frappe/desk/desktop.py:Workspace`: Workspace roles, allowed modules/targets, permitted custom blocks, quick lists/cards, onboarding roles and System Settings enable_onboarding. Sidebar visibility remains navigation, not endpoint authorization.
- Frappe `frappe/public/js/frappe/list/list_filter.js`: saved filters, Save Current Filter, administrator-only global-filter creation, mobile early return. `frappe/public/js/frappe/list/list_view.js`: Customize Quick Filters. `frappe/public/js/frappe/list/base_list.js:FilterArea.make_standard_filters`: metadata/user-settings quick fields, custom_filter_configs and native operators.
- Frappe `frappe/public/js/frappe/ui/toolbar/awesome_bar.js`, `frappe/desk/search.py:awesomebar_search`: native modal/search routes and permission-aware backend. `frappe/public/js/frappe/views/workspace/blocks/onboarding.js` and `frappe/public/js/frappe/widgets/onboarding_widget.js`: native tutorial/step/form-tour/report/page actions; no separate app task ledger needed.
- Frappe `frappe/desk/doctype/desktop_icon/desktop_icon.py`, `frappe/desk/page/desktop/desktop.js`: native app/Sidebar desktop routing. Evaluate these before keeping app-tile DOM interception indefinitely.

## List feature classification for 004

| Custom feature | Classification | Reason / proof still required |
| --- | --- | --- |
| Company→Branch/Department and scoped Employee Link queries | KEEP | Complements native Link UX; server permissions remain separate. Verify actual field availability/composition on nine lists. |
| Today / This Week / This Month buttons | MEASURE FIRST | Native Timespan operator supports the same data filtering, but discovery/actions and phone availability may differ. No removal solely from feature duplication. |
| Custom Range prompt | REPLACE WITH NATIVE candidate | Native Between filter exists; compare keyboard/actions/date validation and retained filters before replacing. |
| Per-user reusable filters | REPLACE WITH NATIVE | Native ListFilter already saves/applies filters. App should not add another saved-filter database/UI. Mobile native saved-filter menu is absent, requiring phone proof. |
| Clock-only Checkin formatting | MEASURE FIRST | Improves daily scanning but may hide the date on mixed-date lists; preserve clear date/evidence meaning. |
| Callback/formatter composition | KEEP | Existing native/app settings must survive; avoid overriding list implementations or scope boundaries. |

## Sidebar and custom-UI risk classification

| Item | Classification / recommendation |
| --- | --- |
| Native Workspace/Sidebar/List/Form/Report/Awesomebar | NATIVE-SUPPORTED; keep foundation. |
| App source installer owns standard=0 Sidebar | APP-LEVEL NECESSARY current ownership; UPGRADE-RISK / REVIEW in 011. Prefer standard app-level JSON only after fresh/migration/persona/private-customization proof. Keep current behavior until then. |
| Native Action Board Custom HTML Block adapter | APP-LEVEL NECESSARY; reuse inspectors; 003 can improve presentation/failure without new calculations or Page. |
| Global full-width and sidebar cap CSS | UPGRADE-RISK / NEEDS MEASUREMENT; 012 compares native shell and critical lists/forms/reports, including collapsed Sidebar. |
| Scrollbar gutter / navbar padding | NEEDS MEASUREMENT; prior rationale is concrete but global overrides need current view/device parity. |
| Navbar brand hiding | REMOVE CANDIDATE after 010 checks native Navbar/Website logo settings; no decision/branding change here. |
| Custom toolbar theme button | APP-LEVEL NECESSARY convenience, native theme APIs; MEASURE FIRST against native theme preference/toggle. Do not add another theme state system. |
| App-tile DOM interception/polling | UPGRADE-RISK; 010 should evaluate native Desktop Icon/Sidebar linking and preserve same-session behavior. |
| Mobile/Live custom Pages | EXISTING APP-LEVEL UI, not authority; no further Page creation. PR #53 is the separate accepted narrow theme correction. |
| Calendar hardcoded status colors in `tradex_hr/public/js/employee_calendar.js` | NEEDS MEASUREMENT under 008/010 boundary; calendar colors are UI semantics, not pay rules. No global CSS workaround here. |

## Artifact/reference audit

All eleven app artifacts below are still **actively converged by installer**, despite no current Home reference. A fresh read-only staging count on 2026-09-30 found zero references for each in Workspace Chart/Workspace Number Card and Dashboard Chart Link/Number Card Link. Repository references are their JSON, installer definitions/rename compatibility and tests/history. External URLs/user preferences/custom content were not exhaustively proven absent. Therefore **LEGACY/COMPATIBILITY; DEAD CANDIDATE**, not permission to delete now.

| Artifact kind | Names | Future decision |
| --- | --- | --- |
| Charts (7) | Tradexcel Attendance Status; Tradexcel Checkins by Day; Tradexcel Employees by Branch; Tradexcel Employees by Department; Tradexcel Headcount by Company; Tradexcel Leave Allocated by Type; Tradexcel Payroll by Month | 013 must remove creation/source only after full stored-reference/compatibility review; sensitive chart public metadata is not proof of safe/unsafe data querying. |
| Number Cards (4) | Tradexcel Absent Records; Tradexcel Active Employees; Tradexcel Present Records; Tradexcel Punches Logged | Same; no per-company hardcoded cards should be reintroduced. |
| Home native Number Cards (3) | Number of Employees on Leave (Today); Number of Employees on Leave (This Month); Expense Claims (This Month) | ACTIVE, referenced by current Home; evaluate utility/scoped meaning in 002. Do not confuse with four app cards. |
| Legacy Workspace aliases/chart/card rename maps | `install.py:LEGACY_WORKSPACE_NAMES`, `LEGACY_DASHBOARD_CHART_NAMES`, rename/orphan functions | LEGACY/COMPATIBILITY; no deletion until current installation and upgrades are tested. |

## Persona job inventory

Risk/device/frequency are proposed operational classifications, not measured staff usage. Primary/alternate screens are source-audited; journey actions are recorded below. For every blocked outcome, native/server reason remains authoritative.

| Persona / task | Frequency / risk / device | Current primary start / route and alternatives | Inputs / retyping concern | Failure, recovery and success |
| --- | --- | --- | --- | --- |
| HR Manager: daily issues/correction drafts | Daily / high / phone-useful; large batches desktop-first | Home board or Today's Attendance → Daily Board; Sidebar/Search alternate; Attendance Request list for drafts | Company/date/Employees/action/explanation; shortcut may require Company again, board route carries context | Per-row blockers; correct native config/evidence; success is DRAFT requests, independent approval still required. |
| HR/Attendance Officer: evidence and corrections | Daily / high / phone-critical review, phone-useful draft batch | Daily Board/Attendance Request/Punch Log; board + Home + Sidebar duplicates | Same plus evidence reason; Current report population must be revalidated | Pending evidence/config/consumed history blocks; review native evidence; draft ≠ payable Attendance. |
| Payroll Manager: monthly run / salary drafts | Monthly / high / desktop-first | Run Monthly Payroll → Readiness; salary coverage/native bulk SSA; Sidebar/Search | Company/month; row links carry Employee and date; direct report may require Company again | Explicit attendance/pay/tax/account blockers; canonical recovery links; prepared native Payroll Entry/slips, not payroll approved. |
| Finance/Accounts Officer: payment/F&F | Monthly/occasional / high / desktop-first | Board native Payroll Entry or Final Settlements → native F&F; Sidebar/Search | Company/payroll period/voucher; do not show partial-company totals as whole | Payment/config/reconciliation findings; reviewed native vouchers; success is native reconciled state. |
| Branch/Department Manager: scoped coverage | Daily / medium / phone-useful | Board → Daily/Shift coverage; native Sidebar reports | Company/date + optional narrowing; permitted scope cannot expand | Scope/config notice, ask authorized operator; read-only finding review, no salary/bulk mutation rights. |
| Factory Supervisor: operational exceptions | Daily / medium / phone-useful | Board/Attendance & Shifts/Punch review as allowed | Date/Employee and review explanation | Pending evidence independent reviewer; no proxy punch or pay authority; success means reviewed evidence/approved native request by correct role. |
| Attendance Correction Approver | Daily / high / phone-critical | Board/native Attendance Request list/form; pending Quick List/Sidebar/Search | Employee/date/request/evidence; no maker create role | Owner/self-scope/consumed guards; separate scoped approver; native submit creates/updates Attendance. |
| Leave Approver | Daily/weekly / high / phone-critical | Assigned board queue or native Leave Application list/form | Request, configured entitlement/evidence | Native overlap/allocation/approver checks; reviewed native leave status. “Open” list can include non-assigned work. |
| Compliance Auditor | Weekly/setup / high / desktop-first | Board → native review/rule records; Sidebar Compliance/Setup | Explicit applicability/effective date/provenance; no inferred law | Missing/review-required stays blocked; approved separate legal/business decision, not UI guessing. |
| Employee/Worker | Daily / high evidence / phone-critical | Direct Mobile Attendance; own native leave/ESS as permitted; no management Home | Linked identity, policy, purpose, camera/GPS; never choose another Employee | Local pending/server rejection/review required; recover network/config/reviewer; server accepted Checkin ≠ payroll Attendance. |
| New low-Frappe-knowledge operator | Daily first use / varies / phone-useful or desktop-first by job | Role Home primary; native Sidebar/Search for advanced work; no current app onboarding block | Terminology/company/date repeated entry and duplicates are learning burdens | Native failure modals/plain guidance; 005 needs native onboarding/tours; measure understanding of draft/submitted/saved states. |

## Target acceptance metrics — not achieved claims

- One obvious primary route per daily job; high-priority work visible/reachable from role Home without a wrong-screen visit. Tentative target: at most two navigation actions from settled Home to the relevant review surface, excluding identity selection, filter input and required safety actions.
- High-risk blocked action always explains the reason and supplies a permitted canonical recovery route or precise next instruction. No “all clear” from unavailable source or silent partial failure.
- Zero wrong-company/scope financial mutations and zero duplicate mutation from retry; preserve existing server regressions. These are safety constraints, not click optimization targets.
- Native Sidebar/Search retains advanced/setup access; Home does not become a full feature catalog.
- Human UAT proposal: ≥90% first-attempt success for agreed daily scenarios; zero critical misunderstanding of draft vs submitted/local saved vs accepted/reviewed; median time/navigation/wrong-turn/backtracking/help-request metrics compared with this campaign's measured **human** baseline once staff testing exists.
- 014 repeats identical starts, fixture populations, viewports/themes and action taxonomy. Do not compare automated timing to human timing or remove preview/confirmation/maker-checker to hit a target.

## Measured journeys — 2026-09-30

Fifteen scenarios attempted. Thirteen reached their stated read-only destination; B04 and B15 encountered genuine scope/configuration blocks. This is navigation evidence, not fifteen completed business workflows. No submit/apply or safety confirmation was exercised. All journeys had zero backtracks. Manual Company entry was needed in B01/B04/B12; other journeys had zero manually entered filters. Native search text is counted separately as an intentional action.

| Scenario / persona | Navigation clicks | Intentional actions | Recovery dismissals | Automation seconds | Observed destination/result |
| --- | ---: | ---: | ---: | ---: | --- |
| B01 / hr_manager | 1 | 4 | 1 | 3.41 | Scoped Daily board loaded; synthetic Employee shows Not Marked |
| B02 / attendance_officer | 1 | 1 | 0 | 1.52 | Native draft Attendance Request form reached; maker does not approve |
| B03 / leave_approver | 1 | 1 | 0 | 1.52 | Native Leave Application list reached; no synthetic pending leave configured |
| B04 / payroll_manager | 1 | 5 | 2 | 4.20 | Payroll Readiness route reached; whole-company execution correctly denied for Branch/Department-only scope |
| B05 / payroll_manager | 1 | 2 | 1 | 3.74 | Scoped salary coverage route reached; Company context passed |
| B06 / finance | 1 | 2 | 1 | 2.20 | Native Full and Final Statement list reached; no synthetic financial posting |
| B07 / hr_manager | 2 | 4 | 2 | 4.59 | Native Employee form reached after dismissing HR Settings read denial |
| B08 / hr_manager | 2 | 6 | 2 | 6.09 | Read-only readiness dialog reached |
| B09 / hr_manager | 2 | 3 | 1 | 2.92 | Native Employee Separation list reached; Final Settlements is alternate Home shortcut |
| B10 / hr_manager | 1 | 2 | 1 | 2.24 | Native Expense Claim list reached |
| B11 / hr_manager | 2 | 3 | 1 | 2.91 | Installed native Shift Assignment Tool reached; no preview/apply |
| B12 / attendance_officer | 1 | 5 | 0 | 3.56 | One synthetic Employee selected; Prepare Attendance Corrections dialog opened. No preview/apply. |
| B13 / hr_manager | 2 | 3 | 1 | 2.89 | Less-common native Training Program list reached |
| B14 / hr_manager | 2 | 4 | 1 | 3.86 | Native search route reached |
| B15 / worker | 0 | 1 | 1 | 2.80 | Blocked: no approved policy. Action still reads Loading; event states not exercised. |

Exact intentional steps: B01 dismiss Home message → Today's Attendance → enter/accept Company. B02 pending synthetic request row → native draft form. B03 Leave Requests → empty scoped list. B04 dismiss scope message → Run Monthly Payroll → enter/accept Company → dismiss scope denial. B05 dismiss Home message → salary finding Open review → scoped Salary Coverage with Company carried. B06 dismiss Home message → Final Settlements. B07 dismiss Home message → Directory → synthetic Employee → dismiss HR Settings message. B08 adds Onboarding group → Check Joiner Readiness to B07. B09 dismiss Home message → Separation section → Exits/Separations. B10 dismiss Home message → Expense Claims. B11 dismiss Home message → Attendance & Shifts section → Bulk Shift Assignment. B12 Today's Attendance → enter/accept Company → select one row → Prepare Attendance Corrections. B13 dismiss Home message → Development & Relations section → Training Programs. B14 dismiss Home message → open Awesomebar → type tool name → choose result. B15 direct-route setup → dismiss missing-policy message; direct-route setup is excluded from navigation count.

B03 did not measure approval of a configured pending Leave Application. B06 did not measure a payment/posting. B08 returned NEEDS_ATTENTION without changing Employee/configuration. B12 opened the real dialog with one selected Employee but did not preview or create requests. B15 could not validate saved/pending/synced/review-needed/rejected transitions without policy/event fixtures; these labels were source-audited only. Physical Android/offline and staff-understanding evidence remains required.

### Reproduced recovery problems and owners

- **003:** Home native permission messages interrupt HR/Finance navigation: “You don't have access to Report: Tradexcel Payroll Readiness.” Scoped Payroll Manager gets “You do not have access to every employee in this payroll company.” Backend safe-item handling does not fully contain native RPC message dialogs. Preserve authorization; investigate presentation/source selection rather than granting access.
- **008:** Native Employee form reports “No permission for HR Settings.” Installed `hrms/public/js/erpnext/employee.js` calls `frappe.db.get_single_value("HR Settings", "emp_created_by")`. Dismissing the message allows the existing read-only Joiner Readiness action. This is a native dependency issue, not authorization to grant settings access or patch core.
- **009:** Missing approved mobile policy correctly blocks the server, but page action remains Loading. `showSuccessState` distinguishes local queue vs IN/OUT acceptance, without an equally explicit review-state result. Actual transition fixtures/UAT are needed before changing labels.
- **007:** Whole-company Payroll Readiness correctly rejects narrower scope. A scoped Salary Coverage drilldown works and carries Company. Do not weaken whole-population authorization to reduce clicks.
- **008 / owner decision:** Expense/Travel/Advance/Leave Encashment approval authority is not resolved merely by navigation. Current persona note records DECISION_REQUIRED for affected native financial workflows; UX cannot invent approval rights.

### Viewport/theme smoke

Home rendered at 1365×900 and 375×900 in light and dark: native Sidebar present, exactly one Action Board block, no custom rail, no document horizontal overflow in all four combinations. This is render smoke, not complete keyboard/contrast/visual approval of every screen; permission overlays were separately observed. Mobile/Live Locations visual acceptance belongs to independent #53 evidence; no new contrast claim is made here.

### Installed core boundary

Frappe checkout is clean but HEAD `f1bdb53ac60cd96528b52de418f9459510acb5bd` contains the previously documented local collapsed-sidebar scrollbar fix. This audit created no core change. Runtime sidebar appearance must not be represented as pristine upstream behavior or source-only app proof. **012** must review this external core boundary; **015** must record deployment/upgrade evidence. Do not copy core CSS into the app without a native-first decision.

### Cleanup and validation boundary

Fixture cleanup explicitly verified zero synthetic Users, User Permissions, Employees, Attendance Requests, Contacts, role grants, Branch and Department; zero Attendance created. No payroll, Leave, Checkin or device mutation was performed. Only the six authorized documentation files change. No runtime tests or full site-backed suite were rerun for documentation-only edits; existing test source and prior dated results are audit inputs, not freshly passing tests.

## Baseline reproducibility contract — P01

B01–B15 are the canonical automation baseline IDs. Future 014 comparison must preserve each scenario's meaning, start surface, persona and action taxonomy. Single-run automation seconds are diagnostic only. Human UAT timing is a separate baseline and must never be numerically compared with these automation seconds. If changed Frappe behavior/configuration prevents reproduction, record the difference rather than fabricate parity. P01 changes no measured values or intentional steps.
