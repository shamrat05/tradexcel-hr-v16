# 01 — Canonical HRMS flow and source of truth

## Design goal

The system should be difficult to operate incorrectly even when attendance devices
go offline, operators have limited computer skills, supervisors change shifts
informally, staff join/leave/change salary mid-period, users retry after network
timeouts, master data is incomplete, legal rules change, or a correction arrives
after payroll was paid.

The goal is not to prevent every error. It is to make common errors hard,
ambiguity visible, financial ambiguity blocking, and corrections traceable.

## End-to-end flow

~~~mermaid
flowchart TD
    A[Identity and Access] --> B[Company / Establishment]
    B --> C[Organization Masters]
    C --> D[Recruitment / Onboarding]
    D --> E[Employee Master + Placement]

    E --> F[Compensation Assignment]
    E --> G[Shift / Holiday Context]
    E --> H[Leave Eligibility]
    E --> I[Attendance Identity / Device / Mobile Policy]

    I --> J[Raw Evidence]
    G --> K[Shift Resolution]
    J --> K
    K --> L[Provisional / Native Auto Attendance]
    H --> M[Approved Leave]
    L --> N[Attendance Review / Corrections]
    M --> N
    N --> O[Finalized Attendance Period]

    F --> P[Payroll Readiness]
    O --> P
    M --> P
    P --> Q[Native Payroll Entry]
    Q --> R[Native Salary Slips]
    R --> S[Maker / Checker / Submit]
    S --> T[Accounting Readiness]
    T --> U[Accounting Posting]
    S --> V[Payment Readiness]
    V --> W[Payment / Bank File]
    U --> X[Reconciliation]
    W --> X

    E --> Y[Transfer / Promotion / Appraisal / Training]
    Y --> E
    E --> Z[Separation]
    Z --> ZA[Full & Final]
    ZA --> ZB[Access Revocation + Retention]

    X --> RC[Retroactive Change Detector]
    RC -->|difference| ADJ[Native Payroll Correction / Arrear]
    ADJ --> Q
~~~

## The three-state boundary

### Evidence

Facts that may be incomplete or noisy:

- biometric terminal event;
- mobile checkin request;
- device timestamp;
- server receive timestamp;
- GPS fix and accuracy;
- selfie/face-match result;
- raw checkin sequence;
- device heartbeat/backlog.

Evidence is preserved; it does not directly decide pay.

### Approved HR state

Records that express an HR conclusion:

- Employee and effective employment interval;
- Shift Assignment / Default Shift;
- Attendance;
- Attendance Request;
- Leave Application / Leave Ledger;
- Overtime Slip or other approved OT state;
- Salary Structure Assignment;
- Additional Salary with authority;
- Transfer / Promotion / Separation.

### Financial state

- Payroll Entry;
- Salary Slip;
- Payroll Correction / Arrear;
- Journal Entry / General Ledger;
- payment register / bank result.

Financial state is downstream and must reconcile back to approved HR state.

## Canonical ownership matrix

| Concept | Canonical owner | Tradexcel may do | Tradexcel must not do |
|---|---|---|---|
| Login identity | Frappe User | guided provisioning, scope checks | create a second user database |
| Employment identity | HRMS Employee | validate readiness/gaps | make User == Employee |
| Org placement | Employee + native lifecycle docs | audit/effective-date helpers | parallel placement ledger |
| Raw terminal/mobile punch | Employee Checkin + delivery evidence | ingest/idempotency/metadata | treat raw punch as salary |
| Shift | Shift Type / Assignment / Schedule | validate coverage | reimplement calendar-date pairing |
| Daily work conclusion | Attendance | exception/finalization control | derive payroll from Checkin |
| Attendance correction | Attendance Request / authorized native flow | simplify UI, maker/checker | overwrite silently |
| Leave | native Leave docs/ledger | readiness/reconciliation | custom leave balance ledger |
| Salary template | Salary Structure | install validated templates | personal salary in code |
| Employee compensation | Salary Structure Assignment | explicit policy binding/readiness | external JSON fallback |
| One-off earning/deduction | Additional Salary or native specialized doc | require provenance | unexplained negative money |
| Overtime | native v16 Shift/Attendance/OT docs where fit | compliance validation | duplicate OT ledger without ADR |
| Payroll batch | Payroll Entry | readiness gate/orchestration | private parallel batch |
| Payroll result | Salary Slip | trace/snapshot/reconcile | hand-build as long-term engine |
| Retro correction | v16 Payroll Correction / Arrear where fit | detect and route | mutate old paid slip |
| Expense | Expense Claim / Employee Advance | role UX | opaque salary reimbursement |
| Accounting | ERPNext JE/GL | readiness/reconciliation | duplicate GL |
| Device identity | Tradexcel device-scoped mapping | effective mapping | assume global PIN |
| Runtime anomaly | future HR Case/work queue | detect/assign/resolve | confuse with Policy Exception |
| Policy override | Tradexcel Policy Exception | preview/version | runtime incident queue |
| Legal version | approved compliance profile | applicability/provenance | timeless law in code |

