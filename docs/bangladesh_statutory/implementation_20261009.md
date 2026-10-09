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
CI workflow expansion and deployed parity remain open. Socket.IO remains a separate preview/runtime service gate; the app-owned legacy
Desktop Icon logo request was repaired idempotently to the packaged Workforce
Suite asset. /undefined remains the known upstream Frappe sidebar request.


## Administrator configuration and realtime checkpoint — 2026-10-09

The layout list now provides a native Prepare Draft Profile action. It selects an
existing Company and optional Branch, copies only the native Company name and
linked Address when available, and opens an editable draft profile with explicit
missing requirements. Registration numbers, applicability, translations,
evidence and approval remain blank/review findings. Repeating the action is
idempotent. New draft layouts link only independently submitted profiles; a
draft profile is never treated as approval. The existing Prepare Draft Layout
action remains available for every applicable catalog entry.

The isolated preview's realtime service was started from installed Frappe source
at port 9032 with DEV_SERVER enabled. Frappe's native socket client then used
the configured socketio_port; Playwright observed successful Socket.IO polling
responses (HTTP 200) rather than the former same-origin 404. No Frappe core or
client workaround was added. The preview web process remains separate from the
realtime process, and workers/scheduler remain stopped.

Remaining statutory work includes the service-book and Forms 24, 35/35(a),
37 variants and Form 40 layouts, complete Form 80/81 period/category
aggregation, payment/rate evidence and the legal/regulatory crosswalk. These
remain draft/legal-review gates. DOCX is documented as an editable working copy:
native letterhead text is included, while PDF/HTML retains the configured native
logo and Letter Head presentation.


## Focused review correction — 2026-10-09

The app-owned legacy logo repair was removed from generic install/after-migrate
code. Historical asset recognition remains only in the explicitly invoked
legacy migration finalization path, where ownership and asset existence are
checked before changing a Desktop Icon. The white-label identifier contract
therefore remains strict.

Profile review findings now require native document read permission and the
same Company scope check used by statutory exports. Submission rejects missing
or unresolved placeholder values for address, registration, legal reference and
review notes before recording reviewer approval. Draft-profile creation now
uses a cache lock keyed by Company and Branch to prevent duplicate concurrent
profiles. Focused source/branding/white-label checks: 56 passed.

The remaining legal and source-data gates are unchanged: service-book and
Forms 24/35/37/40 variants, complete Forms 80/81 aggregation, payment evidence,
regulatory crosswalk, legal approval and real operator acceptance remain open.


## Focused review correction — applicability and concurrency

The establishment profile now records independent Registration Applicability and Licence Applicability states: Required, Not Applicable, or Pending Review. Submission rejects Pending Review, requires the reviewed number for Required, and requires non-applicability evidence for Not Applicable. Draft setup initializes both states to Pending Review and reports the outstanding review work. Concurrent draft-profile requests are covered by a separate-transaction regression; the existing cache lock remains the serialization mechanism. No legal applicability is inferred by the application.


## Site-backed verification — applicability and profile concurrency

On the isolated disposable Frappe v16 site workforce-statutory.localhost (separate database and backup), the corrected applicability and profile-scope tests passed. The full Workforce Suite integration suite completed with **901 passed, 2 skipped, 1 warning**. The synthetic profile, layout, record and export fixtures were cleaned; the two synthetic setup Companies and four Employees remain only as the isolated suite prerequisites. No restored customer site was used or modified.


## Form 40 technical completion — 2026-10-09

Form 40 is now represented as a distinct protected catalog entry and print-layout option. It is sourced from the separate Form 40 register appearing after Form 39 in the inspected source page, with worker register identity, advance amount/payment date, requitals and collection dates, recovery completion date and remarks. It remains a manually reviewed draft until current-law applicability, employer evidence and legal approval are completed; no advance or repayment is inferred from payroll.


## Form 40 repayment-history correction — 2026-10-09

The inspected Form 39/40 source page distinguishes Form 40 from Form 39 and shows a repeatable “each installment amount and collection date” column alongside the advance, total recovery date and remarks. Workforce Suite now keeps that history in a native child table (Workforce Statutory Requital) rather than a single free-text value. Each row requires a positive reviewed amount and collection date; references and notes remain attached to the rendered row. An advance may be recorded before its first repayment, while a non-Form-40 record cannot carry repayment rows. Export expands each reviewed repayment into its own row without changing the canonical payroll or financial ledgers. Form 39 and Form 40 regression coverage asserts their distinct damage-versus-advance field contracts. The form remains a technical draft pending current-law and employer evidence review.


## Current Form 40 verification — 2026-10-09

