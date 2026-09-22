# 08 — Test and acceptance matrix

## Test pyramid

| Layer | Mandatory coverage |
|---|---|
| Unit | interval resolution, policy precedence, rounding, GPS math, dedupe |
| Property/invariant | net arithmetic, determinism, no ambiguous interval, provenance |
| Integration | Checkin -> Attendance -> Payroll, Leave -> Payroll, correction -> arrear |
| Concurrency | duplicate upload, double payroll action, simultaneous approval |
| Migration | v15/v16 data shapes, custom fields, biometric history, policy versions |
| Browser | novice workflow, retry, role visibility, Bangla, native sidebar |
| Performance | punch bursts, large readiness query, exception dashboard |
| Security | horizontal/vertical privilege escalation, scope, session, API auth |
| Recovery | crash mid-run, bridge restart, queue replay, restore rehearsal |

## Permanent regression catalogue

### Payroll

~~~text
PAY-001 join mid-period -> no full-month overpay
PAY-002 leave mid-period -> no pay beyond eligibility
PAY-003 raise mid-period -> native/configured split or explicit block
PAY-004 overlapping salary assignments -> block
PAY-005 missing salary assignment -> block
PAY-006 monthly pay + daily inferred category conflict -> explicit pay basis wins/block
PAY-007 same payroll request retried -> one financial outcome
PAY-008 paid-period source correction -> correction/arrear; old slip unchanged
PAY-009 negative net -> controlled exception
PAY-010 component totals/rounding mismatch -> block
PAY-011 every in-scope employee has an outcome
PAY-012 wrong-company salary structure -> rejected
PAY-013 missing tax version when applicable -> block
PAY-014 unapproved statutory profile -> block
PAY-015 payment bank missing -> payroll may calculate; bank batch blocks
~~~

### Attendance and shifts

~~~text
ATT-001 22:00 IN + 06:00 OUT -> one native night-shift context
ATT-002 IN only -> exception; no invented OUT
ATT-003 identical terminal event x100 -> one effect
ATT-004 device offline 24h -> replay preserves source time/order
ATT-005 overlapping PIN mapping -> finalization blocked
ATT-006 device clock +20 min -> health alert / preserved times
ATT-007 approved leave + Present conflict -> review
ATT-008 shift changes effective boundary -> correct native shift
ATT-009 attendance before joining -> quarantine/block
ATT-010 attendance after relieving -> block unless approved terminal case
ATT-011 device sequence gap -> finalization warning/block by policy
ATT-012 mass early closure -> one approved bulk event, not manual edits
~~~

### Overtime

~~~text
OT-001 native OT parity with approved company/statutory formula
OT-002 weekly/daily compliance threshold validation
OT-003 extra presence is not automatically approved OT
OT-004 approved OT with missing punch -> correction workflow
OT-005 holiday/rest-day work -> configured policy path
OT-006 break handling does not inflate worked time
OT-007 OT rule version changes do not rewrite paid periods
~~~

### Mobile/field duty

~~~text
MOB-001 response lost then retry SAME sync ID -> one checkin
MOB-002 same sync ID used by another employee -> reject
MOB-003 offline policy ONLINE_REQUIRED -> visible failure, no fake success
MOB-004 offline queue replay -> original device time retained
MOB-005 GPS required but accuracy missing/bad -> reject
MOB-006 selfie required but absent -> reject
MOB-007 user cannot attach another user's selfie
MOB-008 field duty allowance OUT retried -> one Additional Salary
MOB-009 allowance requiring approval cannot auto-pay
MOB-010 supervisor outside scope cannot view live location
MOB-011 retention job respects legal/audit hold
MOB-012 face provider unavailable -> fail closed with review path
~~~

### Security

~~~text
SEC-001 HR clerk calls restricted admin API -> reject
SEC-002 supervisor accesses another department -> reject
SEC-003 disabled user/session -> restricted action unavailable
SEC-004 maker self-approval -> reject
SEC-005 report with empty role table never introduced accidentally
SEC-006 bulk import cannot bypass scope
SEC-007 malicious HTML/reason escaped
SEC-008 custom file/model path traversal rejected
SEC-009 sensitive export restricted/audited
~~~

### UI

~~~text
UI-001 double-click financial action -> one result
UI-002 browser disconnect during submit -> deterministic reload state
UI-003 Bangla flow has no hidden English-only blocker
UI-004 case shows cause, consequence, evidence, next action
UI-005 native v16 sidebar persists across Workspace/List/Form/Report/Calendar
UI-006 active route and collapse state correct
UI-007 low-end CPU / slow network remains usable
UI-008 no horizontal overflow at supported widths
UI-009 mobile action clearly shows pending/unsynced state
~~~

### Recovery

~~~text
REC-001 app process crashes after creating native doc before response -> retry idempotent
REC-002 bridge crashes after durable receive -> event later replays once
REC-003 payroll readiness recomputation after crash is side-effect-free
REC-004 DB rollback leaves no partial financial batch
REC-005 backup restores staging and app migrations succeed
REC-006 queue backlog after outage reconciles to source counts
~~~

## Acceptance gates by slice

Every implementation chunk must specify exact tests from this catalogue plus any
new regression that caused the change.

A green app suite is necessary but not sufficient. For a P0 payroll slice require:

- unit/integration;
- real v16 staging fixture;
- concurrency/idempotency where applicable;
- negative permission test;
- reconciliation evidence;
- no submitted production payroll.

For a navigation/UI slice require:

- native sidebar fixture validation;
- route sweep;
- list/form/report/calendar;
- 1440px desktop and a smaller supported viewport;
- role visibility;
- no console/page errors;
- accessibility basics;
- no custom DOM polling repair.

## Test data rule

Use synthetic fixtures for automated tests. Staging copies of real data may be
used for reconciliation only under existing project security rules and must not be
copied into the repository or agent prompts.

## Test skip rule

Do not hide a regression by skipping because data/configuration is absent if that
configuration is part of the feature under test. Skips are acceptable only for
environment-dependent optional capability with an explicit reason.

## Expected invariants

~~~text
net_pay = gross_pay - total_deduction (subject to native rounding fields)
same input snapshot -> same result
no overlapping required effective interval
no financial component without provenance
no duplicate active payroll outcome for one logical identity
no out-of-scope privileged access
no attendance-dependent payroll from raw Checkin
~~~
