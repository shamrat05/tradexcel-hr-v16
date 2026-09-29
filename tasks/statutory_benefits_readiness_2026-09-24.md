# Statutory benefits readiness — 2026-09-24

## Scope

This stacked feature records reviewed, effective-dated PF, institutional Progoti, and group-insurance applicability and employee participation. It does not create a benefit fund, enrollment, salary deduction, contribution, remittance, or legal configuration for TCL/EFL. Native Gratuity and Full & Final remain in the existing exit flow.

## Legal/source review

Primary sources reviewed: [Bangladesh Labour Act section 264 as amended by the Bangladesh Labour (Amendment) Act, 2026](https://bdlaws.minlaw.gov.bd/act-print-1672/section-print-58607.html); [Labour Act section 99](https://bdlaws.minlaw.gov.bd/act-print-952/section-print-29981.html); [National Pension Authority Progoti guidance](https://www.upension.gov.bd/Public/PensionBriefEn); and the [Bangladesh EPZ Labour Act, 2019](https://objectstorage.ap-dcc-gazipur-1.oraclecloud15.com/n/axvjbnqprylg/b/V2Ministry/o/office-legislativediv/2024/12/913f5fc1526046f780c8dd90fe12c48a.pdf). These sources are research references only: no real source row or approved rule was created by this change. Operational Employee counts are not treated as legal permanent-worker counts.

## Installed HRMS v16 finding

Salary Slip supports employer-contribution rows. Installed `PayrollEntry.make_accrual_jv_entry()` gathers earnings and deductions, but not `employer_contributions`. Therefore applicable PF/Progoti participation remains blocked from payroll as `STATUTORY_BENEFIT_ACCOUNTING_PATH_REVIEW_REQUIRED` pending an approved native accounting path. This feature creates no custom Journal Entry. A Salary Slip deduction is not remittance evidence.

## Controls

- Rule sets and enrollments require company scope, source/evidence, independent Owner/Director approval, and are immutable after submission.
- Applicable rules require matching native Salary Component types; the company-specific account mapping is stored on `Salary Component Account`, not core `Salary Component`.
- Enrollment and rule periods are effective-dated and cannot overlap ambiguously.
- Readiness uses explicit approved records; no Employee-count, Employment Type, grade, designation, or pay-basis inference.
- No approved applicable rule means informational review, not a global payroll blocker. Group-insurance readiness checks policy and employee coverage only.
- The readiness payload never includes external account/member references.

## Staging safety

Only synthetic test records may be created and explicitly cleaned. Do not enroll real employees, change components/structures/assignments, approve a real benefit rule, or initiate remittance. The staging database is not a source of legal permanent-worker or demand counts.

## Migration backup

Before standard staging migration, `bench --site hrms-v16.localhost backup --with-files` completed on 2026-09-24 10:31 Asia/Dhaka. Database SHA-256: `af4c7cac0cdd21147706cb2189fa63d79d5176a992ed585264f1230cd2bf7361`; both file archives and database passed archive integrity checks. See `BACKUPS.md`.

## Staging audit (read-only, 2026-09-24)

- Active Employees: TCL 240, EFL 2 (operational counts only).
- No `Employee.provident_fund_account` field exists in this installed site schema.
- Salary Components: 4 Deduction, 0 Employer Contribution; the only PF-like component is `Provident Fund (Employee)` (Deduction).
- Submitted Salary Structure Assignments: 227. No Salary Structure currently has employer-contribution rows; no Salary Structure has deduction rows.
- Gratuity Rules and Gratuity records: 0. Benefit Rule Sets, benefit enrollments, and synthetic benefit components after cleanup: 0.
- Legal establishment regime, permanent-worker counts, PF demand, Progoti registration, and group insurance policies are not evidenced by these operational records.

## Verification record

- Site-backed focused readiness, separation, and native integration tests: 30 passed; follow-up unit suite: 10 passed.
- Full Tradexcel suite: 436 passed, 2 skipped, 31 warnings. The first full run exposed a dict-row access bug in the batched payroll path; a regression test was added and the final full run passed.
- Python `compileall` passed; both new DocType JSON files parsed; `node --check` was not needed because no JavaScript changed; `bench build --app tradex_hr` passed using the already-installed Node 24.15.0 runtime; `git diff --check` passed.
- Standard staging migration was run after a fresh `--with-files` backup. Database gzip and public/private file archives passed integrity checks; cache cleared. No manual metadata convergence was used.
- Synthetic Benefit Rule Set, Enrollment, component, employee, and company records were explicitly cleaned; post-cleanup count is zero. A pre-existing disposable wage-test company/employee fixture was also removed through the repository's guarded synthetic cleanup helper; the synthetic-company/employee count is zero.
- Installed HRMS v16 has a material accounting boundary: `PayrollEntry.make_accrual_jv_entry()` requests earnings and deductions, but not `employer_contributions`. PF/Progoti participation therefore fails closed at `STATUTORY_BENEFIT_ACCOUNTING_PATH_REVIEW_REQUIRED`; no custom Journal Entry or claimed remittance is created.
- Production was not touched. No real employee enrollment, Salary Component, Salary Structure, SSA, deduction, employer contribution, or remittance was changed.

## PR #16 hardening follow-up

- Company-wide rules now apply to employees in any Branch of the same Company. Branch-specific rules remain limited to their Branch. Historical branch-specific applicability is accepted only when a submitted enrollment snapshots that exact rule and Branch; the Employee's current Branch is never used to invent prior history.
- A company-wide rule can be enrolled with the Employee's reviewed Branch snapshot. Current/future enrollments must match the current Employee Branch; historical snapshots may retain a different Branch only within the same Company and the selected rule's scope.
- Group-insurance policy dates must cover the entire payroll period. A start/end transition inside the period requires explicit review.
- Employer-contribution capability is detected from the installed Payroll Entry controller and accrual method. On this HRMS 16.19.0 staging runtime it is absent; if present on a future HRMS build, readiness still blocks until the full native accrual integration is verified. No version-based permanent limitation or custom Journal Entry was added.
- Regression tests: 26 passed, including company-wide and branch-specific scope, historic enrollment, full-period policy coverage, and capability detection. Full suite: 451 passed, 2 skipped, 31 warnings. `compileall` and `git diff --check` passed. No schema or JavaScript changes, so migration/build were not required.
