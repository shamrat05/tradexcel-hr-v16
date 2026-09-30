# Tradexcel UX convergence — resume here

Campaign: **TXUX-260930**. We are simplifying operator routes and presentation around native Frappe v16 records. This is a sequence of focused reviews/PRs, not a replacement Desk or business engine.

## Current integrated base and next checkpoint

- Shared branch: `feature/hrms-v16-hr-only`, exactly `75b37a6fbc61cae0877af46db99e929db6c44007`. **Wave A COMPLETE / independently ACCEPTED / INTEGRATED**; all three accepted heads remain ancestors.
- Wave 0 tasks 000/001 and M02 are integrated (#53/#54/#55). Historical foundation `1a194240b7312609f0dbcf4195558a54bddcca8c` and Wave-0 checkpoint `9ba1e9c185f2e01964d28b650b48f797927f68da` are historical evidence, not current branching instructions.

| Task | PR / state | Accepted head | Normal merge commit |
| --- | --- | --- | --- |
| 002 | #57 MERGED | `91a322c2e00382d1497824699ef127eb12c9617d` | `b1c61fd39c4e23817a0c45141399fb31ef1d503a` |
| 004 | #56 MERGED | `e26cd0fd60ad50db7943f57483e35ed0c0d26f27` | `a214a594f5734994378978560b5b6d731bb34e7c` |
| 009 | #58 MERGED | `b2ab10d33b886e0ebfd2456eb739f946a89af393` | `75b37a6fbc61cae0877af46db99e929db6c44007` |

003 / ACTION BOARD and 005 / WORKSPACE are authorized Wave-B candidates, independently from this exact verified SHA. Current implementation work: [003 / PR #59](https://github.com/shamrat05/tradexcel-hr-v16/pull/59) and [005 / PR #60](https://github.com/shamrat05/tradexcel-hr-v16/pull/60), both OPEN / DRAFT / UNMERGED, awaiting independent review. M03 is administrative synchronization, not a code prerequisite. They remain incomplete pending their own implementation and independent review. Do not stack these branches on each other.

013 remains research-only until 005 is accepted **and integrated**; 011 follows 013. WORKSPACE order remains **002 → 005 → 013 → 011**.

Remote CI did not pass: #57 `36647318651`, #56 `36647320376`, #58 P01 `36675180719` failed before steps (**FAILURE / BLOCKED BEFORE STEPS**). Backed-up Home Workspace convergence/deployed-browser parity, real device/staff UAT and operational release gates remain outstanding. No production approval is implied.

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

Use at most three concurrent implementation owners, one per file lock. Wave B has independent owners for 003 / ACTION BOARD and 005 / WORKSPACE, plus documentation-only M03. Use the same verified integrated base; do not stack them. Maximum recommended active implementation owners remains three.

#53's preferred integration condition for 009 is now satisfied. Do not stack on old #53, cherry-pick it, duplicate its theme fix or recreate its asset-test change. #54's six control-plane files are also integrated. Keep the general integration checkpoints for future predecessors: human/coordinator review, integration, exact shared-SHA verification and next-wave authorization; implementation agents never merge. WORKSPACE order remains **002 → 005 → 013 → 011**; 013 may research references without owning/editing Workspace files before its implementation turn.
