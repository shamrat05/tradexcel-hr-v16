# Configure statutory working copies in native Desk

This feature produces **draft working copies**, not legally approved filings. The coverage matrix lists the protected source structures, distinct variants and external evidence boundaries. An independently reviewed personnel fact does not certify a form, establish a wage entitlement or prove payment.

Operators need native access to the source records **and** statutory-layout access (currently System Manager or Workforce Compliance Auditor), with the appropriate explicit Company scope. An HR/payroll role alone does not authorize this exporter. Contextual actions respect native visibility; server checks remain authoritative. No native source permissions are granted by these actions.

1. An authorized System Manager or scoped Compliance Auditor creates a **Workforce Statutory Profile** for an explicit Company and, where appropriate, Branch. Enter the establishment's EN/BN name/address, actual registration/licence references, effective dates, signatory details and applicable source/review notes. Map the company's actual native annual/casual/sick Leave Types; do not create entitlements here. A different authorized reviewer submits the profile.
2. Create **Workforce Statutory Print Layout**, select the historical form reference, Company/Branch, effective dates and version, then use **Layout Tools → Load Suggested Columns**. Required source keys and sections are protected. Change labels, translated notes and width weights only after checking their meaning. Complete the Bangla title and every label; there is no English fallback. Source hashes are read-only and assigned by the controller. Set the saved paper/card size, orientation, optional custom dimensions, margin, compact style, Company-logo position and watermark text on this layout; only an authorized layout editor can save these defaults.
3. For Form 38, map the actual native earning components to the protected wage columns. The additional mapping child table allows several native components in one prescribed column. A component cannot appear twice, and every included nonzero Salary Slip earning must be mapped. This mapping groups **already calculated native amounts for printing**; it never configures salaries or divides gross wages.
4. Use **Workforce Statutory Record** for missing, reviewed facts. Select the same layout/Company, relevant Employee for a native-source supplement, record date/effective end, explicit field keys, source justification and readable private evidence file where applicable. The native controller rejects unknown fields and native-owned wage, hours, identity and leave-balance overrides. Set each populated fact to Evidence Entered (or use Not Applicable with an explicit reason) before a different reviewer submits the record. Unresolved populated facts are rejected at submission. Draft evidence is never exported as reviewed truth. Externally issued evidence-only entries can retain and independently review a private original without retyping its certificate fields; their PDF/DOCX generation remains blocked.
5. Open the originating Employee Calendar, attendance/pay/leave report or Payroll Entry and use its grouped statutory action. Saved Company/worker/Branch/Department/period filters are reused. A worker card/register has no payroll period. Form 34 requests a Friday–Thursday week when a report's selection is not one. Form 80 needs a full half-year; Form 81 a full year. A leave `as_of_date` is not a reporting history range.
6. Choose **Print & Review → Preview / Download**. The print dialog shows the saved paper and appearance choices, which may be changed for this one preview/download without editing the layout. An authorized editor of a draft layout may check **Save these choices as the default** there; the server checks write access and saves only visual settings. Submitted layouts cannot be changed this way. The preview then offers PDF and editable DOCX from the same selected page setup. Missing mandatory values, unresolved overtime-rate breakdowns, absent allocation evidence and missing receipts appear as findings. Blank draft cells are not invented zeroes. Wide DOCX registers retain all columns in identified bands. Both downloads recheck server permissions and use the same data adapter. A visual watermark is not an approval or filing status.

Generation records are immutable and say `Draft Generated`. They record actor/time, layout/version, source references, selected scope and output hash, without copying the exported personal cell values. There is no fictional filed/paid/approved status. External medical, engineering and licence originals must be retained as controlled evidence rather than fabricated by this exporter.

## Upgrade boundary

This branch adds native DocType metadata and therefore requires a supported migration **only on a backed-up, authorized site**. The completed fresh-site test used a disposable synthetic Frappe 16 bench; the original local HRMS was untouched. Before a real upgrade, back up database/public/private/config recovery material, rehearse restore, compare any existing draft layouts with the protected schemas, and review Company/Branch profiles. Old drafts with incomplete or conflicting schemas fail closed rather than being silently rewritten. No existing submitted Employee, Attendance, salary or financial document is modified by these adapters.

