# Tradexcel HRMS Production Operating Model

## Confirmed business structure

```text
Tradexcel Ceramics Ltd.
└── Tradexcel Headquarters (Headquarters)
    └── TCL Factory (Branch)
```

Branch types are intended to make the hierarchy readable from macro to micro:
Headquarters, Zonal Office, Branch, and Sub-branch. Empty placeholder levels are
not created. Selevo organization identifiers are source metadata only and are not
Frappe business units.

## Data authority

- SenseFace biometric punches are authoritative for attendance.
- Frappe is authoritative for the cleaned production HR structure.
- Selevo HR and compensation data is reference input and must be reconciled before
  changing production records.
- Unmatched or conflicting employees are reported and never silently merged,
  created, renamed, or deleted.

## Cutover

- Reconcile existing attendance through 2026-09-16.
- Capture and delta-sync attendance from 2026-09-17 onward.
- Use device serial plus biometric PIN as the identity key.
- Every sync produces a success/exception report; clean records continue and only
  exceptions wait for review.

## Salary and payroll control

- Compare current Frappe salary/wage assignments with Selevo reference data.
- Compare August and September salary slips, including cancelled and duplicate
  records.
- Show all mismatches before modification or deletion.
- Monthly staff salaries and factory daily wages are separate payroll policies.
- No payroll history is hard-deleted without an approved exception list.

## Effective-dated rule changes

Current implementation (2026-09-17): `Tradexcel Policy Exception` supports
approved numeric exceptions for daily-paid worker payroll only. HR/Payroll
Manager prepares a draft and presses **Preview Impact**; a different user with
the Tradexcel Payroll Approver role submits it when no submitted slip is
affected (Administrator is a setup bypass). The default effective date is
tomorrow. Worker payroll resolves
the rule for each attendance date, including mid-month rate and break changes.
The preview lists affected workers, dates, old/new setting values, and submitted
slips; it does **not** yet calculate exact salary-slip amount differences.
Submitted-slip overlap blocks activation, so historical reconciliation is not
yet implemented. Staff pay, leave, tax, and attendance status rules are not
connected to this exception DocType. Do not describe this as the complete rule
engine or retroactive payroll workflow.

Target operating model:

- Default start is the next applicable date; HR may choose a specific start and end date.
- A past start requires a preview showing every affected employee, date, attendance
  result, leave balance, payroll period, and amount before approval. Preview and
  execution must use the same frozen rule version and input snapshot; if source
  data changes, the preview expires and must be rerun.
- Recalculate only the affected employee/date range and dependent pay periods.
  Attendance and leave changes can affect later balances and payroll, so show
  that downstream impact rather than treating the requested dates as isolated.
- Keep raw biometric punches immutable. Recompute derived attendance or add
  approved correction records; never rewrite the device evidence.
- Draft payroll may be recalculated. Submitted or paid payroll stays immutable;
  corrections become approved, linked adjustments in the next open payroll (or
  a documented reversal-and-reissue workflow). Never silently edit paid slips.
- Rules resolve per field, not by selecting one whole policy. Explicit employee
  overrides win. Other matching rules are compared by scope; a combined narrower
  scope wins only when it is truly more specific. Tenure is an eligibility
  condition, not a blanket rank above designation or department. Incomparable
  rules setting different values create a visible conflict and block only the
  affected employees/periods. Do not break ties with modification timestamp.
- Effective dates, approval, reason, author, and prior/new values are retained.
  The preview must expose which rule supplied each resulting value.
- Statutory minima and tax rules require jurisdiction-specific validation and
  cannot be bypassed by a personal exception without legal review.

## User roles

- Tradexcel Owner/Director
- Tradexcel HR Manager
- Tradexcel HR/Attendance Officer
- Tradexcel Payroll Manager
- Tradexcel Finance/Accounts Officer
- Tradexcel Factory Supervisor
- Tradexcel Branch Manager
- Tradexcel Department Manager
- Tradexcel Device/IT Administrator
- Tradexcel Compliance Auditor
- Tradexcel Employee/Worker
- Tradexcel Attendance Correction Approver
- Tradexcel Leave Approver
- Tradexcel Payroll Approver
- Tradexcel Import Reviewer

## Approval boundaries

- Attendance corrections require a separate approver.
- Leave requests follow the branch/department approval chain.
- Payroll requires payroll preparation and final payroll approval.
- Import and reconciliation exceptions require review before changes.
- Device administration does not grant salary access.

## Recruitment and onboarding

- Employee is the canonical worker identity. Native Job Opening, Job Applicant, Job Offer, and Employee Onboarding support recruited hires; approved direct hires may begin at Employee without a fabricated applicant or email.
- A submitted Salary Structure Assignment and its explicit Salary Structure pay basis are the payroll authority. Employment Type is not pay basis or statutory classification.
- Employee and User are separate identities. Application access is optional; Bank account details are required only for Bank salary mode.
- Shift and biometric setup follows the employee's actual attendance arrangement. Empty `default_shift` or missing biometric mapping is not a universal blocker when applicability is not configured.
- Employee Onboarding does not create salary authority or payroll. Joiner Readiness summarizes the existing company-wide payroll readiness and never creates or submits financial documents.

## Go-live evidence required

- Device serials entered and devices connected.
- Live punch received from each device.
- Punch replay/deduplication verified.
- Employee biometric assignments verified by device.
- Salary and wage exceptions approved.
- August/September reconciliation completed.
- Contabo HTTPS deployment and backups tested.
