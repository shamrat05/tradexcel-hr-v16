# 12 — Research-to-implementation traceability

This file answers one question:

> Did the architecture cover the full Bangladesh HRMS/payroll research, and where
> will each requirement be implemented and tested?

It also records the items that **cannot** be safely solved by a coding agent
without an owner, compliance, legal or accounting decision.

## Traceability matrix

| Research / repo requirement | Architecture owner | Implementation chunks | Acceptance evidence |
|---|---|---|---|
| Checkin is evidence, Attendance is payroll truth | 01, 03, 04 | 06, 07, 10, 12–15 | ATT-001/002/007, PAY readiness |
| No raw-punch payroll | 00, 01, 03, 04 | 07, 12–15 | static boundary test + integration |
| Cross-midnight/night shift | 02, 03 | 06 | ATT-001, ATT-008 |
| Missing IN/OUT never guessed | 03, 05 | 09, 10 | ATT-002, UI-004 |
| Duplicate/replayed device events | 03 | 21, 22 | ATT-003, REC-002 |
| Offline device/backlog/sequence gaps | 03, 10 | 22 | ATT-004/011, REC-006 |
| Device clock drift and dual timestamps | 03 | 22 | ATT-006 |
| PIN reuse/identity overlap | 03 | 21 | ATT-005 |
| Mobile retry idempotency | 00, 03 | 19 | MOB-001/002 |
| Mobile offline behavior | 03 | 20 | MOB-003/004 |
| GPS quality and field duty | 03 | 20, 24 | MOB-005/008/009 |
| Live-location record scope | 06 | 23, 26 | MOB-010, SEC-002 |
| Selfie/face verification fail-closed | 03, 06 | 25 | MOB-006/007/012 |
| Biometric/geolocation privacy | 06 | 23, 25 | retention/access/privacy review |
| Evidence retention lifecycle | 06, 10 | 23 | MOB-011 + dry-run retention job |
| Explicit payroll basis | 00, 01, 04, 07 | 03, 04 | PAY-006 |
| Missing salary assignment | 04 | 05, 12 | PAY-005 |
| Overlapping assignments | 04 | 05, 12 | PAY-004 |
| Mid-period salary change | 01, 04 | 05, 14, 15 | PAY-003 |
| Joiner/leaver proration | 01, 04 | 05, 14, 15 | PAY-001/002 |
| Payroll rerun / double submit | 04, 08 | 12–15 | PAY-007, UI-001 |
| Submitted payroll immutable | 01, 04 | 11, 15 | PAY-008 |
| Retroactive correction/arrear | 02, 04 | 11, 15 | PAY-008 + native v16 parity |
| Every monetary value explainable | 04 | 12–15 | provenance snapshot/assertions |
| Deterministic payroll | 04, 08 | 12–15 | same-input property test |
| Employee payroll outcome completeness | 01, 04 | 12–15 | PAY-011 |
| Negative/impossible pay | 04, 05 | 12–15 | PAY-009/010 |
| Overtime authorization vs presence | 02, 04 | 08 | OT-003/004 |
| OT rate/basis/legal version | 04 | 08, 16–18 | OT-001/007 |
| Weekly/daily work-time checks | 04 | 08, 17 | OT-002 |
| Holiday/rest-day work | 04, 07 | 08 | OT-005 |
| Break handling | 02, 04 | 08 | OT-006 |
| Versioned Bangladesh legal regime | 04, 07 | 16, 17 | statutory-profile tests |
| General Labour vs EPZ/profile differences | 04, 07 | 16–18 | applicability fixtures |
| Minimum-wage profile by sector/class | 04, 07 | 16, 17 | wage-floor fixtures |
| Tax fiscal-year versioning | 04 | 16, 18 | PAY-013 + FY boundary |
| PF/pension/gratuity not universal constants | 04, 07 | 16, 18 | domain-specific fixtures |
| Wage deduction provenance | 04, 06 | 17, 18 | unauthorized deduction negative test |
| Payroll readiness | 04, 05 | 12, 13 | blocker/outcome integration tests |
| Accounting readiness separate | 04 | 31 | reconciliation tests |
| Payment readiness separate | 04 | 32, 33 | PAY-015 + payment tests |
| Payroll-to-accounting reconciliation | 04 | 31 | REC + total equality |
| Payment-to-net-pay reconciliation | 04 | 32, 33 | payment outcome tests |
| Shared privileged-account risk | 06 | 26 | named-user UAT |
| Maker/checker | 06 | 09, 24, 26, 31–33 | SEC-004 |
| Role capability vs record scope | 06 | 23, 26 | SEC-002/006 |
| Server-side authorization | 06 | every sensitive slice | SEC-001..009 |
| Low computer literacy | 05 | 28–30 | UI-003/004/007 |
| Bangla/English operations | 05 | 30 | UI-003 |
| Fewer clicks / progressive disclosure | 05 | 28, 29 | novice Playwright |
| Bulk preview instead of blind imports | 05, 06 | 29 | import validation/security tests |
| Spreadsheet shadow-process risk | 05 | 28, 29 | exception/bulk UX UAT |
| Mass early closure / factory incident | 03, 05 | post-ADR in 09/10 or dedicated slice | ATT-012 |
| Anomaly is not proof of misconduct | 05, 06 | 09, 28 | copy/review tests |
| Command Center / task-first UI | 05 | 28 | role-home browser tests |
| Sophisticated sidebar | 02, 05 | 27 | UI-005/006/008 |
| Prefer native v16 over custom duplicate | 02 | all chunks via ADR | reviewer checklist |
| Native Overtime Type/Slip | 02, 04 | 08 | parity ADR/tests |
| Native Payroll Correction/Arrear | 02, 04 | 11, 15 | native parity tests |
| Native Workspace Sidebar | 02, 05 | 27 | route sweep |
| Backup/restore rehearsal | 10 | 35 | REC-005 |
| Crash/retry recovery | 03, 04, 10 | 19, 22, 34–37 | REC-001..006 |
| CI and regression enforcement | 08, 10 | 34 | required checks |
| Multi-company portability | 07 | 03–18 as applicable | company-scope fixtures |
| No hardcoded TCL/EFL domain behavior | 07 | refactor as touched | portability tests |
| No live writes by agent | AGENTS, 10 | all | task evidence |
| Chunkable coding-agent execution | 09, 11 | all | handoff template |