On the isolated site, the Form 40 repeatable-repayment integration test passed (1 passed, 26 deselected) and the full statutory native integration file passed (27 passed). Source, schema, printing and white-label checks passed (78 passed). A subsequent whole-application run was not a valid completion result: the isolated bench reached Frappe's native 600-job queue guard and reported 43 environment/setup failures, 861 passed and 2 skipped. No queue jobs were purged or altered; the broader run remains an infrastructure-gated follow-up rather than evidence of a Form 40 regression.


## Form 40 edge-case and clean full-suite verification — 2026-10-09

The Form 40 adapter now emits a reviewed advance with no repayments as one row with blank repayment cells. When repayments exist, advance-level remarks are retained and combined with repayment-specific reference/notes rather than overwritten. The regression covers both cases.

The earlier whole-suite attempt was invalid because the disposable site hit its default 600-job guard. After confirming no competing test process, the isolated site was given a temporary 5000-job cap for one run; no jobs were purged or altered. The exact current tree completed **904 passed, 2 skipped, 15 warnings** in 694.29 seconds. The temporary site-specific setting was removed and the prior absent configuration restored. This remains isolated-site evidence; remote CI and legal/staff acceptance are separate gates.


## Periodic return draft aggregation — 2026-10-09

Forms 80 and 81 now have a native read-only aggregation path when no submitted manual return record exists. It is Company/Branch scoped, permission checked, bounded, and uses only submitted Attendance observations for draft adult male/female averages. It reports missing Attendance coverage, working-day review, and legal category review findings instead of treating missing data as zero or silently producing an approved return. Existing reviewed manual records remain authoritative and unchanged. The path is an engineering draft; establishment categories, foreign/contractor/adolescent classifications, working days, payment/safety particulars, current-law mapping and legal approval remain required before official use.


## Periodic aggregation precedence and final isolated validation — 2026-10-09

Automatic Form 80/81 draft aggregation now yields to an existing draft manual evidence record; operator work in progress cannot be bypassed by a snapshot. Submitted manual evidence remains authoritative. After this precedence correction, the exact integrated tree completed **906 passed, 2 skipped, 15 warnings** in the isolated Workforce Suite bench. The queue cap was temporarily raised only for the isolated run, no queued jobs were purged, and the site-specific setting was removed afterward.


## Historical workforce-period aggregation — 2026-10-09

Periodic draft aggregation now also counts employees with a native relieving date inside the Form 81 reporting period as an explicitly reviewable leaver total. Gender averages use submitted Attendance observations and native birth dates for adult classification; missing coverage, category distinctions and working-day totals remain actionable findings. No current headcount is relabeled as a historical average, and no resignation/dismissal classification is inferred without reviewed evidence.


## Final periodic aggregation verification checkpoint — 2026-10-09

The exact tree including historical leaver aggregation completed the isolated full Workforce Suite suite with **906 passed, 2 skipped, 15 warnings** in 842.18 seconds. This validates regression compatibility on the disposable site; it does not convert draft periodic returns into legally approved filings.

## Historical employee-selection correction — continuing statutory completion

Removed the current Active filter from periodic Employee discovery while retaining permission-aware Company/Branch queries. A pure employment-period adapter includes dated joiners/currently Left workers, excludes non-overlapping employment, reports unknown/inconsistent dates and preserves candidate-versus-established-history distinctions. Attendance outside known employment intervals is excluded and worker/date observations are deduplicated. Native leavers are provenance observations, never automatically classified as Other. Missing historical transfers and incomplete Attendance coverage produce explicit findings.

Validation at this checkpoint: 3 pure employment-period tests passed; 2 focused periodic native-adapter tests passed (27 deselected) in the disposable bench. These are focused results, not a new full-suite result. Remaining phases continue; technical completion is not claimed.

## Protected structures, reviewed histories and final completion verification

Implementation commit: `794f12c2383ddd99b94778bbea44f51988299594`, following historical-selection correction `2906446307a5849fa3bea0062caab6685f9b25f9`. Work stayed on PR #77 / `feat/bd-statutory-native-completion` in its isolated worktree. PR #78 and the shared base were not modified, merged, reset or cherry-picked. Production and the original customer preview were untouched.

The catalog has 35 entries: five separate consent/withdrawal/shift variants were added while legacy combined configurations remain explicitly identified working copies. The definitions now contain 828 protected fields. Form 81 has twelve sections and 216 cells, including deduction, maternity, compensation, medical and provident-fund matrices. Form 80/81 native preparation provides a complete scoped checklist; complete historical membership/calendar/classification evidence can opt into disclosed Attendance-based averages. Missing observations block calculation and clear stale derived draft values. Independently reviewed aggregates remain usable for genuine employer history outside native sources. No employment type, current headcount, missing Attendance or transfer assumption becomes a legal category.

