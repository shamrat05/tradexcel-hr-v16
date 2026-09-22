# 05 — Exception-first automation and low-error UX

## Operating principle

> Automate deterministic facts; surface ambiguity; require accountable human
> decisions where judgment is unavoidable; never allow unresolved ambiguity to
> silently cross into payroll.

## Task-oriented default

Do not make a normal operator understand every HRMS DocType.

~~~text
TODAY

✓ 221 attendance records processed

Needs attention                         5
  Missing checkout                     2
  Unknown biometric ID                 1
  Leave conflict                       1
  Device offline                       1

[ Review 5 ]
~~~

Advanced native documents remain available to authorized users.

## Operational case != policy exception

Keep Tradexcel Policy Exception as a configuration override. A runtime anomaly
queue uses a distinct concept such as Tradexcel HR Case.

~~~yaml
case_code: ATT_MISSING_OUT
domain: Attendance
severity: BLOCK | REVIEW | WARNING
company: ...
employee: ...
business_date: ...
source_references: [...]
status: Open | Assigned | AwaitingApproval | Resolved | Dismissed
assigned_to: ...
resolution_code: ...
resolution_reason: ...
proposed_by: ...
approved_by: ...
dedupe_key: ...
~~~

The case references canonical records; it never becomes payroll truth.

## Severity semantics

**BLOCK:** cannot finalize affected Attendance/payroll/payment/accounting action.

**REVIEW:** human decision needed, but may not block unrelated employees.

**WARNING:** operational signal; never financial punishment by itself.

## Automation vs human

| Situation | Default |
|---|---|
| identical event replay | auto-return existing |
| exact deterministic duplicate | auto-dedupe with audit |
| unmapped biometric | human mapping |
| overlapping biometric owners | block finalization |
| missing IN/OUT | review |
| unique native shift | automatic |
| zero/multiple shift context | review/block |
| approved leave | automatic native effect |
| leave + contradictory Attendance | review |
| one valid salary assignment | automatic |
| salary overlap | block |
| mid-period salary boundary | configured/native split or block |
| routine tax under approved version | automatic |
| unapproved legal version | block |
| approved Additional Salary | automatic inclusion |
| free-form deduction | prohibit for normal operator |
| duplicate payroll request | return existing |
| post-paid source change | detect automatically, human approves correction |
| offline device | ingest/replay; visibly incomplete |
| anomaly suggesting misconduct | review only; never auto-label fraud |

## Error-message contract

Every error answers:

1. What happened?
2. Why does it matter?
3. What evidence exists?
4. What can I do?

Example:

~~~text
Missing checkout

Rahim Uddin has no OUT event for the Sep 22 night shift.

Why it matters
Attendance cannot be finalized, so attendance-dependent payroll is blocked for
this employee.

Evidence
IN: Sep 22 21:56 · Factory Gate A
Shift: Sep 22 22:00 -> Sep 23 06:00

Actions
[ Wait for device sync ] [ Request correction ] [ Review raw events ]
~~~

## Sensitive confirmation

Show consequence, not "Are you sure?"

~~~text
Changing Rahim Uddin's monthly base
Tk 28,500 -> Tk 38,500
Effective: 1 Sep 2026
Estimated period impact: +Tk 10,000
Requires Payroll Checker approval.

[Cancel] [Submit for approval]
~~~

Paid-period changes explicitly say the old slip will not be rewritten and route
to correction/arrear preview.

## Progressive disclosure

Normal user sees employee identity, task, reason, evidence, and safe actions.
Advanced setup/report details are role-gated.

## Bangla and English

- all UI strings translatable;
- business logic uses canonical codes, not display labels;
- Bangla names searchable/exportable;
- local BDT/date/time display unambiguous;
- no hidden English-only error required to finish a flow.

## Bulk operations

~~~text
select/import
-> preview
-> validate each row
-> valid/warning/invalid counts
-> apply valid
-> invalid stays as cases
-> export result
~~~

Never direct CSV-to-database writes.

## Role home screens

Attendance Officer: today, punch/shift/device cases, corrections.

Payroll Manager: readiness, compensation conflicts, finalized Attendance, OT,
tax/compliance, variance/reconciliation.

Supervisor: own scoped team and allowed approvals only.

Finance: submitted totals, accounting/payment readiness and reconciliation.

Director: approval/risk summary, not raw record wall.

## Command Center

Build after the control services exist:

1. today summary;
2. Needs Attention;
3. device health;
4. Attendance finalization;
5. payroll readiness;
6. accounting/payment readiness;
7. lifecycle events;
8. role quick actions.

## Navigation

Use native v16 Workspace Sidebar for the shell. Keep a custom Command Center page
only where it adds task workflow, not to reimplement navigation.

## Low-end performance

Operational pages load action queues before decorative charts, paginate/aggregate
server-side, avoid full raw checkin downloads, bound live-location results and
remain usable under slow network and CPU throttling.
