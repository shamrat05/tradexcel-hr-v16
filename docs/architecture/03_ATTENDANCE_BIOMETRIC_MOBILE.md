# 03 — Attendance, biometric, mobile, field-duty and evidence architecture

## Invariant

~~~text
Employee Checkin = evidence
Attendance       = approved/finalized daily work state
Payroll          = consumes Attendance/approved OT, not raw punches
~~~

## Target pipeline

~~~mermaid
flowchart TD
    A[Biometric / Mobile / API] --> B[Durable ingestion identity]
    B --> C{Already received?}
    C -->|Yes| D[Return existing result]
    C -->|No| E[Store evidence / native Checkin]
    E --> F[Resolve employee identity]
    F --> G{Unique mapping at event time?}
    G -->|No| X1[Operational exception]
    G -->|Yes| H[Native v16 shift resolution]
    H --> I{Unique valid shift context?}
    I -->|No| X2[Operational exception]
    I -->|Yes| J[Native auto attendance]
    J --> K[Leave/holiday/request/OT reconciliation]
    K --> L{Clean?}
    L -->|No| X3[Attendance exception queue]
    L -->|Yes| M[Finalized Attendance]
    X1 --> R[Human review / corrected mapping]
    X2 --> R
    X3 --> R
    R --> K
    M --> P[Payroll readiness]
~~~

## Biometric terminal contract

Keep the strong existing worker properties:

- device-scoped mapping key;
- stable source event key;
- durable local state;
- at-least-once delivery;
- inserted/duplicate success semantics;
- failed/unmapped retry queue;
- success cursor that cannot jump over a failed event.

### Add effective identity intervals

Current mapping needs historical validity for safe PIN reuse.

~~~yaml
device: TCL_FACTORY_1
biometric_id: "1042"
employee: EMP-001
valid_from: 2026-01-01T00:00:00+06:00
valid_to: 2026-08-31T23:59:59+06:00
status: retired
~~~

No overlapping interval for the same device + biometric ID. Historical punches
resolve against event time, not today's enabled mapping.

## Preserve two times

For device/mobile evidence retain device_time and received_at plus source event
ID, source device, payload hash, clock skew, and offline/live metadata where
available. Never overwrite original device time.

## Night shifts

Do not group by calendar date. Use HRMS v16 actual shift windows and prove native
behavior against night-shift fixtures before deleting old code.

## Missing/duplicate punches

- identical source event ID: auto-return existing result;
- probable duplicate: collapse only under approved deterministic tolerance;
- missing IN/OUT: create exception; never fabricate 8 hours or an OUT time.

## Attendance finalization

Introduce a light control object, name subject to ADR, e.g. Tradexcel Attendance
Period. It does not duplicate Attendance.

~~~yaml
company: Tradexcel Ceramics Ltd.
from_date: 2026-09-01
to_date: 2026-09-30
status: Open | Reviewing | Finalized | Reopened
blocking_exception_count: 0
finalized_by: user@example.com
finalized_at: ...
revision: 3
snapshot_hash: ...
~~~

Prerequisites include device completeness review where relevant, no identity/shift
ambiguity, required Attendance outcomes, leave conflicts resolved, corrections
applied, and OT state resolved where pay depends on it.

Late data after finalization creates reconciliation, not silent paid-payroll edits.

## Mobile current strengths

Current server code already links to active Employee, resolves submitted policy,
keeps device time as evidence, uses server time for checkin, validates GPS/selfie
ownership, can fail closed on face matching, and has unique server sync events.

## Mobile required fixes

### Persist operation ID across retries

~~~text
create operation UUID
-> persist locally with payload fingerprint
-> POST
-> timeout: retry SAME UUID
-> server returns existing result
-> acknowledge and clear pending operation
~~~

Never generate a new operation ID merely because a response was lost.

### Explicit offline policy

Per policy choose:

- ONLINE_REQUIRED: clear offline failure; no fake success.
- OFFLINE_QUEUE_ALLOWED: protected local queue, original device time, same ID on
  replay, visible unsynced count.

### Location pings

If best-effort, they must not decide pay/finalization. If required evidence,
provide durable queue/completeness state and missing-window cases.

### Server-authoritative scope

Supervisor API access equals role capability + company/branch/department/employee
scope. Direct API calls outside scope must fail.

## Field Duty

Field Duty authorizes/evidences work; it is not a second Attendance ledger.

Suggested workflow:

~~~mermaid
stateDiagram-v2
    [*] --> Draft
    Draft --> PendingApproval
    PendingApproval --> Approved
    PendingApproval --> Rejected
    Approved --> InProgress
    InProgress --> Completed
    Approved --> Cancelled
    Completed --> AllowanceReview
    AllowanceReview --> AllowanceApproved
    AllowanceReview --> AllowanceRejected
    AllowanceApproved --> Closed
~~~

Before Additional Salary:

- duty approved and completed;
- policy effective for duty date frozen/known;
- basis explainable;
- evidence exceptions resolved per policy;
- allowance approval honored;
- unique key prevents duplicate;
- reversal behavior defined.

## Face matching

Face match is optional evidence, not proof of liveness or misconduct.

- disabled by default;
- model/checksum and threshold documented/versioned;
- false-reject review path;
- restrictive access to reference/selfie;
- retention enforced;
- no pay decision directly from score.

## Mass operational override

For fire drill, shutdown, no-work early release, etc., do not manually edit large
populations. After native-capability ADR, use a controlled bulk event with scope,
reason, treatment, impact preview, maker/checker and reversal.

## Monitoring

Expose last seen, last received/applied event, backlog, oldest pending age,
sequence gap, duplicate rate, unmapped count, clock drift, peak throughput and
failed retries. Online status alone is insufficient.
