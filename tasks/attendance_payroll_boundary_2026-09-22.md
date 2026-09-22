# Attendance → Payroll boundary — 2026-09-22

Branch: `feat/attendance-payroll-boundary`
Base: `fix/payroll-p0-safety` at `e390688`
Implementation commit: `bd06c27`
Site inspected: `hrms-v16.localhost` only. No production site was opened, no
salary slip was created or submitted, and no payroll data was changed.

## Native v16 findings

- `Payroll Entry.get_employees_with_unmarked_attendance()` is the native
  coverage check. It counts submitted `Attendance` rows and subtracts the
  employee's native Holiday List; the boundary calls this method instead of
  reproducing holiday math.
- `Salary Slip.get_working_days_details()` calculates `payment_days` from
  submitted Attendance when Payroll Settings is based on Attendance. It
  handles Present, Absent, Half Day, On Leave, holidays, and unmarked-day
  policy. A raw `Employee Checkin` is not a payroll state.
- `Salary Slip.set_salary_structure_assignment()` selects the submitted
  Salary Structure Assignment with `from_date <= actual_start_date`, ordered
  by `from_date desc`. The legacy payroll preflight follows the same rule and
  blocks a mid-period change rather than guessing.
- Native overtime is represented by `Attendance.overtime_type` and
  `actual_overtime_duration`, then reviewed/paid through submitted `Overtime
  Slip` and its native Additional Salary output.
- No native HRMS v16 Attendance Period finalize/reopen control was found.

## Daily-wage conclusion

The staging `TCL Daily Wage` structure currently contains a `Daily Wage`
formula equivalent to `base * payment_days` while the component is also marked
`depends_on_payment_days`. Native HRMS first evaluates the formula and then
applies payment-day proration to flagged components. That combination can
double-prorate a daily wage, so this branch does not claim that the current
structure is production-safe and does not alter it. The boundary reports
`UNSAFE_PAYMENT_DAY_FORMULA` until the structure is corrected and separately
retested.

## Implemented

`tradex_hr/tradexcel_hr/attendance_payroll_boundary.py` is a small read-only
boundary service. It:

- uses native Payroll Entry coverage;
- includes employees by employment-date overlap rather than current status;
- blocks mid-period joiners/leavers and unsupported employment statuses;
- blocks pending mobile evidence, ambiguous device/PIN identity, draft
  Attendance Requests, approved-leave/Attendance contradictions, unapproved
  native overtime, and unsafe payment-day formulas;
- hashes submitted native Attendance and submitted native Overtime Slip state;
- provides one `require_finalized_attendance()` gate for the later native
  payroll orchestration; it does not calculate money.

`Tradexcel Attendance Period` is the deliberately small control document:
company, date range, status, revision, finalization user/time, and a hash of
the native payroll inputs. Finalize refuses blocking findings. Reopen is
explicit. A later payroll integration can call the one gate and detect a late
Attendance/Overtime edit as stale.

The existing raw-checkin runner remains explicitly legacy/comparison-only. No
new production path calls `_checkin_records()` and the boundary module has a
regression assertion that it does not depend on it.

## Verification

Focused boundary/payroll tests:

```text
env/bin/pytest -q \
  apps/tradex_hr/tradex_hr/tests/test_attendance_payroll_boundary.py \
  apps/tradex_hr/tradex_hr/tests/test_attendance_payroll_contract.py \
  apps/tradex_hr/tradex_hr/tests/test_payroll_safety.py
```

Current verification result:

```text
focused boundary/payroll tests: 20 passed
full app suite from /home/sanchita/frappe-bench-v16: 182 passed, 2 skipped
py_compile: passed
git diff --check: passed
```

Read-only staging probe for TCL September 2026 used the native Payroll Entry
coverage method successfully. It returned `BLOCKED` for 238 employees, with
mid-period employment/attendance coverage findings and the known
`UNSAFE_PAYMENT_DAY_FORMULA` on `TCL Daily Wage`. This is a useful safety
result, not a payroll run: no document was inserted, changed, or submitted.

Running the suite from the app directory alone still reproduces the older
fixture-path failure (`apps/tradex_hr/hrms-v16.localhost/logs/database.log`).
The supported bench-root command above passes the explicit v16 sites path and
is the authoritative result.

Not yet performed: an Android airplane-mode test (mobile release gate), a
real native Payroll Entry run, and a staging migration for the new control
DocType. Those require explicit staging execution and are not simulated by
unit tests.
