# Mixed pay basis and Daily Wage input — 2026-09-23

Branch: `feat/mixed-pay-basis-wage-input`
Base: `a36582263e9845f3d2b7d132e6297eebf9d798a3`
Staging only: `hrms-v16.localhost`
Production touched: **NO**

## Decision

HRMS v16 has one site-wide `Payroll Settings.payroll_based_on`; it has no
per-employee or per-structure override. The site remains `Leave`. Switching the
whole site to `Attendance` would change monthly salaried semantics, so it was
rejected.

The financial authority is now:

```text
submitted Salary Structure Assignment (effective date + base)
        ↓
assigned Salary Structure.custom_tradex_pay_basis
        ↓
Monthly Salary | Daily Wage | explicit blocker
```

`Employee.employment_type`, branch, department, designation and naming are not
financial pay-basis authorities. `Tradexcel Payroll Policy.daily_wage` remains
available for policy comparison/legacy review, but the new production input
path never uses it to calculate money. SSA `base` is the only daily-rate source.

## Implemented

- `custom_tradex_pay_basis` on native Salary Structure, populated only from the
  declarative YAML values (`TCL Standard`, `TCL Daily Wage`, `EFL Standard`).
- `resolve_pay_basis()` with explicit `UNRESOLVED`, `CONFLICT`, and
  `MID_PERIOD_CHANGE` outcomes. Same-effective-date assignment corruption and
  mixed-period changes fail closed.
- Attendance finalization uses native Payroll Entry coverage for global
  Attendance payroll plus employees whose explicit pay basis is Daily Wage.
  Monthly Leave-based staff are not forced into factory Attendance coverage.
- `daily_wage_input.py` reads submitted native Attendance, uses the effective
  SSA `base`, and emits/reuses one native Additional Salary per finalized
  Attendance Period revision. It does not read Employee Checkin and refuses the
  old `base * payment_days` structure.
- Daily Wage and Overtime Pay are declared non-prorated component inputs. The
  existing linked staging structure is not rewritten automatically; Frappe
  correctly prevents canceling a submitted structure with submitted assignments.
  A native effective-dated structure/assignment migration is required before
  real Daily Wage inputs are enabled.

## Native evidence

Installed HRMS v16 behavior inspected:

- Salary Slip selects the latest submitted Salary Structure Assignment with
  `from_date <= actual_start_date`.
- Payroll Entry narrows the employee period by date of joining and relieving
  date.
- `Additional Salary` is a native submitted payroll input; native Overtime Slip
  uses it and preserves `ref_doctype`/`ref_docname` provenance.
- Salary Slip formula evaluation plus `depends_on_payment_days` made the old
  staging structure produce approximately Tk417.31 for one forced payment day
  and Tk4,173.08 for ten, instead of Tk350/Tk3,500. This is why the old shape is
  blocked rather than patched with another formula.

The disposable native integration test creates a safe structure, submitted SSA,
submitted Attendance, and native Additional Salary inside a database savepoint:

```text
10 submitted Attendance days × SSA.base Tk350 = Tk3,500
second generation attempt = existing input, no duplicate
native Salary Slip Daily Wage earning = Tk3,500
```

The test also proves native joiner payroll dates are narrowed by Payroll Entry.
No Salary Slip or Additional Salary from the experiment remains after rollback.

## Staging operation

Fresh full backup before schema migration:

```text
2026-09-23 02:20:14 Asia/Dhaka
20260923_022014-hrms-v16_localhost-database.sql.gz
SHA-256: a9270da06feda7404c0f80fbb143b7fe90c2de7bd771bcc4fc52f0682f24f72e
```

`gzip -t` passed. Migration of only `hrms-v16.localhost` succeeded after the
metadata-only hook was corrected to use `db.set_value`; it does not cancel linked
Salary Structures or touch payroll documents.

Post-migration metadata is present on all three declared structures. Current
TCL staging still has the old linked `TCL Daily Wage` child formula and is
therefore intentionally blocked. Current September Attendance inspection finds
159 `ATTENDANCE_UNMARKED` Daily Wage employees, 0 monthly payroll-only blockers
in the Attendance decision, and no global Payroll Settings change.

## Alternatives not chosen

- Global `Payroll Settings = Attendance`: rejected because it is site-wide and
  would silently change monthly Leave-based staff.
- Salary Slip controller monkey-patch: rejected; it duplicates/fights native
  HRMS calculation and has no clean per-employee hook.
- Custom wage ledger/second payroll engine: rejected; native Additional Salary
  already provides the audited payroll-input boundary.

## Release gates

1. Create/converge a safe Daily Wage structure through native effective-dated
   Salary Structure Assignment changes; do not rewrite the submitted linked
   legacy structure.
2. Resolve the current 159 missing Attendance records for the intended payroll
   period before finalization.
3. Review the native Additional Salary input generation with Payroll Entry on
   synthetic/staging data before any real submission.

## Verification

- Focused tests: **25 passed, 1 warning**.
- Full app suite: **201 passed, 2 skipped, 1 warning**.
- Compilation: **passed** with `/home/sanchita/frappe-bench-v16/env/bin/python -m compileall -q tradex_hr`.
- `git diff --check`: **passed**.
- Temporary native records: savepoint-rolled back; no real Salary Slip or
  Additional Salary was submitted.
