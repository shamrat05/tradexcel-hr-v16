# Tradexcel UX convergence — resume here

Campaign: **TXUX-260930**. We are simplifying operator routes and presentation around native Frappe v16 records. This is a sequence of focused reviews/PRs, not a replacement Desk or business engine.

## Accepted foundation and current work

- PR #52 is merged. Shared base: `feature/hrms-v16-hr-only` at `1a194240b7312609f0dbcf4195558a54bddcca8c`.
- TXUX-260930-000 / [PR #53](https://github.com/shamrat05/tradexcel-hr-v16/pull/53): implementation accepted; OPEN / DRAFT / UNMERGED, reviewed head `830c599b19a6074c58f2a9b37977f336d1fe61d4`. Remote source-and-pure-tests check failed before steps; it is not a CI pass.
- TXUX-260930-000-M01 was the separately authorized PR-body correction. It is not runtime work or a dependency commit.
- TXUX-260930-001: [PR #54](https://github.com/shamrat05/tradexcel-hr-v16/pull/54), OPEN / DRAFT / UNMERGED; this documentation/audit branch, `ux/TXUX-260930-001-control-plane`, directly from the shared base. Review the PR for this exact head branch; GitHub is authoritative for its number/head/status.
- 002–015 are reserved, NOT STARTED. No implementation task is authorized by completion of this audit alone.
- Real device/staff UAT is incomplete. Production approval is not implied.

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
3. Find the first authorized incomplete task in MASTER_PLAN; claim its locks before editing. Use a dedicated worktree and task-ID branch.
4. Read that task's evidence/dependencies and exact installed framework source. Preserve any unrelated local work.
5. Make only its assigned change, record evidence, open a focused draft PR and stop. No automatic merge, retarget, force push or next-task start.

## IDs and completion

Primary IDs are `TXUX-260930-NNN`; patches append `-P01`, `-P02`; metadata corrections append `-M01`. Never reuse an ID or redefine its objective. A patch records its parent ID, reproduced defect, files and fresh evidence. A metadata-only task records the exact PR head and creates no code commit unless specifically authorized.

Implementation complete means source/native-mechanism review, permission/business-impact review, required focused/static/browser checks, explicit cleanup, evidence and independent disposition exist. Local acceptance, remote CI, merge and real staff UAT are separate states. A discovered blocker is recorded, not hidden behind “complete”.

## Rules that survive every task

Native records and server permissions remain authoritative; no duplicate ledger, approval database, frontend payroll/legal calculation, inferred statutory value, new custom Page without explicit proof/authorization, permission expansion or real business mutation. Keep the read-only Action Board adapter and native Sidebar foundation. Preserve scope, maker/checker, retries and historical immutability.

Use at most three concurrent implementation owners, one per file lock. Documentation audits can run separately. The next implementation candidates after review are 002, 004 and 009; 013 can perform reference research in parallel, but its installer edits must wait for the Workspace owner.
