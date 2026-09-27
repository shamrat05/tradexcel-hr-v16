# Native feature persona access convergence — 2026-09-27

## 1. Exact starting SHA and branch

- Base branch: `feat/native-hr-workspace-completeness`
- Base PR: `#49` (open, draft, unmerged)
- Starting SHA: `31249677c7c8ba822ca6404747ff312bdf6f53df`
- Working branch: `fix/native-feature-persona-access`
- PR: `#50` (draft, open, unmerged)

## 2. Root cause of flaw in PR #49 persona proof

In PR #49, `tradex_hr/tests/test_hr_workspace_ui.py` defined `PERSONA_ROLES["hr_manager"] = ["Tradexcel HR Manager", "HR Manager"]`. By assigning the native ERPNext/HRMS `HR Manager` role to the test user, the test bypassed the project's strict custom-role-only persona architecture. As a result, the UI catalog exposed many native features, but Desk route access had not been verified under genuine Tradexcel-only custom roles (`assert_only_tradexcel_roles`).

## 3. Full role-isolation verification

All persona fixtures and test cases strictly enforce `assert_only_tradexcel_roles(user)`. No native HR or administrative roles (`HR Manager`, `HR User`, `System Manager`, `Expense Approver`, `Interviewer`) are assigned to any Tradexcel persona, whether in tests or in standard role setup. All access is governed strictly by custom Tradexcel roles:
- `Tradexcel HR Manager`
- `Tradexcel HR/Attendance Officer`
- `Tradexcel Employee/Worker`
- and related scoped custom roles.

## 4. Code permission constants

In `tradex_hr/role_setup.py`:
```python
PERMISSION_FIELDS = (
    "select", "read", "write", "create", "delete", "submit", "cancel",
    "amend", "report", "export", "import", "share", "print", "email",
)

READ_ONLY_PERMS = {"select", "read", "report", "export", "print"}
EDIT_PERMS = READ_ONLY_PERMS | {"write", "create"}
SUBMIT_PERMS = EDIT_PERMS | {"submit"}
APPROVE_PERMS = READ_ONLY_PERMS | {"write", "submit", "cancel"}
```

Note: `EDIT_PERMS` does **NOT** include `delete`, `submit`, `cancel`, `amend`, or `share`.

## 5. Exact effective permission matrix for newly added/managed DocTypes

The following table reflects the exact code truth from `STANDARD_PERMISSION_MATRIX` in `tradex_hr/role_setup.py`:

