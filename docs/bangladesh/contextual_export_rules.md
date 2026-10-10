# Context-aware statutory draft printing

**Status:** historical prototype decision record. For current PDF/DOCX,
paper/card controls and setup instructions, use
[current configuration](../bangladesh_statutory/configuration.md) and
[coverage](../bangladesh_statutory/coverage.md). All government-form profiles
remain unapproved until field-by-field legal and visual acceptance.

## UX choices that avoid redundant clicks

| Work context | What is already known | What must still be requested |
| --- | --- | --- |
| Employee ID / Service Book | Company and selected Employee | Nothing about reporting dates; EN or BN only if both are complete |
| Worker register | Company / Branch / Department from the user's report | Optional Employee or employment-type narrowing; no arbitrary date prompt |
| Form 34 draft attendance register | Company / Branch / Department and sometimes an already-selected *Friday–Thursday* reporting week | If current report period is not one Friday–Thursday week, request **one Friday week-start date**, not a redundant two-date range |
| Wage register | Company, period, branch / department already selected in payroll context | Request period only if no source-period is available |
| Leave register | Company and selected leave period, where known | Request range only if the source page has no dates |
| Manual safety/incident evidence | The submitted evidence/layout | Request the dates needed to select evidence, not employee filters that cannot apply |

The backend receives explicit scoped values. It checks the user's native
Employee, Attendance, Leave and Salary Slip permissions. Company is taken
from the selected saved layout: users cannot cross to a different Company by
changing client-side filter values.

### Why Form 34 is a week, not a generic month-long table

The original Form 34 image shows Friday, Saturday, Sunday, Monday, Tuesday,
Wednesday and Thursday in that order. A draft print for that form therefore
requires exactly one Friday-to-Thursday period. Long-range or monthly
attendance analysis remains available through the native Frappe report;
do not misrepresent it as a single prescribed Form 34 week. A separate
multiweek bundle can be added after the full-page legal layout is approved.

### Language

- **English**: offered when English title and every English column label exist.
- **বাংলা**: offered only when the Bangla title and **every** Bangla column
  label have been entered and reviewed.
- Printed labels use only the selected language. Legal or HR-entered data
  values are preserved in their stored form; the app never guesses a person's
  name, designation or statutory translation.
- Missing Bangla labels are an editor task; no silent English fallback in
  a supposedly complete Bangla document.
- Every template remains a **draft** until verified for legal applicability,
  fidelity and company-specific authorized sources.

### Output formats by actual task

- **A4 PDF**: primary format for draft previews and, after legal approval,
  final statutory register/filing preservation.
- **Editable DOCX**: appropriate for per-employee letters or working drafts,
  not a good substitute for fixed-layout, multi-column statutory registers.
  DOCX delivery is *not implemented in this branch* and must have separate
  A4/translation tests before being exposed.
- **Excel**: preferable for large editable internal tabular analyses, using
  native report export rather than inaccurately labeling it as an official
  government-form print.
- **Government-issued licences/certificates**: original external evidence
  must be attached, not fabricated by the app.

### Printing requirements

- Both A4 portrait and A4 landscape are supported in a simple black-and-white
  HTML/CSS renderer; long tables repeat table headers.
- A4 CI independently renders multi-page synthetic samples and inspects PDF
  geometry and extracted record markers, with all bounding boxes inside the
  paper.
- The final production PDF converter may differ from the CI renderer; verify
  Frappe's actual generated PDF visually on a bench.
- Government source-PDF footnotes/instructions are not inserted into the
  employer's printout. Official source metadata remains available in the UI.

### Known legal/data mapping gaps

- Current government form profiles are **draft suggested fields**, not certified
  reproductions of 28 examined government PDFs. Form 6 and 6(a) are an
  identical source download; do not certify them separately without corrected
  source files.
- Form 9's leave-book columns need a proper calculation from leave history,
  carried-forward balances and approved native records. Native Leave
  Application alone does not fill them all. It is **not** an approved
  automatically populated statutory Form 9 yet.
- Form 34's approved OT hours/rate/payment must come from reviewed overtime
  and pay rules, never inferred solely from raw Employee Checkins or
  Attendance working hours.
- Form 38 payment/acknowledgement must be reconciled against actual payment
  evidence. A Salary Slip is not proof of payment.
- The detailed 11-page Form 81 annual return remains separately under
  transcription and verification.
- All these forms are behind a legal review/approval gate in source; they
  cannot be submitted as verified official templates yet.

### Maintenance

Implement integrations with native `frm.add_custom_button`, Script Report
`onload`, standard Frappe filters and permission-scoped Python APIs. No
Frappe Desk/sidebar overrides or monkey patches. These functions should be
tested after each Frappe/ERPNext/HRMS upgrade.