Official use remains blocked pending current-law review, approved translations and independent acceptance of the source-linked working-copy layouts described in [coverage](coverage.md). Creating a layout or submitting evidence cannot override that gate.

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
configuration; it is not shipped in the application. External entries can be configured to retain private originals; their generated PDF/DOCX exports are rejected.

For a working Employee export, prepare Form 8, open an authorized Employee and
choose the statutory Worker Register action. Preview the draft and its findings,
then choose **Download PDF working copy** or **Editable DOCX working copy**. Form 8 requires
no payroll date range. PDFs/DOCX download to your browser; configuration and
immutable generation audit records remain native DocTypes. An internal draft
is not a legally approved register or government filing.

## Paper, card, logo and watermark defaults

Ordinary registers retain A4 defaults. Form 6 worker identity cards default to
**A7 Card, landscape (105 × 74 mm)** with separate front/back pages; this is
a practical draft size, **not a claimed legal dimension**. The layout editor
can save a compatible standard size or bounded custom millimetre dimensions.
The A7 preset is offered only for Form 6. It is dense; A6 landscape gives
larger text when the card has many details. The operator sees compatible
sizes and the saved defaults in the print dialog and may change them for one
export. PDF and DOCX use the same validated dimensions. Wide registers refuse
a sheet too narrow to retain all reviewed fields.

The Company logo comes from the native Company record and can be placed left,
right or hidden for this print. The existing native Letter Head remains in
non-card drafts; small cards use a compact header so a full Letter Head does
not silently force a third face. Text watermarks are escaped and rendered
behind content in PDF and Word. The draft/working-copy warning remains even
when a custom watermark is selected. Review the preview and a physical test
print for unusually long names, addresses, Bangla text or printer-specific
scaling. Choosing another size never changes protected legal fields, source
records or the saved template; the chosen settings are recorded in the native
generation audit. A submitted layout printed with different settings is
labeled as a working draft pending review of that presentation.

## Reviewed periodic return and history workflow

For Form 80 or 81, choose **Layout Tools → Prepare Return Evidence** and the exact half-year/calendar year. Repeated requests reuse the existing readable record and preserve edits. The draft inherits reviewed establishment identifiers and provides the complete protected field checklist. Enter the actual facts, keep unresolved fields blank, add per-field provenance, attach private originals where needed and use explicit reviewed non-applicability reasons. A separate reviewer submits only a complete return; draft evidence cannot bypass missing-data findings.

Choose **Reviewed Workforce Evidence** only when the establishment membership and calendar are complete. Add native Employees or distinct external workforce identities, explicit reviewed categories, dated establishment membership and original source references. Use **Evidence → Fill Reviewed Calendar Range** to record actual working/non-working dates with source provenance; omitted dates are not holidays. Attest complete coverage and attach its private original. Save calculates averages only with full submitted Attendance observations. Missing/conflicting dates or work observations leave the draft unresolved and clear stale calculated cells. **Reviewed Aggregate Values** remains available for genuine reviewed historical records outside the installed native sources.

For a service book or examination register, **Evidence → Add History Row** selects the actual source table and adds its protected fields with a chronological row number. Enter each historical employer, wage/rate, leave/service or examination fact from its actual evidence. Current designation or compensation never becomes a historical record. Blank source-book pages remain editable, with unsigned signature boxes.

Identity cards/service books accept a private PNG/JPEG portrait linked to the worker. Original files and portraits are fingerprinted on independent submission and rechecked during export. Replacing a reviewed original requires a new review version.

For native wage/overtime forms, choose the precise **Evidence Kind**, link the submitted Salary Slip or Overtime Slip, attach the original receipt/rate evidence and enter its actual dates, amounts and references. Payment instruction/reconciliation does not mean worker payment or acknowledgement. Rate intervals must match each native overtime date/hours and native currency precision; multiple rates remain an appendix rather than an invented blended rate. Evidence submission never changes payroll/accounting.

**Evidence → Preview Return** inherits the record's Employee and reporting dates. Save first, review actionable findings, then choose English/Bangla and PDF/editable DOCX. All source variants have separate protected definitions; the combined historical configurations remain legacy working copies.