| DocType | Role | Exact Permission Flags | Changed by PR #50 |
| :--- | :--- | :--- | :---: |
| `Department` | Tradexcel HR Manager | `select`, `read` | YES |
| `Department` | Tradexcel HR/Attendance Officer | `select`, `read` | YES |
| `Department` | Tradexcel Branch Manager | `select`, `read` | YES |
| `Department` | Tradexcel Department Manager | `select`, `read` | YES |
| `Department` | Tradexcel Factory Supervisor | `select`, `read` | YES |
| `Department` | Tradexcel Payroll Manager | `select`, `read` | YES |
| `Department` | Tradexcel Compliance Auditor | `select`, `read` | YES |
| `Branch` | Tradexcel HR Manager | `select`, `read` | YES |
| `Branch` | Tradexcel HR/Attendance Officer | `select`, `read` | YES |
| `Branch` | Tradexcel Branch Manager | `select`, `read` | YES |
| `Branch` | Tradexcel Department Manager | `select`, `read` | YES |
| `Branch` | Tradexcel Factory Supervisor | `select`, `read` | YES |
| `Branch` | Tradexcel Payroll Manager | `select`, `read` | YES |
| `Branch` | Tradexcel Compliance Auditor | `select`, `read` | YES |
| `Designation` | Tradexcel HR Manager | `select`, `read` | YES |
| `Designation` | Tradexcel HR/Attendance Officer | `select`, `read` | YES |
| `Designation` | Tradexcel Branch Manager | `select`, `read` | YES |
| `Designation` | Tradexcel Department Manager | `select`, `read` | YES |
| `Designation` | Tradexcel Factory Supervisor | `select`, `read` | YES |
| `Designation` | Tradexcel Payroll Manager | `select`, `read` | YES |
| `Designation` | Tradexcel Compliance Auditor | `select`, `read` | YES |
| `Employee Grade` | Tradexcel HR Manager | `select`, `read` | YES |
| `Employee Group` | Tradexcel HR Manager | `select`, `read` | YES |
| `Holiday List` | Tradexcel HR Manager | `select`, `read` | YES |
| `Holiday List` | Tradexcel HR/Attendance Officer | `select`, `read` | YES |
| `Holiday List Assignment` | Tradexcel HR Manager | `select`, `read`, `write`, `create`, `submit`, `report`, `export`, `print` | YES |
| `Leave Block List` | Tradexcel HR Manager | `select`, `read` | YES |
| `Overtime Type` | Tradexcel HR Manager | `select`, `read` | YES |
| `Overtime Type` | Tradexcel HR/Attendance Officer | `select`, `read` | YES |
| `Expense Claim` | Tradexcel HR Manager | `select`, `read`, `write`, `create`, `report`, `export`, `print` | YES |
| `Expense Claim Type` | Tradexcel HR Manager | `select`, `read` | YES |
| `Purpose of Travel` | Tradexcel HR Manager | `select`, `read` | YES |
| `Compensatory Leave Request` | Tradexcel HR Manager | `select`, `read`, `write`, `create`, `submit`, `report`, `export`, `print` | YES |
| `Job Requisition` | Tradexcel HR Manager | `select`, `read`, `write`, `create`, `report`, `export`, `print` | YES |
| `Interview Type` | Tradexcel HR Manager | `select`, `read` | YES |
| `Employee Referral` | Tradexcel HR Manager | `select`, `read`, `write`, `create`, `submit`, `report`, `export`, `print` | YES |
| `Appointment Letter` | Tradexcel HR Manager | `select`, `read`, `write`, `create`, `report`, `export`, `print` | YES |
| `Appointment Letter Template` | Tradexcel HR Manager | `select`, `read` | YES |
| `Employee Grievance` | Tradexcel HR Manager | `select`, `read`, `write`, `create`, `submit`, `report`, `export`, `print` | YES |
| `Grievance Type` | Tradexcel HR Manager | `select`, `read` | YES |
| `Training Program` | Tradexcel HR Manager | `select`, `read`, `write`, `create`, `report`, `export`, `print` | YES |
| `Training Event` | Tradexcel HR Manager | `select`, `read`, `write`, `create`, `submit`, `report`, `export`, `print` | YES |
| `Training Feedback` | Tradexcel HR Manager | `select`, `read`, `report`, `export`, `print` | YES |
| `Training Result` | Tradexcel HR Manager | `select`, `read`, `write`, `create`, `submit`, `report`, `export`, `print` | YES |
| `Appraisal` | Tradexcel HR Manager | `select`, `read`, `write`, `create`, `submit`, `report`, `export`, `print` | YES |
| `Appraisal Cycle` | Tradexcel HR Manager | `select`, `read`, `write`, `create`, `report`, `export`, `print` | YES |
| `Appraisal Template` | Tradexcel HR Manager | `select`, `read` | YES |
| `Goal` | Tradexcel HR Manager | `select`, `read`, `write`, `create`, `report`, `export`, `print` | YES |
| `Employee Skill Map` | Tradexcel HR Manager | `select`, `read`, `write`, `create`, `report`, `export`, `print` | YES |

Correction Notice: Neither `delete` nor `cancel` was granted on any of these DocTypes. Master dependencies receive strictly `select` and `read` (no `export`, `print`, or mutation flags).

## 6. Non-HR-Manager dependency grants

PR #50 also provisioned read/select access to organizational master dependencies for non-HR-manager operational roles:
- `Department`, `Branch`, `Designation`: Granted `{"select", "read"}` to `Tradexcel HR/Attendance Officer`, `Tradexcel Branch Manager`, `Tradexcel Department Manager`, `Tradexcel Factory Supervisor`, `Tradexcel Payroll Manager`, and `Tradexcel Compliance Auditor`.
  - **Rationale**: Needed for link pickers, attendance roster views, organizational filters, and departmental report execution across all operational Desk personas.
- `Holiday List` and `Overtime Type`: Granted `{"select", "read"}` to `Tradexcel HR/Attendance Officer`.
  - **Rationale**: Needed for shift planning and overtime reconciliation inspection.
- **Safety**: None of these roles received `write`, `create`, `delete`, `submit`, `cancel`, `amend`, or `share` on these masters.

## 7. Expense Claim status

- **Maker Rights**: CONVERGED for `Tradexcel HR Manager` (`select`, `read`, `write`, `create`, `report`, `export`, `print`). HR can draft, view, and prepare claims.
- **Checker Rights**: UNRESOLVED / DECISION_REQUIRED. Submit and cancel permissions are intentionally omitted. In native HRMS, claim approval belongs to `Expense Approver`. Tradexcel has deliberately not assigned native `Expense Approver` to any persona. A future owner decision must establish which Tradexcel role, if any, receives native Expense Claim final approval authority and under what scope/workflow.
- **Verdict**: `EXPENSE CLAIM APPROVAL DECISION_REQUIRED`.

