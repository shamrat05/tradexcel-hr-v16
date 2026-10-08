# Native feature persona access convergence — 2026-09-27

## 1. Exact starting SHA and branch

- Base branch: `feat/native-hr-workspace-completeness`
- Base PR: `#49` (open, draft, unmerged)
- PR #50 branch: `fix/native-feature-persona-access`
- PR: `#50` (draft, open, unmerged)
- Current live HEAD: see GitHub PR metadata

## 2. Root cause of flaw in PR #49 persona proof

In PR #49, `workforce_suite/tests/test_hr_workspace_ui.py` defined `PERSONA_ROLES["hr_manager"] = ["Workforce Suite Manager", "HR Manager"]`. By assigning the native ERPNext/HRMS `HR Manager` role to the test user, the test bypassed the project's strict custom-role-only persona architecture. As a result, the UI catalog exposed many native features, but Desk route access had not been verified under genuine Workforce-only custom roles (`assert_only_workforce_roles`).

## 3. Full role-isolation verification

All persona fixtures and test cases strictly enforce `assert_only_workforce_roles(user)`. No native HR or administrative roles (`HR Manager`, `HR User`, `System Manager`, `Expense Approver`, `Interviewer`) are assigned to any Workforce persona, whether in tests or in standard role setup. All access is governed strictly by custom Workforce roles:
- `Workforce Suite Manager`
- `Workforce Suite/Attendance Officer`
- `Workforce Employee/Worker`
- and related scoped custom roles.

## 4. Code permission constants

In `workforce_suite/role_setup.py`:
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

The following table reflects the exact code truth from `STANDARD_PERMISSION_MATRIX` in `workforce_suite/role_setup.py`:

| DocType | Role | Exact Permission Flags | Changed by PR #50 |
| :--- | :--- | :--- | :---: |
| `Department` | Workforce Suite Manager | `select`, `read` | YES |
| `Department` | Workforce Suite/Attendance Officer | `select`, `read` | YES |
| `Department` | Workforce Branch Manager | `select`, `read` | YES |
| `Department` | Workforce Department Manager | `select`, `read` | YES |
| `Department` | Workforce Factory Supervisor | `select`, `read` | YES |
| `Department` | Workforce Payroll Manager | `select`, `read` | YES |
| `Department` | Workforce Compliance Auditor | `select`, `read` | YES |
| `Branch` | Workforce Suite Manager | `select`, `read` | YES |
| `Branch` | Workforce Suite/Attendance Officer | `select`, `read` | YES |
| `Branch` | Workforce Branch Manager | `select`, `read` | YES |
| `Branch` | Workforce Department Manager | `select`, `read` | YES |
| `Branch` | Workforce Factory Supervisor | `select`, `read` | YES |
| `Branch` | Workforce Payroll Manager | `select`, `read` | YES |
| `Branch` | Workforce Compliance Auditor | `select`, `read` | YES |
| `Designation` | Workforce Suite Manager | `select`, `read` | YES |
| `Designation` | Workforce Suite/Attendance Officer | `select`, `read` | YES |
| `Designation` | Workforce Branch Manager | `select`, `read` | YES |
| `Designation` | Workforce Department Manager | `select`, `read` | YES |
| `Designation` | Workforce Factory Supervisor | `select`, `read` | YES |
| `Designation` | Workforce Payroll Manager | `select`, `read` | YES |
| `Designation` | Workforce Compliance Auditor | `select`, `read` | YES |
| `Employee Grade` | Workforce Suite Manager | `select`, `read` | YES |
| `Employee Group` | Workforce Suite Manager | `select`, `read` | YES |
| `Holiday List` | Workforce Suite Manager | `select`, `read` | YES |
| `Holiday List` | Workforce Suite/Attendance Officer | `select`, `read` | YES |
| `Holiday List Assignment` | Workforce Suite Manager | `select`, `read`, `write`, `create`, `submit`, `report`, `export`, `print` | YES |
| `Leave Block List` | Workforce Suite Manager | `select`, `read` | YES |
| `Overtime Type` | Workforce Suite Manager | `select`, `read` | YES |
| `Overtime Type` | Workforce Suite/Attendance Officer | `select`, `read` | YES |
| `Expense Claim` | Workforce Suite Manager | `select`, `read`, `write`, `create`, `report`, `export`, `print` | YES |
| `Expense Claim Type` | Workforce Suite Manager | `select`, `read` | YES |
| `Purpose of Travel` | Workforce Suite Manager | `select`, `read` | YES |
| `Compensatory Leave Request` | Workforce Suite Manager | `select`, `read`, `write`, `create`, `submit`, `report`, `export`, `print` | YES |
| `Job Requisition` | Workforce Suite Manager | `select`, `read`, `write`, `create`, `report`, `export`, `print` | YES |
| `Interview Type` | Workforce Suite Manager | `select`, `read` | YES |
| `Employee Referral` | Workforce Suite Manager | `select`, `read`, `write`, `create`, `submit`, `report`, `export`, `print` | YES |
| `Appointment Letter` | Workforce Suite Manager | `select`, `read`, `write`, `create`, `report`, `export`, `print` | YES |
| `Appointment Letter Template` | Workforce Suite Manager | `select`, `read` | YES |
| `Employee Grievance` | Workforce Suite Manager | `select`, `read`, `write`, `create`, `submit`, `report`, `export`, `print` | YES |
| `Grievance Type` | Workforce Suite Manager | `select`, `read` | YES |
| `Training Program` | Workforce Suite Manager | `select`, `read`, `write`, `create`, `report`, `export`, `print` | YES |
| `Training Event` | Workforce Suite Manager | `select`, `read`, `write`, `create`, `submit`, `report`, `export`, `print` | YES |
| `Training Feedback` | Workforce Suite Manager | `select`, `read`, `report`, `export`, `print` | YES |
| `Training Result` | Workforce Suite Manager | `select`, `read`, `write`, `create`, `submit`, `report`, `export`, `print` | YES |
| `Appraisal` | Workforce Suite Manager | `select`, `read`, `write`, `create`, `submit`, `report`, `export`, `print` | YES |
| `Appraisal Cycle` | Workforce Suite Manager | `select`, `read`, `write`, `create`, `report`, `export`, `print` | YES |
| `Appraisal Template` | Workforce Suite Manager | `select`, `read` | YES |
| `Goal` | Workforce Suite Manager | `select`, `read`, `write`, `create`, `report`, `export`, `print` | YES |
| `Employee Skill Map` | Workforce Suite Manager | `select`, `read`, `write`, `create`, `report`, `export`, `print` | YES |

