# PR merge runbook — 2026-09-26

**Procedure only: no merge authorized or performed by this campaign.**

1. Review `release_stack_2026-09-27.md`, exact head SHAs and ancestry. Resolve
   review comments with new correction commits/PRs; no history rewriting.
2. Owner approves business/security design. Review source-contract CI separately
   from the current local Frappe integration evidence; neither proves real UAT.
3. On explicit later merge authorization, merge oldest accepted dependency first.
   Recheck each descendant diff/base/head after GitHub retargeting; do not blindly
   merge the whole stack or enable auto-merge.
4. Pin Frappe/ERPNext/HRMS v16, app release SHA and separate bridge SHA. Tag only
   the accepted integrated release, then run full staging migration/E2E/browser
   checks on the exact integrated tree before deployment.
5. If a check changes or fails, stop. Never erase a failure by lowering the test
   baseline or claiming draft-PR checks cover an untested merge result.

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
