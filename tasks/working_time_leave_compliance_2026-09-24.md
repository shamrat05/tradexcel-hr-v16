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
- Attendance: 16,077 rows; 0 submitted; 9,535 rows have working-hours values; no OT duration/type values.
- Holiday Lists: 1 (Tradex Holidays 2026), 62 holidays, 52 marked native weekly-off.
- Leave Types: 6; Leave Policies: 3 drafts; submitted Leave Policy Assignments: 1,190; Leave Allocations: 0.
- No approved Working Time rules exist. These are operational counts, not legal coverage decisions.

## Synthetic proof

The native payroll finalization integration fixture is extended to create a synthetic Overtime Type, Attendance with 2 hours of native overtime, an HR Manager-made native Overtime Slip, a dual-role self-approval denial, independent Payroll Approver submission, native Additional Salary provenance, and a managed Salary Slip consuming the input. The OT date is after the joiner's SSA effective date because HRMS resolves salary structure from the slip start date. The fixture removes synthetic records explicitly and asserts cleanup.

Pure tests cover daily and weekly boundaries, missing OT evidence as a blocker, weekly-rest/festival compensation review, native weekly-off calendar matching (including unsupported fractional rest), 52-week history, OT multiplier/component mismatch, fixed-rate OT as a blocker, leave-setting comparison, and festival-calendar tagging.

## Deployment

A fresh `--with-files` backup was verified before the final metadata migration (prefix `20260924_130713-hrms-v16_localhost-`; database SHA-256 `4d3794432a6117bdc81b6ed165a3398832c04d8c810c1edc28181452f75cf05b`). Standard `bench migrate`, `bench build --app tradex_hr`, and cache clear passed; no manual metadata convergence was used. Focused Working Time tests: 15 passed; Working Time plus native payroll-finalization integration: 16 passed. Full Tradexcel suite: 466 passed, 2 skipped. `compileall`, five DocType JSON parses, and `git diff --check` passed. No browser tool is available, so Desk visual E2E remains a release gate. Integration cleanup left zero Working Time rules, classifications, child rows, Overtime Slips, or synthetic payroll test Companies. Production and real staging benefit/attendance/leave records were untouched.
