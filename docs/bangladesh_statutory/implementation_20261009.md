# Bangladesh statutory working exports — implementation evidence

## Scope and disposition

Branch: `feat/bd-statutory-native-completion`, directly based on PR #76 head `f4a82f832a7d93245c7b71b8e13409edc9e217c9`. Published runtime implementation commit: `6b0282a9006a15d4184d00f9ccd92ddcdb0b6867` (application/scripts identical to locally tested `21ee880e11901cd2dd923cf5b9fbc712cdd63458`). Documentation-only descendants record final results; the final PR head is authoritative. PR #75 remains the historical source catalog. PR #74 head `430f7cc1fe16b67dc1f5b1a105b98559117a251f` was unchanged, has no overlapping runtime files, and merges cleanly in a Git merge-tree compatibility check (no merge performed).

**PARTIAL: technically tested working drafts, pending prescribed-layout completion and independent legal review.** Do not use these outputs as approved filings. No merge, original-site migration or production deployment occurred. See the [29-entry coverage matrix](coverage.md) and [native configuration procedure](configuration.md).

## Implemented

- Correct bundle import fixes the PR #76 `app_include_js` wiring failure. Native grouped actions inherit Employee/report/Payroll Entry scope; source callbacks remain composed. Employee documents do not request a payroll date, snapshot leave dates are not reused as history, and Form 34/80/81 validate week/half-year/year respectively.
- Native Company/Branch establishment profiles, independently reviewed supplemental facts and protected layout keys. Presentation/translation/explicit native salary-component print mappings are editable; executable field expressions and overrides of native money/hours/balances are prohibited.
- Form 8 uses canonical Employee facts plus reviewed statutory identifiers, not an invented Employee-ID/NID equivalence. Form 9 uses approved applications and native allocation/ledger balances at each event date. Form 34 uses submitted Attendance and approved native Overtime Slip/Additional Salary; work above a threshold is not automatically approved OT. Form 38 reconciles submitted Salary Slip earnings/deductions/loan repayment/net and explicit component mappings; submission does not prove payment.
- Forms 80/81 use controlled establishment and independently reviewed period evidence. Form 81 now has 105 grouped fields in 12 sections, rather than 22 generic fields; its full prescribed matrix/page layout remains incomplete. Unavailable workforce averages, historical OT rates, payment acknowledgements and safety facts are not fabricated.
- CSRF-protected POST downloads enforce native source permissions, explicit Company scope and permitted Employee/Branch/Department. Native list/REST visibility is scoped too. Generation writes immutable actor/template/version/source/scope/output-hash audits, with `Draft Generated` status and no private cell-value copy. There is no filing/receipt/payment claim or second financial ledger.
- EN/BN use complete draft labels, translated notes and configured establishment/signatory content. PDF is A4 with native wkhtmltopdf; DOCX is a real editable Word package. Wide Word tables use disclosed continuation bands and retain all fields. External medical/engineering/licence documents cannot be fabricated.
- Browser-discovered role mismatch corrected through native UI visibility checks, without granting native HR/payroll access. A regression reproduced ignored caller dates appearing in a personal PDF filename; filenames now use normalized context.

## Installed-source and isolation evidence

A new disposable bench/site was created outside Git: `/home/sanchita/workforce-statutory-20261008/bench`, `workforce-statutory.localhost`. MariaDB uses isolated database `workforce_statutory` on the existing rehearsal datastore port 3309; Redis cache/queue use separate ports 6393/6394. Workers/scheduler stayed stopped, notifications muted, and cross-bench connections rejected by the existing test guard. No customer backup or original working database was used.

Pinned native sources: Frappe **16.34.0** (`f1bdb53ac60cd96528b52de418f9459510acb5bd`), ERPNext **16.35.0** (`12cd563fb9a79731f75ae2a45b1446a0a2dd9e74`), HRMS **16.19.0** (`7e0fba4bf11a63ac7b21a717610e235310815c1a`). Python 3.14.4 and explicit Node **24.15.0**. Native DocPerm/controller/User Permission evaluation, HRMS leave-ledger API, Overtime Slip calculation/provenance and Frappe asset/CSRF/download paths were checked against installed source. No framework source was modified.

Fresh installation of all four apps passed; before synthetic setup Company/Employee/Attendance/Salary Slip/Payroll Entry counts were zero. New app DocType migration passed on this disposable site after private full backups with database/public/private/config artifacts and SHA-256 manifests. A real URL-length defect was corrected to native-supported 512 characters. No direct metadata SQL. The isolated browser setup reused the matching pinned native compiled assets; its initially missing native asset-manifest mappings and native `DEV_SERVER` Socket.IO selection were corrected in the disposable environment, not application/framework source.

## Tests and browser

Private exact logs, JUnit, receipts, PDFs/DOCX, page images and Chromium screenshots: `/home/sanchita/workforce-statutory-20261008/`. These artifacts and synthetic passwords are not committed.

