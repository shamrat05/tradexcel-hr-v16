# Flexible factory work policy - 2026-09-24

## Scope

Adds an optional, approved company policy for work-only Daily Wage proration and a separate, approved Operational Day Override for management-declared shutdown/release days. Native Employee, Shift Assignment, Attendance, Salary Structure Assignment, Additional Salary, and Salary Slip remain authoritative. This change does not activate a real policy, change attendance, or change salary.

## Implementation

- Tradexcel Flexible Work Policy stores effective dates, optional Branch/Department scope, standard paid hours, full-day threshold, and an optional allow-list of native Shift Types.
- Tradexcel Operational Day Override records a one-day, scoped approval for Full Day Pay for Present Employees. Its read-only preview is bound to approved Attendance, the effective flexible policy, and SSA base rates.
- Work-only Present, Half Day, and WFH Attendance with positive approved working_hours can receive a capped base unit: 1 at/above the configured threshold and otherwise actual hours divided by standard paid hours. Attendance linked to leave, holidays under native Payroll Settings, Absent, and On Leave keep native Salary Slip treatment. Missing work hours or positive hours on an absence state fail closed.
- Override changes only a qualifying Present/Half Day work-only Daily Wage unit to 1. It cannot pay Absent, leave, holiday, or WFH rows; it does not alter Attendance or create OT.
- Attendance.working_hours is included in the Attendance Period financial fingerprint. Submitted policies and overrides are immutable; policy/override activation or cancellation is blocked once overlapping Attendance is finalized or payroll has started. A changed preview blocks finalization/payroll until reopened and reviewed.
- Approved policy/override changes invalidate request-local readiness caches. Override preview verification is batched once per company/period/request.
- Flexible shift readiness uses native Shift Assignment and native timestamp resolution. The app never enables HR Settings or creates a shift ledger.

## Read-only staging audit

Verified on hrms-v16.localhost on 2026-09-24; staging only:

- HRMS 16.19.0; Frappe 16.34.0; ERPNext 16.35.0.
- HR Settings.allow_multiple_shift_assignments = 0.
- 242 Active Employees; 237 active submitted Shift Assignments: 237 employees have one, 5 have none, 0 have more than one.
- Native Shift Types: TCL_Factory 08:00-17:00 and General Shift 09:00-18:00; both auto-attendance enabled, 60-minute margins, Half Day threshold 4 hours, Absent threshold 2 hours, overtime disabled. Native code reports these two default types overlap; they must not be put in one flexible pool.
- Effective pay basis as of 2026-08-31: 159 Daily Wage, 65 Monthly Salary, 18 Unresolved.
- August Attendance: 6,416 total rows and 0 submitted. Daily Wage population: 4,468 draft rows (2,794 Present, 1,674 Absent), 2,779 rows have positive hours, and 177 Present rows have missing/zero hours. There are 1,284 Daily Wage early-exit rows. These draft rows are not payroll/statutory evidence and were not submitted.
- Highest August early-exit counts (all employees, by Branch): Aug 4: 92; Aug 31: 84; Aug 28: 79; Aug 8: 78; Aug 5: 61; Aug 20: 58. These are review candidates only.
- Existing enabled Tradexcel Payroll Policies: 5; Attendance Policies: 1; Policy Exceptions: 0. The old Payroll Policy has legacy daily-rate/hours/OT fields; this feature does not use it as financial authority. Managed Daily Wage remains the effective explicit pay basis plus Salary Structure Assignment.base; native Overtime Slip remains OT authority.
- Approved Flexible Work Policies: 0. Submitted Operational Day Overrides: 0. No real policy/override was created.

## Synthetic proofs

- Synthetic-only 8 paid hours / 7 full-day threshold: 8h -> 1.0 unit; 7h -> 1.0; 6h -> 0.75; 4h -> 0.5; 0h/Absent -> 0; 9h -> base 1.0 (OT remains separate).
- Native payroll integration used disposable Attendance/SSA/Salary Structure/policy/override documents and a rollback savepoint. Native baseline units were 2.25. A 6-hour Attendance with approved Operational Day Override raised only its unit from 0.75 to 1.0: 2.5 units x synthetic SSA.base BDT 350 = BDT 875. Preview impact was BDT 87.50. Native Additional Salary was consumed by a native draft Salary Slip at BDT 875.
- Changing the synthetic Attendance hours after override approval produced OPERATIONAL_DAY_OVERRIDE_PREVIEW_STALE; restoring the approved value returned a clean preview.
- Native Shift Assignment proof created three synthetic, non-overlapping Morning, Evening, and cross-midnight Shift Types/assignments in a rollback transaction. Native get_employee_shift resolved morning and evening checkin timestamps on successive days and both sides of the cross-midnight shift. The site HR setting was restored to 0.
- Cleanup verification found zero synthetic policy, override, flexible shift child, Salary Structure, SSA, Attendance, Attendance Period, Daily Wage Additional Salary, Shift Type, or Shift Assignment records after rollback. No employee master was created or changed.
- No custom shift detector/ledger or OT money math was added. The test created only the native derived Additional Salary and draft Salary Slip inside a rolled-back synthetic transaction; no real payroll or Attendance rows were changed.

## Migration and verification

A full --with-files backup was verified before schema migration and another after a first standard migration stopped on the missing minimal child DocType controller. The controller was added and the standard bench --site hrms-v16.localhost migrate completed on retry; approver cancellation permission was then synced by a second standard migration after a fresh verified backup. No manual metadata convergence was used. Backups/checksums are recorded in BACKUPS.md.

bench --site hrms-v16.localhost clear-cache and bench build --app tradex_hr passed using Node 24.15.0. Build reported only the existing outdated Browserslist database notice. Visual Desk/browser E2E was not verified; keep it as a release gate.

## Business decisions and release gates

Management must approve standard paid hours, full-day threshold, proportional short-hours treatment, allowed shift pool, whether to enable native multiple assignments, mass-release candidate thresholds, and authority to declare shutdown days. Reconcile the 177 draft Daily Wage Present rows missing work hours and the staging population of 16,077 draft/0 submitted Attendance before statutory or payroll use.

No real 7/8 rule is active. No production or real employee/payroll records were changed.

## Final hardening verification

- Readiness ignores a policy scoped entirely to another Branch, but reports review if historical Attendance contexts cross a policy boundary. Flexible shift readiness now requires each allowed native Shift Assignment to cover the full requested period.
- Operational override preview resolves employees' native Holiday Lists in batches and respects Payroll Settings.include_holidays_in_total_working_days; those inputs participate in preview staleness. Known Monthly employees do not block a Daily Wage pay override; unrelated Branch overrides do not block other employees. Missing/ambiguous pay authority and contradictory positive hours on Absent/On Leave remain review findings.
- Focused attendance, payroll, and flexible-work tests: 74 passed. Full Tradexcel suite: 500 passed, 2 skipped on the final implementation; two later test-only cases (leave parity and a 20-person mass-release sample) passed in the final focused run. The full suite reported 35 existing Frappe v17 deprecation warnings. The suite reported 35 existing Frappe v17 deprecation warnings. Compileall, DocType JSON parsing, staged diff checks, and bench build passed.
- Post-test staging audit: 242 Active Employees, 237 active submitted Shift Assignments, 16,077 draft and 0 submitted Attendance rows; multiple-shift setting remains 0. Flexible policies, overrides, child rows, and all disposable native payroll/shift artifacts are 0.