## 8. Employee Advance technical rationale

- **Native Behavior**: In pinned HRMS v16.19.0, Employee Advance submission validates and establishes an approved employee advance against an accounting account and participates in later payment and accounting settlement. Native final submit/cancel authority belongs to `Expense Approver`.
- **Status**: Tradexcel has not mapped that authority to a custom persona. Kept removed from Home shortcuts; `DECISION_REQUIRED`.

## 9. Travel Request technical rationale

- **Native Behavior**: Travel Request standard metadata in HRMS 16.19.0 contains only a `System Manager` permission row and does not provide an ordinary operational workflow.
- **Status**: Granting `System Manager` violates least privilege. Integration requires an explicit workflow/permission decision rather than granting System Manager; `DECISION_REQUIRED`.

## 10. Leave Encashment financial effect

- **Native Behavior**: In pinned HRMS, submitting Leave Encashment either creates GL journal entries (if `pay_via_payment_entry` is enabled) or generates submitted `Additional Salary` records, while simultaneously creating `Leave Ledger Entry` rows and reducing `Leave Allocation`.
- **Status**: It is an authoritative financial disbursement document, not a generic HR leave operations record. Kept outside generic HR Manager access; `DECISION_REQUIRED`.

## 11. Payroll extras

- `Employee Incentive`: Submitting generates submitted `Additional Salary`.
- `Retention Bonus`: Submitting creates/updates submitted `Additional Salary`.
- `Salary Withholding`: Directly alters monthly payroll net pay calculations.
- **Status**: All remain strictly gated without submit authority; `DECISION_REQUIRED`.

## 12. Workspace source truth vs. rendering evidence

### Source-Configured Definitions:
- **Number Cards (3)**:
  1. `Number of Employees on Leave (Today)`
  2. `Number of Employees on Leave (This Month)`
  3. `Expense Claims (This Month)`
  (Note: The dead `Holidays in this month` card was removed from `tradex_hr/install.py` and `tradexcel_hr.json` because upstream HRMS defines `type = Custom` with `document_type = null`, causing Frappe core to restrict it from all non-System-Manager personas).
- **Quick Lists (4)**:
  1. `Open Leave Requests` (`Leave Application`)
  2. `Attendance Requests to Review` (`Attendance Request`)
  3. `Expense Claims to Review` (`Expense Claim`)
  4. `Shift Requests to Review` (`Shift Request`)
- **Common Actions (12)**:
  `Employee Directory`, `Today's Attendance`, `Attendance Summary`, `Attendance Fix Requests`, `Mobile Attendance`, `Leave Requests`, `Expense Claims`, `Run Monthly Payroll`, `Salary Setup Coverage`, `Job Applicants`, `Field Duties`, `Final Settlements`.

### Server Permission-Filtered Desktop Page (`get_desktop_page`):
- **Tradexcel HR Manager**:
  - Number Cards (3): `Number of Employees on Leave (Today)`, `Number of Employees on Leave (This Month)`, `Expense Claims (This Month)`.
  - Quick Lists (3): `Open Leave Requests`, `Attendance Requests to Review`, `Expense Claims to Review`. (Filtered: `Shift Requests to Review` due to preserved Shift Request denial).
  - Common Actions (11): `Employee Directory`, `Today's Attendance`, `Attendance Summary`, `Attendance Fix Requests`, `Mobile Attendance`, `Leave Requests`, `Expense Claims`, `Salary Setup Coverage`, `Job Applicants`, `Field Duties`, `Final Settlements`. (`Run Monthly Payroll` filtered).
- **Tradexcel HR/Attendance Officer**:
  - Number Cards (2): `Number of Employees on Leave (Today)`, `Number of Employees on Leave (This Month)`.
  - Quick Lists (2): `Open Leave Requests`, `Attendance Requests to Review`.
  - Common Actions (7): `Employee Directory`, `Today's Attendance`, `Attendance Summary`, `Attendance Fix Requests`, `Mobile Attendance`, `Leave Requests`, `Field Duties`.
- **Tradexcel Payroll Manager**:
  - Number Cards (0).
  - Quick Lists (0).
  - Common Actions (4): `Employee Directory`, `Run Monthly Payroll`, `Salary Setup Coverage`, `Final Settlements`.
