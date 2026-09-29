# Release PR dependency snapshot — 2026-09-27

Read from GitHub; no merges performed. Head SHA is remote truth.

| PR | Title | Base → head | SHA | State / draft | Mergeability | Checks | Files |
| --- | --- | --- | --- | --- | --- | --- | ---: |
| #1 | docs: error-safe HRMS v16 architecture and agent build guide | feature/hrms-v16-hr-only → docs/error-safe-hrms-agent-blueprint | `e71b6949e18b1e7d4a9a84486f1a354dc4d13b9d` | OPEN / False | MERGEABLE | 0 | 17 |
| #2 | fix: harden v16 report routing and mobile offline replay | feature/hrms-v16-hr-only → fix/v16-production-readiness | `69461cf6c96153a99291ae798f58cbf4d98c15a8` | OPEN / False | MERGEABLE | 0 | 29 |
| #3 | fix: preserve receipt-time mobile security policy | fix/v16-production-readiness → fix/mobile-offline-time-integrity | `a83ae92c42fb1b9cff4b1dd1fa7721f8b9f84ce9` | OPEN / False | MERGEABLE | 0 | 11 |
| #4 | fix: separate attendance finalization from payroll readiness | fix/payroll-p0-safety → feat/attendance-payroll-boundary | `a36582263e9845f3d2b7d132e6297eebf9d798a3` | OPEN / False | MERGEABLE | 0 | 8 |
| #5 | feat: enforce native mixed pay-basis wage inputs | feat/attendance-payroll-boundary → feat/mixed-pay-basis-wage-input | `8434d0230a9aa8bc2e9e49c4cdfc2477594af467` | OPEN / False | MERGEABLE | 0 | 16 |
| #6 | feat: orchestrate native payroll drafts | feat/mixed-pay-basis-wage-input → feat/native-payroll-draft-orchestration | `a2edf9fb071da24e82e4829e188039202f042b1d` | OPEN / False | MERGEABLE | 0 | 13 |
| #7 | feat: add payroll readiness operator flow | feat/native-payroll-draft-orchestration → feat/payroll-readiness-operator-flow | `e3e860e58eff070e34d8bc7eab39e71b2175841b` | OPEN / False | MERGEABLE | 0 | 36 |
| #8 | Add native payroll financial readiness | feat/payroll-readiness-operator-flow → feat/payroll-financial-readiness | `23c55ece5b6f2637c7a4407f6c2f7a055fd35a83` | OPEN / False | MERGEABLE | 0 | 18 |
| #9 | Finalize managed payroll through native HRMS accrual | feat/payroll-financial-readiness → feat/payroll-submit-accrual-reconciliation | `88e2945b5d4878d7dba7465af1ed299ff2e5e6fa` | OPEN / False | MERGEABLE | 0 | 14 |
| #10 | Add native payroll payment readiness and reconciliation | feat/payroll-submit-accrual-reconciliation → feat/payroll-payment-readiness-reconciliation | `26bb7f1a301d2268dc8dc70ac877b70e8c442249` | OPEN / False | MERGEABLE | 0 | 7 |
| #11 | Add guarded payroll corrections and arrears | feat/payroll-payment-readiness-reconciliation → feat/payroll-retro-corrections-arrears | `a709811f7327f178369885bdf68ab2e01f921a40` | OPEN / False | MERGEABLE | 0 | 16 |
| #12 | Employee separation and Full & Final readiness | feat/payroll-retro-corrections-arrears → feat/employee-separation-full-final | `61b75101e365bd8461124f5aefd74a3c8c9e586d` | OPEN / False | MERGEABLE | 0 | 21 |
| #13 | feat: version statutory exit review rules | feat/employee-separation-full-final → feat/statutory-exit-compliance-versioning | `824ef16309be9d88a5dc90ab36210d8bfab459f9` | OPEN / False | MERGEABLE | 0 | 22 |
| #14 | feat: add recruitment and joiner readiness | feat/statutory-exit-compliance-versioning → feat/recruitment-joiner-onboarding | `61b5e3dc834a5f44ac71f0bc28dc8220f166e248` | OPEN / False | MERGEABLE | 0 | 10 |
| #15 | feat: add statutory wage floor readiness | feat/recruitment-joiner-onboarding → feat/statutory-wage-floor-readiness | `c0aa9d63e495796b2613d971a4d400c853a3d5a2` | OPEN / False | MERGEABLE | 0 | 26 |
| #16 | feat: add statutory benefits readiness | feat/statutory-wage-floor-readiness → feat/statutory-benefits-readiness | `a58c6c72c011e5d346bd33e56c0dbb952ac95913` | OPEN / False | MERGEABLE | 0 | 17 |
| #17 | Add working-time, overtime, holiday and leave compliance | feat/statutory-benefits-readiness → feat/working-time-leave-compliance | `487676036cf367c9be89e47446004af9b51846c6` | OPEN / False | MERGEABLE | 0 | 24 |
| #18 | feat: Flexible factory work policy | feat/working-time-leave-compliance → feat/flexible-factory-work-policy | `d80d2c94a6f8b4cfff8d568d8950fb99ef550469` | OPEN / False | MERGEABLE | 0 | 23 |
| #19 | feat: add maternity and workplace welfare review | feat/flexible-factory-work-policy → feat/maternity-protected-leave-welfare | `f39ffb93e4b10e9fc02eff52110d937a0302ed1c` | OPEN / False | MERGEABLE | 0 | 26 |
| #20 | feat: add native employee lifecycle safeguards | feat/maternity-protected-leave-welfare → feat/employee-lifecycle | `8a8303cc3d274535224a61fa78754eed458a5cb0` | OPEN / True | MERGEABLE | 0 | 12 |
| #21 | fix: enforce scoped HR report authorization | feat/employee-lifecycle → fix/report-authorization-scope | `7577ce2671d7dcbe37bfa94fa7af2816cb16e4c1` | OPEN / True | MERGEABLE | 0 | 12 |
| #22 | feat: add scoped operational HR reports | fix/report-authorization-scope → feat/operational-report-scope | `22105f0754dc12884848ffd466801b49187c68c9` | OPEN / True | MERGEABLE | 0 | 17 |
| #23 | feat: add scoped financial payroll reports | feat/operational-report-scope → feat/financial-report-scope | `f1bf90c5e41ee7c1b6f6bacaccb8f994d4493467` | OPEN / True | MERGEABLE | 0 | 19 |
| #24 | fix: establish role-scoped operator access | feat/financial-report-scope → feat/persona-access-foundation | `e78bdf6ee88717992e0b74bfa57e1cf1fed2facc` | OPEN / True | MERGEABLE | 0 | 8 |
| #25 | feat: secure native bulk shift assignment | feat/persona-access-foundation → feat/native-bulk-shift-assignment | `52c1af10d44950542a126dc1d56009d6488f71be` | OPEN / True | MERGEABLE | 0 | 7 |
| #26 | feat: add secure bulk salary authority workflow | feat/native-bulk-shift-assignment → feat/bulk-salary-authority | `549462588542d1d615f47e54220df1439a3e4d4a` | OPEN / True | MERGEABLE | 0 | 11 |
| #27 | refactor: converge shift bulk workflow on native HRMS | feat/bulk-salary-authority → fix/converge-shift-bulk-path | `2ebf51b223090a891b42976ea2e036e996ff37fd` | OPEN / True | MERGEABLE | 0 | 5 |
| #28 | feat: add reviewed bulk attendance corrections | fix/converge-shift-bulk-path → feat/bulk-attendance-corrections | `5d30ce89d1d96532cbf10847d226a23559ec0afd` | OPEN / True | MERGEABLE | 0 | 11 |
| #29 | refactor: remove legacy company-specific runtime hazards | feat/bulk-attendance-corrections → refactor/runtime-portability | `bba1daa126594b04f3f03442c87fe340aa6cb924` | OPEN / True | MERGEABLE | 0 | 24 |
| #30 | feat: secure native leave bulk operations | refactor/runtime-portability → feat/native-bulk-leave-control | `10e85ecb3c20a840097638061c689badfbed8fc2` | OPEN / True | MERGEABLE | 0 | 7 |
| #31 | feat: secure native overtime draft preparation | feat/native-bulk-leave-control → feat/native-overtime-bulk | `9fbfbdd04c8f86585424f279a835de4f61f291e3` | OPEN / True | MERGEABLE | 0 | 7 |
| #32 | refactor: converge remaining HR bulk operations | feat/native-overtime-bulk → refactor/native-bulk-closure | `4d6c9af81d5d89e9b1d87867bc5bd97c05bf66ed` | OPEN / True | MERGEABLE | 0 | 14 |
| #33 | fix: scope legacy HR report findings | refactor/native-bulk-closure → fix/legacy-report-boundaries | `c9688a464be4958c4e89cddc2506065e30ada02b` | OPEN / True | MERGEABLE | 0 | 16 |
| #34 | fix: scope native employee-linked records | fix/legacy-report-boundaries → fix/employee-linked-scope | `031120271a393dae93ff90e0aa48614aafc9f4c6` | OPEN / True | MERGEABLE | 0 | 8 |
| #35 | feat: add role-scoped HR action board | fix/employee-linked-scope → feat/action-board | `257fa90fccf815c7d3b5698f20e4dd0acbf94b6f` | OPEN / True | MERGEABLE | 0 | 11 |
| #36 | refactor: simplify role-based HR navigation | feat/action-board → refactor/native-workspace-ia | `fe2e62ce06997284d117b1c320cf46793da29086` | OPEN / True | MERGEABLE | 0 | 11 |
| #37 | fix: preserve bulk job identity and private results | refactor/native-workspace-ia → fix/bulk-job-privacy | `9c56fdc53e78415bb5bce6fe30687be665c096ee` | OPEN / True | MERGEABLE | 0 | 9 |
| #38 | feat: simplify HR operator reviews | fix/bulk-job-privacy → feat/operator-usability | `6a19a7138a03ba3c152032b6920167804a1dda15` | OPEN / True | MERGEABLE | 0 | 12 |
| #39 | fix: protect native HR records and financial fields | feat/operator-usability → fix/security-privacy-hardening | `4ddffbe99d97eccc133295b952edcfde1a534a4f` | OPEN / True | MERGEABLE | 0 | 12 |
| #40 | fix: reconcile native payroll payment amounts | fix/security-privacy-hardening → feat/accounting-reconciliation | `273c64ff22e0bea0a232aca61fc4a8dc594ff881` | OPEN / True | MERGEABLE | 0 | 5 |
| #41 | perf: optimize measured HRMS report bottlenecks | feat/accounting-reconciliation → perf/measured-hrms-pass | `441563798685e996e2f3e60804e26887ec6f98e7` | OPEN / True | MERGEABLE | 0 | 7 |

