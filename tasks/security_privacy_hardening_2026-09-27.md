# Security/privacy engineering pass — 2026-09-27

Parent: PR #38, `feat/operator-usability`, `6a19a7138a03ba3c152032b6920167804a1dda15`.
Branch: `fix/security-privacy-hardening`. Local isolated v16 staging only.

## Reproductions and fixes

- Native `frappe.client.get(Employee)` exposed synthetic CTC and bank account
  identifiers to Attendance Officer, Factory Supervisor and Branch/Department
  Manager. Employee native field permission level 1 now protects `ctc`,
  `bank_ac_no`, `iban`. Native HR/System Manager and intended financial readers
  retain access; only native HR/System Manager and Tradexcel HR Manager write
  these fields. This adds no document access. Operational + Employee role union
  does not reveal the fields. Native API and list-field filtering are tested;
  native print/export field permissions remain authoritative.
- Actual native list/API calls exposed out-of-Branch Shift Assignment, Leave
  Allocation, Additional Salary, Overtime Slip, Biometric mapping, Leave Policy
  Assignment, Leave Application, Full and Final, Field Duty, Location Ping and
  Mobile Event. Reuse the existing permission-aware Employee query/document
  restriction for these records and Shift Schedule Assignment/Shift Request.
  Attendance was already safely scoped: unchanged.
- A Payroll Entry with blank header Branch exposed its out-of-scope Employee
  child through native API and accrual reconciliation. Its list/document access
  now requires every populated Employee child to be in native Employee scope.
  Empty new forms remain governed by ordinary native DocPerms. No payroll data
  is changed; in-scope parents remain readable.
- Native Shift Schedule accepted an Employee absent from scoped preview and
  created native schedule/shift assignments. Native request processing accepted
  an out-of-scope request paired with a forged in-scope Employee ID. Both selected
  request identity and native eligibility are checked at dispatch and execution.
  Native processing, savepoints and private result handling remain in `super()`.
  Tool read is the native action-access permission; no singleton write grant.
- Mixed native HR User + Tradexcel HR Manager was incorrectly restricted to
  Assign Shift. Native-role precedence now works in Python and form JS.
  Custom-only operators still cannot schedule/process requests.
- `get_live_locations` returned an out-of-scope synthetic location; supervisor
  mobile identity checks accepted an out-of-scope Employee. The live SQL now
  includes the existing native Employee permission subquery; supervisor capture
  checks native Employee select permission. Own-Employee identity remains the
  self-service boundary. Punches still do not imply payable Attendance.
- Device Admin is deliberately Employee-select-only. Mapping APIs now check
  select rather than requiring financial Employee-form read. Native mapping and
  device DocPerms plus Employee scope remain mandatory; no device commands ran.

## Native sharing is an explicit grant

Installed Frappe `model/db_query.py:build_match_conditions` ORs native DocShare
with User Permission conditions; `permissions.has_permission` also falls back
 to explicit shares. HRMS `hr/utils.py:share_doc_with_approver` can create such a
 grant for a designated Leave/Shift approver. This is an explicit native access
 grant, not an unshared-record test. The fixture initially designated the
 out-of-scope test reader as Leave Approver, creating that grant; the independent
 scope regression now uses Administrator as approver. No shadow ACL, framework
 patch, global sharing disable or deletion of real shares is introduced.
 Production persona provisioning must review explicit shares and approver
 assignments alongside Roles/User Permissions, including after scope changes.

## Privacy and extension boundaries

- No new public/guest API, generic identity state or permission database.
- Salary Slip historical Branch/Department snapshots remain intact.
- Earlier PR #37 handles lost queue identity and private native realtime results;
  this phase keeps those execution boundaries.
- Bridge controls already require target permissions, host allowlisting, HTTPS
  for non-local hosts, bounded requests and disabled redirects. No external
  terminal was contacted and no secret was printed.
- Face/location retention is a company privacy decision. No automatic evidence
  purge or invented statutory retention period is added. The existing policy's
  retention setting is not represented as proof of an active purge service.
- Native explicit sharing, real staff configuration, physical device acceptance,
  and wider browser print/export UAT remain release/configuration gates.

## Validation and migration

Fresh backup `20260927_052730-hrms-v16_localhost-`: gzip and both tar archives
verified, exact sizes/hashes in BACKUPS.md. Standard migrate/cache clear applied
native Property Setters/DocPerms. Later Python permission hooks require cache
clear only, not a second schema migration. Node 24 syntax and app build passed.
Focused/full results and final cleanup are recorded below after completion.

Final validation: **9 focused passed**; **621 full-suite passed, 0 skipped**
(96 warnings, 474.40 seconds). Existing shift baseline regression now expects
the downstream native record permission to reject the old bypass; native request
control supplies the actual native Employee payload rather than a spy-only partial
row. No tests removed. Compileall, 61 tracked JSON parses, Node 24 syntax/build and
`git diff --check` passed. Harness dependency-order teardown and 16 stable marker
prefix aggregate checks reported zero synthetic identities/linked records.
No production/core files, real accounts or business records changed.