Correction Notice: Neither `delete` nor `cancel` was granted on any of these DocTypes. Master dependencies receive strictly `select` and `read` (no `export`, `print`, or mutation flags).

## 6. Non-HR-Manager dependency grants

PR #50 also provisioned read/select access to organizational master dependencies for non-HR-manager operational roles:
- `Department`, `Branch`, `Designation`: Granted `{"select", "read"}` to `Workforce Suite/Attendance Officer`, `Workforce Branch Manager`, `Workforce Department Manager`, `Workforce Factory Supervisor`, `Workforce Payroll Manager`, and `Workforce Compliance Auditor`.
  - **Rationale**: Needed for link pickers, attendance roster views, organizational filters, and departmental report execution across all operational Desk personas.
- `Holiday List` and `Overtime Type`: Granted `{"select", "read"}` to `Workforce Suite/Attendance Officer`.
  - **Rationale**: Needed for shift planning and overtime reconciliation inspection.
- **Safety**: None of these roles received `write`, `create`, `delete`, `submit`, `cancel`, `amend`, or `share` on these masters.

## 7. Expense Claim status

- **Maker Rights**: CONVERGED for `Workforce Suite Manager` (`select`, `read`, `write`, `create`, `report`, `export`, `print`). HR can draft, view, and prepare claims.
- **Checker Rights**: UNRESOLVED / DECISION_REQUIRED. Submit and cancel permissions are intentionally omitted. In native HRMS, claim approval belongs to `Expense Approver`. Workforce has deliberately not assigned native `Expense Approver` to any persona. A future owner decision must establish which Workforce role, if any, receives native Expense Claim final approval authority and under what scope/workflow.
- **Verdict**: `EXPENSE CLAIM APPROVAL DECISION_REQUIRED`.

## 8. Employee Advance technical rationale

