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
| C Native overtime bulk | COMPLETE | feat/native-overtime-bulk | feat/native-bulk-leave-control | Pending draft PR | 34 passed | 595 passed, 0 skipped | NO; Python/JS hook only, cache clear/build | — | Browser dialog and live >30 worker UAT later |
| D Bulk-domain closure | NOT_STARTED | — | Previous accepted branch | — | — | — | Unknown | — | — |
| E Action Board | NOT_STARTED | — | Previous accepted branch | — | — | — | Unknown | — | — |
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
