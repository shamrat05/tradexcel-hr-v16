# Employee separation and Full & Final — 2026-09-23

## Architecture

- `Employee.relieving_date` is the canonical employment end date; no parallel date field was added.
- Native `Employee Separation` owns operational tasks. One default `Employee Separation Template` is installed only when no template with the Tradexcel title exists.
- A controlled separation type and explicit legal/statutory review status are stored on native `Employee Separation`. No statutory amount is calculated.
- Frappe v16 checks `allow_self_approval` on each transition. The HR maker’s “Submit for Finance Review” transition must allow its owner to route the document; the distinct Finance “Approve and Submit” transition keeps `allow_self_approval = 0`. The synthetic workflow test proves the owner cannot approve even when holding both roles.
- Operational access finalization is independent from financial settlement. It marks an employee `Left`, disables only a dedicated low-privilege linked `User`, and disables application-side biometric mappings without deleting history or sending device commands.
- Native `Full and Final Statement` is the settlement hub. A Finance workflow is maker-checker. Its native Journal Entry method is wrapped for company scope, approved-state control, and idempotent reuse; Bank Transaction evidence remains the source for bank reconciliation.
- `Recover Cost` asset rows require a positive explicit cost and an enabled posting account in the same company before F&F can be submitted. No automatic asset deduction is calculated.
- Final salary stays in native payroll; F&F readiness does not add it a second time. Submitted Salary Slips and consumed Daily Wage inputs remain historical truth.
- Native payroll dates clip to joining/relieving dates. The installed Payroll Entry selector includes status other than `Inactive`, including `Left`; the project boundary no longer blocks mid-period joins/leavers. This branch does not introduce a custom pro-ration formula.
- Approved payable work dated after relieving date is rejected. Offline evidence is classified from device capture time, not server receipt time. Checkins remain evidence, not payable Attendance.

## Installed v16 behavior verified

- `PayrollEntry.get_payroll_dates_for_employee()` clips the period to `date_of_joining` / `relieving_date`.
- `SalarySlip.actual_start_date` / `actual_end_date` use those boundaries. `get_payment_days()` permits a relieved employee when status is `Left`.
- `Leave Encashment` calls `validate_active_employee()`. In this installed HRMS version that helper rejects `Inactive`, not `Left`; marking an employee Left does not itself prevent native encashment. The system still prepares any required settlement inputs before access finalization as an operational sequence.
- Native Full & Final requires native payables/receivables and allocated assets to be settled/returned or have an explicitly selected recovery action. Tradexcel does not calculate recoveries or settlement money.
- Full & Final readiness now marks native `Unsettled` payables/receivables, owned assets still set to `Return`, and `Recover Cost` rows without cost/account as review-required, matching installed HRMS submission checks.
- The readiness endpoint remains the whitelisted user-facing method; its native-row classifier is internal only.
- F&F Journal Entry submission means accounting was posted. A Bank Entry is classified bank-reconciled only when native Bank Transaction allocation is reconciled and the JE has a clearance date. Cash must not be presented as bank-reconciled.
- The current company has no Lending app installed; loan support is not customized.

## Read-only staging snapshot

Site: `hrms-v16.localhost` on the disposable/local v16 staging bench. Counts were read only; no real Employee or financial document was edited.

| Record | Count |
| --- | ---: |
| Active Employees | 242 |
| Left Employees | 0 |
| Active with future relieving date | 0 |
| Left without relieving date | 0 |
| Active with relieving date | 0 |
| Employee Separation | 0 |
| Employee Separation Template | 1 (installed default checklist) |
| Exit Interview | 0 |
| Full and Final Statement | 0 |
| Gratuity Rule / Gratuity | 0 / 0 |
| Encashable Leave Type / Leave Encashment | 0 / 0 |
| Outstanding Employee Advance / Expense Claim | 0 / 0 |
| Employee-assigned Assets / Asset Movement | 0 / 0 |
| Loans | Not installed (Lending app absent) |
| Employees with user_id / enabled linked Users | 1 / 1 |
| Tradexcel Employee Biometric mappings | 221 |

## Migration and build evidence

