# Bulk salary authority — 2026-09-25

## Scope and starting point

Started from `feat/native-bulk-shift-assignment` at `52c1af10d44950542a126dc1d56009d6488f71be`, created branch `feat/bulk-salary-authority`, and kept PR #25 untouched. Runtime was Frappe 16.34.0, ERPNext 16.35.0, HRMS 16.19.0, Workforce Suite 0.1.0 on `hrms-v16.localhost` / MariaDB `127.0.0.1:3307`.

## Installed HRMS behavior and baseline

Inspected the installed sources:

- `apps/hrms/hrms/payroll/doctype/bulk_salary_structure_assignment/bulk_salary_structure_assignment.py`
- `apps/hrms/hrms/payroll/doctype/salary_structure_assignment/salary_structure_assignment.py`
- `apps/hrms/hrms/payroll/doctype/salary_structure/salary_structure.py`
- Frappe `Document` and `frappe.handler.run_doc_method` in `apps/frappe`.

The native singleton already provides Company/Branch/Department/Designation/Grade/Employment Type filters, advanced Employee filters, active/joining/relieving-date checks, overlap exclusion, Grade default-base suggestion, a selectable preview, native Shift-independent SSA creation, per-employee savepoints, completion realtime events, and queue dispatch above 30 rows. The native helper `create_salary_structure_assignment()` saves with `ignore_permissions=True` and submits. HRMS's Salary Structure Assignment controller checks the SSA Company against the selected Structure's Company and validates effective dates/tax currency, but the bulk controller trusts the posted selected Employee rows and amounts. The native Employee query builder call does not apply Frappe User Permissions automatically.

Before app access was enabled, a Workforce Suite Manager could not call the actual document method because there was no DocPerm. The synthetic native-HR control's unextended preview returned out-of-Branch, out-of-Department, and cross-Company synthetic Employees. Calling the unextended controller with out-of-scope Branch and Company Employee IDs did not leave an SSA: existing Workforce Employee-company/scope validation and the SSA maker-checker hook rejected those writes. This establishes the live app boundary, not a claim that HRMS's helper itself validates scope. The native source passes client-supplied `base`, `variable`, Structure, account, tax slab and currency to the SSA helper; the adapted endpoint now validates/canonicalizes these inputs before native submission or draft insertion.

The old Workspace label `Bulk Salary Structure Assignment` pointed to nonexistent `Salary Structure Assignment Tool`; installed HRMS names the native singleton `Bulk Salary Structure Assignment`.

## Design

Used Frappe v16 `extend_doctype_class` to compose a narrow mixin with the installed native controller. No HRMS/Frappe core files, new DocTypes, or salary ledgers were added.

- Workforce Suite Manager and Workforce Payroll Manager get scoped native preview and create native **draft** SSAs only.
- An independent Workforce Payroll Approver submits selected native SSA drafts through Frappe's existing Salary Structure Assignment List View bulk submit endpoint. Existing SSA DocPerm and `before_submit` maker/checker hooks remain authoritative; a maker who also holds approver role cannot submit their own SSA.
- Users with native HR User/HR Manager retain the installed native one-step behavior. A tightly scoped request-local flag is set only inside that native bulk apply call; employee/company visibility is rechecked by existing lifecycle validation. A mixed HR User + Workforce Payroll Manager control exercises this precedence.
- Preview intersects native eligible rows with permission-aware `frappe.get_list("Employee")`. Apply rechecks selected IDs, Employee status/dates, Company/Branch/Department scope, duplicate rows, and same-date draft/submitted SSA. Queued work repeats the checks when execution starts.
- Active submitted Salary Structure and explicit `custom_workforce_pay_basis` (`Monthly Salary` or `Daily Wage`) are mandatory. Company/currency are taken from the Structure. The maker must use the Company's configured payroll payable account, validated as a same-Company leaf Liability Account with compatible currency. Tax slabs must be readable, submitted, enabled, and match Company/currency.
- Base and variable must be finite and nonnegative. No maximum was invented. Zero Base can remain a clearly visible draft, but the canonical Daily Wage readiness resolver blocks it as missing/zero base.
- Same-date existing drafts or submitted assignments are omitted/denied. A submitted Salary Slip whose end date reaches the proposed effective date blocks a retroactive draft.
- Per-row savepoints and native realtime result UX remain. More than 30 rows use the native threshold and queue; the job revalidates at start.
- Grade `default_base_pay` is only a convenience suggestion. The form explains that Base means monthly base or daily rate according to the explicit Structure basis; it is never an approved individual amount until a separate approver submits the native SSA.

