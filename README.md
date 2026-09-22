# Tradexcel HR v16

Custom Frappe/ERPNext/HRMS application for Tradexcel HR operations.

This repository is the **v16 target**. The application is being evolved from a
working v15-era custom layer into a native-first, error-safe HRMS control layer for
Bangladesh operations.

## Start here

| Read | Purpose |
|---|---|
| **AGENTS.md** | mandatory coding-agent safety and workflow rules |
| **docs/architecture/README.md** | canonical architecture handbook |
| **docs/architecture/09_IMPLEMENTATION_CHUNKS.md** | chunk-by-chunk build order |
| **docs/architecture/08_TEST_ACCEPTANCE_MATRIX.md** | permanent regression/acceptance contract |
| **docs/architecture/12_REQUIREMENTS_TRACEABILITY.md** | maps the deep research to implementation |
| **BACKUPS.md** | backup history and destructive-work prerequisite |
| **tasks/** | dated migration/audit/verification evidence |

## Verified v16 staging baseline

The architecture audit used the staging state recorded on **2026-09-22**:

- repository branch: feature/hrms-v16-hr-only
- audited commit: c9502d8d2b167d2847e97cf5632e72905ac18d92
- Frappe 16.34.0
- ERPNext 16.35.0
- HRMS 16.19.0
- app staging suite: **152 passed, 2 skipped**
- v16 asset build and route/report audits previously passed
- the migrated staging copy had 242 Employees, 22,302 Checkins, 16,077
  Attendance rows, 227 Salary Structure Assignments, 237 Shift Assignments and
  221 device-scoped biometric mappings
- staging had **0 Salary Slips** at that snapshot; migration did not invent payroll

These are dated staging facts. Re-read the current site before relying on counts.

## Architecture in one sentence

> Use native HRMS v16 as the system of record; let Tradexcel validate,
> orchestrate, integrate and simplify it; make normal cases automatic and route
> ambiguity into accountable exception workflows before it can become money.

## Three boundaries

~~~text
Evidence
  biometric/mobile/device events
        ↓
Approved HR state
  Checkin -> Attendance, Leave, Shift, OT, Compensation
        ↓
Financial state
  Payroll Entry -> Salary Slip -> Accounting / Payment
~~~

Raw Checkin is **not** payroll truth. Submitted financial history is not silently
rewritten after a later correction.

## What already exists

- v16 staging migration and repeatable migration evidence;
- custom salary setup/policy/exception modules;
- biometric bridge worker with durable sync state and device-scoped PIN mapping;
- attendance/anomaly reports;
- custom roles and approval workflows;
- mobile checkin with GPS/selfie policy;
- field-duty/live-location support;
- optional local face matching;
- a custom persistent HR rail and route coverage;
- extensive app tests.

The architecture guide deliberately preserves useful work while identifying what
must be replaced by stronger native-v16 functionality.

## Highest-priority remaining architecture work

### P0

1. Contain and retire the custom manual payroll engine after native v16 parity.
2. Remove hidden/external compensation fallback; missing compensation blocks.
3. Make pay basis explicit instead of Worker == Daily Wage.
4. Stop payroll from reading raw Employee Checkin.
5. Use native v16 overnight shift context.
6. Correctly resolve joiner/leaver and mid-period compensation intervals.
7. Add payroll readiness and Attendance finalization gates.
8. Version/approve applicable Bangladesh statutory/tax configuration.
9. Prove draft native payroll end-to-end in staging before any production cutover.

### P1

- migrate the custom desktop rail to native v16 Workspace Sidebar fixtures;
- end-to-end mobile idempotency across browser timeouts;
- device completeness and effective biometric-ID history;
- server-side manager record scope;
- field-duty allowance approval/reversal;
- face/location privacy and retention lifecycle;
- real user/role/User Permission UAT;
- accounting/payment readiness and reconciliation;
- CI and restore rehearsal.

See **docs/architecture/00_CURRENT_STATE_AND_DECISIONS.md** for the detailed audit.

## Native v16 changes the plan

The project must not blindly carry v15 custom behavior forward.

Current HRMS v16 includes capabilities that should be evaluated/reused first,
including:

- native persistent Workspace Sidebar;
- cross-midnight shift actual windows;
- Auto Attendance;
- Overtime Type / Overtime Slip;
- Payroll Entry / Salary Slip;
- Payroll Correction;
- Arrear.

The custom app should be thinner because v16 is stronger.

## Code map

| Area | Current code |
|---|---|
| salary templates/import | tradex_hr/tradexcel_hr/salary_setup.py, salary_setup.yaml, salary_excel.py |
| legacy/manual payroll | tradex_hr/tradexcel_hr/run_payroll.py, payroll_rules.py |
| policy resolution | payroll_policy.py, effective_policy_rules.py |
| deductions/exceptions | deduction_rules.py, component_exceptions.py, tax_exceptions.py |
| anomaly detection | anomaly_checks.py and reports |
| device ingest | tradex_hr/tradexcel_hr/biometric/ |
| mobile/field attendance | field_attendance.py, field_attendance_service.py |
| face match | face_match.py |
| permissions/workflows | tradex_hr/role_setup.py, tradex_hr/approval_setup.py |
| Desk UI | tradex_hr/public/js/, public/css/ |
| tests | tradex_hr/tests/ |

## Rules that must not be broken

1. Native records remain canonical.
2. One source of truth for employee compensation.
3. No raw-punch-to-money path.
4. No financial guessing through ambiguity.
5. Effective dates are part of the data model.
6. Submitted payroll is immutable historical truth.
7. Retries cannot create duplicate evidence or money.
8. Statutory rules are approved/versioned data, not developer memory.
9. Sensitive biometric/location/face data is minimized, scoped and retained under
   an approved policy.
10. Production is not a coding sandbox.

## Building the system

Do **not** hand an agent the entire roadmap at once.

Assign one chunk from:

**docs/architecture/09_IMPLEMENTATION_CHUNKS.md**

Use:

**docs/architecture/11_AGENT_HANDOFF_TEMPLATE.md**

and require acceptance IDs from:

**docs/architecture/08_TEST_ACCEPTANCE_MATRIX.md**

This keeps every change reviewable, testable and recoverable.

## Production status

The repository is a strong v16 staging foundation, but this README does **not**
declare production payroll ready.

Production readiness requires the gates in
**docs/architecture/10_RELEASE_MIGRATION_RECOVERY.md**, including native payroll
parity, approved statutory/tax rules, real role/scope UAT, privacy/retention
review, draft payroll reconciliation, backup/restore rehearsal and controlled
cutover sign-off.
