# Native navigation and administration

This change builds on the accepted native actions. Native List, Form, Report,
Workflow, Sidebar, Search, User, Role Profile and Navbar Settings remain the UI
and authorization mechanisms. No alternate navigation or approval engine exists.

## Finding work

Start at Home for exceptions and the eight frequent actions. In the Sidebar,
choose the business job: Employees, Attendance, Shift Planning, Leave & Holidays,
Expenses & Travel, Payroll, Recruitment, Training & Reviews, Employee Exits,
Compliance, or Devices & Locations. Reviews and reports follow the work they
explain. Less frequent configuration is explicitly labelled Organization Setup,
HR Setup, Payroll Setup or Legal Setup. Administration contains native account,
announcement and import tools. Sections remember their collapsed state through
Frappe; Search remains available for any permitted feature.

The catalog preserves every existing destination. Visibility is filtered by
native permissions, so a worker does not receive management access merely
because a link exists. Existing role restrictions on Travel Request, Employee
Advance and other ungranted functions remain unchanged; administrators must
review permissions deliberately, not solve denial by granting broad roles.

## Users and multiple roles

Administrator is Frappe's special administrator account; there is no extra
Workforce superadmin. A designated System Manager can open Administration →
Users & Roles, select a User and use the native Roles & Permissions tab to assign
multiple roles. Role Profiles provide reusable role sets; their native role
editor behaviour is retained. Save the User and reload that user's Desk.

Roles add capabilities; Company/Branch/Employee User Permissions still restrict
data. Assign only required roles. Combining maker and approver roles does not
make one person an independent reviewer. Existing server checks still apply.
Ordinary HR/payroll users cannot grant themselves administrative access.

## Announcements

Administration → Site Announcements opens native Navbar Settings. A System
Manager writes the Announcement Widget and saves. Reload Desk to verify it.
Clear the field and save to withdraw the notice. Editing the text makes it a new
notice under native Frappe behaviour. Administrator-owned field-help overrides
are preserved.

This is a **site-wide, signed-in Desk notice across all companies**. Never put
confidential employee/payroll information in it. Dismissal is browser-local,
not proof of reading or employee acknowledgement. Scheduled, company-targeted,
mandatory-acknowledgement and push/email campaigns are not implemented by this
banner; those require a separately reviewed native solution and delivery UAT.

Installed v16 clears an old notice's dismissal after rendering its navbar, which
required a second reload for a changed notice. A small app-asset compatibility
check now clears only that stale native dismissal before rendering. The native
DIV dismiss control receives a keyboard role/label and Enter/Space activation;
a future native button is left alone. Native storage, rendering and dismissal
remain authoritative; no completion or recipient database is introduced.

## Direct Home and the native Sidebar

Installed v16 auto-generates a flat Sidebar named `workforce-suite`. Native
exact-route matching selected that duplicate instead of `Workforce Suite` on a
direct Home visit. The supported `extend_bootinfo` hook now omits only the
recognized generated duplicate from the already permission-filtered session
payload. Native route resolution then selects the curated Sidebar naturally.
No redirects, database deletion, route interception or framework patch is used.
Unknown public customizations and personal slug Sidebars are left intact; those
require a backed-up comparison before an administrator chooses to converge them.

## Action behaviour

Native Refresh, Save, Submit, Workflow, Print, Export and menu controls stay
native. Our report actions use native Page buttons with a small lifecycle
adapter because installed v16 reuses the QueryReport Page while retaining its
responsive menu copies. Only menu nodes created by our actions are removed on
report changes/refresh; native and other apps' entries are left alone. Stale
callbacks cannot run on a different report. Returning from a Form/List preserves
the original report actions, matching native report caching. No framework prototype is patched.

Payroll payment-record navigation now says **Open Journal Entry**, matching its
actual native destination. Accounting links require native read visibility;
mutation buttons require the existing form write permission. Server readiness,
Director approval, scope and accounting checks remain authoritative. Device
health/configuration actions require write access because both endpoints write
device status. Read-only users retain the record without unusable buttons.

## Complete Sidebar catalog

Every target below is checked for existence on the isolated installed stack.
That is route coverage, not proof that every business workflow has been performed.
Native permissions decide which subset each person sees.

