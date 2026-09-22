# 10 — Release, migration, backup and recovery

## Environments

At minimum distinguish:

~~~text
production/current
staging-v16
test/CI
developer local
~~~

Agents must print/record the target site and bench before any site mutation.

## Before any schema/data migration

1. confirm branch/commit;
2. confirm site/database;
3. read BACKUPS.md;
4. take fresh backup with files;
5. verify archive integrity;
6. record checksum/path;
7. dry-run migration/transform where possible;
8. produce affected-record counts;
9. require explicit coordinator approval for live mutation.

## Data migration rule

Never mix:

- schema migration;
- financial reclassification;
- cleanup/deletion;
- production cutover

in one opaque script.

Separate reversible steps with checkpoints.

## Migration scripts

Must be:

- idempotent or explicitly one-shot with migration marker;
- scoped;
- deterministic;
- dry-run capable when changing business data;
- count/report affected records;
- fail closed on ownership/conflict;
- not commit inside reusable unit tests;
- tested against a restored staging copy.

## Financial migration

For pay basis, salary assignment or policy binding:

1. produce preview;
2. show old source/new source;
3. classify exact conflicts;
4. do not silently choose for ambiguous employees;
5. owner/HR approves ambiguous cases;
6. migrate only approved rows;
7. rerun readiness;
8. no submitted Salary Slip should be created by migration.

## Biometric mapping migration

Preserve device serial/PIN and effective history. If historical validity cannot be
reconstructed, mark unknown interval and block affected historical reprocessing
rather than inventing dates.

## Sidebar migration

Native Sidebar migration is non-financial but still stage it:

1. add fixtures;
2. migrate staging;
3. route sweep;
4. compare custom/native parity;
5. feature flag if needed;
6. remove custom rail;
7. keep rollback commit.

## Backup restore rehearsal

A backup is not proven until restored.

Quarterly/major-release drill:

~~~text
new isolated database/site
-> restore DB
-> restore public/private files
-> install exact app refs
-> migrate
-> run app suite
-> run data counts/checksums
-> run payroll readiness dry run
-> verify critical private files and device config
-> record elapsed steps/failures
~~~

Never rehearse over production.

## Crash recovery expectations

### Device ingestion

At-least-once replay + idempotent application.

### Mobile attendance

Stable operation ID survives browser retry when offline queue mode is enabled.

### Payroll readiness

Read-only/recomputable.

### Payroll calculation

Native transaction/job status must be queryable after browser loss; retry must not
create duplicate active financial results.

### Payment export

Stable batch ID; re-export produces same logical batch or explicit version, not a
second uncontrolled payment.

## Rollback philosophy

Code rollback is easy only before irreversible data/financial state.

Prefer forward correction for already-submitted financial history.

Examples:

- bad UI release -> code rollback;
- bad draft payroll -> cancel/delete draft under controlled procedure;
- paid payroll error -> native correction/arrear, not database rollback;
- bad statutory rule used in paid payroll -> new corrected version + reconciliation.

## Production cutover gate

Required evidence:

- P0 architecture chunks complete;
- full test suite green;
- native payroll draft reconciled in staging;
- leave/Attendance readiness validated;
- approved statutory/tax configuration for applicable populations;
- real user/role/scope UAT;
- device backlog/mapping clean enough for chosen finalization policy;
- private-data retention/access reviewed;
- restore rehearsal passed;
- current backup taken immediately before cutover;
- rollback/forward-correction plan written;
- coordinator/owner sign-off.

## First production payroll

Treat first run as controlled launch:

1. freeze Attendance period;
2. export readiness report;
3. resolve blockers;
4. create draft payroll;
5. reconcile employee count and totals;
6. compare controlled sample manually;
7. maker review;
8. checker approval;
9. submit only after sign-off;
10. reconcile accounting;
11. prepare payment register;
12. reconcile payment result;
13. store run evidence/versions;
14. review exceptions before next cycle.

## Monitoring thresholds

Escalate on:

- duplicate payroll attempt;
- unexplained employee missing from outcome universe;
- new salary overlap;
- checkin backlog age beyond policy;
- device sequence gap;
- unusual manual correction surge;
- payroll variance above configured threshold;
- accounting mismatch;
- payment total mismatch;
- sensitive-data access anomaly;
- retention job failure.

## Secret/data review before push

Before every PR/commit involving integrations:

- grep/diff for API keys/tokens/passwords;
- no site config/private files;
- no employee payroll exports;
- no face/selfie images;
- no raw backups;
- no private bridge DB;
- no production screenshots containing sensitive HR data.

## Documentation as release artifact

Every production-impacting change updates the relevant architecture/task/runbook.
If operational truth changed but documentation did not, the change is incomplete.