## Permissions and Workspace

Added read/write/create (no submit/cancel/delete/export) on `Bulk Salary Structure Assignment` for Workforce Suite Manager and Workforce Payroll Manager only. Added read-only `Income Tax Slab` access to those two roles for Structure-linked slab selection. No payroll-role DocPerm was broadened. Corrected the Workspace shortcut target to the installed native DocType. Site-backed Desk rendering showed the shortcut for HR Manager and Payroll Manager and hid it from Payroll Approver, Finance, Branch Manager and Worker; actual tool endpoints denied those excluded roles.

The integration covers HR Manager/Payroll Manager draft creation, native HR User control submit, mixed native/custom role behavior, independent approver bulk submission, dual maker/approver self-submission denial, Company/Branch/Department scoping, manual filter and Employee-ID tampering, invalid/mismatched Structure/Company/currency/account/tax inputs, negative/invalid numeric values, same-date duplicate authority, consumed payroll guard, partial success, queue threshold/revalidation, explicit monthly/daily resolver parity, zero-base readiness, Workspace visibility, and absence of Attendance/Checkin/Payroll Entry/Salary Slip/Additional Salary/Arrear side effects.

## Backup and migration

Read `BACKUPS.md`; before DocPerm/Workspace migration took a fresh `bench backup --with-files`:

- prefix `/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/20260925_220031-hrms-v16_localhost-`
- timestamp `2026-09-25 22:00:38 Asia/Dhaka`
- database gzip 29,500,665 bytes, SHA-256 `15d9c3178f37676a5d58830a8fb1e6f9d55fa69045fcab6639b91e9f29fddc87`; `gzip -t` passed
- public archive 10,240 bytes, SHA-256 `407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532`; tar listing passed
- private archive 38,932,480 bytes, SHA-256 `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`; tar listing passed
- site-config backup 245 bytes, SHA-256 `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`.

Ran only standard `bench --site hrms-v16.localhost migrate` and `bench --site hrms-v16.localhost clear-cache`. No manual metadata SQL was used. The installed permissions were then exercised through actual Frappe methods/endpoints. Test fixtures restore the pre-test native singleton filters; stable-prefix checks after the suite found zero synthetic `persona-bulkssa` Users, Employees, or SSAs.

## Validation and remaining boundaries

Focused report/pay-basis/SSA/lifecycle/shift/workspace regressions: 32 passed. Full Workforce suite: **573 passed, 0 failed, 0 skipped**. `compileall`, all 62 app JSON files, Node 24.15.0 syntax check, Node 24.15.0 `bench build --app workforce_suite`, and `git diff --check` passed. Build emitted only the existing Browserslist database age warning.

Native HRMS users retain one-step behavior only through the installed native bulk tool. Workforce preparers remain draft-only; approval is over native SSA records. No Employee, Salary Structure, SSA, payroll, attendance, leave, or accounting records from real staff were changed. Browser UAT for the amount/base explanation, live realtime/queue display, and native list-view bulk submission remains open. Company payroll payable-account/tax setup and real operator provisioning remain company configuration, outside this synthetic slice.

This is only the Salary Structure Assignment bulk domain. Onboarding/import, attendance corrections, leave allocations, overtime, payroll blocker handling, statutory classifications/benefits, transfer/promotion, and exits remain separate bulk/workflow slices.
