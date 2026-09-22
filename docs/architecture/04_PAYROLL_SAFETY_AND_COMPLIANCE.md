# 04 — Payroll safety, readiness, Bangladesh compliance and reconciliation

## Principle

The app should become a **control/orchestration layer around native HRMS v16
payroll**, not a second Salary Slip engine.

## Three readiness gates

**Payroll readiness:** can pay be calculated safely?

**Accounting readiness:** can approved payroll be posted to correct accounts and
dimensions?

**Payment readiness:** can approved net pay be paid through the chosen method?

A missing bank account may block a bank batch without invalidating calculation.

## Target flow

~~~mermaid
flowchart TD
    A[Period + company] --> B[Employee universe]
    B --> C[Employment interval]
    C --> D[Explicit pay basis]
    D --> E[Salary assignment intervals]
    E --> F[Finalized Attendance]
    F --> G[Leave/LWP]
    G --> H[Approved overtime]
    H --> I[Additional Salary / loans / corrections]
    I --> J[Approved compliance/tax rules]
    J --> K[Readiness validators]
    K -->|blocked| X[Actionable cases]
    K -->|clean| L[Freeze provenance snapshot]
    L --> M[Native Payroll Entry / Salary Slip]
    M --> N[Reconcile totals/provenance]
    N -->|fail| X
    N -->|pass| O[Maker review]
    O --> P[Checker approval]
    P --> Q[Submit immutable payroll]
    Q --> R[Accounting readiness/posting]
    Q --> S[Payment readiness/payment]
    R --> T[Post-pay reconciliation]
    S --> T
~~~

## Explicit pay basis

Never infer pay solely from Employment Type.

Minimum conceptual values: MONTHLY, DAILY, HOURLY, plus only explicitly implemented
other bases. Record an ADR before deciding where the binding is stored in v16.

## Salary assignment resolution

- zero applicable assignment: BLOCK;
- overlapping conflicting assignments: BLOCK;
- one whole-period assignment: normal;
- boundary inside period: native mechanism or approved split/proration;
- never latest-row-wins for the entire period.

## Joiners/leavers

Eligibility starts at max(period start, joining) and ends at min(period end,
relieving if set). Amount proration follows configured/native behavior proved by
tests, not an ad-hoc calendar assumption.

## Overtime

Keep worked, approved, payable and compliance-exception concepts distinct.
Presence after shift is not automatically approved OT.

Evaluate v16 Overtime Type/Slip/Attendance first; Tradexcel adds compliance or
approval controls only for real gaps.

## Bangladesh statutory control plane

Do not encode a timeless "Bangladesh formula".

~~~yaml
jurisdiction: BD
legal_regime: GENERAL_LABOUR | EPZ | OTHER_APPROVED
establishment_type: factory | office | shop | ...
worker_legal_classification: ...
sector_wage_profile: ...
effective_from: ...
effective_to: ...
rules:
  working_time_version: ...
  overtime_version: ...
  minimum_wage_version: ...
  tax_version: ...
  pf_pension_version: ...
  gratuity_version: ...
  deduction_version: ...
  termination_version: ...
source:
  authority: ...
  gazette_or_circular: ...
  reviewed_by: ...
  reviewed_on: ...
status: Draft | Approved | Retired
~~~

A submitted payroll must be traceable to the approved versions used.

### Legal release gate

Before approving a statutory profile:

1. obtain current authoritative Bangla Gazette/law/NBR source;
2. confirm company/establishment/worker applicability;
3. authorized legal/compliance/accounting review;
4. store source/effective date;
5. run regression fixtures;
6. deploy a new version, never rewrite historical rule meaning.

Current research covers working time, night shifts, OT, wage-payment deadlines,
wage deductions, sector/class minimum wage, employment-income tax, PF/pension and
gratuity. The authoritative Bangla text/current Gazette remains controlling.

Income tax is fiscal-year/version aware. NBR currently lists a 2026–2027 Income
Tax Paripatra; previous-year rules must not remain silently active.

## Deductions need provenance

Do not give normal operators an unrestricted generic negative salary line.

~~~yaml
deduction:
  category: loan_repayment
  authority:
    doctype: Loan
    name: LOAN-00042
  amount: 1250
  effective_period: 2026-09
  created_by: system
  approved_by: payroll_checker
  reversible: true
~~~

Unusual deductions require the evidence and approval demanded by applicable law
and company policy.

## Payroll input/provenance snapshot

Before calculation freeze references/versions, not a duplicate payroll ledger.

~~~yaml
employee: EMP-0214
period: 2026-09
employment:
  legal_regime: BD_GENERAL
  worker_classification: approved-code
  pay_basis: MONTHLY
compensation:
  salary_assignment_ids: [SSA-00421]
attendance:
  finalization_id: ATT-PERIOD-2026-09
  revision: 3
overtime:
  native_overtime_docs: [...]
adjustments:
  additional_salary: [...]
tax_ruleset: BD-TAX-FY2026-27-v2
labour_ruleset: BD-LABOUR-2026-v1
rounding_policy: BDT-PAYROLL-v1
engine_version: ...
input_hash: sha256:...
~~~

Same snapshot/configuration must give the same result.

## Idempotency

Payroll request has a stable logical identity. Double click, network retry,
worker retry and process restart cannot create a second active financial result.

## Retroactive changes

First evaluate native v16 Payroll Correction, Arrear and referenced Additional
Salary.

~~~text
paid September
+ approved backdated correction
-> reconciliation case
-> calculate delta
-> authorized native correction/arrear
-> next eligible payment/accounting result
~~~

Never silently update the paid September slip.

## Reconciliation chain

~~~text
employee universe        <-> payroll outcome universe
final attendance         <-> payment days
approved overtime        <-> paid overtime
salary assignments       <-> regular earnings
Additional Salary        <-> slip adjustments
tax calculation          <-> tax deductions
submitted payroll total  <-> accounting posting
approved net total       <-> payment register
payment register         <-> bank/payment result
~~~

Mismatch becomes a blocking case or an explicitly approved exception.

## Retiring run_payroll.py

1. mark non-production/staging-only;
2. fix obvious crash/fallback behavior so comparison tests are reliable;
3. build native-v16 parity fixtures;
4. compare old preview vs native preview on staging;
5. explain every difference;
6. make native path primary;
7. retain old read-only comparison briefly if needed;
8. remove only after sign-off and dependency search.

End state: custom app validates/orchestrates native payroll; it does not construct
Salary Slips as a parallel engine.
