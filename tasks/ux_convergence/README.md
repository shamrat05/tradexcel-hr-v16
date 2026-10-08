# Workforce UX convergence — resume here

Campaign: **TXUX-260930**. We are simplifying operator routes and presentation around native Frappe v16 records. This is a sequence of focused reviews/PRs, not a replacement Desk or business engine.

## Current integrated base and next checkpoint

- **Current shared branch:** `feature/hrms-v16-hr-only`, exactly `9ba1e9c185f2e01964d28b650b48f797927f68da`. Wave 0 → Wave A integration checkpoint **PASSED**; Wave 0 is **COMPLETE / INTEGRATED**.
- TXUX-260930-000: **COMPLETE / ACCEPTED / INTEGRATED**. [PR #53](https://github.com/shamrat05/workforce-suite/pull/53) **MERGED**; accepted head `830c599b19a6074c58f2a9b37977f336d1fe61d4`, normal merge commit `e03ba50cfe436769fddf3083c4ee6811b7876146`.
- TXUX-260930-001: **COMPLETE / ACCEPTED / INTEGRATED**. [PR #54](https://github.com/shamrat05/workforce-suite/pull/54) **MERGED**; accepted head `deff8fa06002518d16960af6b3b567fffc62bf29`, normal merge commit `9ba1e9c185f2e01964d28b650b48f797927f68da`. Its P01 planning and M01 PR-body corrections are accepted.
- **Historical release foundation only:** PR #52 / `1a194240b7312609f0dbcf4195558a54bddcca8c`. Do not start Wave A from that stale SHA.
- Remote CI **did not pass**: #53 run `36636332224` and #54 run `36641903787` failed before any steps (**FAILURE / BLOCKED BEFORE STEPS**). Real device/staff UAT remains unresolved; production approval is not implied.
- M02 synchronizes this status only. After it is reviewed/integrated, verify and record the resulting shared-base SHA, then separately authorize 002 / WORKSPACE, 004 / LIST and 009 / MOBILE as flat branches from **that same exact integrated SHA**. It will include this status commit and descend from `9ba1e9c185f2e01964d28b650b48f797927f68da`; do not assume the SHA stays unchanged after integration.
- 002–015 remain **NOT STARTED**. 013 is research-only until implementation order **002 → 005 → 013 → 011** permits its edits. M02 does not authorize or start product work.

## Where to look

| Question | Document |
| --- | --- |
| Task IDs, dependencies, waves, acceptance gates | [MASTER_PLAN.md](MASTER_PLAN.md) |
| Current inventory, persona jobs, measured journeys and targets | [BASELINE.md](BASELINE.md) |
| Primary and advanced routes; duplicate-entry decisions | [ROUTE_MATRIX.md](ROUTE_MATRIX.md) |
| File locks and concurrent-agent rules | [OWNERSHIP.md](OWNERSHIP.md) |
| This task's evidence and limitations | [TXUX-260930-001.md](TXUX-260930-001.md) |

## Resume procedure

1. Read the root README and AGENTS, then this directory. Historical status counts are not current evidence.
2. Inspect Git/GitHub: accepted shared base, current PR heads/diffs/checks and active owners. Do not assume an unmerged PR is part of the base.
3. Apply MASTER_PLAN's INTEGRATION CHECKPOINT: predecessors must be accepted and integrated into the verified exact shared base, or genuine stacked code dependencies must record their exact heads. Find the first authorized incomplete task; claim its locks before editing. Use a dedicated worktree and task-ID branch.
4. Read that task's evidence/dependencies and exact installed framework source. Preserve any unrelated local work.
5. Make only its assigned change, record evidence, open a focused draft PR and stop. No automatic merge, retarget, force push or next-task start.

## IDs and completion

Primary IDs are `TXUX-260930-NNN`; patches append `-P01`, `-P02`; metadata corrections append `-M01`. Never reuse an ID or redefine its objective. A patch records its parent ID, reproduced defect, files and fresh evidence. A metadata-only task records the exact PR head and creates no code commit unless specifically authorized.

Implementation complete means source/native-mechanism review, permission/business-impact review, required focused/static/browser checks, explicit cleanup, evidence and independent disposition exist. Local acceptance, remote CI, merge and real staff UAT are separate states. A discovered blocker is recorded, not hidden behind “complete”.

## Rules that survive every task

Native records and server permissions remain authoritative; no duplicate ledger, approval database, frontend payroll/legal calculation, inferred statutory value, new custom Page without explicit proof/authorization, permission expansion or real business mutation. Keep the read-only Action Board adapter and native Sidebar foundation. Preserve scope, maker/checker, retries and historical immutability.

Use at most three concurrent implementation owners, one per file lock. After M02 integration and separate authorization, Agent A may own 002 / WORKSPACE (Home convergence), Agent B 004 / LIST (native List View comparison), and Agent C 009 / MOBILE (state clarity). All branch flat from the same newly verified integrated base; no stack between these tasks.

#53's preferred integration condition for 009 is now satisfied. Do not stack on old #53, cherry-pick it, duplicate its theme fix or recreate its asset-test change. #54's six control-plane files are also integrated. Keep the general integration checkpoints for future predecessors: human/coordinator review, integration, exact shared-SHA verification and next-wave authorization; implementation agents never merge. WORKSPACE order remains **002 → 005 → 013 → 011**; 013 may research references without owning/editing Workspace files before its implementation turn.
