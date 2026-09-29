# UX campaign master plan

TASK-ID: TXUX-260930-001. Current integrated Wave-A shared base: `feature/hrms-v16-hr-only` / `9ba1e9c185f2e01964d28b650b48f797927f68da`. Historical audit/release foundation: `1a194240b7312609f0dbcf4195558a54bddcca8c` (PR #52).

## Current coordination state — M02

Wave 0 is **COMPLETE / INTEGRATED**. #53 is MERGED at `e03ba50cfe436769fddf3083c4ee6811b7876146`, preserving accepted head `830c599b19a6074c58f2a9b37977f336d1fe61d4`. #54 is MERGED at `9ba1e9c185f2e01964d28b650b48f797927f68da`, preserving accepted head `deff8fa06002518d16960af6b3b567fffc62bf29`. Tasks 000/001 are COMPLETE / ACCEPTED / INTEGRATED. Both remote runs (36636332224 / 36641903787) failed before steps, not CI passes.

After M02 is reviewed/integrated, the coordinator verifies its resulting exact shared-base SHA (a descendant of `9ba1e9c185f2e01964d28b650b48f797927f68da`) and may separately authorize exactly **002 / WORKSPACE, 004 / LIST, 009 / MOBILE**. All three use independent flat branches from the **same** resulting SHA, not the historical foundation and not each other's branches. No task is started here; 013 remains research-only until 002 → 005 → 013 → 011 permits implementation. Preserve native Workspace/Sidebar/Awesomebar, read-only Action Board, permissions and maker/checker for 002; compare installed native List features before removal for 004; inherit #53 unchanged for 009. No new dashboard architecture or decorative charts.

## Immutable design contract

Native Employee, Checkin, Attendance Request/Attendance, Leave, Shift, SSA/Salary Structure, payroll and accounting documents remain the authorities. No second ledger, custom approval/task-state database, UI authorization or frontend payroll/legal computation. Existing server scope, maker/checker, idempotency and historical safeguards survive every UI change. No guessed legal rates or company wage defaults. No real business mutation, production change, core modification or new Page without an explicitly approved necessity demonstration.

Decision order: installed native behavior → native metadata → supported hook/standard extension → small app adapter → explicitly authorized custom UI only if the preceding options fail. Native Workspace Sidebar is the foundation. The existing Action Board remains a read-only adapter over existing inspectors/reports; presentation work must not copy their calculations.

## Permanent registry

IDs `TXUX-260930-000` through `015` are reserved with the meanings below. Primary/patch/metadata IDs are never reused. Abbreviated dependencies in the table always mean the full campaign ID. “Shared” means a flat branch from the latest independently accepted and integrated shared base, after the checkpoint below. “Dependency” means stack only if it uses actual unmerged code, record the exact dependency head, and avoid a giant linear stack.

| ID / name / type | Purpose | Dependencies / base strategy | Ownership / primary agent | Parallel-safe with / blocks | Acceptance gate / expected PR scope / rollback |
| --- | --- | --- | --- | --- | --- |
| 000 Native page dark theme / implementation | Correct two existing field-page card surfaces | Historical foundation; #53 now integrated in Shared | Existing GLOBAL UI/MOBILE intersection; independent reviewer | 001 audit; blocks final 009/010 theme integration | COMPLETE / ACCEPTED / INTEGRATED; #53 MERGED, remote CI unresolved. Scoped native tokens; revert CSS/test commit only. |
| 001 Control plane / audit | Permanent IDs, inventory, measured baseline, routes, locks | Historical foundation; #54 now integrated in Shared | Six authorized documentation files; independent reviewer | 000 and nonconflicting research; enables 002/004/009/013 research | COMPLETE / ACCEPTED / INTEGRATED; #54 MERGED. Source/GitHub audit, measured journeys with limitations, scope/link checks; docs-only PR; revert docs. |
| 002 Home convergence / implementation | One obvious primary entry for ordinary work; reduce redundant Home choices | 001; Shared | WORKSPACE; Luna | 004, 009; 013 research only; blocks 003/005 and installer cleanup | Persona Home parity and native target visibility, no lost needed route; Home metadata/tests only; restore prior metadata via standard convergence. |
| 003 Compact Action Board / implementation | Exception-first presentation and clear recovery, preserve adapters | 001, 002; Shared unless Home code is required | ACTION BOARD; Luna + independent review | 004/005/009/013 subject to locks; blocks recovery integration and 014 | Preserve source/scope; compact categories/severity, empty/error honesty; reproduce modal leakage. Adapter/UI/tests only; revert adapter/presentation. |
| 004 Native List View / cleanup | Compare date controls, native quick/saved filters and scoped Link UX | 001; Shared | LIST; Gemini | 002, 009, 003, domain tasks that do not touch list settings; blocks 006/007/008 acceptance | Desktop + phone evidence; preserve negative scope tests and datetime context; one list family; revert customization. |
| 005 Native learnability / implementation | Guided first use through native onboarding/form-tour/help mechanisms | 001, 002; Shared | WORKSPACE metadata (reserve any new onboarding files); Gemini | 003, 004, 009; serial with 013 installer edits; blocks 011 acceptance | Native completion/role filtering, no new task ledger or manufactured config; metadata/guidance/tests; remove guidance metadata. |
| 006 Attendance/Shift recovery / implementation | Explain evidence, draft/submit state and canonical next step | 001, 003, 004; integrate 002 route decisions | ATTENDANCE/SHIFT UI; Luna | 007/008 if no shared Calendar/hook/test edits; blocks 014 | Preview/confirm/partial/retry and independent approval preserved; existing reports/forms only; revert UI. |
| 007 Payroll/Finance recovery / implementation | Precise blocker-to-native-record guidance and money-state explanation | 001, 003, 004; integrate 002 routes | PAYROLL/FINANCE UI; Luna + independent review | 006/008 subject to locks; blocks 014 | No copied money calculation, salary disclosure, mutation/permission changes; existing UI adapters/tests; revert UI. |
| 008 Employee/joiner/exit/expense recovery / implementation | Reuse Employee readiness and native lifecycle/expense forms | 001, 003, 004; integrate 002 routes | EMPLOYEE/LIFECYCLE/EXPENSE UI; Gemini | 006/007 with Calendar boundary; blocks 014 | Identity, readiness, lifecycle/history/maker-checker remain native; existing UI only; revert UI. |
| 009 Mobile state clarity / implementation | Distinguish local saved, server accepted, pending review and rejected evidence | 001, 000 integrated; flat from the same post-M02 verified Shared as 002/004; no old #53 stack | MOBILE; Luna + independent review | 002/004/003; blocks 010/014 | State fixtures/browser offline tests; self-service, quarantine/private media/review/queue unchanged; no new Page; revert labels/UI. |
| 010 Theme/branding/app tile / cleanup | Prefer native settings/theme routing; reduce DOM-specific custom behavior | 001, 000, 009; Shared unless real code dependency | GLOBAL UI; Gemini | 011/domain UI; blocks 012 | Light/dark, desktop/phone, native theme persistence, tile behavior; global family only; restore narrow adapters. |
| 011 Sidebar source ownership / cleanup | Prove standard app-level Sidebar JSON migration vs installer ownership | 001, 002, 005, 013; Shared after Workspace sequence | WORKSPACE; Gemini + independent review | 010/domain UI; blocks 012/014 | Installed export/sync proof, neutral install + persona/stored customizations; no core edit; metadata rollback after verified backup. |
| 012 Global CSS containment / audit+cleanup | Measure shell width/sidebar/gutters before removing risky selectors | 001, 010, 011 | GLOBAL UI; independent reviewer, Gemini patches | Domain UI/docs; blocks 014 | Viewport/overflow/focus/native sidebar regression; no new theme system; bounded CSS/tests; revert CSS. |
| 013 Artifact cleanup / cleanup | Remove only proven unused charts/cards/legacy UI artifacts | 001, **005 accepted/integrated or exact-head stack, then lock release**; Shared or documented dependency | ARTIFACT SOURCE + WORKSPACE; Gemini | 004/009/003; research can precede implementation; edits follow 005; blocks 014 | Repository + stored-reference audit, permissions, installer/fresh-install parity; artifact metadata/tests only; restore source/metadata. |
| 014 Accessibility/resilience/benchmark / validation | Repeat journeys and real-operator protocol, independent final UX audit | 002–013 accepted; Shared integrated head | Independent reviewer; reserve patches separately | Docs/release prep; blocks 015 | Compare same scenarios/starts/devices; keyboard/contrast/overflow/failure; no speculative redesign; evidence-only or separate patch IDs. |
| 015 UX release gate / validation | Prove integrated source/dependency/CI/UAT truth | 000–014; final integrated accepted head | Independent reviewer; documentation | None dependent | Exact PR graph, local/static/browser evidence, honest remote/device/staff gates; no production cutover; docs rollback. |

Primary agent labels are allocation recommendations (Luna/Gemini/independent reviewer), not a request to spawn agents during 001. Reviewers must inspect final heads independently.

## Dependency graph and waves

```mermaid
flowchart LR
  T000[000 Theme integrated / CI unresolved] --> T009[009 Mobile states]
  T001[001 Control plane] --> T002[002 Home]
  T001 --> T004[004 Lists]
  T001 --> T009
  T002 --> T003[003 Action Board]
  T002 --> T005[005 Learnability]
  T005 --> T013[013 Artifacts: installer lock]
  T003 --> T006[006 Attendance/Shift]
  T003 --> T007[007 Payroll/Finance]
  T003 --> T008[008 People/Expenses]
  T004 --> T006
  T004 --> T007
  T004 --> T008
  T009 --> T010[010 Theme/Brand/Tile]
  T013 --> T011[011 Sidebar source]
  T010 --> T012[012 CSS containment]
  T011 --> T012
  T006 --> T014[014 Benchmark]
  T007 --> T014
  T008 --> T014
  T012 --> T014
  T013 --> T014
  T014 --> T015[015 Release gate]
```

| Wave | Work | Lock caveat |
| --- | --- | --- |
| 0 | 000 + 001 COMPLETE / INTEGRATED | #53/#54 merged normally; checkpoint passed at `9ba1e9c185f2e01964d28b650b48f797927f68da`. |
| A | 002 + 004 + 009 | Three independent runtime locks. 013 can audit references additionally, but installer edits wait for 005 and its integration checkpoint. |
| B | 003 + 005, then 013 after 005 checkpoint/lock release | WORKSPACE order is exactly **002 → 005 → 013 → 011**; research does not authorize early edits. |
| C | 006 + 007 + 008 | At most three owners; Calendar/hooks/translations/test conflicts require reservation. |
| D | 010 + 011, then 012 | 011 follows 005/013 Workspace completion; 012 follows both shell/theme and sidebar evidence. |
| E | 014 then 015 | Final integrated benchmark and release disposition. |

Changes to the proposed graph: WORKSPACE implementation order is exactly **002 → 005 → 013 → 011**. Home decisions precede learnability metadata, then proven dead-artifact cleanup, then Sidebar source convergence against the reduced final surface. They share `install.py`; only research can run early. 012 must consume 011's actual sidebar evidence as well as 010. No dependency requires every domain PR to stack sequentially. Acceptance dependencies are not automatically code ancestry dependencies.

## INTEGRATION CHECKPOINT — required between waves

A dependent task may begin only when its predecessor is independently accepted **and integrated/merged into the current shared base**, or it has a genuine, explicitly documented stacked code dependency on the predecessor's **exact head SHA**. Acceptance of an unmerged PR alone does not put its code into another branch. Record every dependency's integrated-base ancestry or exact stacked head before starting.

Wave 0 review → human/coordinator integrates accepted foundation/control-plane prerequisites → records/verifies a new exact shared-base SHA → authorizes Wave A branches from that SHA. After Wave A, independently review every PR → human/coordinator integrates accepted non-conflicting PRs → verify resulting shared-base SHA → authorize Wave B. Repeat review/integration/exact-SHA checkpoints for later waves and for sequential substeps within a wave (including 005 → 013). Genuine exact-head stacks are the explicit alternative, not silent missing-code dependencies. No merge method is mandated; agents never merge.

Apply this gate to 001 → 002/004, 000 → 009, 002 → 003/005, 003/004 → 006/007/008, 009 → 010, 005/013 → 011, 010/011 → 012 and all 002–013 → 014. File-lock release is additional to, not a replacement for, dependency integration/ancestry.

**009 / PR #53:** Preferred integration is satisfied: #53 is MERGED and its CSS/test/evidence are in Shared. 009 branches flat from the then-current integrated shared base after M02 review/integration and authorization, alongside 002/004. Do not stack on old #53, cherry-pick it, duplicate its theme fix or recreate its test changes.

**001 / PR #54:** #54 is MERGED; its six control-plane files are now in Shared. The former unmerged-control-plane exception is no longer needed. M02 must be reviewed/integrated before Wave-A authorization; record that resulting exact SHA for all three branches. The general predecessor checkpoint still applies to subsequent waves and substeps.

## Review / merge protocol

Agents open DRAFT PRs and never merge, close, retarget or force-push. Independent reviewer validates exact base/head, files/locks, native-first decision, behavior, negative permission/maker-checker/retry evidence where relevant, browser evidence and unresolved UAT. Remote failing/unexecuted checks remain separate from local acceptance. Only the authorized human decides integration order and when the shared accepted base advances. Recheck affected sibling diffs after integration; do not rewrite another active branch.

Targets and baseline limits are in BASELINE. Required previews, confirmations and independent approvals are safety actions, not navigation waste. No future task may remove them to lower a click count.
