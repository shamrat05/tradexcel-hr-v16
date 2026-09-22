# 00 — Current v16 state, gaps, and architecture decisions

## Repository baseline

Repository: **shamrat05/tradexcel-hr-v16**

Baseline audited for this guide:

- branch: **feature/hrms-v16-hr-only**
- commit: **c9502d8d2b167d2847e97cf5632e72905ac18d92**
- staging: Frappe 16.34.0, ERPNext 16.35.0, HRMS 16.19.0
- staging app suite: **152 passed, 2 skipped**
- staging data snapshot after migration:
  - 242 Employee
  - 22,302 Employee Checkin
  - 16,077 Attendance
  - 227 Salary Structure Assignment
  - 237 Shift Assignment
  - 221 device-scoped biometric mappings
  - 0 Salary Slip

These are **dated staging facts**, not promises about current production.

## What the repo already does well

Do not rewrite these casually.

| Area | Existing capability | Direction |
|---|---|---|
| Device ingestion | device-scoped identity, durable sync state, retry status, idempotent event key | **KEEP / extend** |
| Policy overrides | submitted Tradexcel Policy Exception, effective dates, preview signature | **KEEP as policy override** |
| Anomaly detection | punch, attendance, payroll, leave and tax checks | **REUSE as detectors** |
| Roles/workflows | named Tradexcel roles; no-self-approval on attendance/leave/payroll workflows | **KEEP / harden scope** |
| Mobile attendance | GPS/selfie policy, sync event, field duty, live pings, optional face match | **KEEP / harden** |
| v16 staging | isolated bench/site/db, repeatable backups, migration records | **KEEP** |
| Script reports | v16 standard Script Report repair and explicit roles | **KEEP** |

## P0/P1 findings that remain

### P0 — custom payroll runner is a second payroll engine

**tradex_hr/tradexcel_hr/run_payroll.py** manually constructs Salary Slips,
suppresses native working-day/component calculation, reads raw Employee Checkin
for daily workers, computes payment days/OT itself and commits per employee.

That violates the desired boundary:

~~~text
Checkin evidence -> finalized Attendance -> native Payroll Entry/Salary Slip
~~~

It must be retired as the eventual production calculation engine after parity
tests prove the native v16 path.

### P0 — current monthly branch contains an undefined fallback variable

The current runner references **source_record** when assignment base is empty
without assigning it first. More importantly, production payroll should not
silently seed salary from an external Selevo JSON file at all.

Decision: **empty/ambiguous compensation becomes a blocking readiness case.**

### P0 — calendar-date punch grouping breaks overnight work

The manual runner groups punches by timestamp calendar date. A 22:00 IN and 06:00
OUT becomes two broken dates. HRMS v16 already has shift actual start/end fields
and native cross-midnight shift resolution. Custom payroll must stop re-pairing
punches.

### P0 — pay basis is inferred from Employee.employment_type

Current custom policy resolution maps Worker to Daily Wage, while historical data
contains employees called Workers with monthly compensation.

Decision: pay basis is **explicit and effective-dated**. Employment Type may
suggest a default in a setup wizard but can never be the financial authority.

### P0 — mid-period salary/join/relieve handling is unsafe in manual runner

Selecting the latest assignment with from_date <= period_end can apply a raise to
the whole month. Monthly slips currently pass full calendar days. Native v16
behavior and any Tradexcel extension must be proved with permanent fixtures for
joiners, leavers, and mid-period changes.

### P1 — current custom desktop rail duplicates Frappe v16 native Sidebar

Frappe v16 already provides a persistent, collapsible Workspace Sidebar with route
activation, collapse state, search, notifications, nested sections, filters and
route options. HRMS v16 ships standard sidebars for Payroll, Shift & Attendance,
Leaves, Recruitment, Expenses, Performance, Tax & Benefits and HR Setup.

