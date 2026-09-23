# Tradexcel HR source-only agent rules

## Start here

**Read `README.md` first.** It carries the one-screen status: what is done and
verified, what still blocks production, what needs an owner decision, and the
rules that must not be broken. The full change record is in `tasks/`.

## Before deleting or migrating data

**Read `BACKUPS.md` in this repository root first.** It lists every backup with
exact timestamps, file names, sizes and SHA-256 checksums, including the restore
point for each destructive operation. Take a fresh `bench backup --with-files` and
add a row to it before changing data. Note that a `bench restore` has never been
rehearsed on this machine — see the limitation recorded there.

## Canonical checkout — do not work anywhere else

- **This checkout is the only one to edit:** `/home/sanchita/frappe-bench/apps/tradex_hr` (WSL). It is the app directory the live bench loads via `~/frappe-bench/sites/apps.txt`, so it is the only tree whose edits affect runtime.
- A second clone exists at `/mnt/c/Users/Sanchita/Desktop/tradexcel-hr-audit-app` (Windows, reached through `/mnt/c`). Treat it as a stale read-only reference. Do not edit, commit, or branch there. It holds no unique content.
- Line endings are pinned to LF by `.gitattributes`. If `git status` reports the entire tree modified with equal insertion and deletion counts, that is a CRLF artifact, not real work. Confirm with `git diff --ignore-cr-at-eol` before acting on it.

- This repository contains the Frappe custom app, **not** the live bench/site or the standalone SenseFace listener. Never read or copy `sites/`, `sync/data/`, tokens, backups, payroll exports or employee records into this repository or an agent prompt.
- Frappe HR/ERPNext native Employee, Checkin, Attendance, Leave, Shift and Payroll documents are canonical. Build guided previews and audited actions around them; do not duplicate ledgers.
- No agent may run migrations, import employees, alter salary slips, submit payroll, or issue device commands against the live site. Coordinator owns staging verification and live cutover.
- The current app checkout is **not yet deployable on its own**: verified payroll and biometric worker runtime/tests remain under the bench's `sync/`. Complete packaging tasks before claiming release readiness.
- Local one-off false-import cleanup, prototype salary importer, and cancelled-slip purge scripts are intentionally excluded from the remote baseline. Do not reintroduce or execute them without a separate data review and owner authorization.
- Keep the SenseFace bridge in its own pinned repository. Its current receiver and JSON attendance API exist, but Frappe's device-configuration call has no matching bridge endpoint; do not claim that UI action works until implemented and tested.
- For each slice: use a dedicated worktree, change only assigned files, add negative permission/idempotency/date tests, review the diff for secrets, and report what remains unverified. Do not invent statutory rates or user identities.

## v16 repository handoff

- For tasks explicitly targeting `shamrat05/tradexcel-hr-v16`, the checkout is `/home/sanchita/frappe-bench-v16/apps/tradex_hr`. The separate `/home/sanchita/frappe-bench/apps/tradex_hr` checkout has a different Git remote; verify the target repository and branch before editing.
- Prefer codebase-memory MCP for code discovery. For this WSL checkout, pass `\\wsl.localhost\Ubuntu\home\sanchita\frappe-bench-v16\apps\tradex_hr`; if indexing/search fails, use `rg` and report the MCP failure. Use Context7 before relying on Frappe/HRMS behavior.
- Use Serena for semantic symbols/references when the graph is insufficient; call `initial_instructions` before coding, and start Codex from this WSL repo so Serena auto-activates the correct checkout. Use Sequential Thinking only for genuinely multi-step or high-risk reasoning.
- Payroll authority is the effective submitted Salary Structure Assignment plus its Salary Structure's explicit `custom_tradex_pay_basis`; the assignment `base` is the Daily Wage rate. Never infer money from Employment Type or raw Employee Checkin. The target Daily Wage path is current finalized native Attendance through native Additional Salary into native Payroll Entry/Salary Slip; do not call draft orchestration production-ready until its full reconciliation, retry and permission gates pass. Keep global Payroll Settings unchanged unless the company policy explicitly requires it.
- Native `PayrollEntry.create_salary_slips()` can commit internally. Integration tests must track and explicitly clean up only their synthetic documents, then verify cleanup; do not rely on savepoint rollback alone.
- Run site-backed tests from `/home/sanchita/frappe-bench-v16` so Frappe resolves `sites/` correctly. Keep real payroll unsubmitted and production untouched; document each implementation in the existing relevant task note.
- After code is pushed, review pasted code-reviewer findings as proposals: validate them against project rules, concrete boundary cases, and current Frappe/HRMS behavior in Context7; implement justified fixes or additions, and explain any finding that is invalid or conflicts with project invariants.
- `README.md` status figures are a 2026-09-18 snapshot. Use the latest dated task note and fresh read-only staging checks for current counts or settings.
## Historical payroll corrections

