# Statutory wage-floor readiness — 2026-09-24

Status: implemented on `feat/statutory-wage-floor-readiness`, based on corrected PR #14 head `61b5e3dc834a5f44ac71f0bc28dc8220f166e248`.

This phase is limited to effective-dated, source-backed minimum-wage readiness. It does not change compensation, create an operative TCL/EFL wage rule, or infer legal grade from HR/payroll fields.

## Read-only staging audit

- Site: `hrms-v16.localhost` (non-production).
- Companies: Tradexcel Ceramics Ltd. (TCL), Elegance Footwear Ltd. (EFL), both BDT.
- Active Employees: 242. TCL has 218 `Worker` records at `TCL Factory`, 12 `Full-time` at `Tradexcel Headquarters`, 9 `Full-time` at `TCL Factory`, and 1 record with blank branch/employment type. EFL has 2 `Full-time` records at `Elegance Footwear Ltd. (H O)`.
- Employee Grade is blank for all 242. Designations are not a legal classification.
- Salary mode: TCL 208 Cash, 2 Bank, 30 blank, and 1 blank branch/type Employee; EFL 2 blank. Both Bank employees lack `bank_ac_no`.
- Active salary structures: TCL Standard (Monthly Salary), TCL Daily Wage (Daily Wage), EFL Standard (Monthly Salary); all use BDT. Submitted Salary Structure Assignments: 227.
- There is no wage-floor DocType/rule. There are 0 statutory exit Rule Sets.
- The staged branch directory has company names and one factory address for TCL (`Angutiachala, Bhawal Mirzapur`, Gazipur), and only an EFL head-office branch in Dhaka. No DIFE license/registration evidence or explicit EPZ classification was found in the staged Company/Branch records.
- No real Employee, compensation, SSA, or wage-rule record was changed.

## Government-source review

Research is for legal-scope discovery only. It does not activate any statutory value.

| Establishment | DIFE registration evidence | Sector/location/EPZ | Wage notification candidate | Status |
| --- | --- | --- | --- | --- |
| TCL Factory | No company-specific license/registration evidence found in this read-only repo/staging or exact-name DIFE search. | Staging branch records Gazipur address; registered industrial sector and Labour Act vs EPZ regime remain unverified. | No final ceramics wage notification scoped to this establishment was verified. | `NOT FOUND / LEGAL REVIEW REQUIRED` |
| EFL | No company-specific license/registration evidence found in this read-only repo/staging or exact-name DIFE search. | Staging records only a Dhaka head-office branch; operating factory/site, registered sector, and Labour Act vs EPZ regime remain unverified. | The 2020 leather-goods/footwear final notification is a candidate only if establishment scope is verified; 2026 proposal remains draft. | `CANDIDATE ONLY / LEGAL REVIEW REQUIRED` |

Official DPP lists an Aug. 14, 2026 leather-goods/footwear minimum-wage item explicitly as a **draft recommendation**, not a final wage declaration. The final leather-goods/footwear wage notification located is S.R.O. 145-Law/2020, published in the Bangladesh Gazette on Sep. 8, 2020 (notification dated Sep. 2, 2020). The DPP September 2026 extraordinary-gazette listing through Sep. 20 and targeted title/sector searches did not locate a later leather/footwear final notification by Sep. 24, 2026; this is not treated as proof that no later order exists. The official BDLaws consolidated Labour Act describes the Minimum Wage Board process and government declaration of minimum rates in Chapter XI. Exact company coverage and worker status need Legal/DIFE evidence.

Sources:

- Bangladesh Government Press, Aug. 2026 extraordinary gazette listing: <https://dpp.gov.bd/bgpress/index.php/document/get_extraordinary/62649>
- Bangladesh Government Press, final leather/leather goods/footwear wage notification, published Sep. 8, 2020: <https://www.dpp.gov.bd/upload_file/gazettes/36842_13729.pdf>
- BDLaws, Bangladesh Labour Act, 2006 consolidated text: <https://bdlaws.minlaw.gov.bd/act-print-952.html>
- DIFE LIMA official establishment search: <https://lima.dife.gov.bd/public-report/establishment-list>

