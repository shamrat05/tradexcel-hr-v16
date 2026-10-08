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
- `ACCEPTED_BASELINE_PASS_COUNT`: **585 passed, 0 skipped** (full Workforce suite
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
| D follow-up Employee-linked scope | COMPLETE | fix/employee-linked-scope | fix/legacy-report-boundaries | #34 open/draft/unmerged | 23 passed; Request/Checkin/SSA scope regressions | 604 passed, 0 skipped | YES, standard migrate/cache clear | 20260926_173459-hrms-v16_localhost- | Synthetic cleanup zero; browser UAT later |
| E Action Board | COMPLETE | feat/action-board | fix/employee-linked-scope | #35 open/draft/unmerged | 25 passed; native block/persona/source checks | 607 passed, 0 skipped | YES, standard migrate/cache clear | 20260926_180505-hrms-v16_localhost-; final script 20260926_181032-hrms-v16_localhost- | Synthetic cleanup zero; browser UAT later |
| F Native navigation | COMPLETE | refactor/native-workspace-ia | feat/action-board | #36 open/draft/unmerged | 25 passed; 3-persona desktop/phone browser smoke passed | 609 passed, 0 skipped | YES, standard migrate/cache clear | 20260926_183119-, 183319-, 231100-, 233132-hrms-v16_localhost-; full filenames in BACKUPS.md | Wider browser UAT later; cleanup zero |
| F follow-up Bulk job privacy | COMPLETE | fix/bulk-job-privacy | refactor/native-workspace-ia | #37 open/draft/unmerged | 8 passed; live cross-company browser delivery proof | 613 passed, 0 skipped | NO; Python hooks and runtime wrappers only | — | Cleanup zero; internal realtime buffer is version-tested; mixed-role Shift compatibility stays in H |
| G Operator usability/localization | COMPLETE | feat/operator-usability | fix/bulk-job-privacy | #38 open/draft/unmerged | 18 passed; Bangla/keyboard/phone-width and native correction-draft browser flow passed | 616 passed, 0 skipped | YES, standard migrate/cache clear | 20260927_001652-hrms-v16_localhost- | Cleanup zero; wider staff/browser/device UAT later |
| H Security/privacy | COMPLETE | fix/security-privacy-hardening | feat/operator-usability | #39 open/draft/unmerged | 9 passed | 621 passed, 0 skipped | YES, standard migrate/cache clear | 20260927_052730-hrms-v16_localhost- | Cleanup zero; native explicit shares/staff provisioning and wider export/browser UAT remain configuration/evidence gates |
| I Accounting/reconciliation | COMPLETE | feat/accounting-reconciliation | fix/security-privacy-hardening | #40 open/draft/unmerged | 34 native/payment + 74 broader focused passed | 627 passed, 0 skipped | NO | — | Cleanup zero; real Finance configuration/settlement review remains |
| J Measured performance/async | COMPLETE | perf/measured-hrms-pass | feat/accounting-reconciliation | #41 open/draft/unmerged | 14 focused + 1 parity + 1 live worker passed | 629 passed, 0 skipped | NO | — | Cleanup zero; real configured-company concurrency/payroll-volume UAT remains |
| K Release contract | BLOCKED | test/release-readiness-contract | perf/measured-hrms-pass | #42 open/draft/unmerged | 12 site-focused + 11 isolated pure; neutral install/restore and 3-persona browser passed | 629 passed, 0 skipped | YES, standard migrate/cache clear | 20260927_062331-hrms-v16_localhost- | App release evidence complete; whole-bench pinning blocked by pre-existing ERPNext banking/yarn.lock drift; GitHub Actions billing prevented job startup. Real business/device gates remain |

## Initial audit facts to preserve on resume

- The accepted head was clean and descended from `2ebf51b223090a891b42976ea2e036e996ff37fd`.
- Installed apps: Frappe 16.34.0, ERPNext 16.35.0, HRMS 16.19.0,
  Workforce Suite 0.1.0. The shell defaults to Node 20; the installed Node
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
- **Closed by PR #33:** the D audit found `Daily Attendance Summary` and `Workforce Anomaly Radar` contained
  Company-filtered SQL without the report Employee-scope helper. The latter
  also loads salary values while allowing the attendance role. Reproduce and
  resolve these boundaries before using either as an Action Board data source.
- **Closed by PR #33:** the D audit found `Workforce Payroll Register` read Salary Slips with Company-only SQL
  and no cancelled-state boundary. Reproduce record-scope/state behavior before
  using that older register for financial drill-through.
- The Shift Assignment Tool's custom action restriction still keys on presence
  of a Workforce role; mixed native/custom-role compatibility requires the
  dedicated regression identified by the master campaign.
- Pagination hypothesis checked in the D report follow-up: installed native
  `get_list` returns all 21 synthetic slips without an explicit limit. No
  default-20 truncation defect was reproduced; generic API docs were stale.

## E handoff observations for later phases

- F: installed `boot.get_sidebar_items` and `WorkspaceSidebar` already filter
  native links using `DeskViews.is_item_allowed`. A source-backed sidebar named
  for the app Module replaces automatic module enumeration and can link the
  canonical `workforce-suite` home. Inspect native route resolution before removing
  the existing rail; preserve the separate theme and app-tile IIFEs.
- G: distinguish per-Employee and per-payroll-entry cards with a readable native
  identity/period label during the usability pass. API items already retain
  Employee/form routes; do not add money or duplicate state for that label.
- K: system Python did not have Playwright; actual browser execution has not
  been claimed. Assess available browser tooling separately from backend tests.

## Security follow-up discovered during F validation

Installed `frappe.realtime.publish_realtime` chooses room `all` when supplied a
DocType without a document name/user/task. Native Shift and Leave bulk completion
calls and the app SSA draft completion do exactly this. A no-network test of the
installed publisher captured `all` with synthetic payload. Before broader UX
work, reproduce recipient behavior and scope completion events using supported
transaction callbacks/native per-user rooms; do not patch framework code or copy
native mutation loops. Also address the previously recorded queued-retry identity
and mixed native/custom Shift action checks in a bounded current-stack follow-up.

## Release evidence superseding earlier handoff cautions — 2026-09-27

PR #37 closed queued retry identity/public completion delivery. PR #39 closed
the mixed native/custom Shift action caveat with actual scope tamper regression.
PR #38 and the release repeat executed Chromium through an isolated temporary
Playwright environment: three synthetic personas, desktop/phone widths and
Bangla correction-draft flow. Earlier notes saying browser tooling was unavailable
are historical; wider real staff/device UAT still remains.

## Final handoff / safe resume

Final local suite: **629 passed, 0 skipped**, 97 warnings, 504.97 seconds.
All audited staging business/configuration aggregates match the pre-release
read-only snapshot. Synthetic marker counts and disposable databases/sites are
zero. Final branch: `test/release-readiness-contract`; its Git/GitHub head and
CI run are authoritative, not a self-referential SHA in this file.

On resume, reuse this branch/PR. Do not rerun migrations or recreate disposable
sites just to repeat evidence. Resolve the external ERPNext lockfile review in
its proper source context before claiming whole-bench deployment reproducibility.
Do not reset the pre-existing change or touch framework source without authority.
Step 16 retains the supported-native employer-contribution capability blocker;
no custom accounting bypass is authorized. See current roadmap and business gate.

GitHub PR #42 is open/draft/unmerged, base `perf/measured-hrms-pass`.
Source-contract run 36283160723 never started a runner job (zero steps): GitHub
reported failed account payments or a spending-limit requirement. This is
**REMOTE CI BLOCKED**, not a test failure or a CI pass. The same source checks
and 11 pure tests passed locally in an isolated environment. No billing,
repository security setting or workflow protection was changed to bypass it.

## Post-Sol correction resume point

Current branch: `fix/release-lineage-security-closure`, parent #42
`test/release-readiness-contract`. Status COMPLETE: draft correction PR #44 is open on #42; final validation
and cleanup passed. Phase K remains BLOCKED by external release gates. Reuse this branch; do not recreate
#43 or repeat the completed staging metadata migration. Backup prefix:
`20260927_133159-hrms-v16_localhost-` (verified archives/config; BACKUPS.md).

Corrected topology: #2 → #43 (existing payroll P0 seven commits) → #4 … #42 →
this correction. #1 is independent docs; #3 diverged and is superseded by a
current-source semantic port, not a blind cherry-pick. Phase K remains BLOCKED.
Both #42 Actions runs (36283160723 and 36283208413) failed before any steps;
GitHub's annotation confirms account billing/spending limits. No remote CI pass.

Post-Sol correction final local validation: **653 passed, 0 skipped** (103 warnings),
60 focused + 4 final release regressions; source/compile/build/smoke passed.
Final narrow permission migration used verified backup
`20260927_134711-hrms-v16_localhost-`. Synthetic and disposable-site cleanup zero.
Draft correction PR #44 is published, open and unmerged;
Phase K remains BLOCKED by external CI/source/business/device gates.

| Post-Sol release correction | COMPLETE | fix/release-lineage-security-closure | test/release-readiness-contract | #44 open/draft/unmerged | 60 focused + 4 final release regressions | 653 passed, 0 skipped | YES, standard migrate/cache | 20260927_133159- and 20260927_134711-hrms-v16_localhost- | Phase K external gates remain BLOCKED |