## Research items that need organization decisions

A coding agent must not invent these.

### Compensation classification

For any employee whose Employment Type, Salary Structure, contract, historical
pay and expected pay basis disagree, the owner/HR team must decide the contractual
truth before migration.

Examples include the historical monthly-paid employees labelled Worker.

### Tax

The applicable current tax treatment, fiscal/assessment-year package and any
company-specific payroll withholding procedure require finance/tax review before
activation.

### PF / pension / gratuity

The company must state:

- whether a scheme exists;
- employee eligibility;
- employee/employer contribution/basis;
- effective dates;
- vesting/withdrawal/termination handling;
- how statutory requirements and company benefits interact.

Developers do not infer this from old code.

### Minimum wage / sector wage order

Each establishment/population needs an approved applicable sector/class/grade
mapping and effective rule source.

### Overtime policy

The legal basis, approval model, salary-component basis, rounding, break
treatment, holiday/rest-day treatment and permitted limits must be approved.
The coding agent then maps this onto native v16 Overtime capability where possible.

### Attendance/pay treatment

The organization must approve policies for:

- missing punches;
- flexible/unscheduled shift attendance;
- authorized early closure/no-work days;
- field duty;
- work from home;
- late/early grace;
- half-day/absence thresholds;
- offline mobile capture;
- device-data completeness before finalization.

### Payment methods

Bank transfer, cash, mobile financial service or other lawful payment methods
need company/accounting rules and reconciliation design.

### Sensitive tracking

The organization must approve whether and when it is necessary to use:

- active GPS pings;
- selfies;
- automated face matching;
- biometric template transfer.

Purpose, legal basis/consent where required, retention and access must be reviewed.

## Gaps in the original deep-research report that this repo guide adds

The research was strong on controls and failure modes, but it was intentionally
framework-neutral. The v16 repo review adds these implementation-critical points:

1. **Native v16 Workspace Sidebar exists.** The app should migrate away from its
   parallel desktop rail rather than keep repairing a duplicate shell.
2. **Native v16 overtime is materially richer than the v15-era custom assumptions.**
   Overtime Type, Attendance OT fields and Overtime Slip must be evaluated before
   retaining custom OT math.
3. **Native v16 Payroll Correction and Arrear exist.** Retroactive adjustment
   design should reuse them where semantics fit.
4. **Native v16 shift resolution already models actual cross-midnight windows.**
   The right fix is to stop the custom payroll runner from pairing by calendar
   date, not to invent another night-shift engine.
5. **The repo now has mobile/GPS/selfie/face features.** This creates privacy,
   retention, retry and record-scope requirements beyond the original payroll
   focus.
6. **The server's sync ID is not sufficient if the browser creates a new ID after
   timeout.** End-to-end idempotency requires persistent client operation IDs.
7. **Field Duty allowance is a money path.** It needs explicit lifecycle,
   approval and reversal controls, not just an idempotency key.
8. **A retention-days field without a retention job is not retention.**
9. **Bangladesh enacted a new Personal Data Protection Act in 2026.** Biometric
   and real-time geolocation processing need an explicit privacy architecture
   and current legal review.
10. **The root README/AGENTS documentation was stale relative to v16 staging.**
    Agent instructions must describe the repository the agent is actually changing.

## Coverage conclusion

The architecture set now covers the research domains requested for:

- access/identity;
- organization/master data;
- onboarding and lifecycle;
- shifts, attendance, biometric and mobile evidence;
- leave;
- compensation;
- overtime;
- payroll readiness/calculation/correction;
- legal/statutory versioning;
- accounting and payment;
- reporting/reconciliation;
- human factors and low-skill UX;
- permissions/maker-checker;
- privacy/retention;
- offline/idempotency/recovery;
- testing, migration and disaster recovery;
- multi-company portability;
- chunked agent delivery.

What remains deliberately unresolved is **business/legal truth**, not an
engineering omission. Those decisions are listed above and must become approved
configuration before production payroll.
