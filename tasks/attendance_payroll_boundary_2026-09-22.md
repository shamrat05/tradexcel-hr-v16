# Attendance → Payroll boundary — 2026-09-22

Branch: `feat/attendance-payroll-boundary`
Base: `fix/payroll-p0-safety` at `e390688`
Site inspected/migrated: `hrms-v16.localhost` only
Production touched: **NO**

No Salary Slip was created or submitted. The only staging data operation was a
backup followed by migration to install the new Attendance Period DocType.

## Native v16 behavior verified

- `PayrollEntry.get_employees_with_unmarked_attendance()` is the native
  Attendance coverage check. It uses submitted Attendance and the employee's
  native holiday list; the app does not reproduce that holiday math.
- `SalarySlip.get_working_days_details()` uses `Payroll Settings.payroll_based_on`.
  It calculates `payment_days` from Attendance only when the setting is
  `Attendance`; `Leave` uses native Leave Application semantics.
- `SalarySlip.set_salary_structure_assignment()` selects the latest submitted
  assignment with `from_date <= actual_start_date`.
- Native Leave Application `update_attendance()` excludes holiday dates when
  the Leave Type does not include holidays. The custom date-by-date leave
  contradiction loop was therefore removed.
- Native overtime starts from submitted Attendance overtime fields and is
  paid through submitted `Overtime Slip`/Additional Salary. Pending OT is a
  payroll-readiness issue, not an Attendance validity issue.
- No native v16 Attendance Period finalize/reopen control was found, so the
  small Tradexcel control document remains justified.

## Separation implemented

`inspect_attendance_integrity()` now contains only Attendance Officer concerns:

- native unmarked Attendance, but only when Payroll Settings is based on
  Attendance;
- pending mobile time-integrity evidence;
- ambiguous enrolled device/PIN identity;
- draft Attendance Requests.

`inspect_payroll_readiness()` keeps the later payroll-only findings available
without making Attendance finalization noisy:

- mid-period joining/leaving and unsupported employment status;
- unsafe payment-day salary formulas;
- unapproved native overtime.

The old combined function name remains as a compatibility alias to Attendance
integrity. No payroll calculation or Payroll Readiness UI was added.

## Daily wage native experiment

Staging structure: `TCL Daily Wage`
Assignment base: `Tk 350`
Native generated working/payment days for the September test slip: `26/26`
Configured formula: `base * payment_days`
Configured flag: `depends_on_payment_days = 1`

Using the real native `SalarySlip` component path without saving a Slip:

| Payable days | Expected at Tk 350/day | Current native result |
|---:|---:|---:|
| 1 | Tk 350 | Tk 417.31 |
| 10 | Tk 3,500 | Tk 4,173.08 |

The structure is therefore correctly reported as
`UNSAFE_PAYMENT_DAY_FORMULA`. This branch does not modify real salary data.
The native-safe regression uses the smallest configuration change conceptually:
keep the formula and remove the second `depends_on_payment_days` proration;
that configuration produces Tk 350 and Tk 3,500 through the native component
path in tests. The actual staging structure remains unchanged for the later
payroll work.

## Attendance Period control

`Tradexcel Attendance Period` is the minimal control document for company and
exact date range. It stores status, revision, finalization user/time, and a
fingerprint of payroll-relevant submitted Attendance fields only:

`employee`, `attendance_date`, `status`, `leave_type`, `leave_application`,
`half_day_status`, and `docstatus`.

`modified`, notes, custom metadata, and overtime state do not make Attendance
finalization stale. Exact duplicate company/date periods are rejected, and the
payroll gate requires exactly one finalized exact period. Status changes must
use Finalize/Reopen actions; direct edits are rejected.

## Staging findings

Before separation, the September 2026 inspection returned 240 findings:

| Code | Count |
|---|---:|
| `ATTENDANCE_UNMARKED` | 238 |
| `BLOCKED_JOIN_MID_PERIOD` | 1 |
| `UNSAFE_PAYMENT_DAY_FORMULA` | 1 |

After separation, Attendance integrity is `READY` with 0 blockers. The later
payroll-readiness inspection reports:

| Code | Count |
|---|---:|
| `BLOCKED_JOIN_MID_PERIOD` | 1 |
| `UNSAFE_PAYMENT_DAY_FORMULA` | 1 |

Staging Payroll Settings inspected:

- `payroll_based_on`: `Leave`
- `include_holidays_in_total_working_days`: `0`
- `consider_unmarked_attendance_as`: `Present`
- `consider_marked_attendance_on_holidays`: `0`

## Backup and migration

Fresh staging backup: `20260923_011812-hrms-v16_localhost-*` under
`sites/hrms-v16.localhost/private/backups/`.

Verified with `gzip -t`, `tar -tf` for both file archives, and SHA-256:

```text
database.sql.gz  e4175dbce66b1b15fca9f31984122b4977f7f17d0fc5d889e4d1f9410276f917
files.tar        407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532
private-files.tar 7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe
```

Migration completed successfully for `hrms-v16.localhost` only. The new
`Tradexcel Attendance Period` DocType exists on staging.

## Verification at final working head

Focused:

```text
14 passed
```

Full app suite:

```text
188 passed, 2 skipped
```

Additional checks:

```text
/home/sanchita/frappe-bench-v16/env/bin/python -m compileall -q tradex_hr: passed
git diff --check: passed
```

The authoritative test command uses the v16 bench root and explicit
`FRAPPE_TEST_SITE=hrms-v16.localhost` and
`FRAPPE_TEST_SITES_PATH=/home/sanchita/frappe-bench-v16/sites`.

## Remaining gates

- Android airplane-mode E2E for the frozen mobile branch is still required
  before mobile release; no ADB device was used here.
- The unsafe staging daily-wage structure needs a separate payroll change and
  review; it was not silently migrated.
- The next branch is the Attendance-finalization → payroll-input integration.
  Native Payroll Entry/Salaries remain deliberately out of this branch.
