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

## Remaining release proof

- Actual native monthly leaver/joiner Salary Slip amounts/payment-days through a full managed Payroll Entry run.
- Daily Wage leaver end-to-end native Additional Salary proof.
- Native Leave Encashment and synthetic Gratuity Rule mechanics.
- Full & Final Journal Entry submit plus native Bank Transaction reconciliation; this slice currently proves maker-checker, draft creation, retry reuse, and the unpaid operational exit boundary only.
- Desk visual workflow review.
- The standard migration followed backup `20260923_195210` after field/workflow setup changes. Later readiness/test changes are Python-only; the final asset build and cache clear ran after the JavaScript changes.

## Synthetic integration cleanup

- The native separation/F&F integration test initially left its dedicated synthetic Employee User because the fixture-company cleanup commits before that User is deleted. The test cleanup now commits the User deletion explicitly.
- Read-only verification after the final integration run: 0 synthetic finalization companies, 0 scoped finalization users, 0 exit-employee test users, 0 Employee Separations, and 0 Full & Final Statements.
- An earlier run had left 15 unlinked `exit-employee-*` test users from previous attempts. Each was checked for Employee links (none), then removed by exact test-only email prefix. Current count is 0. No real Employee/User records were changed.

## Final validation

- `env/bin/python -m pytest apps/tradex_hr/tradex_hr/tests -q`: **403 passed, 2 skipped**.
- `env/bin/python -m compileall -q apps/tradex_hr/tradex_hr`: passed.
- Node v24 `--check` for `employee_calendar.js` and `employee_separation.js`: passed.
- `bench build --app tradex_hr`: passed.
- `bench --site hrms-v16.localhost clear-cache`: passed.
- `git diff --check`: passed.
- Standard migration proof: passed from fresh backup, workers healthy, `after_migrate` normal, no manual metadata convergence.