Form 7 preserves the verified 2022 replacement employer/employment and wage tables, identity and reviewed private portrait, chronological leave/cash and conduct history, signatures and source-book page capacity. Form 24 has three distinct repeatable original-certificate/examination reference tables. Forms 35 and 35(a), and 37/37(a)/37(b), have separate definitions and workflow fields. Source examination findings and professional originals are never manufactured. Identity-card front/back, training/drill workforce headers and two-page accident particulars were refined during source inspection. The appointment sample now retains its six-component wage table, sixteen individual reviewed conditions and four supporting instructions across all three source pages; historical sample rates and conditions are not installed as employer policy.

Native Record child rows carry field labels, unresolved/entered/non-applicable states, row numbers, references and reviewed non-applicability notes. Native administrative controls load missing source fields, add prescribed history rows, fill explicitly reviewed calendar ranges and inherit worker/reporting dates into preview. Explicit companion fields support combined source cells without permitting unrelated-form or native-money overrides. Date/type/finite-number and prescribed-total checks preserve chronology and missing-data distinctions. Permission-aware locking reads and a scoped lock make repeated return preparation reuse an existing readable work item.

Financial evidence has separate instruction, reconciliation, worker receipt and acknowledgement states linked to a submitted native Salary Slip. Historical rate intervals reconcile to their actual approved overtime dates/hours and submitted provenance-linked Additional Salary at native currency precision. Mixed rates remain individual appendix rows, never a blended rate. Receipt totals cannot exceed net wages or be silently duplicated. Supporting originals/portraits are private and fingerprinted at independent submission; changed content is rejected at export. No financial or attendance document is changed.

The [current coverage matrix](coverage.md) and [828-field crosswalk](source_field_crosswalk.json) supersede earlier partial-implementation descriptions. They record historical rule identity, source/version/page range, protected sections, native/reviewed authority, calculations, missing-value behavior, repeatable records, exports and independent legal approval. Page ranges identify inspected source sections rather than asserting certified cell-coordinate transcription.

### Actual final verification

- Final full isolated Workforce Suite run on the complete application implementation: **933 passed, 2 skipped, 18 warnings in 688.50 seconds**. The two skips concern a deliberately absent customer-specific `Example Daily Wage` legacy fixture; synthetic Daily Wage tests ran. All 18 warnings are upstream premailer `codecs.open()` deprecations in joiner-readiness integration. The earlier 930-pass run is a checkpoint and is not substituted for this final run.
- Focused source/schema/renderer/historical-calculation group: **85 passed**. Expanded native statutory integration group: **37 passed** before the final chronology/finite-number refinement; the final full run includes the final versions of those tests. Python/JSON/JavaScript source checks passed (302 Python, 64 JSON and 37 JavaScript files), white-label wiring passed and native action placement passed all 15 checks.
- All **31 generatable catalog entries** were rendered in EN/BN: **62 WeasyPrint A4 PDFs + 62 editable DOCX files**, **62 actual native Frappe wkhtmltopdf PDFs**, and **62 actual LibreOffice-rendered Word outputs**. Four external-evidence entries intentionally reject generation. Checks cover A4 dimensions, text bounds, final-row retention, editable Word tables and Bengali fonts. Native service-book stress output contains two complete 16-page individual books. Selected EN/BN first/middle/last pages of book, return, examination, identity and notice outputs were optically inspected. Synthetic files remain outside committed source; no employer/worker exports were copied into the repository.
- Actual native Desk Record editor check passed the missing-field action, NID/grade companion fields and unresolved blank states with zero page JavaScript errors. The browser did not save or submit a Record. Initial browser attempts referenced an obsolete prior-test layout; a new owned disposable layout resolved the fixture issue, and its cleanup was verified. Standalone development serving has no Socket.IO process; its polling 404s are not reported as a completed full multi-service browser/UAT rehearsal.
- Standard migrations succeeded on the isolated rehearsal site after verified fresh `backup --with-files` restore points. The backup index contains timestamps/filenames/sizes/SHA-256 and gzip/tar integrity verification; no backup contents are in Git.
- Fresh disposable-site standard Frappe/ERPNext/HRMS/Workforce Suite installation completed and metadata/import-path checks passed. Installation first hit the existing isolated 650-job queue guard after app registration; the native `install-app --force` reran the interrupted install hooks under a temporary site-specific allowance. This was not a clean first-attempt install. Fresh-site checks confirmed all new evidence children/fingerprint/calculation fields, zero Employees and zero automatically created statutory profiles/layouts/records/exports. No customer data was restored into the fresh site.
- Both temporary isolated `max_queued_jobs` overrides were removed, restoring their original absent settings. Queued jobs were retained; no purge occurred. Only explicitly owned synthetic documents were cleaned up. Immutable export audits were not deleted.
- GitHub Source contract, White-label QA and Bangladesh statutory print QA passed on implementation head `794f12c`; final documentation-head checks must be verified separately before handoff.