| Section | Operator label | Native kind | Target |
|---|---|---|---|
| Employees | Employee Directory | DocType | Employee |
| Employees | Joiners & Leavers | Report | Workforce Joiners and Leavers |
| Employees | Employee Transfers | DocType | Employee Transfer |
| Employees | Employee Promotions | DocType | Employee Promotion |
| Employees | Missing Employee Data | Report | Employee Data Gaps |
| Attendance | Today's Attendance | Report | Workforce Daily Attendance Board |
| Attendance | Attendance Summary | Report | Daily Attendance Summary |
| Attendance | Attendance Fix Requests | DocType | Attendance Request |
| Attendance | Attendance Records | DocType | Attendance |
| Attendance | Punch Log | DocType | Employee Checkin |
| Attendance | Mobile Attendance | Page | workforce-mobile-attendance |
| Attendance | Field Duties | DocType | Workforce Field Duty |
| Attendance | Overtime Reviews | DocType | Overtime Slip |
| Attendance | Attendance Periods | DocType | Workforce Attendance Period |
| Attendance | Monthly Attendance Sheet | Report | Monthly Attendance Sheet |
| Attendance | Employees Working on a Holiday | Report | Employees working on a holiday |
| Shift Planning | Shift Assignments | DocType | Shift Assignment |
| Shift Planning | Bulk Shift Assignment | DocType | Shift Assignment Tool |
| Shift Planning | Shift Requests | DocType | Shift Request |
| Shift Planning | Shift Schedule Assignments | DocType | Shift Schedule Assignment |
| Shift Planning | Shift Planner | DocType | Shift Schedule |
| Shift Planning | Shift Coverage | Report | Workforce Shift Coverage |
| Shift Planning | Shift Attendance | Report | Shift Attendance |
| Leave & Holidays | Leave Requests | DocType | Leave Application |
| Leave & Holidays | Compensatory Leave Requests | DocType | Compensatory Leave Request |
| Leave & Holidays | Leave Balances | Report | Workforce Leave Balance Board |
| Leave & Holidays | Leave Allocations | DocType | Leave Allocation |
| Leave & Holidays | Bulk Leave Allocation | DocType | Leave Control Panel |
| Leave & Holidays | Leave Encashment | DocType | Leave Encashment |
| Leave & Holidays | Leave Policy Assignments | DocType | Leave Policy Assignment |
| Leave & Holidays | Holiday List Assignments | DocType | Holiday List Assignment |
| Expenses & Travel | Expense Claims | DocType | Expense Claim |
| Expenses & Travel | Employee Advances | DocType | Employee Advance |
| Expenses & Travel | Travel Requests | DocType | Travel Request |
| Expenses & Travel | Employee Advance Summary | Report | Employee Advance Summary |
| Expenses & Travel | Unpaid Expense Claims | Report | Unpaid Expense Claim |
| Payroll | Run Monthly Payroll | Report | Workforce Payroll Readiness |
| Payroll | Salary Setup Coverage | Report | Workforce Salary Coverage Board |
| Payroll | Bulk Salary Structure Assignment | DocType | Bulk Salary Structure Assignment |
| Payroll | Salary Assignments | DocType | Salary Structure Assignment |
| Payroll | Payroll Entries (Advanced) | DocType | Payroll Entry |
| Payroll | Salary Slips | DocType | Salary Slip |
| Payroll | Extra Pay & Deductions | DocType | Additional Salary |
| Payroll | Payroll Corrections | DocType | Payroll Correction |
| Payroll | Salary Arrears | DocType | Arrear |
| Payroll | Employee Incentive | DocType | Employee Incentive |
| Payroll | Retention Bonus | DocType | Retention Bonus |
| Payroll | Salary Withholding | DocType | Salary Withholding |
| Payroll | Payroll Register | Report | Workforce Payroll Register |
| Payroll | Payroll Variance | Report | Workforce Payroll Variance |
| Payroll | Pay Component Register | Report | Workforce Pay Component Register |
| Recruitment | Staffing Plans | DocType | Staffing Plan |
| Recruitment | Job Requisitions | DocType | Job Requisition |
| Recruitment | Job Openings | DocType | Job Opening |
| Recruitment | Job Applicants | DocType | Job Applicant |
| Recruitment | Interviews | DocType | Interview |
| Recruitment | Interview Feedback | DocType | Interview Feedback |
| Recruitment | Employee Referrals | DocType | Employee Referral |
| Recruitment | Job Offers | DocType | Job Offer |
| Recruitment | Appointment Letters | DocType | Appointment Letter |
| Recruitment | Onboarding | DocType | Employee Onboarding |
| Recruitment | Recruitment Analytics | Report | Recruitment Analytics |
| Training & Reviews | Employee Grievances | DocType | Employee Grievance |
| Training & Reviews | Training Programs | DocType | Training Program |
| Training & Reviews | Training Events | DocType | Training Event |
| Training & Reviews | Appraisals | DocType | Appraisal |
| Training & Reviews | Goals | DocType | Goal |
| Training & Reviews | Employee Skill Map | DocType | Employee Skill Map |
| Training & Reviews | Training Feedback | DocType | Training Feedback |
| Training & Reviews | Training Results | DocType | Training Result |
| Training & Reviews | Appraisal Cycles | DocType | Appraisal Cycle |
| Employee Exits | Exits / Separations | DocType | Employee Separation |
| Employee Exits | Final Settlements | DocType | Full and Final Statement |
| Compliance | Wage Floor Reviews | DocType | Workforce Wage Floor Classification |
| Compliance | Benefit Enrollments | DocType | Workforce Statutory Benefit Enrollment |
| Compliance | Working Time Reviews | DocType | Workforce Working Time Classification |
| Compliance | Maternity Reviews | DocType | Workforce Maternity Review |
| Compliance | Welfare Reviews | DocType | Workforce Workplace Welfare Review |
| Compliance | Anomaly Radar | Report | Workforce Anomaly Radar |
| Devices & Locations | Biometric Devices | DocType | Workforce Biometric Device |
| Devices & Locations | Employee Biometric IDs | DocType | Workforce Employee Biometric |
| Devices & Locations | Face Match Settings | DocType | Workforce Face Match Settings |
| Devices & Locations | Live Locations | Page | workforce-live-locations |
| Devices & Locations | Location Pings | DocType | Workforce Location Ping |
| Devices & Locations | Biometric ID Audit | Report | Biometric ID Audit |
| Organization Setup | Departments | DocType | Department |
| Organization Setup | Designations | DocType | Designation |
| Organization Setup | Branches / Locations | DocType | Branch |
| Organization Setup | Employee Grades | DocType | Employee Grade |
| Organization Setup | Employee Groups | DocType | Employee Group |
| HR Setup | HR Settings | DocType | HR Settings |
| HR Setup | Shift Types | DocType | Shift Type |
| HR Setup | Shift Locations | DocType | Shift Location |
| HR Setup | Attendance Policies | DocType | Workforce Attendance Policy |
| HR Setup | Overtime Types | DocType | Overtime Type |
| HR Setup | Holiday Lists | DocType | Holiday List |
| HR Setup | Leave Types | DocType | Leave Type |
| HR Setup | Leave Policies | DocType | Leave Policy |
| HR Setup | Leave Periods | DocType | Leave Period |
| HR Setup | Leave Block Lists | DocType | Leave Block List |
| HR Setup | Expense Claim Types | DocType | Expense Claim Type |
| HR Setup | Purpose of Travel | DocType | Purpose of Travel |
| HR Setup | Interview Types | DocType | Interview Type |
| HR Setup | Appointment Letter Templates | DocType | Appointment Letter Template |
| HR Setup | Grievance Types | DocType | Grievance Type |
| HR Setup | Appraisal Templates | DocType | Appraisal Template |
| Payroll Setup | Payroll Settings | DocType | Payroll Settings |
| Payroll Setup | Salary Structures | DocType | Salary Structure |
| Payroll Setup | Salary Components | DocType | Salary Component |
| Payroll Setup | Payroll Rules | DocType | Workforce Payroll Policy |
| Payroll Setup | Income Tax Slabs | DocType | Income Tax Slab |
| Payroll Setup | Payroll Periods | DocType | Payroll Period |
| Legal Setup | Statutory Exit Rules | DocType | Workforce Statutory Rule Set |
| Legal Setup | Wage Floor Rules | DocType | Workforce Wage Floor Rule Set |
| Legal Setup | Benefit Rules | DocType | Workforce Statutory Benefit Rule Set |
| Legal Setup | Working Time Rules | DocType | Workforce Working Time Rule Set |
| Legal Setup | Maternity Rules | DocType | Workforce Maternity Rule Set |
| Legal Setup | Policy Exceptions | DocType | Workforce Policy Exception |
| Administration | Users & Roles | DocType | User |
| Administration | Role Profiles | DocType | Role Profile |
| Administration | User Permissions | DocType | User Permission |
| Administration | Site Announcements | DocType | Navbar Settings |
| Administration | Bulk Data Import | DocType | Data Import |

