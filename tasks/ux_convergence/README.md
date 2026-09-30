# Tradexcel UX convergence — resume here

Campaign: **TXUX-260930**. We are simplifying operator routes and presentation around native Frappe v16 records. This is a sequence of focused reviews/PRs, not a replacement Desk or business engine.

## Current integrated base and release checkpoint

- **Current shared branch:** `feature/hrms-v16-hr-only` at `bb48574050214e364c73a15e38dce6128bea2f80`. Fetch and verify before new work; never branch from historical campaign snapshots.
- 000–011 and 013 source implementations/evidence are integrated. 012 is an independently accepted containment audit/test: no speculative runtime CSS change was justified. 014 evidence is integrated via #71, but **validation is PARTIAL / release acceptance BLOCKED**.
- [Final audit](TXUX-260930-015.md) records full accepted-head/merge ancestry, measured evidence and deployment/rollback checklist. The 015 audit is draft work, not production approval.
- #67, #69, #68 integrated normally in that order; FINAL_UX_BASE_SHA `09bfca490a04d5e185cfd183bd85ce8d39fe442b`. #70 audit merge `4a9b1d5ff3fc0d5ae23fa99786764f4dc50f87a2`; #71 partial evidence merge `bb48574050214e364c73a15e38dce6128bea2f80`.
- **Next:** independent final-audit review and separately authorized backed-up staging/disposable validation, then deployed B01–B15, device/staff UAT and release decision. No next implementation wave or speculative redesign is authorized.
- Served staging still has old Home/Action Board/Icon metadata and lacks native guidance. Public Sidebar matches 132 expected routes, but unknown public edits require fresh backed-up comparison; personal Administrator Sidebar is absent. Eleven retired artifacts and historical column remain; deletion is a separate guarded operation.
- Remote checks have zero job steps: **FAILURE / BLOCKED BEFORE STEPS**, not PASS. Physical device/staff UAT, configuration/parallel-payroll and recovery/cutover approval remain unresolved.
- #61 remains OPEN/DRAFT as a historical Wave-A snapshot. Do not merge its stale current-base claims; coordinator disposition requires separate authorization.
- Historical foundation `1a194240b7312609f0dbcf4195558a54bddcca8c`, Wave-0 `9ba1e9c185f2e01964d28b650b48f797927f68da` and original Wave-A/B bases remain historical evidence only.

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

Use at most three concurrent implementation owners, one per file lock. Historical Wave-A tasks are already integrated; no additional implementation task is authorized by this status refresh. Preserve independent branches and exact integration checkpoints for separately authorized future work.

#53's preferred integration condition for 009 is now satisfied. Do not stack on old #53, cherry-pick it, duplicate its theme fix or recreate its asset-test change. #54's six control-plane files are also integrated. Keep the general integration checkpoints for future predecessors: human/coordinator review, integration, exact shared-SHA verification and next-wave authorization; implementation agents never merge. WORKSPACE order remains **002 → 005 → 013 → 011** and has been respected. Source retirement is integrated; physical artifact deletion remains separately guarded.
