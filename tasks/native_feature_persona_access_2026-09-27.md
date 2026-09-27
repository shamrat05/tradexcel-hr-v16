# Native feature persona access convergence — 2026-09-27

## 1. Exact starting SHA and branch

- Base branch: `feat/native-hr-workspace-completeness`
- Base PR: `#49` (open, draft, unmerged)
- Starting SHA: `31249677c7c8ba822ca6404747ff312bdf6f53df`
- Working branch: `fix/native-feature-persona-access`

## 2. Root cause of flaw in PR #49 persona proof

In PR #49, `tradex_hr/tests/test_hr_workspace_ui.py` defined `PERSONA_ROLES["hr_manager"] = ["Tradexcel HR Manager", "HR Manager"]`. By assigning the native ERPNext/HRMS `HR Manager` role to the test user, the test bypassed the project's strict custom-role-only persona architecture. As a result, the UI catalog exposed many native features, but Desk route access had not been verified under genuine Tradexcel-only custom roles (`assert_only_tradexcel_roles`).

## 3. Full role-isolation verification

All persona fixtures and test cases strictly enforce `assert_only_tradexcel_roles(user)`. No native HR or administrative roles (`HR Manager`, `HR User`, `System Manager`, `Expense Approver`, `Interviewer`) are assigned to any Tradexcel persona, whether in tests or in standard role setup. All access is governed strictly by custom Tradexcel roles:
- `Tradexcel HR Manager`
- `Tradexcel HR/Attendance Officer`
- `Tradexcel Employee/Worker`
- and related scoped custom roles.

## 4. Full list of newly granted Custom DocPerms by DocType and permission flags

All grants are defined in `STANDARD_PERMISSION_MATRIX` within `tradex_hr/role_setup.py` for role `Tradexcel HR Manager`:

### Read-only configuration dependencies
- `Department`: `read`, `select`, `export`
- `Branch`: `read`, `select`, `export`
- `Designation`: `read`, `select`, `export`
- `Employee Grade`: `read`, `select`, `export`
- `Employee Group`: `read`, `select`, `export`
- `Holiday List`: `read`, `select`, `export`
- `Leave Block List`: `read`, `select`, `export`
- `Overtime Type`: `read`, `select`, `export`

### Expense and travel
- `Expense Claim`: `read`, `write`, `create`, `delete`, `select`, `export`, `report` (submit/cancel omitted; maker-level only)
- `Expense Claim Type`: `read`, `select`, `export`
- `Purpose of Travel`: `read`, `select`, `export`

### Leaves and calendar assignment
- `Compensatory Leave Request`: `read`, `write`, `create`, `delete`, `submit`, `cancel`, `select`, `export`, `report`
- `Holiday List Assignment`: `read`, `write`, `create`, `delete`, `submit`, `cancel`, `select`, `export`, `report`

### Recruitment and letters
- `Job Requisition`: `read`, `write`, `create`, `delete`, `select`, `export`, `report`
- `Interview Type`: `read`, `select`, `export`
- `Employee Referral`: `read`, `write`, `create`, `delete`, `submit`, `cancel`, `select`, `export`, `report`
- `Appointment Letter`: `read`, `write`, `create`, `delete`, `select`, `export`, `report`
- `Appointment Letter Template`: `read`, `select`, `export`

### Grievance, appraisal, and training
- `Employee Grievance`: `read`, `write`, `create`, `delete`, `submit`, `cancel`, `select`, `export`, `report`
- `Grievance Type`: `read`, `select`, `export`
- `Training Program`: `read`, `write`, `create`, `delete`, `select`, `export`, `report`
- `Training Event`: `read`, `write`, `create`, `delete`, `submit`, `cancel`, `select`, `export`, `report`
- `Training Feedback`: `read`, `select`, `export`, `report` (evaluations are submitted by participants)
- `Training Result`: `read`, `write`, `create`, `delete`, `submit`, `cancel`, `select`, `export`, `report`
- `Appraisal`: `read`, `write`, `create`, `delete`, `submit`, `cancel`, `select`, `export`, `report`
- `Appraisal Cycle`: `read`, `write`, `create`, `delete`, `select`, `export`, `report`
- `Appraisal Template`: `read`, `select`, `export`
- `Goal`: `read`, `write`, `create`, `delete`, `select`, `export`, `report`
- `Employee Skill Map`: `read`, `write`, `create`, `delete`, `select`, `export`, `report`