- **Native Behavior**: In pinned HRMS v16.19.0, Employee Advance submission validates and establishes an approved employee advance against an accounting account and participates in later payment and accounting settlement. Native final submit/cancel authority belongs to `Expense Approver`.
- **Status**: Workforce has not mapped that authority to a custom persona. Kept removed from Home shortcuts; `DECISION_REQUIRED`.

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
  (Note: The dead `Holidays in this month` card was removed from `workforce_suite/install.py` and `workforce_suite.json` because upstream HRMS defines `type = Custom` with `document_type = null`, causing Frappe core to restrict it from all non-System-Manager personas).
- **Quick Lists (3)**:
  1. `Open Leave Requests` (`Leave Application`, filter `{"status": "Open"}`)
  2. `Attendance Requests to Review` (`Attendance Request`, filter `{"docstatus": 0}`)
  3. `Draft Expense Claims` (`Expense Claim`, filter `{"docstatus": 0, "approval_status": "Draft"}`)
  (Note: `Shift Requests to Review` was removed from the Home layout because `Shift Request` read permission is denied for all operational personas; `Expense Claims to Review` was renamed to `Draft Expense Claims` for workflow truth, reflecting that `Workforce Suite Manager` holds maker rights only and final checker rights remain unresolved/DECISION_REQUIRED).
- **Common Actions (12)**:
  `Employee Directory`, `Today's Attendance`, `Attendance Summary`, `Attendance Fix Requests`, `Mobile Attendance`, `Leave Requests`, `Expense Claims`, `Run Monthly Payroll`, `Salary Setup Coverage`, `Job Applicants`, `Field Duties`, `Final Settlements`.
- **Custom Blocks (1)**: `Workforce Work Needing Attention`.
- **Charts (0)**.

### Server Permission-Filtered Desktop Page (`get_desktop_page`):
- **Workforce Suite Manager**:
  - Number Cards (3): `Number of Employees on Leave (Today)`, `Number of Employees on Leave (This Month)`, `Expense Claims (This Month)`.
  - Quick Lists (3): `Open Leave Requests`, `Attendance Requests to Review`, `Draft Expense Claims`.
  - Common Actions (11): `Employee Directory`, `Today's Attendance`, `Attendance Summary`, `Attendance Fix Requests`, `Mobile Attendance`, `Leave Requests`, `Expense Claims`, `Salary Setup Coverage`, `Job Applicants`, `Field Duties`, `Final Settlements`. (`Run Monthly Payroll` filtered).
- **Workforce Suite/Attendance Officer**:
  - Number Cards (2): `Number of Employees on Leave (Today)`, `Number of Employees on Leave (This Month)`.
  - Quick Lists (2): `Open Leave Requests`, `Attendance Requests to Review`.
  - Common Actions (7): `Employee Directory`, `Today's Attendance`, `Attendance Summary`, `Attendance Fix Requests`, `Mobile Attendance`, `Leave Requests`, `Field Duties`.
- **Workforce Payroll Manager**:
  - Number Cards (0).
  - Quick Lists (0).
  - Common Actions (4): `Employee Directory`, `Run Monthly Payroll`, `Salary Setup Coverage`, `Final Settlements`.
- **Workforce Finance/Accounts Officer**:
  - Number Cards (0).
  - Quick Lists (0).
  - Common Actions (3): `Employee Directory`, `Salary Setup Coverage`, `Final Settlements`.
- **Workforce Branch Manager**:
  - Number Cards (2): `Number of Employees on Leave (Today)`, `Number of Employees on Leave (This Month)`.
  - Quick Lists (2): `Open Leave Requests`, `Attendance Requests to Review`.
  - Common Actions (6): `Employee Directory`, `Today's Attendance`, `Attendance Fix Requests`, `Mobile Attendance`, `Leave Requests`, `Field Duties`.
- **Workforce Employee/Worker**:
  - `"workforce-suite"` workspace is not visible (`"workforce-suite"` not in `get_workspaces()["pages"]`).