No real statutory wage value is configured, approved, or activated by this work.

## Design decisions

- A dedicated wage Rule Set represents one reviewed, effective-dated government wage order for an explicit company/optional Branch scope, legal regime, sector, currency, source(s), and rows.
- Rule rows use explicit legal component/grade/location and an explicit native Salary Component mapping. Total-floor rows sum only mapped floor-eligible components; overtime, bonus, allowances not mapped into the approved floor package, deductions, and net pay cannot mask a deficient package.
- An effective-dated employee classification explicitly records `Covered` or `Reviewed Outside Scope`. A submitted wage Rule Set activates rollout only for its declared company/Branch scope. Inside that scope an employee must have an approved classification; missing classification is not called compliant. Outside configured scopes readiness reports that no approved scope applies, without blocking all employees.
- Frappe/HRMS native Salary Structure Assignment evaluation (`get_evaluated_components()`) supplies full-cycle `default_amount` values. Payment-day reduced Salary Slip `amount`, overtime, bonuses, tax, loans, and `net_pay` are not used to prove the floor.
- A covered or outside-scope classification is bound to the exact submitted Rule Set and its effective dates. Past payroll uses that immutable historical classification's establishment snapshot; a current/future payroll after an Employee establishment change requires re-review.
- Rate-period conversion (Monthly versus Daily), mid-period changes, apprentice duration, and annual increments remain explicit review findings when not directly represented by approved rule data.
- A below-floor finding never edits an SSA or salary structure. Compensation changes continue through separately approved native SSA.
- The wage-floor boundary remains separate from separation-law rules. Approved wage orders require an establishment reference and complete official notification/source provenance; source status must be `Final Gazette` to activate.

## Migration record

Before adding the wage-floor DocTypes and role permissions, a fresh `bench --site hrms-v16.localhost backup --with-files` completed at 2026-09-24 08:15 Asia/Dhaka. The database archive passed `gzip -t`; both public/private file archives passed `tar -tf`. The exact files and SHA-256 values are recorded in `BACKUPS.md` §2. The first standard migration attempt stopped during DocType sync because the child-table DocTypes lacked controller modules; minimal controller modules were added and the standard `bench --site hrms-v16.localhost migrate` then completed successfully. There was no manual metadata convergence and no real configuration change. `clear-cache` completed. `bench build --app tradex_hr` completed with Node 24.15.0; the system-default Node 20.20.2 did not satisfy the installed Frappe asset-builder engine requirement.

## Verification log

- Synthetic native Salary Structure evaluation and compliance integration passed; the installed HRMS API returned the full-cycle `default_amount` values before payment-day reduction.
- Wage-floor unit and native integration tests passed after historical branch-snapshot, exact Rule Set binding, and draft/mixed-source activation checks were added.
- Focused wage-floor/native payroll checks: 18 passed. Full Tradexcel suite after the final permission-hook and branch-normalization fixes: 422 passed, 2 skipped. `compileall`, four DocType JSON validations, asset build with Node 24.15.0, repeat standard migration, cache clear, and `git diff --check` passed. No JavaScript source changed.
- Warm `prepare_wage_floor_context` for the 240 TCL active/left employee population loaded rules/classifications in 2 SQL calls and 0.0023 seconds. Staging had 0 approved wage Rule Sets and 0 submitted wage classifications.
- Native synthetic rule/classification maker-checker persisted and resolved through readiness; cleanup left 0 wage Rule Sets, 0 wage Classifications, 0 wage Source rows, and 0 wage Rate rows. Blank Branch values are normalized consistently for historical/current scope comparison. Desk visual E2E is not verified and remains a release gate. The first Node 20 asset-build attempt was rejected by the installed Frappe engine requirement; rerun with the available Node 24.15.0 passed.
