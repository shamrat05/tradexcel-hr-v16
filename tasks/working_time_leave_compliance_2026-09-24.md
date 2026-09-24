# Working Time / Overtime / Holiday / Leave Compliance — 2026-09-24

## Scope

Phase B on feat/working-time-leave-compliance adds an effective-dated, company/establishment-scoped Working Time Rule Set and an explicit Employee classification. Native submitted Attendance remains approved work evidence; native Overtime Type, Overtime Slip, Additional Salary, Holiday List, Leave Type, Leave Policy Assignment, and Leave Allocation remain canonical.

No legal production rules, real employee classifications, overtime slips, or leave changes are being activated.

## Findings and controls

- Daily/weekly maximum and standard hours are read from approved rules, never Python legal constants.
- Weekly average uses 52 complete weeks of submitted Attendance; incomplete history is a review finding.
- Break and spread-over evidence are review findings where native Attendance cannot prove them.
- Festival holidays require an explicit category on native Holiday rows; weekly rest also uses native weekly_off.
- Native Leave Type values and effective Leave Policy Assignment are inspected; no allocation is created.
- Native Overtime Slip submission is gated by company scope, independent Payroll Approver, exact submitted Attendance provenance, finalized non-stale Attendance Period, no started payroll, and working-time readiness.
- Payroll Approver has no standalone Additional Salary create permission. Its before-submit guard accepts only matching submitted native Overtime Slip, Payroll Correction, or Arrear provenance; adjustment-linked component and amount must match the approved parent.
- No rule means staged rollout review only; an establishment without a matching branch rule is informational until reviewed. No covered company population is blocked by guessed applicability. Fixed-hourly OT remains blocked because this rule model cannot bind a reviewed statutory amount and wage basis; whole-day native Holiday List rows cannot represent fractional weekly-rest requirements, so those block pending review.

## Primary legal references

- Bangladesh Labour Act consolidated text, hours / overtime / rest / leave chapters: https://bdlaws.minlaw.gov.bd/act-952/act-chapter-print-1039.html
- Bangladesh EPZ Labour Act, 2019 (separate regime): https://bdlaws.minlaw.gov.bd/act-1285/act-chapter-print-2174.html

The references are source candidates only. No production legal values are approved by this implementation; each rule needs legal review and source/effective-date provenance.

## Staging audit

Read-only site: hrms-v16.localhost; HRMS 16.19.0, ERPNext 16.35.0, Frappe 16.34.0.
- Shift Types: 2; Overtime Types: 0; Overtime Slips: 0.
- Attendance: 16,077 rows; 0 submitted; 9,535 have positive working hours (all rows have a non-null value); 0 OT duration/type rows; 1,786 late-entry and 3,155 early-exit rows.
- Holiday Lists: 1 (Tradex Holidays 2026), 62 holidays, 52 marked native weekly-off.
- Leave Types: 6; Leave Policies: 3 drafts; Leave Policy Assignments: 0; Leave Allocations: 1,190 submitted (confirmed by direct read-only table counts).
- No approved Working Time rules exist. These are operational counts, not legal coverage decisions.

## Synthetic proof

The native payroll finalization integration fixture is extended to create a synthetic Overtime Type, Attendance with 2 hours of native overtime, an HR Manager-made native Overtime Slip, a dual-role self-approval denial, independent Payroll Approver submission, native Additional Salary provenance, and a managed Salary Slip consuming the input. The OT date is after the joiner's SSA effective date because HRMS resolves salary structure from the slip start date. The fixture removes synthetic records explicitly and asserts cleanup.

Pure tests cover daily and weekly boundaries, missing OT evidence as a blocker, weekly-rest/festival compensation review, native weekly-off calendar matching (including unsupported fractional rest), 52-week history, OT multiplier/component mismatch, fixed-rate OT as a blocker, leave-setting comparison, and festival-calendar tagging.

## Deployment

A fresh `--with-files` backup was verified before the final metadata migration (prefix `20260924_130713-hrms-v16_localhost-`; database SHA-256 `4d3794432a6117bdc81b6ed165a3398832c04d8c810c1edc28181452f75cf05b`). Standard `bench migrate`, `bench build --app tradex_hr`, and cache clear passed; no manual metadata convergence was used. Focused Working Time tests: 15 passed; Working Time plus native payroll-finalization integration: 16 passed. Full Tradexcel suite: 466 passed, 2 skipped. `compileall`, five DocType JSON parses, and `git diff --check` passed. No browser tool is available, so Desk visual E2E remains a release gate. Integration cleanup left zero Working Time rules, classifications, child rows, Overtime Slips, or synthetic payroll test Companies. Production and real staging benefit/attendance/leave records were untouched.

## PR #17 hardening — 2026-09-24

Reproduced and fixed five integrity gaps on the working-time branch:

- Approved work hours include Present, Half Day, and Work From Home. Positive hours on Absent or On Leave Attendance now produce a status-conflict finding.
- Daily and weekly statutory excess hours must be covered by native overtime-duration evidence at the Attendance field precision. Tradexcel still does not calculate OT money.
- Complete weeks use submitted Attendance dates plus dates present in the employee's native Holiday List; the 52-week check loads the exact prior holiday window, including dates in the previous calendar year.
- Casual/Sick Leave readiness accepts either an effective submitted Leave Policy Assignment with sufficient native entitlement or a submitted Leave Allocation covering the reviewed period and requirement. Annual leave remains review-only until native earned-leave parity is established.
- Payroll Approver Additional Salary linked to an Overtime Slip must match the submitted slip's native component/amount map at company currency precision; duplicate active rows for the same slip/component are rejected. Payroll Correction and Arrear validation remains unchanged.

Verification after fixes: focused Working Time tests 27 passed; Working Time plus native payroll finalization and adjustment regressions 32 passed; complete Tradexcel pytest suite 478 passed, 2 skipped; compileall and all 50 app JSON files parsed. git diff --check passed. The first bench build attempt used system Node 20.20.2 and stopped because installed Frappe requires Node >=24; rerunning with the bench's installed Node 24.15.0 succeeded. No JavaScript changed. No schema changed, so migration/backup was not required. The staging audit still has 16,077 Attendance rows and zero submitted; no real Attendance, leave, overtime, or payroll records were changed.