- Never "fix" historical payroll by editing submitted Salary Slips or consumed Daily Wage inputs.
- Use native Payroll Correction for approved LWP reversals and native Arrear for approved positive retroactive salary differences.
- Retroactive reductions and Daily Wage history changes require explicit HR/Finance adjustment review; do not create automatic recovery money.
- Preserve native Additional Salary provenance and route every approved adjustment into a later payroll.

## Employee separation

- `Employee.relieving_date` is the canonical employment end date; do not duplicate it.
- Native Employee Separation owns operational exit tasks; native Full and Final Statement owns settlement aggregation.
- Access shutdown is separate from unpaid settlement. Disable only a dedicated employee User and application biometric mapping; never delete identity or attendance history.
- Never infer statutory classification or calculate exit entitlements without an approved effective rule.
- Reject payable Attendance or overtime dated after relieving date; classify offline evidence by its captured event time.

## Statutory exit rules

- Legal regime and legal classification are explicit; never infer them from Employment Type, designation, or payroll pay basis.
- Statutory Rule Sets are source-linked, effective-dated, approved by a separate reviewer, and immutable after approval. An Employee Separation retains the exact approved version and reviewed applicability date.
- Unapproved or unresolved statutory rules never produce money. Native Gratuity, Leave Encashment, Additional Salary, and Full and Final documents remain the financial records.
- A `Not Applicable` decision requires an explicit reviewed classification and notes. Later rule versions never silently change a historical separation or settlement.

## Statutory wage floors

- Sector wage floors come only from approved effective rules with official final-source provenance; draft proposals are never operative.
- Wage-floor classification is explicit and effective-dated. Employment Type, Employee Grade, Designation, and payroll pay basis do not determine statutory category or grade.
- Compare against native full-period Salary Structure component values, not net pay or payment-day-reduced amounts.
- Under-floor findings block readiness but never change compensation. Historical payroll resolves against the immutable rule and classification effective for that period.

## Recruitment and onboarding

- Employee is the canonical worker identity. Recruited hires use native Job Opening, Job Applicant, accepted Job Offer, and Employee Onboarding; legitimate direct hires may begin at Employee and never need a fake applicant/email.
- Company scope for Job Applicant, Interview, and Interview Feedback derives from the linked Job Opening; recruiter APIs and writes must not cross explicit Company User Permissions.
- A submitted Salary Structure Assignment and its explicit Salary Structure pay basis authorize payroll. Employment Type is not pay basis or legal classification.
- Employee and User remain separate; account access is optional. Bank details are required only for Bank salary mode. Shift and biometric needs follow the actual attendance setup, not a universal default-shift rule.
- Joiner Readiness reflects that Employee's own canonical payroll outcome; the company-wide Payroll Readiness screen owns blockers from other employees. Onboarding never creates payroll or submits financial records.

## Statutory benefits

- PF, Progoti, and group-insurance applicability require explicit, source-linked, effective-dated approval; operational Employee counts and Employment Type never decide legal thresholds or participation.
- Salary Slip deductions do not prove remittance. Do not activate PF/Progoti payroll deductions until native employer-contribution accrual accounting is supported and verified; never substitute a custom Journal Entry.
- Native Gratuity and Full and Final remain the only gratuity/settlement path; do not create a parallel benefit ledger.
