# 11 — Agent task and handoff templates

## One-chunk task prompt

Use this template when assigning a coding agent.

~~~markdown
You are implementing CHUNK-XX from
docs/architecture/09_IMPLEMENTATION_CHUNKS.md.

Repository:
shamrat05/tradexcel-hr-v16

Required reading:
- AGENTS.md
- docs/architecture/README.md
- <list the exact architecture files for this chunk>

Objective:
<one bounded outcome>

Hard invariants:
- native Frappe/HRMS records remain canonical;
- no live production writes;
- no invented statutory rate/user identity;
- ambiguity fails closed for money;
- server-side permissions/scopes;
- idempotency for financial/evidence writes;
- add negative/boundary tests.

Before coding:
1. inspect the installed/current HRMS v16 native capability;
2. write/update ADR if a custom concept is proposed;
3. record current tests and affected files.

Deliverables:
- code
- tests
- migration/rollback if required
- task note with evidence
- no unrelated refactor

Acceptance tests:
<IDs from 08_TEST_ACCEPTANCE_MATRIX.md>

Stop instead of guessing if:
<chunk-specific conditions>
~~~

## Agent completion report

~~~markdown
# CHUNK-XX completion

## Objective
...

## Baseline
- branch:
- base commit:
- Frappe:
- ERPNext:
- HRMS:
- site:
- environment:

## Native capability inspected
...

## Changes
...

## Source-of-truth impact
...

## Schema/data migration
...

## Permission/scope impact
...

## Idempotency/retry behavior
...

## Tests
- command:
- result:
- named regression IDs:

## Staging verification
...

## Security/privacy review
...

## Rollback / forward correction
...

## Known gaps
...

## Files changed
...

## Next allowed chunk
...
~~~

## Reviewer checklist

~~~markdown
[ ] scoped to one chunk
[ ] no duplicate native ledger
[ ] no hidden production/live write
[ ] no statutory value invented
[ ] effective dates handled
[ ] permission checked server-side
[ ] row scope tested
[ ] retry/idempotency tested
[ ] negative/boundary tests added
[ ] migration dry-run/preview exists where needed
[ ] rollback/forward-correction documented
[ ] secrets/sensitive data absent
[ ] task/architecture docs updated
~~~

## Decision log template

~~~markdown
### ADR-XXX — title

Date:
Status: Proposed | Accepted | Superseded

Context:
Native v16 capability inspected:
Options:
1.
2.
3.

Decision:

Why:

Source of truth:

Effective-date behavior:

Permission/privacy impact:

Migration:

Rollback:

Tests:

Consequences:
~~~

## Exception-rule template

~~~yaml
code: PAY_SALARY_ASSIGNMENT_OVERLAP
domain: Payroll
severity: BLOCK

scope:
  employee: required
  company: required
  period: required

detection:
  canonical_sources:
    - Salary Structure Assignment
  condition: more_than_one_conflicting_effective_assignment

message:
  what: Multiple salary assignments overlap this payroll period.
  consequence: Payroll cannot determine one compensation basis.
  evidence: Show assignment IDs and date ranges.
  actions:
    - Open assignments
    - Request compensation review

auto_resolution: prohibited
resolution_requires:
  - authorized compensation maker
  - effective-date correction
revalidate_after_resolution: true
~~~

## UI task template

~~~markdown
User role:
Primary task:
Normal path:
Exception path:
Minimum fields shown:
Advanced fields hidden:
Server API:
Permission/scope:
Offline/retry behavior:
Success acknowledgement:
Error copy:
Bangla translation required:
Performance budget:
Playwright scenarios:
~~~

## Rule-release template

~~~markdown
Rule domain:
Jurisdiction:
Legal regime:
Population:
Effective from:
Effective to:

Authoritative source:
Gazette/circular/reference:
Reviewed by:
Reviewed date:

Native HRMS capability:
Tradexcel extension:

Regression fixtures:
Migration impact:
Historical payroll impact:
Approval:
~~~

## Handoff principle

A good handoff lets the next agent continue using only the repository. Do not put
critical architecture decisions only in chat, terminal history or personal notes.
