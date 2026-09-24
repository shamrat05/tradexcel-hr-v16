# Maternity, Protected Leave, and Workplace Welfare

Date: 2026-09-25

Branch: `feat/maternity-protected-leave-welfare`
Parent: `feat/flexible-factory-work-policy` at `d80d2c94a6f8b4cfff8d568d8950fb99ef550469`

## Scope

This change adds source-linked, company-scoped maternity Rule Sets, restricted employee-specific Maternity Reviews, an independent maternity separation review, and an establishment-level Workplace Welfare Review. Native Leave Application, Attendance, Leave Ledger, Employee Separation, Full & Final, and Payroll remain authoritative.

Maternity eligibility and actual delivery evidence are restricted to Tradexcel HR Manager and Owner/Director. Payroll Readiness receives generic finding codes and messages only. The implementation does not infer pregnancy from gender and stores no diagnosis, medical narrative, or child identity data.

Maternity salary payment is deliberately not automated. The read-only inspection returns no amount and reports a review state. Monthly gross / divisor, average wages / actual days worked, or manual legal review are explicit Rule Set configurations; no salary component is selected by name heuristics. No Additional Salary or Journal Entry is created.

Welfare uses reviewed aggregate establishment evidence, not Employee or gender counts. First-aid readiness checks reviewed box count, trained-custodian evidence, and accessibility evidence. Its findings are not wired into Payroll Readiness.

## Source basis

Official consolidated general Labour Act text: [BDLaws, Chapter IV](https://bdlaws.minlaw.gov.bd/act-952/act-chapter-print-1034.html). It includes the current general maternity framework and links the relevant changes to the 2026 amendment.

Official amendment: [Bangladesh Labour (Amendment) Act, 2026](https://bdlaws.minlaw.gov.bd/act-print-1672/section-print-58628.html).

Separate regime: [Bangladesh EPZ Labour Act, Chapter III](https://bdlaws.minlaw.gov.bd/act-1285/act-chapter-print-2175.html). It has distinct maternity durations and wage-average treatment. Rule Sets require an explicit regime; no general-Labour-Act fallback is provided.

Welfare source: [BDLaws, Bangladesh Labour Act](https://bdlaws.minlaw.gov.bd/act-print-952.html), sections 89 and 94. The code accepts reviewed workforce counts and evidence as inputs; it does not assert that the statutory thresholds apply to TCL or EFL.

These references are source provenance for configuration design, not a legal applicability decision for either company.

## Local read-only audit

The most recent read-only site audit found one Leave Type with maternity-like naming, five Leave Allocations, and zero Leave Applications. These are counts only; existing Leave configuration and allocations were not changed.

The new Maternity Rule Set, Maternity Review, and Workplace Welfare tables are not installed on the local site because no migration was run. Consequently the site has no operative rules or cases from this feature. Operational branch employee counts previously observed were EFL H.O. 2, TCL without branch 1, TCL Factory 227, and Tradexcel HQ 12; these are operational counts only, not legal worker counts.

## Native Leave proof

A synthetic company, employee, Leave Type, Leave Period, Leave Allocation, Leave Application, Holiday List row, Attendance, and Leave Ledger Entry were created on `hrms-v16.localhost`. Submitted native Leave Application created three calendar days of leave across a configured holiday, native On Leave Attendance, and native Leave Ledger records. Cleanup completed in the test's `finally` path. No real Leave configuration changed.

## Readiness and privacy

- Rule and case records require explicit Company scope and maker/checker review.
- Submitted Rule Sets and reviews are immutable through application validation.
- The statutory separation safeguard runs at Employee Separation submission, including the expected-delivery pre-delivery review window, allowing an independent review to be linked before submit.
- Eligible maternity payment remains `MATERNITY_BENEFIT_PAYMENT_PATH_REVIEW_REQUIRED`; pending eligibility uses a distinct generic review code; a Leave Only decision does not create a statutory payment blocker.
- Company Payroll Readiness batches event cases for the requested population and returns only generic code/message pairs.

## Verification

Focused maternity and native Payroll Readiness tests: 32 passed.
Native Leave integration on the local site: passed; synthetic records cleaned.
Full Tradexcel suite: 532 passed, 3 skipped, 36 upstream deprecation warnings.
Compileall, all-app JSON validation, JavaScript syntax, build, and diff checks are recorded in the completion report.

No migration, site configuration change, production access, real employee maternity data, real Leave mutation, or real payroll mutation was performed. The original local MariaDB on 127.0.0.1:3307 remained the configured site database; the app returned HTTP 200.