### External boundaries

All output remains a technical working copy. Independent qualified current-law/2022/2026 applicability review, approved EN/BN translations and actual employer/filing-authority acceptance remain required. The Rule 353 original machinery-layout source remains unavailable and its precise document identity is not invented. Actual historical establishment membership/transfers, worker classifications, service/wage records, welfare/committee/fund particulars, examination originals, receipts and signed acknowledgements must come from the employer or authorized issuer. Software provides scoped entry/review/export workflows for these facts; it does not certify their truth or create legal or financial records to fill missing evidence.


## Final evidence boundary and test-mode correction — 2026-10-10

Evidence-state implementation head: `71ab9bb0ee1e2906bea351737eed772031f55a3d`. Subsequent test-only head `ad2b1f7` explicitly resets a copied service-history fixture to draft before its separate reviewer submits it. Frappe's `copy_doc` retains submitted status when `frappe.in_test` is enabled; a focused run alone did not expose that full-suite mode difference. The first final full run therefore reported **1 failed, 935 passed, 2 skipped, 18 warnings in 649.77 seconds**, rather than passing. Its failure was the fixture's attempted owner insertion of a submitted copy; the independent-review guard correctly rejected it. The focused correction passed (1 passed, 39 deselected). A new complete run on the corrected tree is recorded below; the failed run is not completion evidence.

The final native evidence group passed **40 tests**. All populated supplemental facts, across every form, must leave Unresolved state before independent submission. Evidence-only entries can retain and independently review a private original without retyping an externally issued certificate; generation remains prohibited. Valid zero-native-net wage acknowledgements are allowed without making a zero payment claim. Distinct historical employers/events on the same date retain separate natural identities, while conflicting active versions fail closed. Portrait validation fully decodes PNG/JPEG content and rejects corrupt payloads; the logo fixture was replaced by a checksum-valid synthetic PNG.

An additional real Word-to-PDF Form 9 fixture kept 85 leave entries for the same coherent worker header: **9 EN / 8 BN A4 pages**, final entry retained and page bounds checked. The catalog-wide 255-page stress output represents deliberately differing header groups, not a normal single-worker book. Bangla PDF extraction reordered the Latin final-marker fragments; the actual page was optically inspected and showed the complete identifier correctly. This supplementary extraction issue was not silently reported as a layout failure or hidden as a passing initial assertion.

A further financial review found that comparing payment date only with entered record date allowed both dates to be in the future. Commit `124ba7c` additionally compares against actual today for instruction, reconciliation, worker-payment and acknowledgement events. A regression covers all four states with both dates set to tomorrow; the focused financial/history group passed (2 passed, 38 deselected). The intermediate full run was intentionally interrupted to apply this concrete fix: 383 passed, 1 skipped, 18 warnings in 225.55 seconds. It is not full-suite validation, and no queued jobs were deleted.

Final complete isolated Workforce Suite run on application/test head `124ba7c0cae437b599865f3ed5249161c613bd8e`: **936 passed, 2 skipped, 18 warnings in 688.21 seconds**. Both skips concern absent customer-specific legacy Daily Wage fixtures; synthetic Daily Wage regressions ran. All warnings are the upstream premailer `codecs.open()` deprecation described above. This supersedes the 933-pass implementation checkpoint, the failed fixture run and the intentionally interrupted run. No application or test code changed after this successful run.

Final Python/JSON/JavaScript source checks passed (302/64/37 files); white-label wiring passed. GitHub Source contract, White-label QA and Bangladesh statutory print QA all passed on this application head. Final documentation-only head checks are verified at handoff separately.

Final restoration verified that both disposable sites have their original absent `max_queued_jobs` setting, and retained all queued jobs. Production, the original customer preview, PR #78 and the shared base remain untouched. No PR was created or merged. Backup/migration, fresh-site metadata, native Desk, all-catalog four-format and supplementary optical Word evidence remain as detailed above; the final changes concern validation and fixtures, with prescribed structures/renderers unchanged.

Technical implementation is complete for the cataloged source-backed working copies and distinct variants, with the explicitly unavailable Rule 353 original as the source exception. All prescribed fields have native authority or scoped independently reviewed evidence input; unresolved truth, employer history, external originals, translations/current-law approval and real operational/filing acceptance remain external gates. Technical completion does not approve a government filing or establish production recovery readiness.
