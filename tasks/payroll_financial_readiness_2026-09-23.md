# Payroll financial readiness — 2026-09-23

## Scope and operating boundary

This stacked change is on `feat/payroll-financial-readiness`, based on
`feat/payroll-readiness-operator-flow`. It adds a read-only financial gate for
approved native payroll drafts. It does not submit Salary Slips, create Journal
Entries, pay employees, change live tax/account mappings, or touch production.

The sequence stays:

```text
Payroll Readiness → Prepare Payroll → Submit for Review → review draft slips
→ financial checks → Director approval
```

Salary Slip submission remains a later authorized action; the new service only
blocks it when a managed Payroll Entry is not approved or has financial blockers.

## Implementation

- Removed the Salary Slip `before_validate` hook to
  `tax_exceptions.apply_tax_exemption`, and removed the unused helper that
  stripped deduction rows. The legacy `Mark Tax Exempt` value remains readable
  for history, the field is labelled as legacy, and existing Tax Policy
  Exceptions are shown as review findings; submitted records block the
  financial gate until reviewed against native configuration.
- Uses native HRMS Income Tax Slab, Payroll Period, Salary Structure Assignment,
  Salary Component and Salary Slip data. The service calls HRMS's own
  `Salary Slip.get_tax_components()` selection, checks each assignment's
  effective submitted slab and Tradexcel review status, and verifies that each
  draft slip carries the native `current_payroll_period`. A valid zero tax
  amount is accepted; a positive deduction is never required.
- Native tax slab provenance is stored in five app-owned Custom Fields. Only a
  named System Manager or Tradexcel Owner/Director can approve a submitted slab
  with a source reference. The controlled action checks company access before
  writing; ordinary saves cannot alter review provenance.
- The read-only financial service inspects the actual draft Salary Slips,
  compares the employee population, validates payroll payable account type and
  company, checks only salary components represented in rows HRMS includes in
  accounting, validates native cost-center distributions and required
  accounting dimensions, checks gross/deduction/net arithmetic and negative
  net, and summarizes native slip amounts. The service does not build an
  accrual Journal Entry.
- Component Policy Exception effects include component, action and source in
  the operator report. Financial findings link to the matching native repair
  surface: tax slab, Payroll Period, Salary Assignment, Salary Component,
  policy exception, account, cost center, accounting dimension or Salary Slip.
- A Payroll Entry cannot advance to Director approval when the financial
  service is blocked. The enforcement event is
  `before_update_after_submit`: installed Frappe v16 uses this event for
  submitted Workflow transitions and does not run `validate()` on that path.
  An integration test exercises blocked Review Complete and Director Approve
  transitions. Direct API Salary Slip submission rechecks the service; a
  request-local cache avoids recalculating it once per slip in native bulk
  submission. Payroll Managers, Approvers and Directors need an explicit
  Company User Permission before the service returns financial data.
- Net variance against each employee's immediately previous submitted Salary
  Slip is shown as review information without an automatic variance blocker.

No Bangladesh tax rates or statutory amounts were added. NBR's official site
lists the 2026–2027 Income Tax Paripatra and Nirdeshika and the 2026 Withholding
Tax Rules, including a July 2026 amendment. These are source references for
the human reviewer only; this work does not determine company applicability or
transcribe values. See [NBR Income Tax Paripatra](https://nbr.gov.bd/taxtypes/income-tax/income-tax-paripatra/eng)
and [NBR Income Tax Rules](https://nbr.gov.bd/regulations/rules/income-tax-rules/eng).

## Staging evidence (read-only except schema migration)

Site: `hrms-v16.localhost`. No payroll financial records or financial
configuration were created or changed. The staging migration followed the
normal Frappe lifecycle; Frappe also removed an orphan Workspace and queued its
normal search-index rebuild.

September 2026 readiness returned 238 employees: 63 ready and 175 needing
attention. Findings overlap: 159 `ATTENDANCE_UNMARKED`, 159
`BLOCKED_UNSAFE_STRUCTURE`, and 16 `BLOCKED_PAY_BASIS` findings. Existing
Attendance, Salary Structures, assignments and employee records were not
modified.

Financial setup audit found:

| Item | Staging result |
| --- | ---: |
| Native Income Tax Slabs / submitted slabs | 0 / 0 |
| Payroll Periods | 0 |
| Salary Components flagged variable by taxable salary | 0 |
| Salary Components flagged as income-tax components | 1 |
| Tax / Component Policy Exceptions | 0 / 0 |
| Salary Slips / Payroll Entries | 0 / 0 |
| Active Salary Components | 19 |
| Mapped active components (each company) | 15 / 19 |
| Active non-group Cost Centers (each company) | 1 |
| Enabled accounting dimensions | 0 |

Both companies have a configured Company default Payroll Payable Account, but
its native Account Type is blank. Financial readiness will block its use until
the account configuration is corrected by finance. Mapping coverage above is
for all active components; because staging has no draft Salary Slips, no
statement is made about the mappings actually used by a payroll run.

## Migration and verification

Before migration, a full staging backup with public/private files was created:

```text
Timestamp: 2026-09-23 09:25:57 +06:00
Database: 20260923_092555-hrms-v16_localhost-database.sql.gz
SHA-256: 4f869e44cfe6d3668ab458a6d532863121c7078e1714834907de96160eeda472
Public files SHA-256: 407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532
Private files SHA-256: 7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe
Site config SHA-256: 904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73
```

The database gzip and both file archives passed integrity checks. Standard
`bench --site hrms-v16.localhost migrate` exited successfully; the normal
`after_migrate` hook created all five fields. No direct `ensure_*()` call or
manual metadata convergence was used. Frappe ran its normal orphan Workspace
cleanup and queued its normal search-index rebuild.

`bench build --app tradex_hr` and `clear-cache` passed using the already
installed Node 24.15.0 runtime (the default WSL shell selects Node 20, which is
below Frappe v16's engine requirement). The served app bundle is
`tradex_hr.bundle.TAYVRSUG.js`. JavaScript syntax checks passed.

Final focused tests: 58 passed. Full suite: 272 passed, 2 skipped. Compile,
JavaScript syntax and `git diff --check` passed. Tests use synthetic or mocked
payroll data. No synthetic tax configuration could be exercised through a
complete native Salary Slip calculation because staging has no Payroll Period,
Income Tax Slab, tax calculation component, Payroll Entry or Salary Slip. This
is an explicit test limitation, not a claim of native tax integration proof.

Browser routes were not opened in this turn because no Chrome DevTools/browser
tool is configured in this environment. The real report `execute()` path was
run read-only against staging, and the built assets and Frappe migration were
verified.

## Remaining configuration gates

- Finance/legal must decide applicable current NBR rules and configure native
  Income Tax Slabs and Payroll Periods with reviewed source provenance.
- Finance must correct the default Payroll Payable Account Type and map every
  component that actually appears in draft Salary Slip accounting rows.
- HR must resolve the 159 attendance gaps, 159 unsafe Daily Wage structure
  findings, and 16 pay-basis/assignment findings without automatic changes.
- Re-run Payroll Readiness and Financial Review after those native records are
  approved. Actual Salary Slip submission and accrual accounting remain outside
  this branch.
