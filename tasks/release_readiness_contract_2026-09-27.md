# Release readiness contract — 2026-09-27

Parent: PR #41, `perf/measured-hrms-pass`,
`4415637` (full SHA is in Git). Branch `test/release-readiness-contract`.
This is release engineering, not production approval.

## Source and supported extension contract

Frappe 16.34.0, ERPNext 16.35.0, HRMS 16.19.0, app 0.1.0,
Python 3.14.4, Node 24.15.0. Declared framework range remains >=16,<17.
No framework core modification or v17 upgrade. Versioned runtime, hooks,
standard reports, Workspace/sidebar, Custom DocPerms, custom fields, native tool
mixins and assets are the source of truth. v16 `sync/` is absent. Historical
migration importers/quarantine are not deployment dependencies.

Read-only separate bridge checkout remains clean `main` at
`2cb9c50e2af2c0b995cd3e7d75185b98487d58e2`; no source/secrets copied and no
physical device contacted. See `docs/senseface_bridge_contract.md`.

`scripts/check_source.py` parses Python/JSON and checks JS with Node.
`scripts/release_smoke.py` uses installed metadata/controllers and asserts native
mixins, 13 standard Script Reports, no query-report override, Workspace and
explicit pay-basis field. Its neutral mode rejects manufactured business data.
`scripts/run_release_integration.sh` runs the full synthetic native contract from
the isolated v16 bench. No test framework creates a second business ledger.

## Fresh install and restore actually executed

Created **sol-neutral-20260927.localhost** using a separate database/user on the
isolated MariaDB 3307 socket. Installed Frappe → ERPNext → HRMS → Tradexcel from
current local versioned app sources, with a random disposable Administrator
password never exported. Neutral smoke passed: no Company, Employee, Branch,
Salary Structure, SSA, payroll, leave entitlement or legal/flexible policy created.
All 13 reports and native extensions converge from source. This proves application
source-install neutrality on this bench; it does not prove a new production OS
provision or an air-gapped dependency installation. Generic metadata/components
and exit-task templates are expected, not personal salary authority.

Fresh staging backup **20260927_062331-hrms-v16_localhost-** verified by gzip/tar,
size and SHA-256 in BACKUPS.md. Standard staging migrate/cache clear and installed
smoke passed. No direct metadata SQL or real business-data update.

Created a second separate **sol-restore-20260927.localhost** database/site, restored
that database and both file archives with standard bench restore, kept scheduler
disabled, then standard migrate/cache clear and installed smoke passed. Staging
was never overwritten. Secrets/encryption-key recovery and production off-box
host/network outage remain a production recovery exercise; this rehearsal did
not decrypt device secrets or invoke integrations. Disposable sites/databases
are removed after aggregate parity/cleanup verification.

## Synthetic release E2E evidence

The full suite is an executable cross-domain contract, not a claim that every
scenario lives in a single enormous fixture:

- recruitment/direct hire and readiness: `test_joiner_readiness_integration.py`;
- Monthly/Daily authority and independent approval: bulk SSA, mixed-pay and
  lifecycle integration;
- shift/leave/OT: installed native bulk integrations, selected-ID attacks,
  maker/checker, actual Additional Salary source behavior and retry;
- Attendance Request → Attendance, stale finalization and consumed history:
  `test_bulk_attendance_corrections_integration.py`;
- native draft payroll → Salary Slips → partial submission/retry → accrual →
  bank/cash payment/reconciliation: `test_payroll_finalization_integration.py`;
- corrections/arrears, transfer, separation/F&F/native benefits, access shutdown,
  wage/benefit/maternity/working-time readiness: existing named integrations;
- all 15 personas, linked/unlinked ESS, Company/Branch/Department, combined roles,
  financial field privacy, direct APIs and native shares: persona/security suites;
- actual 31-row isolated RQ worker plus changed-scope rejection: live queue test.

Synthetic policy values are explicitly test fixtures, never real legal advice.
Real-company legal/configuration absence remains fail-closed. Full suite and
cleanup results are recorded below after final execution.

## Truthful CI and acceptance limits

