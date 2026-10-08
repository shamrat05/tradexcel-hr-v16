# Recruitment and joiner readiness — 2026-09-24

## Scope

This slice keeps Employee as the canonical identity and adds consistency checks around native Employee Onboarding plus a read-only Joiner Readiness action on Employee. Recruited onboarding requires a submitted Accepted Job Offer tied to the same applicant and company, with the applicant linked to a Job Opening in that company. Direct hires may start at Employee and do not need Job Applicant, email, or User records.

Joiner Readiness uses the effective submitted Salary Structure Assignment and explicit Salary Structure pay basis, the existing native payroll readiness service, native Holiday List and Shift resolution, native salary mode, and optional access. It does not calculate salary, create payroll, create a User, or return employee bank account values. Payroll Readiness remains company-wide, but Joiner Readiness uses only this employee's outcome so unrelated employees' blockers do not make this hire appear unconfigured.

Company-scoped recruitment reads and writes derive Job Applicant scope through its linked Job Opening. The same boundary covers native Interviews and Interview Feedback because HR User grants can otherwise expose candidate details across companies. Employee Onboarding validation and the existing Employee `before_insert` path prevent inconsistent offer/applicant/company links and duplicate Employees for an applicant.

## Staging read-only audit

Site: `hrms-v16.localhost`. No real records were changed.

| Item | Count / result |
| --- | ---: |
| Active Employees | 242 |
| Left Employees | 0 |
| Job Openings | 0 |
| Job Applicants | 0 |
| Interviews | 0 |
| Job Offers | 0 |
| Employee Onboardings | 0 |
| Employee Onboarding Templates | 0 |
| Active Employees linked to Job Applicant | 0 |
| Active Employees with personal email | 0 |
| Active Employees with User | 1 |
| Active salary mode: Bank / Cash / Cheque / blank | 2 / 208 / 0 / 32 |
| Bank-mode employees missing bank name / account | 0 / 2 |
| Submitted Salary Structure Assignments (all) | 227 |
| Active employees with resolved September 2026 Monthly or Daily pay basis | 225 |
| Active employees unresolved for that payroll period | 17 |
| Active submitted Shift Assignments | 237 |
| Enabled / total biometric mappings | 221 / 221 |

The resolved basis count is computed for 2026-09-24 through 2026-09-30 using the current resolver; the 17 unresolved employees include missing or otherwise unresolved effective assignments. It is not a count of missing SSA rows alone.

Basic employee-field completeness among active employees: branch 241, department 234, designation 70, employment type 241, grade 0, Employee Holiday List 241, default shift 237. A Company Holiday List is resolved natively where the Employee field is blank. These fields are not all universal blockers.

## Installed behavior checked

- HRMS v16 `Employee Onboarding.validate()` resolves an existing Employee by Job Applicant and rejects duplicate non-cancelled onboarding. Native `make_employee()` maps onboarding to Employee and sets Active status and Applicant email; mandatory Employee fields still require entry before insertion.
- HRMS v16 onboarding submission creates a Project and Task records from onboarding activities. Native cancellation removes its linked tasks/project; the integration test cleans those records by cancelling its synthetic onboarding.
- Employee Onboarding does not guarantee SSA, payment mode, shift/attendance, biometric, or application access. Joiner Readiness reports these separately.
- Job Applicant has no Company field; its Job Opening link is the company scope source. Company-scoped read/write guards cover Job Opening, Job Applicant, Interview, Interview Feedback, Job Offer, and Employee Onboarding for Workforce recruitment roles.
- Employee.salary_mode options are Bank, Cash, and Cheque. Cheque requires Finance review because the managed payroll payment path supports Bank/Cash only.

## Verification

The site-backed integration test creates two disposable companies and synthetic recruitment records. It exercises accepted, draft, awaiting-response, applicant mismatch, company mismatch, cross-company Job Opening, designation mismatch, duplicate Employee, and company-scoped recruitment read/write boundaries. It invokes native Employee Onboarding submission and `make_employee()`, then creates a synthetic monthly SSA and finalized Attendance period and runs the existing managed Payroll Entry workflow through a native draft Salary Slip. It also checks direct hire without applicant/email/User, Bank/Cash/Cheque/blank payment readiness, company-wide payroll gating, biometric review messaging, and that readiness output omits the synthetic bank account value.

All test-owned records are explicitly cleaned through native onboarding cancellation and the synthetic-company cleanup helper. Desk visual verification is still a release gate; no browser session was available in this work slice.

## PR #14 hardening work in progress — 2026-09-24

Reproduced two boundaries before changing code: an otherwise-ready hire inherited a blocker caused by another employee in the company payroll population, and native `Job Applicant.make_employee()` could insert an Employee without any managed onboarding. Native `Job Offer.make_employee()` is covered by the same new insert-guard test. The fix keeps the existing company-wide readiness call but bases joiner status on the selected employee's canonical outcome. A recruited Employee now requires one submitted onboarding, revalidates the same recruitment/company links, and invokes native onboarding employee-creation validation for required tasks. Direct hires without `job_applicant` remain valid.

The integration previously added the native `HR User` role to its synthetic Workforce Suite Manager. That hidden dependency has been removed. A custom-role-only path exercises Job Opening, Job Applicant, Job Offer, Employee Onboarding submission, native task assignment/completion, Employee creation, and Joiner Readiness; it asserts that payroll/accounting mutation and delete/cancel permissions remain absent. Native Job Opening requires Staffing Plan read, and Employee BoardingController requires Task write before assigning generated tasks. The role matrix grants read-only Staffing Plan access and company-scoped Task read/write, without Task create/delete. A read-only full-company payroll blocker no longer changes an individual joiner's result. The native `has_permission` hook now returns `True` when the company check permits access; Frappe v16 treats `None` from a controller permission hook as a denial, so the previous return value rejected otherwise-authorized users. Native Applicant/Offer mapper inserts now require exactly one valid submitted onboarding and delegate mandatory-task validation to HRMS. Direct Employee inserts with no Job Applicant remain supported.

The minimum DocPerm matrix is provisioned through the existing role setup. Two verified `--with-files` staging backups are recorded in `BACKUPS.md`. A standard `bench --site hrms-v16.localhost migrate` and `clear-cache` completed successfully after the final role matrix change; post-migration integration passed. No manual metadata convergence was used.


## Scoped onboarding Task assignment follow-up

Native Employee Onboarding assigns generated Tasks through Frappe's Share API. The scoped Workforce Suite Manager role therefore needs Task share permission in addition to read/write. This permission applies only to Tasks allowed by the user's explicit Company User Permission; integration checks verify an COMPANY_B Task cannot be read, written, or shared by a COMPANY_A-scoped HR user. HR still cannot create or delete Tasks.