- Fresh `bench backup --with-files` completed before the final migration: `20260923_195210`.
- Archive checks: database gzip `gzip -t` passed; public/private file archives listed successfully. SHA-256: config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`; database `e7c31e20113d73b5bb5797bcd78edd3730eadbd72b7d82fb45e5b1eba1376c66`; public files `407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532`; private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`.
- `bench --site hrms-v16.localhost migrate` completed normally and ran `after_migrate`; no direct `ensure_*` call or manual metadata convergence was needed.
- Workflow, custom fields, and default native template were verified from the migrated site.
- Final asset build succeeded with Node v24.15.0: JS `tradex_hr.bundle.TAYVRSUG.js`, CSS `tradex_hr.bundle.FKLLR2DQ.css`, RTL CSS `tradex_hr.bundle.V2V7YM4T.css`. `bench --site hrms-v16.localhost clear-cache` completed after the build.
- Python `compileall` and Node v24 `--check` passed for `employee_calendar.js` and `employee_separation.js`.
- Full Tradexcel suite passed: 403 passed, 2 skipped. The focused separation/readiness/native workflow tests passed.
- `git diff --check` passed.
- Browser/Desk visual E2E has not been performed; no browser DevTools tool is available, so it remains a release gate.

## PR #12 Phase A follow-up

- The synthetic managed Payroll Entry integration now proves monthly joiner/leaver monetary results through native Salary Slip creation. For the configured synthetic base of BDT 30,000 and native `depends_on_payment_days` component: joiner (2026-08-15 through 2026-08-31) had 17/31 payment days, gross/net BDT 16,451.61; leaver (2026-08-01 through 2026-08-20, Employee status `Left`) had 20/31 payment days, gross/net BDT 19,354.84. Both native component rows retain default amount BDT 30,000 and native-calculated prorated amounts; deductions were zero. The manager-prepared full company Payroll Entry included both employees. No Tradexcel proration formula was added.
- The synthetic Daily Wage leaver (relieving date 2026-08-20, status `Left`) had a BDT 400 SSA daily base, 20 payable finalized Attendance days, and native Additional Salary of BDT 8,000 dated on the relieving date. Native Salary Slip gross/net were BDT 8,000. Submitting payable Attendance dated 2026-08-21 was rejected. Raw Checkin was not used.
- Synthetic Leave Encashment worked for an employee already marked `Left`: the test-only Leave Type allowed two encashable days, native per-day SSA amount was BDT 100, and native Leave Encashment produced BDT 200 plus a submitted Additional Salary with Leave Encashment provenance. Native `validate_active_employee()` rejects `Inactive`, not `Left`.
- Synthetic Gratuity used a deliberately arbitrary TEST ONLY rule (10% slab; not Bangladesh law). Native Gratuity calculated a positive amount from the submitted native Salary Slip and the native F&F source rows linked to both Gratuity and Leave Encashment.
- `Not Applicable` statutory review no longer receives global Gratuity/Leave Encashment configuration findings. `Approved` without an explicit entitlement ruleset returns `STATUTORY_ENTITLEMENT_RULESET_REQUIRED` and blocks F&F submission.
- F&F JE identity now checks the exact F&F reference, same company, enabled/non-group same-company accounts, native non-balancing rows against the F&F rows, and submitted debit/credit balance. Foreign F&F references and a linked JE using an Expense balancing account are rejected. Cash/Bank interpretation comes from the selected balancing Account type, not the initial native voucher type. Native Cash Entry submission reports `CASH_SETTLEMENT_ACCOUNTING_POSTED`; a native Bank Entry remains `AWAITING_BANK_RECONCILIATION` until its Bank Transaction is reconciled and the native clearance date is set.
- Access finalization is exercised while the submitted F&F is still `Unpaid`; settlement then continues through Cash and Bank native accounting. Access disablement remains independent of settlement status.
- Focused exit/payroll tests: **28 passed**. Full Tradexcel pytest suite: **405 passed, 2 skipped**. Python compileall and Node syntax checks passed. Build passed with Node v24.15.0; the bench's default Node v20.20.2 failed the engine requirement (`>=24`) before rerunning with the installed v24 binary. Latest built assets: JS `tradex_hr.bundle.TAYVRSUG.js`, CSS `tradex_hr.bundle.MDQITTNZ.css`, RTL CSS `tradex_hr.bundle.UTBWMS7H.css`. Cache clear passed.
- These follow-up changes add no DocTypes or fields, so no migration was run. Staging was read only except disposable synthetic integration fixtures. Post-test query found zero synthetic finalization companies, zero synthetic exit employees/shared-link employees, and zero synthetic leave types/Gratuity Rules after cleanup. No production or real employee/F&F records were changed.
- Desk visual E2E remains a release gate; no browser DevTools tool was available.
## Synthetic integration cleanup