New `Source contract` GitHub workflow pins official action commit SHAs, Python
3.14, Node 24.15.0 and pytest 8.4.2. It runs Python/JSON/JS checks, compileall,
11 database-independent tests and diff-check. It does **not** claim Frappe/site
integration. Full integration remains an explicit local release gate with the
bench command above; no secret-dependent fake integration workflow is included.

Physical Android/terminal UAT is NOT executed. Current synthetic browser smoke
is narrower than actual staff/full export/print UAT. See release UAT checklist,
Business Configuration Gate, roadmap and six runbooks. No production cutover,
real staff provisioning or legal/rate invention occurred.

## Rehearsal results

Neutral install and restore smoke passed. Restored aggregate counts match the
source for ten native business-record categories. Both disposable sites/databases
and their archived site copies were removed; the verified source backup remains.
Release browser repeat passed all six persona/viewport combinations with no rail,
overflow or page errors. HR Bangla report-selection/preview/draft/list path passed;
zero Attendance mutation. Browser synthetic users/requests/permissions cleaned.

The CI subset also passed in a separate temporary Python environment without
Frappe installed: **11 passed**. Site-focused release contracts: **12 passed**.
No app JS changed in this phase, so no redundant asset build; Node 24 checks
cover all tracked JS. Full final suite/cleanup and GitHub status follow below.

A final runtime-source scan found no hardcoded `350`, TCL Factory/company names,
absolute migration paths, custom rail, or `query_report.run` override in app
Python/JS/CSS outside tests. Historical docs and explicitly synthetic fixtures
retain contextual names. No critical implementation exists only in bench sync.

Final source inventory: 52 whitelisted functions/methods; guest entry points:
[]. There are no app `allow_guest=True` entry points. Actual document/service
permissions and current actor validation remain mandatory after authentication;
whitelisting alone is never treated as authorization. No new API was added here.

## Explicit remaining capability boundary

Installed HRMS 16.19 Payroll Entry has no
`make_employer_contribution_jv_entry` accrual path. Existing capability detection
fails closed for active PF/Progoti participation. Step 16 is therefore **PARTIAL**,
not disguised as configuration-only completion: enabling this money needs a
supported native capability and integration proof after legal applicability is
reviewed. A parallel custom Journal Entry/benefit ledger would violate the
architecture and was not built. Annual-leave statutory parity also remains an
explicit reviewed rule/configuration decision, not a guessed automatic accrual.
Other operations do not depend on enabling those unconfigured benefit schemes.

## Installed framework source pins

| App | SHA | Worktree |
| --- | --- | --- |
| frappe | `c1f1e8ec3708750d7254f7f99d869ffb9886f19f` | clean |
| erpnext | `12cd563fb9a79731f75ae2a45b1446a0a2dd9e74` | dirty (inspect before release) |
| hrms | `7e0fba4bf11a63ac7b21a717610e235310815c1a` | clean |

## External dependency source blocker — preserved, not overwritten

Framework source audit found a pre-existing ERPNext `banking/yarn.lock` delta
(last filesystem modification 2026-09-22, before this campaign). It replaces
`follow-redirects` 1.15.11 with 1.16.0 and `proxy-from-env` 1.1.0 with 2.1.0.
Frappe and HRMS worktrees are clean. No Python/controller core delta exists.
This is outside the authorized app checkout and was not reset, committed or
modified. Application neutral install/restore proof remains valid, but a fully
pinned whole-bench frontend deployment is **not yet proven**. Review/pin or
discard that vendor dependency change in its proper repository, then perform
a clean integrated target-host build before release. Phase K records this
external-source blocker instead of pretending every release gate is complete.

## Final validation

**629 passed, 0 skipped**, 97 warnings, 504.97 seconds. Site-focused: 12 passed.
Isolated CI subset: 11 passed. Compileall, 61 tracked JSON files, 29 JS syntax
checks under Node 24, shell syntax and diff-check passed. No JS asset change in
this PR. Synthetic markers zero; final read-only staging audit exactly matches
all pre-release aggregate counts/states. No unreviewed business cleanup.

Phase K is marked BLOCKED solely for unresolved whole-bench external dependency
pinning; the honest release contract is committed as a draft PR. Device/staff/
business/production gates remain separately classified, not engineering passes.
