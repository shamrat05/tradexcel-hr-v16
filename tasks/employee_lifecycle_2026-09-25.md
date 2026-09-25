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