## 5. Proof of why each granted permission is justified for Tradexcel HR Manager

- **Operational dependencies**: Selecting or filtering employees in standard HRMS doctypes requires reading the underlying classification masters (`Department`, `Branch`, `Designation`, `Employee Grade`, `Holiday List`). Without read/select permission, list filters and link pickers crash or appear empty.
- **Operational HR workflows**: Grievances, appraisals, compensatory leaves, holiday assignments, training sessions, and job requisitions are standard operational HR duties carried out by the HR department head. They do not trigger automated payroll mutations or alter company general ledger balances.
- **Expense Claim safety**: `Expense Claim` is granted edit/create/read permissions for claims coordination, but `submit` and `cancel` are intentionally omitted. Direct financial approval belongs to finance/expense approvers, preserving maker-checker separation.

## 6. Explicit rejection/isolation of Shift Request and Shift Schedule Assignment

- `Shift Request`: Denied for `Tradexcel HR Manager`. The project intentionally uses the audited `Shift Assignment Tool` and supervisor shift scheduling. Native `Shift Request` documents remain filtered out of Quick Lists and blocked from direct navigation without proper supervisor workflow authority.
- `Shift Schedule Assignment`: Denied. Shift assignments are governed by the custom bulk assignment engine and explicit shift rosters.

## 7. Features marked DECISION_REQUIRED with owner rationale

1. **Employee Advance**: Requires native role `Expense Approver`. Submitting creates an immediate accounting liability / advance ledger impact. Decision required on whether HR Manager or Finance Approver holds authority.
2. **Travel Request**: Requires native role `System Manager` in HRMS 16.19.0. Granting System Manager violates least-privilege. Decision required on custom role adaptation.
3. **Leave Encashment (finalization)**: Submitting triggers Additional Salary creation and GL financial disbursement. Belongs to financial payroll review.
4. **Employee Incentive**: Submitting automatically generates native `Additional Salary` records. Financial authority must not be circumvented.
5. **Retention Bonus**: Directly generates native `Additional Salary` records. Financial authority required.
6. **Salary Withholding**: Directly modifies monthly payroll disbursement and net pay. Belongs to payroll maker/checker workflow.

## 8. Home shortcut replacement details

- **Original shortcut**: `Employee Advances` (List route to `Employee Advance`).
- **Issue**: `Employee Advance` requires `Expense Approver` and produces accounting ledger records. For a pure HR Manager persona, navigating to `Employee Advance` resulted in permission denial (`Not permitted`).
- **Replacement**: `Attendance Summary` (Report route to `Daily Attendance Summary`).
- **Rationale**: Daily attendance monitoring is a high-frequency, daily operational activity for HR managers. The `Daily Attendance Summary` report is fully permission-scoped and accessible.
- **Result**: Home Common Actions now contains 12 genuinely accessible, high-frequency shortcuts.

## 9. Browser UAT results

Playwright browser verification was executed against `hrms-v16.localhost` at `http://127.0.0.1:8001` with synthetic user `audit.sweep@tradexcel.invalid` possessing strictly `['Tradexcel HR Manager', 'All', 'Guest', 'Desk User']` and User Permission for Company `Tradexcel Ceramics Ltd.`:
- **Desk load**: Clean Desk load with no console JavaScript errors.
- **Home rendering**: Rendered Action Board, 3 Number Cards (Active Employees, Today Present, Unassigned Biometric Users), 3 Quick Lists (Attendance Corrections, Leave Applications, Field Duty Applications; Shift Requests cleanly filtered out), and 11 accessible Shortcuts.
- **Accessible routes tested**:
  - `Expense Claim` (`/app/expense-claim`): 200 OK, 0 modal errors.
  - `Employee Grievance` (`/app/employee-grievance`): 200 OK, 0 modal errors.
  - `Compensatory Leave Request` (`/app/compensatory-leave-request`): 200 OK, 0 modal errors.
  - `Appraisal` (`/app/appraisal`): 200 OK, 0 modal errors.
  - `Job Requisition` (`/app/job-requisition`): 200 OK, 0 modal errors.