## App-owned action inventory

Native upstream actions are preserved. The following lists app-owned toolbar registrations, including state-conditional actions. Per-record server checks still decide whether an action may succeed.

| Source | Actions |
|---|---|
| `workforce_suite/public/js/employee_calendar.js` | Calendar; Check Joiner Readiness; Check Exit Readiness; Finalize Exit Access; Check Full & Final Readiness |
| `workforce_suite/public/js/employee_separation.js` | Record Legal Review |
| `workforce_suite/public/js/income_tax_slab.js` | Approve Tax Configuration |
| `workforce_suite/public/js/overtime_bulk_list.js` | Prepare Overtime Drafts |
| `workforce_suite/public/js/payroll_entry.js` | Finalize Payroll / Retry Unsubmitted Salary Slips; Prepare Payment; Open Journal Entry; Open Bank Transaction |
| `workforce_suite/public/js/salary_slip_adjustments.js` | Review Payroll Adjustment |
| `workforce_suite/public/js/workforce_attendance_period.js` | Finalize Attendance; Reopen Attendance |
| `workforce_suite/public/js/workforce_biometric_device.js` | Check Bridge Health; Push Configuration to Bridge |
| `workforce_suite/workforce_suite/report/biometric_id_audit/biometric_id_audit.js` | Assign Biometric ID; Copy Biometric to Device |
| `workforce_suite/workforce_suite/report/employee_data_gaps/employee_data_gaps.js` | Review Employees; Open Salary Assignment Tool; Open Bulk Shift Assignment; Create Employee Transfer; Create Employee Promotion; View Employee Onboardings |
| `workforce_suite/workforce_suite/report/workforce_daily_attendance_board/workforce_daily_attendance_board.js` | Prepare Attendance Corrections |
| `workforce_suite/workforce_suite/report/workforce_joiners_and_leavers/workforce_joiners_and_leavers.js` | View Employee Onboardings; View Employee Separations |
| `workforce_suite/workforce_suite/report/workforce_payroll_readiness/workforce_payroll_readiness.js` | Prepare Payroll; Review Structure Migration; Open Payroll Entry for retry |
| `workforce_suite/workforce_suite/report/workforce_shift_coverage/workforce_shift_coverage.js` | Review / Assign Shift |

