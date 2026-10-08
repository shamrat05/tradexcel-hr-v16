# Configure statutory working copies in native Desk

This feature produces **draft working copies**, not legally approved filings. The coverage matrix lists incomplete prescribed variants and external evidence. An independently reviewed personnel fact does not certify a form, establish a wage entitlement or prove payment.

Operators need native access to the source records **and** statutory-layout access (currently System Manager or Workforce Compliance Auditor), with the appropriate explicit Company scope. An HR/payroll role alone does not authorize this exporter. Contextual actions respect native visibility; server checks remain authoritative. No native source permissions are granted by these actions.

1. An authorized System Manager or scoped Compliance Auditor creates a **Workforce Statutory Profile** for an explicit Company and, where appropriate, Branch. Enter the establishment's EN/BN name/address, actual registration/licence references, effective dates, signatory details and applicable source/review notes. Map the company's actual native annual/casual/sick Leave Types; do not create entitlements here. A different authorized reviewer submits the profile.
2. Create **Workforce Statutory Print Layout**, select the historical form reference, Company/Branch, effective dates and version, then use **Layout Tools → Load Suggested Columns**. Required source keys and sections are protected. Change labels, translated notes and width weights only after checking their meaning. Complete the Bangla title and every label; there is no English fallback. Source hashes are read-only and assigned by the controller.
3. For Form 38, map the actual native earning components to the protected wage columns. The additional mapping child table allows several native components in one prescribed column. A component cannot appear twice, and every included nonzero Salary Slip earning must be mapped. This mapping groups **already calculated native amounts for printing**; it never configures salaries or divides gross wages.
4. Use **Workforce Statutory Record** for missing, reviewed facts. Select the same layout/Company, relevant Employee for a native-source supplement, record date/effective end, explicit field keys, source justification and readable private evidence file where applicable. The native controller rejects unknown fields and native-owned wage, hours, identity and leave-balance overrides. A different reviewer submits the record. Draft evidence is never exported as reviewed truth.
5. Open the originating Employee Calendar, attendance/pay/leave report or Payroll Entry and use its grouped statutory action. Saved Company/worker/Branch/Department/period filters are reused. A worker card/register has no payroll period. Form 34 requests a Friday–Thursday week when a report's selection is not one. Form 80 needs a full half-year; Form 81 a full year. A leave `as_of_date` is not a reporting history range.
6. Preview before downloading. Missing mandatory values, unresolved overtime-rate breakdowns, absent allocation evidence and missing receipts appear as findings. Blank draft cells are not invented zeroes. PDF is fixed-layout A4; DOCX is an editable working copy, with explicitly identified column bands on wide registers. Both downloads recheck server permissions and use the same data adapter.

Generation records are immutable and say `Draft Generated`. They record actor/time, layout/version, source references, selected scope and output hash, without copying the exported personal cell values. There is no fictional filed/paid/approved status. External medical, engineering and licence originals must be retained as controlled evidence rather than fabricated by this exporter.

## Upgrade boundary

This branch adds native DocType metadata and therefore requires a supported migration **only on a backed-up, authorized site**. The completed fresh-site test used a disposable synthetic Frappe 16 bench; the original local HRMS was untouched. Before a real upgrade, back up database/public/private/config recovery material, rehearse restore, compare any existing draft layouts with the protected schemas, and review Company/Branch profiles. Old drafts with incomplete or conflicting schemas fail closed rather than being silently rewritten. No existing submitted Employee, Attendance, salary or financial document is modified by these adapters.

Official use remains blocked pending current-law review, approved translations and completion of the prescribed variant/page geometries described in [coverage](coverage.md). Creating a layout or submitting evidence cannot override that gate.

## Explicit first-use setup

Open **Workforce Statutory Print Layout** through native search/list navigation.
Use **Menu → Prepare Draft Layout**, select your permitted Company, optional
Branch, source form and explicit draft effective date. The action creates one
internal draft from protected reusable definitions or returns the existing
configuration without replacing its labels, mappings, dates or administrator
edits. It is never called during installation/migration. Repeated/concurrent
requests reuse the same scope; existing approved layouts are not modified.

This action does not infer legal applicability or create a reviewed establishment
profile. Missing registration, address, signatory, statutory identity, salary
mapping and Bangla heading remain review findings or editable configuration.
Company-specific information comes from native records or explicit authorized
configuration; it is not shipped in the application. External certificates are
rejected as generated layouts.

For a working Employee export, prepare Form 8, open an authorized Employee and
choose the statutory Worker Register action. Preview the draft and its findings,
then choose **Download A4 PDF** or **Editable DOCX working copy**. Form 8 requires
no payroll date range. PDFs/DOCX download to your browser; configuration and
immutable generation audit records remain native DocTypes. An internal draft
is not a legally approved register or government filing.