## Independent employee states

Do not collapse all lifecycle into Employee.status.

~~~yaml
employment_state:
  - preboarding
  - active
  - probation
  - confirmed
  - notice_period
  - relieved
  - archived

access_state:
  - no_user
  - active
  - suspended
  - disabled

attendance_state:
  - not_configured
  - collecting
  - exception
  - finalized

payroll_state:
  - not_ready
  - ready
  - blocked
  - processing
  - submitted
  - paid
  - final_settlement
  - closed
~~~

Valid example: Active employee, no User account, payroll ready.

## Effective dating

Historical truth must not be reconstructed from today's Employee row.

Every resolver accepts an as-of date or interval. Financially relevant
effective-dated inputs include employment start/end, company/branch/department
where relevant, pay basis, Salary Structure Assignment, payroll/compliance rule,
Shift Assignment, leave eligibility, tax rule, PF/pension/gratuity scheme,
minimum-wage profile and lifecycle change.

### Interval rule

For payroll interval [period_start, period_end]:

1. find all applicable intervals that intersect it;
2. zero where required means blocker;
3. conflicting values at the same instant mean blocker;
4. a legitimate boundary inside the period invokes explicit split/proration or
   a proved native v16 mechanism;
5. never choose a financial winner merely because it was modified latest.

## Payroll outcome completeness

Every employee whose employment overlaps a payroll period has an explainable
outcome:

~~~text
SALARY_SLIP_CREATED
PAYROLL_BLOCKED(reason)
NOT_PAYABLE_WITH_APPROVED_REASON
FINAL_SETTLEMENT_PATH
~~~

Nobody simply disappears because a query returned no row.

## Change propagation

~~~mermaid
flowchart LR
    S[Source changed] --> D{Downstream finalized?}
    D -->|No| R[Recompute derived state]
    D -->|Yes| C[Create reconciliation case]
    C --> P[Preview financial difference]
    P --> A[Authorized correction / arrear]
    A --> N[Next eligible payroll / accounting adjustment]
~~~

No job silently rewrites submitted Salary Slip values.

## Master-data governance

### Minimum viable setup

Keep initial setup small.

**Base:** Company/currency, employees/employment dates, needed organization
identifiers, Holiday List, salary structure/assignment, explicit pay basis, and
payment method when a payment batch is used.

**Attendance-dependent payroll:** Shift/default or Shift Assignment, auto
attendance, device/mobile mapping, and attendance finalization.

**Optional only when used:** recruitment, appraisal/training, field tracking,
face matching, loans/advances, expenses, statutory adapters and bank integration.

Do not block a small office on factory-device configuration it does not use.

### Governance rules

- setup wizards may propose defaults; they do not silently rewrite contracts;
- imports use the same validation services as UI/API;
- bulk changes use preview -> validate -> apply -> exception result;
- unknown values remain unresolved rather than fabricated;
- high-risk master changes show old -> new, effective date and estimated impact;
- money-driving configuration is versioned/approved, not silently edited in place.
