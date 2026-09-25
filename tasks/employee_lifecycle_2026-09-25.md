# Employee Lifecycle — 2026-09-25

## Scope and implementation

This source-only slice validates native HRMS Employee Transfer, Employee
Promotion, Employee, and Salary Structure Assignment records. It adds no
employment, payroll, or history ledger and has no schema migration.

- Cross-company Employee Transfer uses HRMS's `create_new_employee_id` path.
- A Promotion changing CTC requires a submitted SSA for that Employee, effective
  on the promotion date, in the Employee's current Company, with an explicit
  `custom_tradex_pay_basis` on the linked Salary Structure.
- A recorded relieving date cannot be removed or changed, and a completed
  `Left` Employee cannot be reactivated to model a rehire. Ordinary exit-related
  Employee metadata remains maintainable. Native new-ID transfer cancellation
  can reverse the old Employee's status and relieving date inside HRMS's own
  cancellation method.

## Local v16 verification

- The intended DB is the existing `/home/sanchita/mariadb-v16` data directory
  on `127.0.0.1:3307`; it was started without changing site config or touching
  the system MariaDB on 3306. `list-apps` reports Frappe 16.34, ERPNext 16.35,
  HRMS 16.19, and `tradex_hr`.
- A fresh `--with-files` backup was taken at 2026-09-25 11:14 Asia/Dhaka before
  migration. Database gzip and both file archives passed integrity checks;
  full sizes and hashes are recorded in `BACKUPS.md`.
- Standard `bench --site hrms-v16.localhost migrate` and `clear-cache` completed
  successfully. The four maternity/welfare DocTypes are installed and the
  staging site returns HTTP 200. The migration's search-index job completed;
  `bench show-pending-jobs` reports no pending jobs.
- Synthetic native transfer submission/cancellation and rehire integration
  passed with explicit cleanup. Lifecycle unit/integration, separation-flow,
  and identifier tests passed together (`11 passed`).
- Clean full suite: `551 passed, 2 skipped` (40 deprecation warnings).
- The local start/stop procedure is in `tasks/local_v16_start_stop_guide.md`.

No production site, real employee record, payroll record, or site credentials
were changed. No PR was merged.

## PR #20 hardening — 2026-09-25

- Provisioned native Employee Transfer and Employee Promotion permissions for
  `Tradexcel HR Manager`; Owner/Director and Compliance Auditor remain read-only.
  No native HR User/Manager role was added to the custom-role path.
- Added scoped Employee/Company checks for Transfer, Promotion, and SSA. Existing
  Employee company, branch, department, designation, grade, employment type,
  CTC, and native Internal Work History changes now require the matching native
  Transfer/Promotion submit context. New Employee creation and separation-only
  status/relieving-date edits remain valid.
- SSA remains the native salary authority. HR Manager can save a draft but cannot
  submit. A different `Tradexcel Payroll Approver` can submit; owner-based
  maker/checker also blocks a User who holds both roles. The before-submit guard
  remains active when an HRMS bulk helper saves with ignored permissions.
- Transfer/Promotion cancellation blocks submitted Attendance, overlapping or
  later submitted Salary Slip, dependent submitted SSA, effective legal-review
  snapshots, and later submitted movement. A financial Promotion requires its
  exact-date SSA to be safely cancelled first; the SSA itself cannot be cancelled
  after a submitted Salary Slip or later assignment consumes it.
- Installed-source review used this bench's HRMS 16.19.0. Native Transfer and
  Promotion mutate Employee through their own submit/cancel methods; the app
  wraps those methods with a tightly scoped, restored `frappe.flags` context.
  The Employee Promotion property UI permits editable Employee fields such as
  grade and employment type, so the guard covers those fields too.
- Pre-migration staging audit: no Employee Transfer or Employee Promotion rows;
  no custom DocPerm rows for either doctype; no SSA Workflow; 227 submitted SSAs.
  Native SSA DocPerm gave HR Manager/HR User submit, while Tradexcel HR Manager
  had draft create/write only and Payroll Approver had no row. The migrated
  matrix now gives Payroll Approver write/submit/cancel without create.
- A fresh `--with-files` backup was verified and recorded before standard
  `bench --site hrms-v16.localhost migrate` and `clear-cache`. The site remained
  on `127.0.0.1:3307`; no site credentials or production settings changed.
- Site-backed synthetic tests prove scoped HR Manager Transfer/Promotion,
  get_list/get_doc company isolation, direct-edit rejection including as
  Administrator, native Internal Work History, HR Manager SSA draft, independent
  Payroll Approver submit, dual-role self-approval rejection, cross-company SSA
  denial, financial Promotion/SSA reversal ordering, and cancellation after
  Attendance or a later movement. The completed Employee Separation test and
  Joiner/Daily Wage/payroll/maternity integrations all pass.
- Clean final Tradexcel suite: `557 passed, 2 skipped`. Compileall, all 58 app
  JSON files, and `git diff --check` pass. No JS/assets changed. Synthetic
  lifecycle Users, User Permissions, Employees, Transfers, Promotions, and SSAs
  were verified absent after cleanup; zero Transfer/Promotion rows remain.
- The first full run exposed four unrelated synthetic-company tests failing on
  two stale test-only payroll Companies left by earlier runs. Their company,
  employee, structure, and SSA counts were checked; a fresh backup was taken,
  and the repository's scoped synthetic-company cleanup routine removed only
  those fixtures. The subsequent clean full suite passed.
