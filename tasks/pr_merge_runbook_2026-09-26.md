# PR merge runbook — 2026-09-26

**Procedure only: no merge authorized or performed by this campaign.**

1. Review `release_stack_2026-09-27.md`, exact head SHAs and ancestry. Resolve
   review comments with new correction commits/PRs; no history rewriting.
2. Owner approves business/security design. Review source-contract CI separately
   from the 629-test local Frappe integration evidence; neither proves real UAT.
3. On explicit later merge authorization, merge oldest accepted dependency first.
   Recheck each descendant diff/base/head after GitHub retargeting; do not blindly
   merge the whole stack or enable auto-merge.
4. Pin Frappe/ERPNext/HRMS v16, app release SHA and separate bridge SHA. Tag only
   the accepted integrated release, then run full staging migration/E2E/browser
   checks on the exact integrated tree before deployment.
5. If a check changes or fails, stop. Never erase a failure by lowering the test
   baseline or claiming draft-PR checks cover an untested merge result.