- **Denied routes tested**:
  - `Employee Advance` (`/app/employee-advance`): Displays native permission error modal ("Not permitted to access 'Employee Advance'").
  - `Shift Request` (`/app/shift-request`): Displays native permission error modal ("Not permitted to access 'Shift Request'").
- **Sidebar behavior**:
  - Expanded: Clean layout, full functional categories.
  - Collapsed: Narrow icon-only state; no clipping or horizontal scrollbars (verified with local Frappe core commit `f1bdb53ac60cd96528b52de418f9459510acb5bd`).
- **Screenshots captured**:
  - `uat_workspace_expanded.png`
  - `uat_workspace_collapsed.png`
  - `uat_expense_claim.png`
  - `uat_employee_grievance.png`
  - `uat_compensatory_leave.png`
  - `uat_appraisal.png`
  - `uat_job_requisition.png`
  - `uat_employee_advance.png`
  - `uat_shift_request.png`

## 10. Test results

- **`test_hr_workspace_ui.py`**: 6 passed in 7.07s.
  - `test_hr_manager_workspace_shortcuts_have_permission`: Passed.
  - `test_officer_workspace_shortcuts_permission_filtering`: Passed.
  - `test_worker_workspace_shortcuts_restricted`: Passed.
  - `test_workspace_role_isolation`: Passed (`assert_only_tradexcel_roles`).
  - `test_quick_list_permission_filtering`: Passed (`Shift Request` filtered).
  - `test_hr_manager_record_scope_user_permission`: Passed (Company isolation enforced).
- **Regression suites**:
  - `test_action_board_integration.py`, `test_operational_reports.py`, `test_dashboard_setup.py`, `test_hr_navigation.py`, `test_native_navigation_integration.py`: 39 passed in 37.33s.
  - `test_security_privacy_integration.py`: 5 passed in 23.36s.
- **Full test suite**:
  - `694 passed, 120 warnings in 593.19s (0:09:53)`. 0 failed, 0 skipped.

## 11. Backup metadata from BACKUPS.md

Backup taken before schema/permission migration:
- Timestamp: `2026-09-27 20:26:39` (Asia/Dhaka)
- Site: `hrms-v16.localhost`
- Database: `20260927_202639-hrms-v16_localhost-database.sql.gz` (53,584,703 bytes, SHA-256 `03f662e0579cda0c3bd5956d963301e09ec9397f9321287e6cb0c42293fa58b7`)
- Public files: `20260927_202639-hrms-v16_localhost-files.tar` (10,240 bytes, SHA-256 `f49715451643b96039b30f5528643f6139b1f9b89658922847006c4b0ca79454`)
- Private files: `20260927_202639-hrms-v16_localhost-private-files.tar` (38,942,720 bytes, SHA-256 `c0940518ed6ddc1dea5301062151264b3ffb173d0e7348e0daec646e55d1d930`)
- Config: `20260927_202639-hrms-v16_localhost-site_config_backup.json` (245 bytes, SHA-256 `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`)

## 12. Migration and cache-clearing confirmation

Standard Frappe bench migration executed:
```bash
bench --site hrms-v16.localhost migrate
bench --site hrms-v16.localhost clear-cache
```
Completed cleanly. No raw SQL or unmanaged schema manipulation.

## 13. Clean synthetic record verification

All synthetic test users and audit records (`audit.sweep@tradexcel.invalid`, `*.ui.test@tradexcel.invalid`) were completely unlinked and deleted. Database query verified 0 lingering test users for domain `tradexcel.invalid`. Redis background queue emptied.

## 14. Final branch and commit SHA

- Branch: `fix/native-feature-persona-access`
- Commit SHA: To be assigned upon commit.

## 15. PR details

- PR Title: `fix(auth): align native HR features with Tradexcel personas`
- Target Base Branch: `feat/native-hr-workspace-completeness` (PR #49)
- Status: Draft, unmerged.

## 16. Exact remaining unverified production items

- Physical SenseFace device hardware sync and biometric push verification.
- Decision on financial and administrative roles for `Employee Advance`, `Travel Request`, and incentive doctypes (`DECISION_REQUIRED`).
- Production cutover rehearsal and live multi-company permission signoff.

## 17. Explicit declaration of production readiness status

Ready for PR submission on top of PR #49. Production cutover remains subject to owner decisions on financial advance doctypes and live biometric hardware verification.