### Route Authorization Verification:
Every visible Common Action shortcut across all 5 personas is verified against actual server-returned shortcut records (`desktop_page["shortcuts"]["items"]`), matching its exact destination:
- `Employee Directory` -> `Employee` -> `DocType`
- `Today's Attendance` -> `Workforce Daily Attendance Board` -> `Report`
- `Attendance Summary` -> `Daily Attendance Summary` -> `Report`
- `Attendance Fix Requests` -> `Attendance Request` -> `DocType`
- `Mobile Attendance` -> `workforce-mobile-attendance` -> `Page`
- `Leave Requests` -> `Leave Application` -> `DocType`
- `Expense Claims` -> `Expense Claim` -> `DocType`
- `Run Monthly Payroll` -> `Workforce Payroll Readiness` -> `Report` (Note: Points to Report `Workforce Payroll Readiness`, NOT `Payroll Entry`)
- `Salary Setup Coverage` -> `Workforce Salary Coverage Board` -> `Report`
- `Job Applicants` -> `Job Applicant` -> `DocType`
- `Field Duties` -> `Workforce Field Duty` -> `DocType`
- `Final Settlements` -> `Full and Final Statement` -> `DocType`

- DocType targets have `frappe.has_permission(doctype, 'read') == True`.
- Report targets are in `DeskViews.get_allowed_reports()`.
- Page targets are in `DeskViews.get_allowed_pages()`.

### Action Board Metrics vs. Native Number Cards:
The custom block `Workforce Work Needing Attention` renders operational metrics (`Active Employees`, `Today Present`, `Unassigned Biometric Users`) and action queue lists (`Attendance Fix Requests`, `Leave Applications`, `Field Duty Applications`). These are custom Action Board elements and must not be conflated with native Workspace Number Cards or Quick Lists.

## 13. Scope proof for newly enabled native DocTypes

Scope dimensions and isolation were verified with synthetic records across `Example Company A` (Company A) and `Example Company B` (Company B):
- **`Expense Claim`**: Scoped directly by `Company` User Permission via `company` link. Scoped user sees Company A record and cannot see Company B record in `get_list`. Direct read on Company B record raises `frappe.PermissionError`.
- **`Appraisal`**: Scoped directly by `Company` User Permission via `company` link. Scoped user sees Company A record and cannot see Company B record in `get_list`. Direct read on Company B record raises `frappe.PermissionError`.
- **`Employee Grievance`**: DocType has no direct `company` field; links to `Employee` via `raised_by` and `employee_responsible`. Scoped by `Employee` User Permission. Scoped user sees Employee A record and cannot see Employee B record in `get_list`. Direct read raises `frappe.PermissionError`.
- **`Compensatory Leave Request`**: DocType has no direct `company` field; links to `Employee` via `employee` and `Department` via `department`. Scoped by `Department` and `Employee` User Permission. Scoped user sees Dept A / Emp A record and cannot see Dept B / Emp B record in `get_list`. Direct read raises `frappe.PermissionError`.

## 14. Shift and worker security

- `Shift Request` and `Shift Schedule Assignment` remain strictly denied for `Workforce Suite Manager`.
- `Shift Request` remains strictly denied for `Workforce Suite/Attendance Officer`.
- `Shift Requests to Review` is filtered from native Quick Lists for all operational roles.
- `Workforce Employee/Worker` cannot see or access the administrative `workforce-suite` workspace.

## 15. Frappe core sidebar truth

- Local checkout: `/home/sanchita/frappe-bench-v16/apps/frappe`
- Branch: `fix/v16-collapsed-sidebar-scrollbar-clipping`
- HEAD: `f1bdb53ac60cd96528b52de418f9459510acb5bd`
- Remote status: Unpushed to upstream (`LOCAL FRAPPE CORE COMMIT ONLY`).
- Scoped fix: Adds `scrollbar-width: none` and WebKit scrollbar hiding to `.body-sidebar-container:not(.expanded) .body-sidebar-top`.

## 16. Test results