- The native separation/F&F integration test initially left its dedicated synthetic Employee User because the fixture-company cleanup commits before that User is deleted. The test cleanup now commits the User deletion explicitly.
- Read-only verification after the final integration run: 0 synthetic finalization companies, 0 scoped finalization users, 0 exit-employee test users, 0 Employee Separations, and 0 Full & Final Statements.
- An earlier run had left 15 unlinked `exit-employee-*` test users from previous attempts. Each was checked for Employee links (none), then removed by exact test-only email prefix. Current count is 0. No real Employee/User records were changed.

## Final validation

- `env/bin/python -m pytest apps/tradex_hr/tradex_hr/tests -q`: **405 passed, 2 skipped**.
- Focused exit/payroll tests: **28 passed**.
- `env/bin/python -m compileall -q apps/tradex_hr/tradex_hr`: passed.
- Node v24.15.0 `--check` for `employee_calendar.js` and `employee_separation.js`: passed.
- `bench build --app tradex_hr`: passed with Node v24.15.0; the bench default Node v20.20.2 is below the required `>=24` engine.
- `bench --site hrms-v16.localhost clear-cache`: passed.
- `git diff --check`: passed.
- Standard migration proof is the earlier migration from backup `20260923_195210`; the follow-up changed Python/tests only and added no schema, so migration was not rerun.
- Browser/Desk visual E2E remains unverified and is a release gate.

## Phase B — versioned statutory exit review

- Added `Tradexcel Statutory Rule Set`, `Tradexcel Statutory Source`, and `Tradexcel Statutory Entitlement`. No rules are installed automatically; current staging has **0** rulesets.
- A Rule Set records company and optional branch scope, explicit Bangladesh/regime fields, effective dates, applicability-date basis, service method, reviewer metadata, official source references, and explicit exit-type/classification/entitlement handling rows. Approval requires notes, source sections, mappings, separate Owner/Director approval, and a non-maker reviewer. Approved legal meaning is immutable; corrections require a new effective version.
- Employee Separation now binds to the exact approved Rule Set, explicit legal classification, and reviewed applicability date. It does not select a later “latest” rule. `Not Applicable` requires an explicit out-of-scope/service-rule classification and review notes. Changing `Employee.relieving_date` makes the prior date review stale.
- The readiness service reports applicability and source/configuration findings only. It does not calculate statutory money. A manual-calculation mapping remains blocked for legal handling. Native Gratuity, Leave Encashment, and Full and Final remain financial records.
- The ruleset workflow is maker/checker: HR Manager drafts/submits; Owner/Director approves. A maker who also holds Director cannot self-approve. Company-scoped user permissions filter rule visibility and server checks enforce scope.
- Synthetic integration proves source requirements, draft rejection, self-approval/cross-company denial, approval metadata, immutable rule meaning, overlapping-date rejection, later version selection, exact version retention, stale relieving-date rejection, Holiday List deadline calculation, and absence of calculated money. Synthetic rules are deleted by test cleanup; staging verifies 0 Rule Sets, 0 Employee Separations, 0 Full & Final Statements, 0 synthetic companies and 0 synthetic test users.
- The integration cleanup now records each synthetic Rule Set immediately after insertion, so a failed workflow transition cannot leave an orphan draft. One orphan from an earlier failed run (`TRS-2026-00001`, synthetic company `Tradexcel Finalization Test 0D7C1380`) was inspected, confirmed unlinked to any Employee or Separation, and deleted. Post-cleanup Rule Set count is 0.
- Three standard backups with files preceded the schema migrations: `20260923_221017`, `20260923_222608`, and `20260923_222857`; each archive was checked (`gzip -t`, public/private `tar -tf`). Migrations used ordinary `bench migrate`; initial missing controller modules were added, and subsequent migration completed without manual metadata convergence. The latest migration was run after the workflow transition change; later changes were Python/tests/docs only.
- Validation: statutory/separation focused tests **5 passed**; full Tradexcel suite **409 passed, 2 skipped**; statutory integration rerun after cleanup hardening **1 passed**. `compileall`, JS syntax, `bench build --app tradex_hr` with Node v24.15.0, and cache clear passed. Desk visual E2E remains **unverified / release gate**.
- No real statutory Rule Set was approved, no real employee exit/F&F was changed, and production was not touched.
