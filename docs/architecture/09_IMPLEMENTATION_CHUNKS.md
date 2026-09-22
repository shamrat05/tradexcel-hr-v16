# 09 — Implementation chunks for coding agents

## How to use this plan

Give an agent **one chunk at a time**. Do not ask an agent to "build the whole
HRMS". Each chunk has a bounded objective and acceptance gate.

Before any chunk, the agent must read root AGENTS.md and the architecture files
listed for that chunk.

## Phase 0 — freeze and prove baseline

### CHUNK-00 — baseline verification

**Priority:** P0 prerequisite

Read:

- 00 current state
- 08 tests
- 10 release/recovery

Tasks:

1. verify branch/site/bench identity;
2. run current app suite;
3. record installed Frappe/ERPNext/HRMS versions;
4. confirm production is not the target;
5. create task note with exact baseline.

Exit: clean baseline or documented pre-existing failures.

---

## Phase 1 — stop unsafe payroll behavior

### CHUNK-01 — emergency payroll runner safety

**Priority:** P0

Likely files:

- run_payroll.py
- payroll tests
- docs/task note

Tasks:

- remove undefined source_record path;
- remove implicit external salary fallback from production behavior;
- zero/missing base becomes explicit blocker/result;
- remove or deprecate no-op CLI flags;
- make site/path configurable if runner remains for staging comparison;
- no new salary calculation semantics.

Tests:

PAY-004, PAY-005, PAY-007 plus direct orchestration coverage.

Exit: runner cannot silently source money outside canonical assignment.

### CHUNK-02 — payroll runner containment

Mark manual runner as staging/reconciliation only. Prevent normal UI/production
workflow from invoking it. Search for batch/shim/launcher dependencies and
document them.

Exit: one documented production payroll path target = native HRMS v16.

---

## Phase 2 — explicit effective financial configuration

### CHUNK-03 — native capability ADR for pay basis and assignment binding

Inspect v16 Salary Structure Assignment and payroll settings. Choose narrowest
schema for explicit pay basis/policy binding.

Do not code schema before ADR.

### CHUNK-04 — explicit pay basis

Implement chosen binding, migration preview, validation and UI helper.

Rules:

- Employment Type does not decide pay;
- company mismatch rejected;
- missing pay basis blocks readiness;
- historical effective date retained.

Tests: PAY-006, PAY-012.

### CHUNK-05 — effective interval resolver

Create one tested interval service used by readiness, not scattered queries.

Cover:

- employment interval;
- salary assignment;
- pay-policy version;
- statutory profile;
- optional organization/shift use cases.

Tests: PAY-001..005 boundary cases.

---

## Phase 3 — native v16 attendance/OT first

### CHUNK-06 — native overnight-shift parity

Write integration tests against installed HRMS v16 for overnight shift resolution.
Do not alter core behavior until the test documents the native result.

Then remove custom calendar-date payroll pairing dependency.

Tests: ATT-001, ATT-008.

### CHUNK-07 — payroll input boundary

Refactor daily/attendance-dependent pay readiness so raw Employee Checkin is never
the payroll source. Use submitted/finalized Attendance + approved OT.

Add static/architectural test that production payroll services do not query raw
Checkin for pay calculation.

Tests: ATT-002, ATT-007, invariant.

### CHUNK-08 — native overtime parity study

Configure and compare native Overtime Type/Slip to approved policy. Produce ADR.

Only implement custom compliance adapter for proven native gaps.

Tests: OT-001..007.

---

## Phase 4 — finalization and exception control

### CHUNK-09 — operational case model

Keep Policy Exception unchanged. Add normalized runtime case only if reports alone
cannot support workflow.

Requirements:

- dedupe key;
- source refs;
- severity;
- assignee;
- resolution/approval;
- no duplicate financial truth.

### CHUNK-10 — Attendance Period finalization

Implement Open -> Reviewing -> Finalized -> Reopened control around native
Attendance.

Finalization validators include identity, shift, leave, device completeness and
OT state by applicable population.

Tests: ATT-002, 005, 007, 011 and reopen/late-data flow.

### CHUNK-11 — retroactive attendance reconciliation

Late evidence/correction after finalized/paid period creates a case and routes to
native payroll correction where applicable.

No silent Salary Slip mutation.

Tests: PAY-008, REC paths.

---

## Phase 5 — native payroll readiness and parity

### CHUNK-12 — Payroll Readiness service

Pure/read-only service first. Per employee output:

~~~json
{
  "employee": "EMP-001",
  "outcome": "BLOCKED",
  "blockers": [{"code": "SALARY_ASSIGNMENT_OVERLAP"}],
  "warnings": []
}
~~~

No Salary Slip creation in this chunk.

### CHUNK-13 — company payroll readiness UI/report

Show population counts, blockers, fix links, legal/tax version status and
Attendance finalization.

Do not build decorative dashboard first.