Additional state-driven/native extensions:

| Source | Actions and retained native mechanism |
|---|---|
| `workforce_suite/public/js/employee_checkin_review.js` | Approve Evidence / Reject Evidence; pending quarantine, reviewer roles, reason and server POST checks |
| `workforce_suite/public/js/list_scope.js` | Today / This Week / This Month grouped under Date; native advanced filters and cascading Link queries |
| `workforce_suite/workforce_suite/doctype/workforce_policy_exception/workforce_policy_exception.js` | Preview Impact; native approval workflow remains authoritative |
| `workforce_suite/public/js/bulk_salary_structure_assignment.js` | Native bulk assignment preview/callbacks retained |
| `workforce_suite/public/js/shift_assignment_tool.js` | Native scope/filter defaults retained |
| `workforce_suite/workforce_suite/page/workforce_mobile_attendance/workforce_mobile_attendance.js` | Check In/Out, capture, sync and retry; existing evidence state and privacy contracts retained |
| `workforce_suite/workforce_suite/page/workforce_live_locations/workforce_live_locations.js` | Existing permitted read-only location controls retained |
| Remaining seven standard reports | Native filters, Refresh, Print, Export and chart controls; no custom mutation toolbar |

## Deployment and remaining acceptance

This PR is tested on a new disposable synthetic site, never by rewriting a
populated customer preview. Before applying to an existing site, compare and
back up the managed public Sidebar: the established installer replaces its
managed items. Personal Sidebars are preserved, and may retain an older menu.
Do not delete personal customizations to force parity. Use the normal supported
asset build and reviewed metadata migration after backup/recovery checks.

Native framework accessibility defects must be reported separately rather than
hidden by a replacement Sidebar. Candidate browser checks, physical-device UAT,
staff learnability testing and production approval are distinct gates. See the
PR evidence for exact results and limitations; the inventory alone is not a
production-readiness claim.