Campaign test/migration evidence for each phase is in `sol_completion_state_2026-09-26.md`; backup hashes are in BACKUPS.md. Existing non-draft PRs were not changed. This release PR intentionally does not record its own commit SHA inside itself. GitHub is authoritative for its final head/checks.

Local ancestry verified for 41 PR base/head pairs; failures: []. No branch was retargeted or rewritten.

## Release-lineage correction — 2026-09-27

The prior base/head-pair checks did **not** prove all PR heads belonged to the integrated release.
PR #1 is independent documentation, not a runtime dependency. PR #3 diverged after
PR #2: merge-base is `69461cf6c96153a99291ae798f58cbf4d98c15a8`; its head
`a83ae92c42fb1b9cff4b1dd1fa7721f8b9f84ce9` is **not** an ancestor of #42
(`9173b5aaa5e9e6cee7daa23ce3c88b7f519138e3`). Its required security behavior is
ported into `fix/release-lineage-security-closure` on top of #42, preserving later
scope/privacy/performance work. Do not blindly merge old #3 after accepting this
correction. It remains open; no historical branch was rewritten or closed.

[PR #43](https://github.com/shamrat05/tradexcel-hr-v16/pull/43) exposes the seven
already-existing commits from `fix/v16-production-readiness` to
`fix/payroll-p0-safety` (`e39068819a20569319f0b21a1d81cd7e5ccfd995`). No commit
was added to that historical branch. #43 is open/draft/mergeable and precedes #4.

Eventual runtime merge dependency: **#2 → #43 → #4 → #5 … #42 → release-lineage
security correction**. #1 is separately reviewable documentation; old #3 is
superseded by the integrated semantic port. This is a future runbook, not merge
authorization. Preserve and recheck every actual base/head at merge time.

Both #42 Actions attempts were blocked before steps:
- `36283160723`, commit `3ec045d44e254f855984758252150857d7409c5a`: failure, zero steps.
- `36283208413`, commit `9173b5aaa5e9e6cee7daa23ce3c88b7f519138e3`: failure, zero steps.

The current final-run check annotation explicitly says account payments failed
or the spending limit needs increasing. This is **BLOCKED BEFORE STEPS**, never
remote CI PASS. No rerun or account-setting workaround was attempted. Phase K
remains **BLOCKED** until remote checks execute and the separate framework/source
and external release gates are resolved.

Correction publication: [PR #44](https://github.com/shamrat05/tradexcel-hr-v16/pull/44)
is open/draft/mergeable, base `test/release-readiness-contract`, head
`fix/release-lineage-security-closure`. Eventual order is **#2 → #43 → #4 … #42
→ #44**; old #3 is superseded by #44, while #1 remains independent docs.
The first #44 source-contract run is `36304838645` on code commit `fe90092b8757cccbce05111dccefb1d7a9dc43ca`;
it was queued at publication. No remote PASS is claimed. Current head and check
state remain authoritative on GitHub, including the documentation-only publication
follow-up. No merge or force-push occurred.