- **Tradexcel Finance/Accounts Officer**:
  - Number Cards (0).
  - Quick Lists (0).
  - Common Actions (3): `Employee Directory`, `Salary Setup Coverage`, `Final Settlements`.
- **Tradexcel Branch Manager**:
  - Number Cards (2): `Number of Employees on Leave (Today)`, `Number of Employees on Leave (This Month)`.
  - Quick Lists (2): `Open Leave Requests`, `Attendance Requests to Review`.
  - Common Actions (6): `Employee Directory`, `Today's Attendance`, `Attendance Fix Requests`, `Mobile Attendance`, `Leave Requests`, `Field Duties`.
- **Tradexcel Employee/Worker**:
  - `"tradexcel-hr"` workspace is not visible (`"tradexcel-hr"` not in `get_workspaces()["pages"]`).

### Route Authorization Verification:
Every visible Common Action shortcut across all 5 personas is verified to point to an authorized destination:
- DocType targets (`Employee`, `Attendance Request`, `Leave Application`, `Expense Claim`, `Payroll Entry`, `Job Applicant`, `Tradexcel Field Duty`, `Full and Final Statement`) have `frappe.has_permission(doctype, 'read') == True`.
- Report targets (`Tradexcel Daily Attendance Board`, `Daily Attendance Summary`, `Tradexcel Salary Coverage Board`) are in `DeskViews.get_allowed_reports()`.
- Page targets (`tradexcel-mobile-attendance`) are in `DeskViews.get_allowed_pages()`.

### Action Board Metrics vs. Native Number Cards:
The custom block `Tradexcel Work Needing Attention` renders operational metrics (`Active Employees`, `Today Present`, `Unassigned Biometric Users`) and action queue lists (`Attendance Fix Requests`, `Leave Applications`, `Field Duty Applications`). These are custom Action Board elements and must not be conflated with native Workspace Number Cards or Quick Lists.

## 13. Scope proof for newly enabled native DocTypes

Scope dimensions and isolation were verified with synthetic records across `Tradexcel Ceramics Ltd.` (Company A) and `Elegance Footwear Ltd.` (Company B):
- **`Expense Claim`**: Scoped directly by `Company` User Permission via `company` link. Scoped user sees Company A record and cannot see Company B record in `get_list`. Direct read on Company B record raises `frappe.PermissionError`.
- **`Appraisal`**: Scoped directly by `Company` User Permission via `company` link. Scoped user sees Company A record and cannot see Company B record in `get_list`. Direct read on Company B record raises `frappe.PermissionError`.
- **`Employee Grievance`**: DocType has no direct `company` field; links to `Employee` via `raised_by` and `employee_responsible`. Scoped by `Employee` User Permission. Scoped user sees Employee A record and cannot see Employee B record in `get_list`. Direct read raises `frappe.PermissionError`.
- **`Compensatory Leave Request`**: DocType has no direct `company` field; links to `Employee` via `employee` and `Department` via `department`. Scoped by `Department` and `Employee` User Permission. Scoped user sees Dept A / Emp A record and cannot see Dept B / Emp B record in `get_list`. Direct read raises `frappe.PermissionError`.

## 14. Shift and worker security

- `Shift Request` and `Shift Schedule Assignment` remain strictly denied for `Tradexcel HR Manager`.
- `Shift Request` remains strictly denied for `Tradexcel HR/Attendance Officer`.
- `Shift Requests to Review` is filtered from native Quick Lists for all operational roles.
- `Tradexcel Employee/Worker` cannot see or access the administrative `tradexcel-hr` workspace.

## 15. Frappe core sidebar truth

- Local checkout: `/home/sanchita/frappe-bench-v16/apps/frappe`
- Branch: `fix/v16-collapsed-sidebar-scrollbar-clipping`
- HEAD: `f1bdb53ac60cd96528b52de418f9459510acb5bd`
- Remote status: Unpushed to upstream (`LOCAL FRAPPE CORE COMMIT ONLY`).
- Scoped fix: Adds `scrollbar-width: none` and WebKit scrollbar hiding to `.body-sidebar-container:not(.expanded) .body-sidebar-top`.

## 16. Test results