- First exploratory full run: **867 passed, 11 failed, 5 skipped**. Failures exposed fresh-site prerequisites, two framework-location assumptions, a prototype Workspace source shortcut mismatch and submitted-document fixture copies. They were corrected without weakening approval gates. No tests were deleted to inflate counts.
- Second uninterrupted run: **885 passed, 0 failed, 2 skipped**, 614.72 seconds. This preceded the final visibility/filename regressions. The final uninterrupted run is recorded in the completion subsection below.
- Final focused statutory/white-label/migration source checks: **80 passed**. Final native statutory tests: **13 passed** in 17.92 seconds, covering protected fields, four-eyes approval, Company/Employee/Branch denial, draft/submitted Attendance/leave/payroll/manual evidence, native approved OT, reconciliation, private files, cancelled/expired templates, immutable audits and normalized filenames.
- The two legacy skips require an absent historical `Example Daily Wage` structure: `test_current_daily_wage_structure_is_explicitly_detected_as_unsafe` and `test_legacy_staging_daily_structure_remains_blocked`. The generic site intentionally does not seed that unsafe historical configuration.
- Source validation, white-label asset/controller wiring, genericization check, Python compile, tracked JSON parse, Node syntax and whitespace checks passed. Narrow `bench build --app workforce_suite` passed under Node 24.15.0.
- Every printable catalog draft: **50 EN/BN PDFs and 50 genuine DOCX packages** passed A4/structure/final-row QA. Native wkhtmltopdf: **12 PDFs** (8/9/34/38/80/81 × EN/BN) passed A4 bounds, final-row and Bangla-font checks. LibreOffice actually rendered **12 DOCX files** to PDFs; pages/images were inspected, blue headings removed and dense PDF text enlarged. This is renderer evidence, not legal approval of all facsimiles.
- **Actual served isolated Desk:** 16 preview cases (authorized HR+Compliance and Compliance+native HR User × 1365/375px × light/dark × EN/BN), plus two persona denial cases. Grouped actions work through native desktop dropdown/mobile More menu and keyboard activation. Employee and Company inherited, no repeated employee/date inputs; 8 PDF/DOCX downloads completed. No document-level horizontal overflow or JavaScript page error. Four deliberate HTTP 403 responses cover cross-company previews and forbidden GET downloads; no unexpected asset/API failures in the successful matrix.
- Permissions are server-enforced; an HR/payroll role alone is not statutory export authority. Synthetic browser users were explicitly assigned the native HR and existing statutory roles needed for their journeys. This does not prove real staff UAT, physical device behavior or deployed-original-site parity.

## Current-source/legal gaps

The 28 historical reference PDFs (48 pages) were inspected including rotation, duplicate Form 6/6(a) sections and all 11 Form 81 pages. Each of the 29 entries has an evidence-backed status. National SRO 284-Law/2022 and the retrieved 47-page 2026 Act 43 are recorded; the complete current-law crosswalk/sector applicability and translations require independent legal review. The machinery-layout reference remains unverified.

Full service-book changes, Form 24 parts, separate 35/35(a), 37/37(a)/37(b), uncataloged Form 40 and Form 81 matrix facsimiles remain incomplete. Forms 80/81 lack safe automated period/category/average aggregation; reviewed evidence is required. Historical approved rate breakdowns and actual receipt/remittance evidence remain source-data gates. All `legal_approved` flags remain false and official template submission is blocked. No fixed salary split, OT rate, entitlement or client applicability was introduced.

## Safety, cleanup and rollback

Only the isolated synthetic site was migrated and tested. Original checkout `bb48574050214e364c73a15e38dce6128bea2f80`, its dirty `BACKUPS.md`, historical worktrees and customer site were preserved. No real Employee/Attendance/payroll/payment record or existing native permission was modified. New app configuration/audit DocTypes use controlled native permissions.

Synthetic cleanup and final full-suite/remote CI results are recorded in the completion subsection below. Immutable audit records must not be deleted through controller bypasses. The supported disposable-site restore of the verified pre-fixture backup is the cleanup mechanism. Real upgrade rollback requires a full compatible database/files/config restore; reverting Git alone is insufficient after metadata migration. Before any real upgrade, rehearse backup/restore and inspect existing layouts for protected-schema conflicts.

## CI publication boundary

The OAuth credential rejected creation/update of `.github/workflows/bd-statutory-print-qa.yml` because it lacks `workflow` scope. The proposed addition of `test_statutory_schema.py`, explicit Node 24 and DOCX artifact upload is preserved in the local unpublished `feat/bd-statutory-completion` branch and private patch. The publication branch retains the existing workflow exactly. Existing CI still runs its statutory-print tests and the expanded A4 renderer; the additional schema/native integrations have local results and must not be claimed as remote executions. An authorized repository owner must review/apply the CI expansion or provide the required credential scope. No protection or OAuth gate was bypassed.