- **`test_hr_workspace_ui.py`**: 13 passed in 11.39s.
  - `test_workspace_layout_and_progressive_disclosure`: Passed (verifies 3 Number Cards and 3 Quick Lists on Home).
  - `test_curated_sidebar_sections_and_targets_exist`: Passed.
  - `test_curated_navigation_does_not_promote_excluded_features`: Passed.
  - `test_workforce_only_personas_and_permission_enforcement`: Passed.
  - `test_quick_list_native_permission_filtering`: Passed (asserts server payload for Quick Lists and Number Cards).
  - `test_workforce_persona_workspace_and_shortcut_authorization` (5 parameterized tests):
    - `hr_manager` (`Workforce Suite Manager`): 3 Number Cards, 3 Quick Lists, 11 Common Actions (`Run Monthly Payroll` filtered). All visible targets verified authorized.
    - `attendance_officer` (`Workforce Suite/Attendance Officer`): 2 Number Cards, 2 Quick Lists, 7 Common Actions (`Employee Directory`, `Today's Attendance`, `Attendance Summary`, `Attendance Fix Requests`, `Mobile Attendance`, `Leave Requests`, `Field Duties`). All visible targets verified authorized.
    - `payroll_manager` (`Workforce Payroll Manager`): 0 Number Cards, 0 Quick Lists, 4 Common Actions (`Employee Directory`, `Run Monthly Payroll`, `Salary Setup Coverage`, `Final Settlements`). All visible targets verified authorized.
    - `finance` (`Workforce Finance/Accounts Officer`): 0 Number Cards, 0 Quick Lists, 3 Common Actions (`Employee Directory`, `Salary Setup Coverage`, `Final Settlements`). All visible targets verified authorized.
    - `branch_manager` (`Workforce Branch Manager`): 2 Number Cards, 2 Quick Lists, 6 Common Actions (`Employee Directory`, `Today's Attendance`, `Attendance Fix Requests`, `Mobile Attendance`, `Leave Requests`, `Field Duties`). All visible targets verified authorized.
  - `test_expense_claim_maker_checker_boundary`: Passed (asserts maker rights and proves no Workforce role holds submit).
  - `test_record_scope_user_permission_isolation`: Passed (Employee scope).
  - `test_new_native_features_scope_and_record_isolation`: Passed (Expense Claim, Appraisal, Grievance, Compensatory Leave scope).
- **Focused Suites**:
  - `test_action_board_integration.py`: 3 passed.
  - `test_dashboard_setup.py`: 11 passed.
  - `test_hr_navigation.py`: 2 passed.
  - `test_native_navigation_integration.py`: 5 passed.
  - `test_operational_reports.py`: 16 passed.
  - `test_security_privacy_integration.py`: 7 passed.
- **Full Suite**: 701 passed, 0 skipped, 0 failed in 563.08s.

## 17. Remote Actions truth

Remote CI is externally blocked before execution while the repository Actions quota/account restriction remains active. See PR #50 for the current-head run.

## 18. Backup and migration status

- **Pre-Migration Restore Point**: Fresh staging backup taken before migration on 2026-09-28 at 01:14:22 (Asia/Dhaka) with `--with-files`.
  - Prefix: `20260928_011422-hrms-v16_localhost-`
  - Database: `20260928_011422-hrms-v16_localhost-database.sql.gz` (56,934,971 bytes, SHA-256 `4083ba08edd55406383b7dacb6d62db23e01259f2272d28bb2aaef6b472819cd`).
  - Public files: `20260928_011422-hrms-v16_localhost-files.tar` (10,240 bytes, SHA-256 `f19e72269068fcdadb732273e700d23d0e494af3919a17417c3d207b8a9d3414`).
  - Private files: `20260928_011422-hrms-v16_localhost-private-files.tar` (38,942,720 bytes, SHA-256 `6a74f355d0a2da5f0bbe3c10c6f1bad5f6c401c4911f27ba637f83d58f85325a`).
  - Site config: `20260928_011422-hrms-v16_localhost-site_config_backup.json` (245 bytes, SHA-256 `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`).
  - Archive integrity verified with `gzip -t` and `tar -tf`; documented in `BACKUPS.md`.
- **Migration & Cache Execution**:
  - `bench --site hrms-v16.localhost migrate` completed with exit code 0, cleanly syncing workspace schema/content without errors.
  - `bench --site hrms-v16.localhost clear-cache` executed.
- **Current Database State**:
  - Current staging database reflects this post-migration state with 3 Number Cards, 3 Quick Lists, 12 Common Actions, 1 Action Board, 0 Charts.
  - Pre-migration restore point `20260928_011422-hrms-v16_localhost-` stands verified and intact as pre-migration recovery point.

## 19. Production readiness status

PR #50 evidence and persona access closure complete. Production cutover remains subject to owner decisions on financial advance doctypes and live biometric hardware verification.
