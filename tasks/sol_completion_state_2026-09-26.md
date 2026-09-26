# Engineering completion campaign state — 2026-09-26

This file is the resume marker, not a replacement for Git or GitHub. On resume,
verify the actual checkout, ancestry, worktree, remote branches and draft PRs
before continuing. Never recreate an existing branch or PR. All site-backed
work targets `hrms-v16.localhost` on the isolated MariaDB endpoint
`127.0.0.1:3307`; production is outside this campaign.

## Accepted parent

- `MASTER_PARENT_BRANCH`: `feat/bulk-attendance-corrections`
- Parent PR: #28, open/draft/unmerged, based on `fix/converge-shift-bulk-path`
- Accepted attendance focused tests: **10 passed**
- `ACCEPTED_BASELINE_PASS_COUNT`: **585 passed, 0 skipped** (full Tradexcel suite
  rerun on the accepted attendance head on 2026-09-26; 64 warnings)
- Acceptance: the source-backed native Attendance Request draft and independent
  approval path, Employee scope checks, maker/checker, consumed-payroll guards,
  Attendance Period hash staleness and explicit synthetic cleanup were reviewed.
  No attendance correction PR was required. Browser UAT and large-batch latency
  remain release evidence gaps, not reasons to rewrite the accepted slice.

## Phase ledger

Statuses are `NOT_STARTED`, `IN_PROGRESS`, `COMPLETE`, or `BLOCKED`.
An already complete phase can be recorded as `COMPLETE (already complete)` and
does not get an empty PR. Final commit SHAs belong to Git/GitHub.

| Phase | Status | Branch | Parent branch | PR | Focused tests | Full suite | Migration | Backup prefix | Remaining blocker |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 Attendance acceptance | COMPLETE | feat/bulk-attendance-corrections | fix/converge-shift-bulk-path | #28 | 10 passed | 585 passed, 0 skipped | Previous slice | See `BACKUPS.md` | Browser/volume UAT later |
| 0-B Repository/runtime audit | COMPLETE | refactor/runtime-portability | feat/bulk-attendance-corrections | — | Source inventory and static scans | Baseline above | NO | — | Threat-oriented adversarial verification belongs to H |
| A Portability/legacy hazards | COMPLETE | refactor/runtime-portability | feat/bulk-attendance-corrections | #29 open/draft/unmerged | 35 passed | 593 passed, 0 skipped | YES, standard migrate and cache clear | 20260926_012737-hrms-v16_localhost- | Fresh neutral-site install belongs to K |
| B Native leave bulk | COMPLETE | feat/native-bulk-leave-control | refactor/runtime-portability | #30 open/draft/unmerged | 40 passed, plus final native integration 1 passed | 594 passed, 0 skipped | YES, standard migrate and cache clear | 20260926_014339-hrms-v16_localhost- | Real entitlement configuration and browser/volume UAT later |
| C Native overtime bulk | COMPLETE | feat/native-overtime-bulk | feat/native-bulk-leave-control | #31 open/draft/unmerged | 34 passed, plus cancellation regression | 595 passed, 0 skipped | NO; Python/JS hook only, cache clear/build | — | Browser dialog and live >30 worker UAT later |
| D Bulk-domain closure | COMPLETE | refactor/native-bulk-closure | feat/native-overtime-bulk | #32 open/draft/unmerged | 28 passed; 12 report/persona and 4 attendance/salary recovery passed | 597 passed, 0 skipped | YES, standard migrate/cache clear | 20260926_070248-hrms-v16_localhost-; synthetic cleanup backup 20260926_092011-hrms-v16_localhost- | Browser UAT and wider import delegation remain gated |
| D follow-up Older report boundaries | COMPLETE | fix/legacy-report-boundaries | refactor/native-bulk-closure | #33 open/draft/unmerged | 37 focused + 22 post-migration + 36 restart checks passed | 602 passed, 0 skipped | YES, standard migrate/cache clear | 20260926_101050-hrms-v16_localhost- | Browser/export UAT later; synthetic cleanup zero |
| D follow-up Employee-linked scope | COMPLETE | fix/employee-linked-scope | fix/legacy-report-boundaries | — | 23 passed; Request/Checkin/SSA scope regressions | 604 passed, 0 skipped | YES, standard migrate/cache clear | 20260926_173459-hrms-v16_localhost- | Synthetic cleanup zero; draft PR creation pending |
| E Action Board | NOT_STARTED | — | Previous accepted branch | — | — | — | Unknown | — | Employee-linked scope prerequisite accepted; ready to start |
| F Native navigation | NOT_STARTED | — | Previous accepted branch | — | — | — | Unknown | — | — |
| G Operator usability/localization | NOT_STARTED | — | Previous accepted branch | — | — | — | Unknown | — | — |
| H Security/privacy | NOT_STARTED | — | Previous accepted branch | — | — | — | Unknown | — | — |
| I Accounting/reconciliation | NOT_STARTED | — | Previous accepted branch | — | — | — | Unknown | — | — |
| J Measured performance/async | NOT_STARTED | — | Previous accepted branch | — | — | — | Unknown | — | — |
| K Release contract | NOT_STARTED | — | Previous accepted branch | — | — | — | Unknown | — | — |

## Initial audit facts to preserve on resume

- The accepted head was clean and descended from `2ebf51b223090a891b42976ea2e036e996ff37fd`.
- Installed apps: Frappe 16.34.0, ERPNext 16.35.0, HRMS 16.19.0,
  Tradexcel HR 0.1.0. The shell defaults to Node 20; the installed Node
  24.15.0 binary is under `/home/sanchita/.nvm/versions/node/v24.15.0/bin`.
- `git ls-files` found 390 tracked files: 222 Python, 27 JavaScript, 63 JSON,
  60 Markdown, plus other source/configuration files. A source inventory and
  sensitive-call scan are part of phase 0-B.
- The bench-local `sync/` directory was absent in this v16 bench. The app
  contains the biometric worker and payroll runtime under version control.
- Read-only bridge checkout: `/mnt/c/Users/Sanchita/Desktop/Projects/SenseFace-HRMS-Bridge`,
  clean `main` at `2cb9c50e2af2c0b995cd3e7d75185b98487d58e2`; no bridge
  files or secrets were copied. Its current source implements the device
  configure endpoint, while the app's older bridge contract says it is absent.
- Codebase-memory and Serena tools were not exposed in this session; `rg`,
  installed source and Frappe v16 Context7 were used for discovery.

## Follow-up audit targets from D

- Frappe background-job deadlock retry omits the original `user` argument.
  Overtime preparation already fails closed on lost identity. Audit the other
  native/app queued mutation entry points before broadening import access.
- `Daily Attendance Summary` and `Workforce Anomaly Radar` still contain
  Company-filtered SQL without the report Employee-scope helper. The latter
  also loads salary values while allowing the attendance role. Reproduce and
  resolve these boundaries before using either as an Action Board data source.
- `Tradexcel Payroll Register` still reads Salary Slips with Company-only SQL
  and no cancelled-state boundary. Reproduce record-scope/state behavior before
  using that older register for financial drill-through.
- The Shift Assignment Tool's custom action restriction still keys on presence
  of a Tradexcel role; mixed native/custom-role compatibility requires the
  dedicated regression identified by the master campaign.
- Pagination hypothesis checked in the D report follow-up: installed native
  `get_list` returns all 21 synthetic slips without an explicit limit. No
  default-20 truncation defect was reproduced; generic API docs were stale.
