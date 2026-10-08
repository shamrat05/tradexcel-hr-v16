# File ownership and concurrency

TASK-ID: TXUX-260930-001. Paths below are repository-relative. Ownership is a file lock, not permission to change business behavior. Every implementation must list its exact files before editing.

## Locks

| Lock | Exact file family / evidence | Eligible tasks; sequencing |
| --- | --- | --- |
| WORKSPACE | `workforce_suite/install.py`; `workforce_suite/workforce_suite/workspace/workforce_suite/workforce_suite.json`; any future app-level `workspace_sidebar` source; `workforce_suite/tests/test_hr_workspace_ui.py`, `test_native_navigation_integration.py`, `test_dashboard_setup.py`, `test_reports_and_workspace.py` | **002 → 005 → 013 → 011**, exactly: Home, native learning metadata, proven dead-artifact cleanup, then Sidebar source ownership. **One active owner**; each dependency must satisfy the integration checkpoint before edits. |
| ACTION BOARD | `workforce_suite/workforce_suite/action_board.py`; `workforce_suite/public/action_board/home.html`, `home.js`, `home.css`; `workforce_suite/tests/test_action_board_integration.py` | 003 presentation/read-only adapter behavior. 006/007/008 may propose routes; they cannot independently edit the board. |
| LIST | `workforce_suite/public/js/list_scope.js`; directly related assertions in `workforce_suite/tests/test_report_filters.py` and `workforce_suite/tests/test_hr_navigation.py` (reserve shared test edits) | 004. Existing native per-DocType list extensions are separate domain owners; shared settings composition must be tested. |
| GLOBAL UI | `workforce_suite/public/js/workforce_suite.bundle.js`; `workforce_suite/public/css/workforce_suite.bundle.css`; `workforce_suite/tests/test_hr_navigation.py`, related frontend tests | 010 then 012. Do not remove theme/app-tile functionality as a side effect. |
| MOBILE | `workforce_suite/workforce_suite/page/workforce_mobile_attendance/`; `workforce_suite/workforce_suite/page/workforce_live_locations/`; `workforce_suite/tests/test_mobile_page_assets.py` and directly related browser/static contracts | 000 holds its accepted CSS/test changes separately; 009 owns state clarity only after #53 integration into its base, or an explicit stack on exact #53 head `830c599b19a6074c58f2a9b37977f336d1fe61d4`. No cherry-pick or duplicate theme/test changes. 010 requests any mobile changes through 009; no simultaneous ownership. |
| ATTENDANCE / SHIFT UI | `workforce_suite/workforce_suite/report/workforce_daily_attendance_board/`; `workforce_suite/workforce_suite/report/workforce_shift_coverage/`; `workforce_suite/public/js/workforce_attendance_period.js`, `shift_assignment_tool.js`, `employee_checkin_review.js`; related operator tests | 006. Controllers, mutation services and DocPerms are outside UX scope. `employee_calendar.js` belongs to 008 despite also extending Attendance. |
| PAYROLL / FINANCE UI | `workforce_suite/workforce_suite/report/workforce_payroll_readiness/`; `workforce_suite/workforce_suite/report/workforce_salary_coverage_board/`; `workforce_suite/public/js/payroll_entry.js`, `bulk_salary_structure_assignment.js`, `salary_slip_adjustments.js`, `overtime_bulk_list.js`, `income_tax_slab.js`; `workforce_suite/tests/test_payroll_readiness_operator.py` | 007. Canonical calculations/readiness/security controllers are read-only dependencies. |
| EMPLOYEE / LIFECYCLE / EXPENSE UI | `workforce_suite/public/js/employee_calendar.js`, `employee_separation.js`; UI files under `workforce_suite/workforce_suite/report/employee_data_gaps/` and `workforce_suite/workforce_suite/report/workforce_joiners_and_leavers/`; native expense forms are installed-source dependencies | 008. No new expense page or lifecycle mutation API. Coordinate Calendar changes with 006. |
| ARTIFACT SOURCE | `workforce_suite/workforce_suite/dashboard_chart/`; `workforce_suite/workforce_suite/number_card/`; installer definitions and reference tests share WORKSPACE | 013. Research can run early; deleting/converging installer/source metadata must follow 005, before 011, with checkpoint and lock release. |
| SHARED HOOKS / TRANSLATIONS | `workforce_suite/hooks.py`, `workforce_suite/translations/bn.csv` | No broad owner. Reserve exact edits with coordinator and current lock owner; otherwise CROSS_SCOPE_DEPENDENCY. No permission-hook change in UX tasks. |
| CONTROL DOCUMENTS | The six files created by 001 | 001; subsequent status updates require a named metadata/patch task. Evidence for another task is that task's own ID file. |

Test files shared by two domains receive one owner just like runtime files. Add list-specific tests only inside the later task's explicitly assigned scope.

## Operating rules

- Maximum recommended ACTIVE implementation PRs: **3**. This reduces elapsed work while keeping diffs, shared metadata and review decisions manageable. Independent documentation audits may run additionally.
- Claim: ID, branch, base SHA, exact files, dependency heads, agent, start status. Release only after PR disposition or explicit handoff. Stale claim does not authorize editing another branch.
- A domain needing `install.py`, hooks, translations or another lock reports **CROSS_SCOPE_DEPENDENCY**, writes a proposal, and continues independent work. Do not split the same file among agents by line numbers.
- Never run a full site-backed suite concurrently against `hrms-v16.localhost`. Reserve a site-test window; mutation tests use unique synthetic markers and explicit cleanup. Read-only browser journeys may run only when fixture/test work does not interfere.
- Apply MASTER_PLAN's **INTEGRATION CHECKPOINT** before each wave/substep: predecessors must be independently accepted and integrated into the exact shared base, or genuine stacked code dependencies must name their exact heads. An accepted unmerged PR is not silently present. Prefer integrating #54's six control-plane files; an intentional unmerged exception requires reading its exact head and declaring the exception, without waiving this gate.
- PRs start flat from the latest accepted and integrated shared base. Stack only on a true, explicitly recorded code dependency. No shared-history rebase/force push, merge, close or retarget by agents.
- Review the final diff, not only the summary. Required checks scale to touched files; browser evidence is mandatory for visual/navigation behavior. No schema migration for 001.

## PR and patch protocol

Task ID appears in branch, title, evidence and final response. Each evidence note records objective, dependency IDs/heads, exact base, branch/PR, changed/owned files, native mechanism, tests, browser/device limits, permission/business impact, migration/backup, cleanup, unresolved items and disposition. Final head SHA is recorded in GitHub/final handoff; a document cannot embed its own commit SHA without changing it.

A code patch uses a new `-Pnn` ID and reproduces the defect before editing. Correct in place only when branch ownership and user authorization permit; otherwise create a new focused correction branch. An `-Mnn` task changes metadata only. Do not silently broaden the original objective or rewrite historical evidence.
