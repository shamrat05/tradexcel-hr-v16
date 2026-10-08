# Business configuration gate — 2026-09-26

Refreshed from read-only isolated staging on **2026-09-27**. These are
configuration/data decisions, not permission to change real records.
No identities, individual pay amounts or bank numbers are included.

## Fresh staging counts

- Example Company A: 240 active Employees; authority {"Monthly Salary": 64, "effective_submitted_assignment": 223, "Daily Wage": 159, "UNRESOLVED": 17, "No submitted Salary Structure Assignment applies on 2026-09-27": 17}; 237 active submitted Shift Assignments; 5 without active assignment/default; 0 overlapping active-assignment Employees.
- Example Company B: 2 active Employees; authority {"Monthly Salary": 2, "effective_submitted_assignment": 2}; 0 active submitted Shift Assignments; 0 without active assignment/default; 0 overlapping active-assignment Employees.

| Native/configuration record | Count | State |
| --- | ---: | --- |
| Account | 166 | docstatus: {"0": 166} |
| Additional Salary | 1 | docstatus: {"0": 1} |
| Arrear | 0 | docstatus: {}; workflow_state: {} |
| Attendance | 16077 | docstatus: {"0": 16077}; status: {"Present": 11421, "Absent": 4631, "On Leave": 25} |
| Attendance Request | 0 | docstatus: {}; workflow_state: {} |
| Bank Account | 0 | docstatus: {} |
| Employee | 242 | docstatus: {"0": 242}; status: {"Active": 242} |
| Employee Checkin | 22302 | docstatus: {"0": 22302} |
| Employee Separation | 0 | docstatus: {} |
| Full and Final Statement | 0 | docstatus: {}; status: {}; workflow_state: {} |
| Holiday List | 1 | docstatus: {"0": 1} |
| Income Tax Slab | 0 | docstatus: {} |
| Leave Allocation | 1190 | docstatus: {"1": 1190} |
| Leave Period | 0 | docstatus: {} |
| Leave Policy | 3 | docstatus: {"0": 3} |
| Leave Policy Assignment | 0 | docstatus: {} |
| Mode of Payment | 8 | docstatus: {"0": 8} |
| Overtime Slip | 0 | docstatus: {} |
| Overtime Type | 0 | docstatus: {} |
| Payroll Correction | 0 | docstatus: {}; workflow_state: {} |
| Payroll Entry | 0 | docstatus: {}; status: {}; workflow_state: {} |
| Payroll Period | 0 | docstatus: {} |
| Salary Slip | 0 | docstatus: {}; status: {} |
| Salary Structure | 3 | docstatus: {"1": 3} |
| Salary Structure Assignment | 227 | docstatus: {"1": 227} |
| Shift Assignment | 237 | docstatus: {"1": 237}; status: {"Active": 237} |
| Workforce Mobile Event | 15 | docstatus: {"0": 15}; status: {"Created": 15} |
| Workforce Attendance Period | 0 | docstatus: {}; status: {} |
| Workforce Attendance Policy | 1 | docstatus: {"1": 1} |
| Workforce Biometric Device | 2 | docstatus: {"0": 2} |
| Workforce Employee Biometric | 221 | docstatus: {"0": 221} |
| Workforce Field Duty | 1 | docstatus: {"1": 1}; status: {"Approved": 1} |
| Workforce Flexible Work Policy | 0 | docstatus: {} |
| Workforce Location Ping | 6 | docstatus: {"0": 6} |
| Workforce Maternity Review | 0 | docstatus: {} |
| Workforce Maternity Rule Set | 0 | docstatus: {} |
| Workforce Maternity Separation Review | 0 | docstatus: {} |
| Workforce Operational Day Override | 0 | docstatus: {} |
| Workforce Payroll Policy | 5 | docstatus: {"0": 5} |
| Workforce Policy Exception | 0 | docstatus: {} |
| Workforce Statutory Benefit Enrollment | 0 | docstatus: {} |
| Workforce Statutory Benefit Rule Set | 0 | docstatus: {} |
| Workforce Statutory Rule Set | 0 | docstatus: {}; workflow_state: {} |
| Workforce Wage Floor Classification | 0 | docstatus: {} |
| Workforce Wage Floor Rule Set | 0 | docstatus: {} |
| Workforce Working Time Classification | 0 | docstatus: {} |
| Workforce Working Time Rule Set | 0 | docstatus: {} |
| Workforce Workplace Welfare Review | 0 | docstatus: {} |

There are **0 enabled non-Administrator System Users**, 0 with Workforce roles;
1 Company User Permission, 0 Branch and 0 Department permissions. Synthetic
personas are engineering evidence, not configured real staff. All 16,077
Attendance records are draft; submitted work-hour and finalization coverage
are zero. There are 0 real Salary Slips/Payroll Entries. Existing 1,190
submitted Leave Allocations do not prove an approved current entitlement policy;
there are 0 Leave Periods/Policy Assignments and 3 draft Leave Policies.
Two active Bank-mode Employees lack account values; Company Bank Accounts: 0.
13 app Script Reports, 0 Query Reports. No blanket production-ready conclusion.

## Required decisions and accountable review

| Decision | Reviewer | Acceptance evidence |
| --- | --- | --- |
| Final roster, 17 missing authorities, effective Daily Wage migration dates | HR + Payroll + independent approver | Reviewed Employee/SSA reconciliation; explicit structure pay basis; no guessed wage |
| Staff identities, role separation, Company/Branch/Department and explicit DocShares | Owner + HR/security | Named approved roster; linked ESS identity; native share/approver review; persona UAT |
| Attendance drafts, five missing shifts, mobile/checkin review | HR/Attendance approver | Native evidence reviewed, Attendance submitted and periods finalized; no punch-to-pay inference |
| Leave Period, entitlements, carry-forward/encashment, holiday dates | HR + legal/owner | Approved native policies and effective dates; allocations reconciled |
| Payroll Period, tax slab/review, payable/expense mappings | Finance + Payroll | Native configuration and independently approved sample accrual |
| Salary modes, bank details, Company Bank Account and payment accounts | Finance | Verified bank ownership and payment/reconciliation rehearsal |
| Establishment identity, Labour Act/EPZ scope, Gazette/category/location | Legal/owner | Official provenance, applicability and approved effective rules |
| PF/Progoti/insurance participation and employer-contribution accounting | Legal + Finance | Explicit applicability; installed accounting capability and integration proof before deductions |
| Working-time/OT rules and approved Overtime Type | Legal + Payroll approver | Approved rates/limits from source; no invented multiplier |
| Flexible hours / early-release authority | Owner + HR/legal | Approved effective policy/override, reviewed authority and limits |
| Maternity, welfare and statutory exit classifications | Legal + HR | Approved source-linked rules and explicit classifications |
| Location/biometric retention, exports and operational access | Owner/security | Approved retention/access policy; no automatic destructive default |

Sign off this gate before production-like rehearsal. Legal scope stays
REVIEW_REQUIRED/NOT CONFIGURED until reviewed; software must not fill it in.
