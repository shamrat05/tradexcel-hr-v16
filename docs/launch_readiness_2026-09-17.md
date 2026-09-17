# Tradexcel HR launch gate — 17 September 2026

This is a site-specific audit, not a claim that the system is production-ready.
Run `sync/audit_hrms_readiness.py` and `sync/audit_all_salary_slips.py` from the
bench's `sites` directory whenever data or configuration changes.

## Confirmed now

- 474 Salary Slips remain as drafts across August/September; zero submitted,
  zero cancelled, zero active employee-period duplicates. Superseded cancelled
  originals were deleted after the database backup
  `20260917_060142-hrms_localhost-database.sql.gz`.
- No Salary Slip GL entries or Payment Entry references were found. One
  submitted August Payroll Entry (`HR-PRUN-2026-00001`) remains, but no current
  Salary Slip links to it. Review and resolve it before live payroll approval.
- All six active Salary Structures have zero deduction rows. The code can now
  calculate configured fixed/formula deductions, but it does not create tax,
  provident-fund, or gratuity policy. Zero submitted Income Tax Slabs were found.
- 124 worker draft slips across August/September have zero gross pay (66 in
  September). These require punch/identity/leave/reconciliation review; do not
  auto-pay or invent wages.
- Only two enabled Users and no assigned Tradexcel-specific roles were found.
  A role or workflow definition alone does not grant anybody authority.
- Administrator can create a User, assign multiple roles to that User, and add
  User Permission records for Company, Branch, or Department. The payroll
  preparer role deliberately lacks Salary Slip submit permission; the separate
  approver role has it. Employee/Worker currently has no broad Employee read
  permission until own-record ESS restrictions have been tested.
- No submitted Leave Policy was found; verify whether leave allocations and
  balances are still valid before treating leave as payroll-ready.

## Build from Frappe HR first, customize only missing workflow

Frappe HR already has Employee Onboarding/Promotion/Transfer/Separation,
Full and Final Statement, Leave Application, Attendance Request, Salary Slip,
and Data Import for bulk inserts/updates. They are **not** configured and
end-to-end verified for Tradexcel merely because their DocTypes are installed.

1. **Money gate:** reconcile zero-wage drafts and salary assignment coverage;
   choose the tax year/slab, company PF/gratuity decisions, payment accounts,
   bank advice format, and authorized payroll approvers. Test net pay, journal
   posting, payment and rollback in a staging clone before any submission.
2. **Access gate:** assign named users to HR admin, preparer, reviewer/approver,
   branch manager, and employee self-service roles. Test each role with a real
   non-admin account and verify company/branch/employee row restrictions.
3. **Lifecycle gate:** configure onboarding/separation templates and letter
   formats; exercise promotion, transfer, leave, attendance regularization and
   full-and-final on sample employees. Do not rebuild standard flows needlessly.
4. **Scale gate:** use standard Data Import for reviewed bulk inserts/updates;
   add preview, row-level validation, dry-run and rollback for Tradexcel-specific
   mass rules. The legacy Selevo bulk importer is **not** safe as the future
   incremental feed: it matches by name, invents missing dates, and assumes TCL.
5. **Decision gate:** a daily queue should group missing punches, duplicate PINs,
   unmatched employees, zero/negative wages, late/OT anomalies, and leave
   conflicts, with owner, due date, evidence and resolution. A dashboard count
   without a documented action is only detection.

No statutory rate or worker tax exemption should be enabled from a guess.
Policy exceptions must be previewed, dated, auditable, and must not silently
rewrite approved/paid periods. Do not move the site to Contabo or expose the
biometric bridge publicly until access, TLS, backups, device authentication,
and restore tests pass.

## Administrator access setup

In Desk, open **User** to create/enable a login and attach its Employee record.
One User can hold several Tradexcel roles; assign only the responsibilities that
person actually performs. Use **User Permission** for the permitted Company,
Branch, and Department; use **Role Permission Manager** to inspect DocType
actions. Test with that user's own login—Administrator bypasses ordinary
restrictions and cannot prove that a manager or employee sees only their scope.
The Employee/Worker role is intentionally not a working self-service grant yet.
Do not assign it expecting salary or personnel privacy to be solved.
