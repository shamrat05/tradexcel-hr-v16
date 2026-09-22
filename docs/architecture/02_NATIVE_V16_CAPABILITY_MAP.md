# 02 — Native Frappe/HRMS v16 capability map

## Why this file exists

V15-era assumptions are not safe for v16. HRMS v16 expanded navigation, shift
context, overtime, payroll correction and arrears. An agent must inspect the
installed v16 version before creating a custom equivalent.

Default question:

> Can native v16 own this concept, with Tradexcel adding validation or UX around it?

## Capability decisions

| Need | v16 capability observed | Decision |
|---|---|---|
| Persistent desktop navigation | Workspace Sidebar, nested items, route state, collapse state, search/notifications | **REUSE_NATIVE** |
| HR navigation taxonomy | standard HRMS sidebars for major modules | **EXTEND_NATIVE** |
| Cross-midnight shift context | Checkin shift actual start/end; native resolver | **REUSE_NATIVE** |
| Checkin -> Attendance | native Auto Attendance | **REUSE_NATIVE** |
| OT source data | Shift Type overtime + Attendance OT fields | **REUSE_NATIVE** |
| OT calculation/approval docs | Overtime Type / Overtime Slip / Details | **EVALUATE then reuse** |
| Payroll batch | Payroll Entry | **REUSE_NATIVE** |
| Salary result | Salary Slip | **REUSE_NATIVE** |
| Attendance validation in payroll | v16 Payroll Entry support | **REUSE / extend gate** |
| Retro LWP/pay correction | Payroll Correction | **REUSE_NATIVE where applicable** |
| Retro salary arrear | Arrear | **REUSE_NATIVE where applicable** |
| One-off pay | Additional Salary | **REUSE_NATIVE** |
| Expense/advance | Expense Claim / Employee Advance | **REUSE_NATIVE** |
| Leave | native HRMS leave docs/ledger | **REUSE_NATIVE** |
| User/role/scope | Frappe permissions/workflows | **REUSE_NATIVE** |
| Device-scoped PIN history | native single attendance ID is insufficient | **CUSTOM_REQUIRED** |
| SenseFace durable transport | not native HRMS transport | **CUSTOM_REQUIRED** |
| Field-duty GPS evidence | company-specific | **CUSTOM_REQUIRED / minimal** |
| Cross-domain payroll readiness | no single native control plane | **CUSTOM_REQUIRED validation layer** |
| Attendance period finalization | explicit freeze/reopen not equivalent to Auto Attendance | **CUSTOM_REQUIRED control layer** |
| Bangladesh rule provenance | jurisdiction/company-specific | **CUSTOM_REQUIRED configuration** |
| Unified operational case queue | detectors exist, no normalized queue in app | **CUSTOM_REQUIRED if needed** |

## Navigation decision

Current Tradexcel code hides the native desktop sidebar and injects a parallel
rail. That duplicates framework responsibilities and has already needed shell,
boot, active-route and route-repair fixes.

Target: standard v16 Workspace Sidebar fixtures.

Suggested structure:

~~~text
Home
People
Time & Attendance
Leave
Payroll
Finance
Compliance
Reports
Administration
~~~

Navigation visibility is convenience, not security. Server permission remains
authoritative.

### Migration rule

Do not delete the custom rail first.

1. build equivalent native sidebar fixtures;
2. add route/role tests;
3. Playwright workspace/list/form/report/calendar/payroll routes;
4. compare parity;
5. optionally feature-flag;
6. remove custom rail only after parity.

## Attendance/shift decision

Do not fix overnight work with another pairing algorithm. Use and test native:

~~~text
Employee Checkin.shift
Employee Checkin.shift_start
Employee Checkin.shift_end
Employee Checkin.shift_actual_start
Employee Checkin.shift_actual_end
Employee Checkin.attendance
Employee Checkin.overtime_type
~~~

Permanent fixture: Sep 22 22:00 -> Sep 23 06:00 with valid IN/OUT resolves to one
native shift context.

## Overtime decision

Current app has custom OT math, but v16 has native OT objects. Run a parity study:

1. configure native Overtime Type;
2. configure Shift Type native OT;
3. create native Attendance/Overtime Slip;
4. compare with approved Bangladesh/company policy;
5. test daily/weekly limits, holiday/rest day, rounding and special cases;
6. record actual gaps.

If native expresses the rule, retire duplicate custom OT math after migration.
If not, extend native documents narrowly.

## Retroactive corrections

Before inventing a new adjustment ledger, evaluate:

- Payroll Correction;
- Arrear;
- Additional Salary with the correct reference.

Tradexcel detects, previews, routes and reconciles; native payroll owns the money
where its semantics fit.

## Native-first ADR template

~~~markdown
### ADR-NNN — decision

Installed versions:
- Frappe:
- ERPNext:
- HRMS:

Problem:
Native candidates inspected:
Observed native behavior/tests:
Gap:
Decision: REUSE_NATIVE | EXTEND_NATIVE | CUSTOM_REQUIRED
Why:
Migration/rollback:
Tests:
~~~

## Upgrade resilience

Avoid undocumented DOM patches where a fixture/doctype/hook exists. Any core
layout CSS/JS patch needs a documented gap, minimal selector surface, route tests
and a removal plan.