### CHUNK-14 — native Payroll Entry staging adapter

From a clean readiness set, create/configure native Payroll Entry and native
Salary Slips in **draft staging only**.

Compare with canonical assignments/Attendance/OT/Additional Salary.

### CHUNK-15 — native payroll parity and retirement decision

Run synthetic + staging comparison. Explain all differences. Approve ADR for
native path. Then disable manual runner as production calculation engine.

Exit: draft native payroll reconciles for agreed scenarios.

---

## Phase 6 — statutory/versioned compliance

### CHUNK-16 — legal profile schema ADR

Design minimal versioned profile without reimplementing all law in code.

Must support legal regime, establishment, worker classification, sector/wage
profile, tax version, effective range, source/reviewer/status.

### CHUNK-17 — compliance validators

Implement only approved rules with authoritative references. Draft/unapproved
profile never drives submitted payroll.

### CHUNK-18 — tax/PF/pension/gratuity adapters

One domain at a time. Use native HRMS capability where available. Each domain has
separate legal/accounting review and fixtures.

---

## Phase 7 — mobile/biometric privacy and resilience

### CHUNK-19 — persistent mobile idempotency

Client persists same operation ID through timeout/retry.

Tests MOB-001/002 and UI network interruption.

### CHUNK-20 — offline mode decision

ADR per attendance policy: online-required vs offline queue.

If queue enabled: durable local queue, payload fingerprint, same sync ID, visible
pending count and secure storage review.

### CHUNK-21 — biometric identity validity intervals

Add effective mapping history and collision validator. Migrate current enabled
rows with preview; never guess past reuse.

Tests ATT-003..006.

### CHUNK-22 — device completeness/health

Heartbeat/backlog/sequence/drift metrics and finalization integration.

### CHUNK-23 — live-location scope + retention

Enforce record scope, current-duty filtering, bounded results. Implement retention
dry run/job with legal/audit holds.

### CHUNK-24 — field-duty lifecycle and allowance

Add proper approval/completion/allowance states, freeze policy basis, honor
allowance approval, define cancellation/reversal.

Tests MOB-008/009.

### CHUNK-25 — face-match governance

Version model/threshold, review path, private-file scope, retention. Keep optional
and disabled until approved.

---

## Phase 8 — roles and low-error UX

### CHUNK-26 — real role/scope provisioning design

Create documented role bundles and User Permission templates. Test real staging
users for each role.

### CHUNK-27 — native v16 sidebar migration

Build Workspace Sidebar fixtures using native v16.

Parity-test all 44+ required routes, then remove custom rail DOM implementation.

### CHUNK-28 — exception-first Command Center

Build role-specific task dashboard backed by real readiness/case/device services.

### CHUNK-29 — guided wizards and bulk preview

High-value flows:

- set compensation/pay basis;
- assign shifts;
- bulk leave allocation;
- organization transfer;
- payment details import.

Every bulk operation validates before write and reports partial failures.

### CHUNK-30 — Bangla/low-end accessibility

Translation, operator language, CPU/network tests, mobile UX, printable/exportable
exception list only where operationally required.

---

## Phase 9 — finance/payment and close controls

### CHUNK-31 — accounting readiness

Validate accounts/cost centers/dimensions and reconcile submitted payroll to JE/GL.

### CHUNK-32 — payment readiness/register

Separate payment method readiness from payroll. Build idempotent payment export or
integration boundary.

### CHUNK-33 — payment reconciliation

Import/receive bank/payment outcome; match to approved register; exceptions for
rejected/missing/duplicate payments.

---

## Phase 10 — production hardening

### CHUNK-34 — CI

Add GitHub Actions for pure/unit/static/security checks. Add integration environment
when stable. Do not fake Frappe integration with mocks only.

### CHUNK-35 — restore rehearsal

Restore verified backup to isolated staging, migrate, run smoke/reconciliation.

### CHUNK-36 — production cutover rehearsal

Follow 10_RELEASE_MIGRATION_RECOVERY.md. Draft payroll only until owner/compliance
sign-off.

### CHUNK-37 — post-cutover monitoring

Define first payroll enhanced monitoring, rollback thresholds and reconciliation
sign-off.

## Chunk completion template

Every chunk PR/task must contain:

~~~markdown
Objective:
Architecture docs read:
Native v16 features inspected:
Files changed:
Schema changes:
Data migration:
Permissions/scopes:
Idempotency:
Tests run:
Staging verification:
Rollback:
Known gaps:
Next allowed chunk:
~~~

## Stop conditions

An agent stops and reports instead of guessing when:

- statutory applicability/rate is unknown;
- compensation classification is ambiguous;
- a migration would alter live data;
- native v16 behavior is not understood;
- a destructive operation lacks a verified backup;
- user/approver identity would need invention;
- a requested shortcut violates a source-of-truth invariant;
- staging and production identity cannot be distinguished.