- **`test_hr_workspace_ui.py`**: 13 passed in 11.40s.
  - `test_workspace_layout_and_progressive_disclosure`: Passed (verifies 3 Number Cards on Home).
  - `test_curated_sidebar_sections_and_targets_exist`: Passed.
  - `test_curated_navigation_does_not_promote_excluded_features`: Passed.
  - `test_tradexcel_only_personas_and_permission_enforcement`: Passed.
  - `test_quick_list_native_permission_filtering`: Passed (asserts server payload for Quick Lists and Number Cards).
  - `test_tradexcel_persona_workspace_and_shortcut_authorization` (5 parameterized tests):
    - `hr_manager` (`Tradexcel HR Manager`): 3 Number Cards, 3 Quick Lists, 11 Common Actions (`Run Monthly Payroll` filtered). All visible targets verified authorized.
    - `attendance_officer` (`Tradexcel HR/Attendance Officer`): 2 Number Cards, 2 Quick Lists, 7 Common Actions (`Employee Directory`, `Today's Attendance`, `Attendance Summary`, `Attendance Fix Requests`, `Mobile Attendance`, `Leave Requests`, `Field Duties`). All visible targets verified authorized.
    - `payroll_manager` (`Tradexcel Payroll Manager`): 0 Number Cards, 0 Quick Lists, 4 Common Actions (`Employee Directory`, `Run Monthly Payroll`, `Salary Setup Coverage`, `Final Settlements`). All visible targets verified authorized.
    - `finance` (`Tradexcel Finance/Accounts Officer`): 0 Number Cards, 0 Quick Lists, 3 Common Actions (`Employee Directory`, `Salary Setup Coverage`, `Final Settlements`). All visible targets verified authorized.
    - `branch_manager` (`Tradexcel Branch Manager`): 2 Number Cards, 2 Quick Lists, 6 Common Actions (`Employee Directory`, `Today's Attendance`, `Attendance Fix Requests`, `Mobile Attendance`, `Leave Requests`, `Field Duties`). All visible targets verified authorized.
  - `test_expense_claim_maker_checker_boundary`: Passed (asserts maker rights and proves no Tradexcel role holds submit).
  - `test_record_scope_user_permission_isolation`: Passed (Employee scope).
  - `test_new_native_features_scope_and_record_isolation`: Passed (Expense Claim, Appraisal, Grievance, Compensatory Leave scope).
- **Focused Suites**:
  - `test_action_board_integration.py`: 3 passed in 7.83s.
  - `test_dashboard_setup.py`: 11 passed in 0.27s.
- **Full Suite**: 701 passed, 0 skipped, 0 failed in 582.06s.

## 17. Remote Actions truth

- Head SHA: `b7f6841e9782d9be2bec82cb6c1ca0d8f9fe7d98`
- GitHub Actions Run ID: `36333091558`
- Workflow: `Source contract` (`source-and-pure-tests`)
- Status: `failure`, `steps: []` (0 steps executed)
- Failure Reason: Account spending limit / billing condition (`The job was not started because recent account payments have failed or your spending limit needs to be increased`).
- Root Cause Confirmed: The repository owner account exceeded its monthly 2,000-minute GitHub Actions quota for private repositories.
- Official Classification: `REMOTE CI: BLOCKED BEFORE STEPS (Run ID 36333091558)`.

## 18. Backup and migration status

- **Pre-Migration Restore Point**: Fresh staging backup taken before migration on 2026-09-27 at 22:01:01 (Asia/Dhaka) with `--with-files`.
  - Database: `20260927_220101-hrms-v16_localhost-database.sql.gz` (56,079,166 bytes, SHA-256 `33ceef6497c798c62a689ffd40e86ab2d9959dd3ed880c804235ab7019aa09a7`).
  - Public files: `20260927_220101-hrms-v16_localhost-files.tar` (10,240 bytes, SHA-256 `d4f33a231170e3868813efd04a70b43f30bbf4d5b07985c0de1f205d2b012bf1`).
  - Private files: `20260927_220101-hrms-v16_localhost-private-files.tar` (38,942,720 bytes, SHA-256 `cf7fae0acf87ee5ec817ebaad257cbedd06852ed4da38291b9cf1ba3f462065d`).
  - Site config: `20260927_220101-hrms-v16_localhost-site_config_backup.json` (245 bytes, SHA-256 `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`).
  - Integrity verified with `gzip -t` and `tar -tf`; documented in `BACKUPS.md`.
- **Migration & Cache Execution**:
  - `bench --site hrms-v16.localhost migrate` completed with exit code 0, cleanly syncing workspace schema/content without errors.
  - `bench --site hrms-v16.localhost clear-cache` executed.
- **Current Database State**:
  - Current staging database reflects this post-migration state with the dead Holiday card removed and 3 operational cards active.
  - Pre-migration restore point `20260927_220101-hrms-v16_localhost-` stands verified and intact.

## 19. Production readiness status

PR #50 evidence and persona access closure complete. Production cutover remains subject to owner decisions on financial advance doctypes and live biometric hardware verification.
