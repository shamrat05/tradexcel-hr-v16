# Tradexcel HR v16 — agent operating rules

This file is mandatory for every coding agent working in
**shamrat05/tradexcel-hr-v16**.

## 1. Start here

Read, in order:

1. **README.md**
2. **docs/architecture/README.md**
3. the architecture files required by your assigned chunk
4. **docs/architecture/09_IMPLEMENTATION_CHUNKS.md**
5. **docs/architecture/08_TEST_ACCEPTANCE_MATRIX.md**
6. relevant current task/audit files under **tasks/**
7. **BACKUPS.md** before any schema/data/destructive work

Do not implement from chat history alone. Repository documentation is the handoff.

## 2. Work one implementation chunk at a time

The canonical build plan is
**docs/architecture/09_IMPLEMENTATION_CHUNKS.md**.

Do not accept a vague instruction such as "finish payroll" as permission to edit
multiple unrelated domains. Bound the work to one chunk, its prerequisites and
its acceptance tests.

Use a dedicated branch/worktree for each implementation slice.

## 3. Native v16 first

Before adding a custom DocType, ledger, calculation engine or navigation shell:

1. inspect the **installed/current Frappe/ERPNext/HRMS v16** capability;
2. record whether the decision is:
   - REUSE_NATIVE
   - EXTEND_NATIVE
   - CUSTOM_REQUIRED
3. add/update an ADR when a custom concept is proposed.

Do not rebuild a feature merely because the older v15 app lacked it.

Important v16 examples already identified:

- native Workspace Sidebar;
- native cross-midnight shift context;
- native Auto Attendance;
- Overtime Type / Overtime Slip;
- Payroll Entry / Salary Slip;
- Payroll Correction;
- Arrear.

## 4. Canonical source-of-truth rules

Frappe/HRMS native records remain canonical where they own the domain.

- User != Employee.
- Employee Checkin = raw/evidence event.
- Attendance = payroll-facing daily work state.
- Leave uses native leave documents/ledger.
- shifts use native Shift Type/Assignment/Schedule.
- Salary Structure defines the template.
- Salary Structure Assignment defines employee compensation/effective date.
- Additional Salary/native specialized docs hold authorized one-off money.
- Payroll Entry is the payroll batch.
- Salary Slip is the payroll result.
- Journal Entry/GL are accounting truth.
- Native Payroll Correction/Arrear are preferred for supported retroactive cases.

Custom code may validate, orchestrate, aggregate, preview, integrate and explain.
It must not create a duplicate ledger without an accepted ADR.

## 5. Payroll safety

Never:

- calculate production payroll directly from raw Employee Checkin;
- infer pay basis solely from Employment Type, designation, branch or department;
- silently pick one of overlapping salary assignments;
- silently seed a missing wage from an external JSON/Excel file;
- invent a missing IN/OUT time;
- mutate paid/submitted payroll because a source record changed later;
- hardcode a statutory rate from memory;
- create duplicate payroll on retry;
- bypass maker/checker for controlled actions.

Critical ambiguity **fails closed for money** and becomes an actionable case.

## 6. Effective dates

Every financially relevant resolver must use an as-of date or interval.

Never reconstruct historical payroll from current Employee values.

Test boundaries for:

- joining/releasing;
- salary changes;
- pay-basis changes;
- shift changes;
- policy/legal versions;
- leave/Attendance corrections;
- transfers/promotions where financially relevant.

## 7. Bangladesh legal/compliance rule

Do not invent law.

Any statutory implementation requires:

- current authoritative source;
- applicability to the company/establishment/population;
- effective date/version;
- authorized compliance/legal/accounting review;
- regression fixtures;
- historical version preservation.

Bangladesh legal regime may differ by establishment/population, including EPZ and
sector-specific wage instruments. Do not assume one universal company profile.

The Bangla authoritative text/current Gazette prevails where applicable.

## 8. Sensitive personal data

The app processes biometric, selfie and real-time location data.

Treat this as high sensitivity:

- no sensitive files in Git;
- no face/selfie/raw employee evidence in prompts/task notes;
- minimize collection;
- server-side record scope;
- private storage;
- approved retention/deletion;
- no payroll punishment directly from face/GPS anomaly score;
- no organization-wide live-location access merely because a user has a manager role.

Read **docs/architecture/06_SECURITY_PRIVACY_ROLES.md** before modifying these
features.

## 9. Permissions

UI hiding is not security.

Every sensitive API/action checks:

~~~text
named authenticated user
+ role capability
+ record scope
+ document/workflow state
+ server-side permission
~~~

Add negative tests for out-of-scope direct API access.

Preserve no-self-approval on controlled workflows.

Do not invent production users, emails, approvers or role assignments.

## 10. Idempotency and retries

Evidence and financial writes need stable logical IDs.

A retry after lost response must return/reconcile the existing result, not create
another one.

Test:

- browser double click;
- network timeout then retry;
- worker/process restart;
- duplicate device upload;
- concurrent callers.

## 11. Staging only unless explicitly coordinated

No coding agent may, as part of normal implementation work:

- migrate the production/current site;
- submit/cancel production Salary Slips or Payroll Entries;
- alter real employee compensation;
- import employees to production;
- issue live biometric device commands;
- purge production evidence;
- rotate production secrets.

Use the isolated v16 staging environment documented under **tasks/**.

Before any site mutation, print/record the exact bench, site, database/environment,
branch and commit.

## 12. Backups and destructive work

Read **BACKUPS.md** first.

Before a destructive or business-data migration:

- fresh backup with files;
- verify archive integrity;
- record checksum/path;
- dry-run/preview affected rows;
- document rollback/forward-correction;
- use isolated staging first.

A backup is not considered operationally proven until a restore rehearsal passes.

## 13. Tests are part of the change

Use the IDs in **docs/architecture/08_TEST_ACCEPTANCE_MATRIX.md**.

For every defect, add a regression test that would have failed before the fix.

For P0/P1 work, cover as applicable:

- unit;
- integration against v16;
- negative permissions;
- effective-date boundaries;
- concurrency/idempotency;
- recovery;
- browser/Playwright;
- performance for high-volume paths.

Do not hide a real regression with a skip.

## 14. Imports/bulk changes

All bulk changes follow:

~~~text
preview -> validate -> permission/scope -> apply -> result/exceptions
~~~

No blind CSV-to-database path.

The same domain validation service should be used by UI, import and API.

## 15. Navigation/UI

Frappe v16 native Workspace Sidebar is the target navigation shell.

Do not add more custom rail/DOM repair logic unless an ADR demonstrates a native
gap. Migrate to native sidebar fixtures with route parity tests before deleting
the existing rail.

Design normal-user screens around tasks/exceptions, not raw DocType knowledge.

UI strings must remain translatable; business logic must not depend on translated
labels.

## 16. Secrets and repository hygiene

Never commit:

- site_config secrets;
- API keys/tokens;
- payroll exports;
- employee private data;
- biometric templates;
- selfies/reference photos;
- location history exports;
- backups;
- bridge database;
- production screenshots containing private HR data.

Review the full diff before push.

## 17. Stop instead of guessing

Stop and report a blocker when:

- statutory applicability/rate is unknown;
- employee compensation/pay basis is ambiguous;
- a destructive operation lacks a verified backup;
- native v16 behavior has not been inspected;
- production/staging identity is unclear;
- an approver/user identity would need invention;
- business policy is missing;
- the requested shortcut violates a source-of-truth or audit invariant.

Partial safe completion is better than guessing.

## 18. Required completion note

Every chunk records:

- objective;
- base branch/commit;
- environment/site;
- native capability inspected;
- files/schema/data changed;
- permissions/scopes;
- idempotency/retry behavior;
- tests and exact results;
- staging verification;
- rollback/forward correction;
- known gaps;
- next allowed chunk.

Use **docs/architecture/11_AGENT_HANDOFF_TEMPLATE.md**.

## 19. Current status warning

The v16 staging branch has been migrated and tested, but this does **not** mean
production payroll is ready. The architecture audit identifies remaining P0/P1
gates, especially custom payroll retirement/native parity, explicit pay basis,
Attendance finalization, statutory/tax configuration, real user/scope UAT,
privacy/retention hardening and restore rehearsal.

Do not claim production readiness until the documented production gate passes.