## Completion checkpoint — 2026-10-09

PR: #77, OPEN / DRAFT / UNMERGED, base `feat/bd-statutory-printing-v1`. Runtime corrections through `846432cb0b5ae92ef0d34f7392d3bca5ee7fd0b5` were tested; the final documentation-only descendant does not change that code.

- Final uninterrupted integration suite: **894 passed, 0 failed, 2 explained skipped**, 595.31 seconds, exact private log/JUnit `full-integration-final-scope.log` / `.xml`. All application tests were executed in one run. The two historical-structure skips remain the ones listed above.
- The preceding committed-source run had **886 passed, 1 failed, 2 skipped**. Its sole failure selected an Employee without a Department for a Department User Permission fixture. The fixture now selects an Employee with a Department; no permission or payroll calculation was relaxed.
- Additional negative testing reproduced a real manual-evidence disclosure for an Employee-restricted auditor. Manual establishment evidence is now denied under Employee/Department narrowing; a Branch-restricted user requires an explicitly matching Branch layout. Native list, record and preview checks apply, including explicitly narrowed System Managers. Positive matching-Branch evidence remains usable. Final focused run: **21 passed** (20 native statutory tests plus the Workspace isolation fixture).
- Additional actual served Chromium checks: Employee-restricted auditor record GET **403**, list GET **200** with the manual record excluded, preview **403**, protected test value absent from every response. These supplement the 16 preview/8 download browser matrix; they are not mocked projections.
- Synthetic cleanup used supported `bench restore` of the SHA-256-verified empty pre-fixture database/public/private backup, followed by a newly backed-up standard migration on the same disposable database. Both new full backup sets have private manifests; no customer backup or original database was used. Residual task-created isolated files were removed after verifying the original file archives were empty. Company, Employee, Checkin, Attendance, Salary Structure/Assignment, Additional Salary, Payroll Entry/Slip, GL Entry, Leave Allocation, Shift Assignment and statutory Profile/Layout/Record/Export counts are **zero**. Only native Administrator/Guest remain; User Permissions and non-folder File records are zero; native Home/Attachments folders remain. The temporary site queue-cap key was removed; workers/scheduler were never started. Test evidence and archives remain private outside Git.
- Existing final-runtime GitHub checks executed and passed: statutory A4 run **37827788211**, Source contract **37827788334**, White-label QA **37827788297**. Final documentation-head checks are verified separately on the PR. These workflows do not execute the added schema/native integration suite; those results are local. Workflow expansion still requires authorized credential scope.
- Final source/wiring, Python compile, all tracked JSON, touched JavaScript under Node 24.15.0 and `git diff --check` passed. PR #74 remains unchanged and merge-tree compatible. Original checkout and its unrelated changes remain preserved.

Disposition remains **PARTIAL / ready for engineering and legal review**, not production or official filing. Incomplete prescribed variant layouts, full Form 81 matrix/automatic period aggregation, unavailable receipt/rate evidence, current-law/translation approval and real staff/device UAT remain outstanding. No government template was marked legally approved.

A documentation-only follow-up initially failed White-label QA because an inline repository URL matched the existing customer-identifier contract. The note now references the PR number; no test or identifier restriction was weakened. The affected source checks were rerun before publication.


## Final consolidation and local preview checkpoint — 2026-10-09

The statutory candidate now includes the consolidated Workforce Suite base:
canonical base a20c33e27dfb27ae840e9edd220c422b71bfd0b4, including PR #73
merge a20c33e27dfb27ae840e9edd220c422b71bfd0b4 and PR #74 merge
1fa37a3d831e64f237b5963378a63a111dfa8551. PRs #75/#76 were superseded;
their verified catalog/prototype content is preserved through PR #77. The
current statutory head is authoritative and remains OPEN/DRAFT/UNMERGED.

The isolated populated preview was synchronized to statutory head
1147ea66328abe5f6ea35754920f565a24128890, migrated once from a verified
backup, built with Node 24.15.0, and served at
http://workforce-preview.localhost:8032. Existing company/employee and
protected HR/payroll counts remained unchanged. Administrator Desk and
Employee List browser smoke passed at desktop/mobile sizes with no document
overflow or uncaught page errors. One reviewed draft Form 8 layout was created
idempotently for preview only; no profile, legal approval, or official filing
was invented.

Statutory output branding now reuses native Company company_logo and the
Company default_letter_head; a disabled native Letter Head is omitted. No
second branding store was introduced. The feature remains partial: statutory
variant completion, legal/translation approval, physical-device/staff UAT,
CI workflow expansion and deployed parity remain open. Socket.IO and the
legacy stored tradex_hr logo request require separate preview/runtime
cleanup; /undefined remains the known upstream Frappe sidebar request.
