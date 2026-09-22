# Tradexcel HR v16 — canonical engineering guide

This directory is the **implementation contract** for agents working on the v16 HRMS.
It converts the Bangladesh failure-mode research, the current v16 staging repo, and
Frappe/HRMS v16 capabilities into an ordered build plan.

## Read in this order

1. [00_CURRENT_STATE_AND_DECISIONS.md](00_CURRENT_STATE_AND_DECISIONS.md)
2. [01_CANONICAL_FLOW_AND_SOURCE_OF_TRUTH.md](01_CANONICAL_FLOW_AND_SOURCE_OF_TRUTH.md)
3. [02_NATIVE_V16_CAPABILITY_MAP.md](02_NATIVE_V16_CAPABILITY_MAP.md)
4. [03_ATTENDANCE_BIOMETRIC_MOBILE.md](03_ATTENDANCE_BIOMETRIC_MOBILE.md)
5. [04_PAYROLL_SAFETY_AND_COMPLIANCE.md](04_PAYROLL_SAFETY_AND_COMPLIANCE.md)
6. [05_EXCEPTIONS_AUTOMATION_AND_UX.md](05_EXCEPTIONS_AUTOMATION_AND_UX.md)
7. [06_SECURITY_PRIVACY_ROLES.md](06_SECURITY_PRIVACY_ROLES.md)
8. [07_MULTI_COMPANY_CONFIGURATION.md](07_MULTI_COMPANY_CONFIGURATION.md)
9. [08_TEST_ACCEPTANCE_MATRIX.md](08_TEST_ACCEPTANCE_MATRIX.md)
10. [09_IMPLEMENTATION_CHUNKS.md](09_IMPLEMENTATION_CHUNKS.md)
11. [10_RELEASE_MIGRATION_RECOVERY.md](10_RELEASE_MIGRATION_RECOVERY.md)
12. [11_AGENT_HANDOFF_TEMPLATE.md](11_AGENT_HANDOFF_TEMPLATE.md)

Root **AGENTS.md** is the enforcement entry point.

## Safety contract

The system is built around three boundaries:

~~~text
EVIDENCE                       APPROVED HR STATE              FINANCIAL STATE
──────────────────────         ──────────────────────         ─────────────────────
raw device/mobile event   ->   Employee Checkin         ->   Payroll Entry
device time + receive time     Attendance                    Salary Slip
GPS/selfie/face evidence       approved Leave                Additional Salary
                               approved Overtime             Journal Entry / payment
~~~

A downstream state may be derived from an upstream state, but later changes must
never silently mutate an already-approved financial result.

### Non-negotiable rules

- Native Frappe/HRMS records remain canonical where v16 already owns the concept.
- Employee Checkin is evidence. Attendance is the payroll-facing work-state.
- Payroll must not calculate money directly from raw punches.
- Critical ambiguity blocks payroll; it does not block evidence ingestion.
- Salary, pay basis, shift and legal rules are effective-dated.
- Submitted payroll is immutable history. Retroactive differences use native v16
  correction/arrear mechanisms where they fit.
- Every monetary result must be explainable from versioned inputs.
- Financial writes must be idempotent.
- Privileged actions require named users, record scope, and server-side checks.
- Low-skill operators work from tasks and exception queues, not schema knowledge.
- Biometric, face and live-location data is sensitive; collection, access and
  retention require an approved data-protection basis.
- Bangladesh statutory values are configuration approved from authoritative
  sources, not constants invented by developers.

## What "done" means

A feature is not done because its page loads or a unit test passes. A slice is done
only when:

1. its source of truth is explicit;
2. the normal path is automated or guided;
3. ambiguous cases become actionable exceptions;
4. authorization is enforced server-side;
5. retries are idempotent where money/evidence is involved;
6. negative, boundary, concurrency and recovery tests exist;
7. staging migration and rollback are documented;
8. no production/live data was changed by the agent;
9. evidence of verification is recorded in the task/PR;
10. the next agent can understand the state without reading chat history.

## Priority legend

- **P0** — can silently create wrong/legal-unsafe pay, identity, or irreversible
  financial history. Blocks production.
- **P1** — serious security, integrity, operational or privacy risk. Must close
  before broad rollout.
- **P2** — usability/resilience/maintainability improvement. May follow a safe core.

## Research basis

The architecture incorporates the 2026 Bangladesh HRMS/payroll deep-research report
supplied for this project, the staging audit under **tasks/**, current Frappe/HRMS
v16 source inspection, and current authoritative Bangladesh legal sources. Legal
implementation still requires organization-specific review: this is a control
framework, not legal advice.
