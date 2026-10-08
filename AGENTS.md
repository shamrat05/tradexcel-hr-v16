# Workforce Suite source-only agent rules

## Start here

**Read `README.md` first.** It carries the one-screen status: what is done and
verified, what still blocks production, what needs an owner decision, and the
rules that must not be broken. The full change record is in `tasks/`.

## Before deleting or migrating data

**Read `BACKUPS.md` in this repository root first.** It lists every backup with
exact timestamps, file names, sizes and SHA-256 checksums, including the restore
point for each destructive operation. Take a fresh `bench backup --with-files` and
add a row before schema/data migration. A disposable v16 staging restore and
migration were rehearsed in September 2026; production recovery is unproven.

## Canonical checkout — do not work anywhere else

- **For this v16 repository, edit only:** `/home/sanchita/frappe-bench-v16/apps/workforce_suite` (WSL). The older `/home/sanchita/frappe-bench/apps/workforce_suite` has a different remote and is a historical checkout.
- A second clone exists at `/mnt/c/Users/Sanchita/Desktop/workforce-suite-audit-app` (Windows, reached through `/mnt/c`). Treat it as a stale read-only reference. Do not edit, commit, or branch there. It holds no unique content.
- Line endings are pinned to LF by `.gitattributes`. If `git status` reports the entire tree modified with equal insertion and deletion counts, that is a CRLF artifact, not real work. Confirm with `git diff --ignore-cr-at-eol` before acting on it.

- This repository contains the Frappe custom app, **not** the live bench/site or the standalone SenseFace listener. Never read or copy `sites/`, `sync/data/`, tokens, backups, payroll exports or employee records into this repository or an agent prompt.
- Frappe HR/ERPNext native Employee, Checkin, Attendance, Leave, Shift and Payroll documents are canonical. Build guided previews and audited actions around them; do not duplicate ledgers.
- Never migrate, import employees, alter salary slips, submit payroll, or issue device commands against production. On isolated v16 staging, run a user-authorized standard migration only after a verified fresh backup. Real employee/payroll data remains read-only during engineering tests.
- Payroll and biometric worker implementations are versioned in this app. The v16 bench has no `sync/` runtime directory. Source packaging still needs a clean-install and release rehearsal before deployability is claimed.
- Local one-off false-import cleanup, prototype salary importer, and cancelled-slip purge scripts are intentionally excluded from the remote baseline. Do not reintroduce or execute them without a separate data review and owner authorization.
- Keep the SenseFace bridge in its own pinned repository. Its current source has an authenticated device-configuration endpoint, but the response records a bridge profile and does not prove terminal settings were applied. Physical device and browser UAT remain required; see `docs/senseface_bridge_contract.md`.
- For each slice: use a dedicated worktree, change only assigned files, add negative permission/idempotency/date tests, review the diff for secrets, and report what remains unverified. Do not invent statutory rates or user identities.

## v16 repository handoff

- For tasks explicitly targeting `shamrat05/workforce-suite`, the checkout is `/home/sanchita/frappe-bench-v16/apps/workforce_suite`. The separate `/home/sanchita/frappe-bench/apps/workforce_suite` checkout has a different Git remote; verify the target repository and branch before editing.
- Prefer codebase-memory MCP for code discovery. For this WSL checkout, pass `\\wsl.localhost\Ubuntu\home\sanchita\frappe-bench-v16\apps\workforce_suite`; if indexing/search fails, use `rg` and report the MCP failure. Use Context7 before relying on Frappe/HRMS behavior.
- Use Serena for semantic symbols/references when the graph is insufficient; call `initial_instructions` before coding, and start Codex from this WSL repo so Serena auto-activates the correct checkout. Use Sequential Thinking only for genuinely multi-step or high-risk reasoning.
- Payroll authority is the effective submitted Salary Structure Assignment plus its Salary Structure's explicit `custom_workforce_pay_basis`; the assignment `base` is the Daily Wage rate. Never infer money from Employment Type or raw Employee Checkin. The target Daily Wage path is current finalized native Attendance through native Additional Salary into native Payroll Entry/Salary Slip; do not call draft orchestration production-ready until its full reconciliation, retry and permission gates pass. Keep global Payroll Settings unchanged unless the company policy explicitly requires it.
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
- A company-wide benefit rule applies to all Branches in its Company; branch-specific rules and enrollment snapshots must match the reviewed establishment, including historical same-company transfers.
- Salary Slip deductions do not prove remittance. Do not activate PF/Progoti payroll deductions until native employer-contribution accrual accounting is supported and verified; never substitute a custom Journal Entry.
- Detect native employer-contribution accrual from the installed Payroll Entry controller and accrual path, not a permanent HRMS version assumption; capability alone is not integration proof.
- Native Gratuity and Full and Final remain the only gratuity/settlement path; do not create a parallel benefit ledger.

## Working time, overtime, holidays, and leave

- Submitted Attendance is the approved work-time source; raw Employee Checkin evidence is never counted directly as legal or payroll hours.
- Legal work-time scope and limits are explicit, source-linked, effective-dated, and company/establishment-scoped; Employment Type and payroll pay basis do not determine legal coverage.
- Native Overtime Type, Overtime Slip, Additional Salary, Holiday List, Leave Policy, and Leave Allocation remain canonical. Workforce validates configuration/readiness and does not calculate overtime money or allocate statutory leave.
- Statutory hours include positive approved working_hours on Present, Half Day, and Work From Home Attendance; positive hours on Absent/On Leave are a data-integrity conflict. Raw Employee Checkin evidence is never counted directly.
- Native overtime duration must cover daily and weekly hours above the approved statutory normal limits. Workforce checks evidence only and never computes OT money.
- A native Holiday List holiday accounts for a calendar date without Attendance when checking week completeness; do not manufacture Attendance for holidays. Load the full 52-week holiday range for rolling checks.
- Casual/Sick leave readiness accepts either a sufficient effective submitted Leave Policy Assignment or a submitted Leave Allocation covering the period. Annual-leave statutory accrual remains review-only until native parity is proven.
- Payroll Approver Additional Salary sourced from Overtime Slip must match the slip's native component/amount calculation at currency precision and cannot duplicate an active slip/component row. Preserve native Payroll Correction and Arrear provenance.
- Missing legal scope stays review-only during staged rollout. Approved-rule violations block the relevant attendance/payroll approval; historical finalized Attendance and submitted payroll remain immutable.


## Flexible factory work

- Daily Wage money remains effective Salary Structure Assignment.base with the explicit Salary Structure pay basis; flexible policy changes only capped base payable units and never calculates OT.
- Work-hour proration uses submitted Attendance working_hours only for work-only statuses; native Leave/Holiday semantics remain intact. Working hours are part of finalized Attendance financial provenance.
- An Operational Day Override can grant full-day base pay only to a present employee with positive approved work evidence. It never changes Attendance, pays absence/leave, or creates OT.
- Native Shift Assignment and HRMS timestamp resolution own flexible shift selection. Never enable multiple same-date assignments site-wide from app code.
- Effective flexible policy and override changes require Attendance reopen/refinalization and cannot rewrite consumed payroll.
