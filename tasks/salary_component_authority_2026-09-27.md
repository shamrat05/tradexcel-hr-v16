# Explicit salary component authority — 2026-09-27

## Finding and caller audit

At the accepted head, `payroll_rules.py` exposed an implicit 60/30/5/5 split through `calculate_wage(gross)` and still contained an unused dated-pay helper that priced work from `Workforce Payroll Policy.daily_wage`. No managed payroll path called either helper. The legacy split API and dated-pay adapter are removed; pure attendance/overtime helpers remain and require explicit work-policy inputs. `native_payroll.py` delegates Monthly Salary to HRMS and derives Daily Wage money from finalized Attendance plus effective submitted SSA.base.

The managed Daily Wage path also hardcoded the Salary Component name `Daily Wage` in `daily_wage_input.py` and `native_payroll.py`; callers could override it at input creation. That constant and override are removed. Historical `salary_setup.yaml` remains a manually invoked COMPANY_A migration specification and now explicitly maps its `daily_wage_component` key to the native Salary Structure field. It is not generic install behavior.

## Authority and validation

Native Salary Structure now owns `custom_workforce_daily_wage_component` (Link to Salary Component, no default, conditional on Daily Wage, not editable after submit). The same source-owned metadata convergence path owns this field and `custom_workforce_pay_basis`. A narrow Salary Structure validate hook requires a Daily Wage component that exists, is an Earning, appears exactly once in Earnings, and is neutral: no payment-day dependency, formula, or nonzero amount. Monthly Salary structures reject a populated Daily Wage component.

Pay-basis snapshots batch both native Structure fields in the existing report context. A Daily Wage assignment with missing component configuration is unresolved. The managed native Additional Salary input takes its component only from that resolved Structure, includes component identity in its idempotency key and payroll fingerprint, and blocks old derived inputs for the same period/revision when component authority differs. No submitted historical Additional Salary, SSA, Salary Structure, or payroll document is rewritten.

## Portability and tests

Native payroll integration uses a synthetic nonstandard component (`Synthetic Day Rate …`) and proves the derived Additional Salary and native draft Salary Slip use that component. Bulk SSA tests use synthetic `Factory Day Rate …` configuration. A payroll-readiness migration preview no longer displays sample component names; it directs the operator to configure the component on the native Structure. Generic install creates metadata only and does not seed components, structures, assignments, or wages. Explicit historical COMPANY_A values remain only in the migration YAML.

Focused suites: 75 passed, 0 skipped. Full Workforce suite: 684 passed, 0 skipped (final run). One stale report-authorization fixture was converted to a synthetic neutral Daily Wage component and its isolated regression passed before the final full run. Post-suite marker audit found zero synthetic payroll components, structures, or persona records left by this slice.

## Staging backup and migration

Required because this change adds Salary Structure metadata. Before migration, `bench --site hrms-v16.localhost backup --with-files` completed at 2026-09-27 16:49:54 Asia/Dhaka. Prefix `20260927_164954-hrms-v16_localhost-`. Database gzip and public/private tar listings verified. File sizes and SHA-256 hashes are recorded in `BACKUPS.md`. Standard `bench migrate` and `bench clear-cache` completed; no direct metadata SQL was used.

## Read-only staging configuration audit

One submitted Daily Wage Salary Structure is present: `Example Daily Wage`, Company `Example Company A`, blank `custom_workforce_daily_wage_component`, 159 submitted Salary Structure Assignments. It is intentionally `NEEDS ATTENTION / BLOCKED` for managed Daily Wage payroll. No component was backfilled and no real Salary Structure or assignment was changed.

## Safety

Staging schema migration only. No real Salary Component, Salary Structure, Salary Structure Assignment, Attendance, Additional Salary, Payroll Entry, or Salary Slip was changed. Production was not touched. Owner/company configuration remains required before managed Daily Wage payroll can proceed for that existing structure.