Current Tradexcel JS/CSS hides the native desktop sidebar and maintains a parallel
rail; several recent commits are repair work for shell replacement, boot timing and
active-route state.

Decision: **migrate the Tradexcel information architecture to native v16 Workspace
Sidebar fixtures**. Keep custom JS only for a measured gap native v16 cannot meet.

### P1 — role definitions exist, real user/record scope is not production-proven

The staging audit found Tradexcel roles but no real operational user assignments.
Role capability is not equivalent to record scope. Company/branch/department scope
must be enforced and tested server-side.

### P1 — mobile retry is not end-to-end idempotent

The server honors a repeated sync ID, but the browser generates a fresh ID on each
action. If the server commits and the response is lost, a user retry may send a new
ID and create another checkin.

Decision: the client persists the same operation ID until acknowledgement.

### P1 — active location has no durable client retry queue

Failed live pings are currently ignored by the browser and the watch continues.
This is acceptable only if pings are explicitly best-effort and never used as pay
evidence. If policy requires evidence completeness, a durable offline queue and
visible sync state are required.

### P1 — sensitive location visibility needs record scope

The live-locations service checks roles, but the final service must also restrict
company/branch/department/employee scope. A manager role alone must not grant
organization-wide live-location visibility.

### P1 — retention setting exists without a demonstrated retention job

Attendance Policy has retention_days, but collection without a purge/retention
process is incomplete. Selfies, face evidence and live-location history require a
documented lifecycle.

### P1 — Field Duty allowance path needs stronger lifecycle guards

The allowance service is idempotent by allowance key, but must prove:

- duty is in the allowed completed/approved state;
- selected policy is the policy frozen for the duty;
- allowance_requires_approval is honored;
- maker/checker applies where money is affected;
- repeated OUT/retry never creates duplicate Additional Salary;
- cancellation/rejection has defined downstream behavior.

## Architecture decisions

### ADR-001 — native-first

Before adding a custom DocType/service/field, inspect **the installed HRMS v16
version** and record one of:

- REUSE_NATIVE
- EXTEND_NATIVE
- CUSTOM_REQUIRED

A custom implementation without this decision is not mergeable.

### ADR-002 — no duplicate ledgers

Do not duplicate Employee, Checkin, Attendance, Leave, Shift, Salary Assignment,
Salary Slip, Payroll Entry, Overtime Slip, Arrear, Payroll Correction,
Additional Salary, Expense Claim, Employee Advance or accounting ledgers.

### ADR-003 — exception-first operations

Normal deterministic cases progress automatically. Users work on exceptions,
approvals and irreversible decisions.

### ADR-004 — three readiness gates

~~~text
Payroll readiness != Accounting readiness != Payment readiness
~~~

A missing bank account may block a bank payment batch without invalidating salary
calculation.

### ADR-005 — policy override != operational exception

Tradexcel Policy Exception is a submitted **configuration override**. A future
runtime work queue must use a different DocType/name, e.g. Tradexcel HR Case, so
configuration and operational anomalies never share lifecycle semantics.

### ADR-006 — historical financial state is immutable

Use native v16 Payroll Correction / Arrear mechanisms where suitable. Never
silently rewrite paid Salary Slips because a source record changed later.

### ADR-007 — legal configuration is versioned data

No country-specific rate hardcoded as timeless law. Legal regime, sector/wage
order, worker classification, tax year and rule version are explicit and reviewed.

### ADR-008 — privacy is architecture, not a checkbox

Biometric data and real-time geolocation are sensitive personal data under the
Bangladesh Personal Data Protection Act, 2026. Collection, role scope, retention,
export, breach response and deletion/archival behavior are implementation
requirements, not optional UI text.

## Production gate

Do not call this repository production-ready until the P0 slices in
**09_IMPLEMENTATION_CHUNKS.md** are complete, a draft-only end-to-end payroll is
reconciled in staging, record-scope UAT passes for real roles, and a restore
rehearsal succeeds.
