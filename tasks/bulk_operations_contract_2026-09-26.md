# Bulk operations contract — 2026-09-26

This contract records the canonical mutation path at the current stacked head.
It is an engineering route map, not approval to change real employees or legal
configuration. Native Frappe/HRMS documents remain the only ledgers.

| Domain | Classification | Canonical route and boundary |
| --- | --- | --- |
| Shift | NATIVE_SECURED | HRMS Shift Assignment Tool, with the Workforce selected-Employee scope extension; submitted native Shift Assignment. |
| Salary / SSA | DRAFT_NATIVE_WORKFLOW | HRMS Bulk Salary Structure Assignment surface prepares draft native SSAs for Workforce makers; independent Payroll Approver submits. |
| Attendance correction | DRAFT_NATIVE_WORKFLOW | Daily Attendance Board prepares draft native Attendance Requests; independent approver submits, allowing HRMS to create/update native Attendance. |
| Leave entitlement | NATIVE_SECURED | HRMS Leave Control Panel, with selected-Employee scope and reviewed Leave Policy/Period configuration. No invented entitlement. |
| Overtime | DRAFT_NATIVE_WORKFLOW | Workforce preview prepares draft native Overtime Slips; Payroll Approver submits and HRMS produces native Additional Salary. |
| Employee master data | INTENTIONALLY_PER_RECORD | Native Employee form for ordinary fields; native Transfer/Promotion for guarded lifecycle fields. Frappe Data Import remains System Manager-controlled pending its queued authorization review. |
| Onboarding / import | INTENTIONALLY_PER_RECORD | Native Job Opening → Applicant → Offer → Onboarding → Employee, or reviewed direct hire. Native Data Import is available only to its authorized administrator. |
| Transfer | INTENTIONALLY_PER_RECORD | Native Employee Transfer and Internal Work History. No direct bulk Employee department/branch rewrite. |
| Promotion | INTENTIONALLY_PER_RECORD | Native Employee Promotion and Internal Work History, with submitted SSA for financial changes. |
| Exits | INTENTIONALLY_PER_RECORD | Native Employee Separation, relieving date, and Full and Final Statement. No mass exit action without an approved need. |
| Payroll blockers | ALREADY_COMPLETE | Resolve each at its authority: Attendance Request, Shift Assignment Tool, SSA, Overtime Slip, tax/account setup, native Payroll Entry or payment evidence. No “fix everything” endpoint. |
| Statutory classification | BLOCKED_CONFIGURATION | Explicit reviewed, effective-dated classification in existing Workforce review DocTypes. Legal scope and rates require an owner/legal decision. |
| Benefit enrollment | BLOCKED_CONFIGURATION | Explicit reviewed enrollment snapshots in existing Workforce DocTypes; native payroll/accounting remain financial authority. |

## Employee Data Gaps convergence

Before this phase, `bulk_fix.resolve_gap` was a second whitelisted mutation
endpoint for Employee department, designation and holiday list. The Employee
lifecycle guard already blocked the first two direct changes; the third
duplicated native Employee maintenance. It was removed. The report still finds
gaps, but now links to the native Shift Assignment Tool, Bulk Salary Structure
Assignment, Employee Transfer/Promotion, or the permission-aware Employee List.
No report-selected Employee IDs are sent to a bulk mutation method.

The report formerly queried every Employee in an allowed Company through raw
SQL. A synthetic Company+Branch-scoped attendance user could obtain a synthetic
Employee in another Branch. The report now derives its Employee IDs with the
existing native permission-aware `permitted_employee_names` helper and binds
those IDs to SQL. The helper explicitly requests the complete authorized
population rather than Frappe's default first page. Company, Branch,
Department, manual-filter, zero-scope and direct execution are covered by the
site integration test. The old report also inferred wage structures from their
names and Employment Type. It now uses the canonical submitted SSA and its
Salary Structure's explicit pay basis; multiple historical SSAs no longer
misreport as simultaneous conflicts.

The report's bundled JavaScript is the only active source. Standard migration
cleared the stale `Report.javascript` copy; the installed Workspace remained.
The old bulk-fix endpoint and associated tests were retired and replaced with
report convergence tests.

## Data Import boundary

Installed Frappe `DataImport.validate_doctype` requires import permission on
the target DocType. `Importer.update_record` loads the existing Employee and
saves it through normal validation; an existing Employee's guarded lifecycle
field update was rejected in a synthetic site-backed test. Workforce Suite Manager
currently lacks Employee `import` and Data Import `create`, so no custom role
was granted general import access in this phase. Frappe's background-job retry
path warrants a focused security review before broader import provisioning:
its deadlock retry call does not propagate the original `user` argument, and a
job initialized without one defaults to Administrator. This is a framework
boundary, not permission to bypass it with custom import code. Review in the
security/privacy phase; native per-record workflows remain available.

The older `docs/bulk_operations_roadmap.md` lists letter templates, reminder
calendars, percentage revision batches and mass lifecycle actions as pending.
Those proposals are **OUT_OF_CURRENT_ROADMAP** unless a current approved
requirement depends on them. They are not grounds for a second ledger or a
mass-submit action. The old report Query Report and payroll-draft counts in
that September 17 snapshot are superseded by later task evidence.

The remaining bulk-domain labels above represent intentional native per-record
workflows or configuration gates, not missing custom bulk engines. Browser UAT
and real staff provisioning remain separate. Synthetic records only were used
for the report and Data Import probes and were explicitly cleaned.

## Release convergence follow-up — 2026-09-27

PR #37's installed `before_job` guard now rejects lost/disabled queued actors,
including the native retry identity loss described above; PR #39 closes native
record/field scope gaps. General Data Import remains intentionally restricted
to its authorized administrator; Import Reviewer is not an unrestricted importer.
This is an explicit per-record/administrative design, not a missing custom bulk
engine. Future delegation requires a separate target-DocType/scoped import UAT.
PR #41 proves real 31-row native Shift worker execution and changed-scope rejection.
