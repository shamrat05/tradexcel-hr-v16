# Measured performance / asynchronous execution — 2026-09-27

Parent PR #40: `273c64ff22e0bea0a232aca61fc4a8dc594ff881`.
Branch `perf/measured-hrms-pass`.

## Measurement

Read-only current staging workload: **240 permitted Employees**, synthetic
Company-scoped HR Manager + Payroll Manager, no native HR/System Manager role.
Two calls per operation; figures below use the second (warm) call. SQL count is
instrumented at the installed `frappe.db.sql` boundary. These are local response
measurements, not concurrency/P95 or production capacity claims. No employee
names, amounts or bank data were exported; the temporary user was removed.

| Operation | Before seconds / SQL | After seconds / SQL |
| --- | ---: | ---: |
| Employee scope | 0.0030 / 5 | 0.0025 / 5 |
| Employee search | 0.0018 / 2 | 0.0012 / 2 |
| Daily Attendance Board | 0.0221 / 6 | 0.0285 / 6 |
| Salary Coverage | 0.1834 / 472 | 0.0132 / 12 |
| Native Shift preview | 0.0017 / 1 | 0.0021 / 1 |
| Native Leave preview | 0.0070 / 7 | 0.0069 / 7 |
| Working-time rule readiness | 0.0015 / 4 | 0.0020 / 4 |
| Direct native-payroll readiness | 0.9605 / 2391 | 0.9393 / 2391 |
| Direct Payroll Readiness report | 1.1781 / 3346 | 1.1706 / 3346 |
| Action Board | 2.7860 / 7280 | 0.5450 / 1474 |

## Narrow optimization

Repeated per-Employee SSA, Salary Structure basis and joining-date reads were the
measured dominant Action Board/Salary Coverage issue. A context-local, explicitly
read-only batch snapshot loads these facts in three queries. The existing
canonical `resolve_pay_basis` still decides amounts, explicit basis, dates,
same-date conflicts, mid-period changes and joining dates. It is not a new pay
resolver or global authority cache. Nested read-only calls reuse the snapshot;
normal and exceptional exits reset it. Non-financial Action Board personas do
not prefetch salary facts. Independent preparation/submission calls get fresh
native state; mutation paths never enter this read context.

No authorization removed, shared cross-user cache, index, native controller
fork, or speculative optimization. Direct payroll preparation/readiness remains
unchanged; its roughly one-second local result does not justify expanding this
slice. Real configured-company payroll volume and concurrent-user timing remain
staging rehearsal evidence, not a claim of production load testing.

## Real asynchronous proof

The durable integration test sends **31 synthetic Employees** through the native
Shift Assignment Tool threshold and actual Frappe enqueue serialization. Only
the queue destination is isolated. A real RQ worker executes installed Frappe
`execute_job`, actor hooks, native shift processing and commit. Result: 31 native
submitted Shift Assignments. Replayed selection creates no duplicate.

A second queued date is dispatched while the maker is authorized, then its
synthetic Branch User Permission changes before a new real worker runs. The job
fails and creates no additional assignments. No Attendance, Checkin, SSA or
Salary Slip is created. Worker runs with scheduler disabled and consumes only
its unique test queue; job/queue/error records and all synthetic native records
are cleaned. No singleton, site worker configuration or real permission changes.

Existing synthetic native Payroll Entry integration still proves preparation,
partial submit/retry, no duplicate slips, accrual and payment. Its >30 dispatch
is a controlled spy; this phase's live 31-row worker proof is **Shift**, not a
claim of live 240-employee payroll execution.

No metadata/JS changed; no migration, backup or asset build required.
Final validation/cleanup recorded below.

## Validation and cleanup

Focused report/resolver authorization: 14 passed; final parity: 1 passed.
Actual isolated worker integration: 1 passed. Full suite: **629 passed,
0 skipped**, 97 warnings, 479.75 seconds. Compileall, all 61 app JSON files
and diff-check passed. Synthetic persona/permission/Employee/shift/financial
markers and the isolated queue were explicitly cleaned; zero leftovers.
