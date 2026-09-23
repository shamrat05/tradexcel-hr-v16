# Mixed pay basis and Daily Wage input — 2026-09-23

Branch: `feat/mixed-pay-basis-wage-input`
Base: `a36582263e9845f3d2b7d132e6297eebf9d798a3`
Staging only: `hrms-v16.localhost`
Production touched: **NO**

## Decision

HRMS v16 has one site-wide `Payroll Settings.payroll_based_on`; it has no
per-employee or per-structure override. The site remains `Leave`. Switching the
whole site to `Attendance` would change monthly salaried semantics, so it was
rejected.

The financial authority is now:

```text
submitted Salary Structure Assignment (effective date + base)
        ↓
assigned Salary Structure.custom_tradex_pay_basis
        ↓
Monthly Salary | Daily Wage | explicit blocker
```

`Employee.employment_type`, branch, department, designation and naming are not
financial pay-basis authorities. `Tradexcel Payroll Policy.daily_wage` remains
available for policy comparison/legacy review, but the new production input
path never uses it to calculate money. SSA `base` is the only daily-rate source.

## Implemented

- `custom_tradex_pay_basis` on native Salary Structure, populated only from the
  declarative YAML values (`TCL Standard`, `TCL Daily Wage`, `EFL Standard`).
- `resolve_pay_basis()` with explicit `UNRESOLVED`, `CONFLICT`, and
  `MID_PERIOD_CHANGE` outcomes. Same-effective-date assignment corruption and
  mixed-period changes fail closed.
- Attendance finalization uses native Payroll Entry coverage for global
  Attendance payroll plus employees whose explicit pay basis is Daily Wage.
  Monthly Leave-based staff are not forced into factory Attendance coverage.
- `daily_wage_input.py` reads submitted native Attendance, uses the effective
  SSA `base`, and emits/reuses one native Additional Salary per finalized
  Attendance Period revision. It does not read Employee Checkin and refuses the
  old `base * payment_days` structure.
- Daily Wage and Overtime Pay are declared non-prorated component inputs. The
  existing linked staging structure is not rewritten automatically; Frappe
  correctly prevents canceling a submitted structure with submitted assignments.
  A native effective-dated structure/assignment migration is required before
  real Daily Wage inputs are enabled.
- Pay-basis metadata now fails closed if a populated value would change on a
  structure with submitted assignments. Blank metadata may be seeded once;
  later changes require a new native structure and effective-dated assignment.
- Reopening a finalized period disables unconsumed derived Daily Wage inputs.
  If a draft or submitted Salary Slip already references one, ordinary reopen
  is blocked and payroll correction is required instead.
- Existing Daily Wage input reuse verifies employee, company, component, amount,
  payroll date, Attendance Period reference, docstatus and disabled state. A
  unique-key insert race re-reads the winning row and returns `EXISTING`.
- Daily Wage unit calculation delegates to native `SalarySlip` attendance
  methods for holidays, LWP/PPL, half-day fraction and marked-holiday policy;
  it does not maintain a parallel status calculator.

## Native evidence

Installed HRMS v16 behavior inspected:

- Salary Slip selects the latest submitted Salary Structure Assignment with
  `from_date <= actual_start_date`.
- Payroll Entry narrows the employee period by date of joining and relieving
  date.
- `Additional Salary` is a native submitted payroll input; native Overtime Slip
  uses it and preserves `ref_doctype`/`ref_docname` provenance.
- Salary Slip formula evaluation plus `depends_on_payment_days` made the old
  staging structure produce approximately Tk417.31 for one forced payment day
  and Tk4,173.08 for ten, instead of Tk350/Tk3,500. This is why the old shape is
  blocked rather than patched with another formula.

The disposable native integration test creates a safe structure, submitted SSA,
submitted Attendance, a native Additional Salary, a draft Payroll Entry and
draft Salary Slip. Native Salary Slip creation commits internally, so the test
records each generated name and explicitly cancels/deletes only those synthetic
records in cleanup:

```text
10 submitted Attendance days × SSA.base Tk350 = Tk3,500
second generation attempt = existing input, no duplicate
native Salary Slip Daily Wage earning = Tk3,500
```

The test also proves native joiner payroll dates are narrowed by Payroll Entry.
No synthetic payroll or Attendance records from the experiment remain after
cleanup.

## Staging operation

Fresh full backup before schema migration:

```text
2026-09-23 02:20:14 Asia/Dhaka
20260923_022014-hrms-v16_localhost-database.sql.gz
SHA-256: a9270da06feda7404c0f80fbb143b7fe90c2de7bd771bcc4fc52f0682f24f72e
```

`gzip -t` passed. Migration of only `hrms-v16.localhost` succeeded after the
metadata-only hook was corrected to use `db.set_value`; it does not cancel linked
Salary Structures or touch payroll documents.

Post-migration metadata is present on all three declared structures. Current
TCL staging still has the old linked `TCL Daily Wage` child formula and is
therefore intentionally blocked. Current September Attendance inspection finds
238 employees in scope, with 159 `ATTENDANCE_UNMARKED` Daily Wage blockers. The
assignment population is 159 Daily Wage and 64 Monthly Salary employees; 15
employees have no currently applicable submitted assignment and therefore
remain an explicit pay-basis blocker. Monthly staff are not forced into
Attendance completeness while the site remains Leave-based. No global Payroll
Settings change was made.

## Alternatives not chosen

- Global `Payroll Settings = Attendance`: rejected because it is site-wide and
  would silently change monthly Leave-based staff.
- Salary Slip controller monkey-patch: rejected; it duplicates/fights native
  HRMS calculation and has no clean per-employee hook.
- Custom wage ledger/second payroll engine: rejected; native Additional Salary
  already provides the audited payroll-input boundary.

## Release gates

1. Create/converge a safe Daily Wage structure through native effective-dated
   Salary Structure Assignment changes; do not rewrite the submitted linked
   legacy structure.
2. Resolve the current 159 missing Attendance records for the intended payroll
   period before finalization.
3. Review the native Additional Salary input generation with Payroll Entry on
   synthetic/staging data before any real submission.

## Verification

- Focused Phase A tests: **22 passed, 2 warnings**.
- Full app suite before Phase B: **208 passed, 2 skipped, 2 warnings**.
- Staging has no configured LWP/PPL Leave Types; those cases are delegated to
  native HRMS semantics and remain a configuration/test-data gate.
- Compilation: **passed** with `/home/sanchita/frappe-bench-v16/env/bin/python -m compileall -q tradex_hr`.
- `git diff --check`: **passed**.
- Temporary native records: explicitly cleaned by exact generated names; no
  real Salary Slip or Payroll Entry was submitted.

## Phase B — native Payroll Entry draft orchestration

Branch: `feat/native-payroll-draft-orchestration`
Base: `feat/mixed-pay-basis-wage-input` at `8434d0230a9aa8bc2e9e49c4cdfc2477594af467`

The new `native_payroll.py` service is a narrow orchestrator. It requires the
exact finalized/current Attendance Period for Attendance-dependent populations,
resolves the explicit Salary Structure pay basis, creates/reuses the native
Daily Wage Additional Salary input, inserts one native Payroll Entry, and calls
HRMS `PayrollEntry.create_salary_slips()` for draft Salary Slips. It does not
calculate Salary Slip amounts, submit payroll, post accounting, or read raw
Employee Checkin. A second call returns the existing exact-period native
Payroll Entry instead of creating another batch.

The native input writer does not bypass Additional Salary permissions. Payroll
account configuration is checked before any Daily Wage input is written, and
Payroll Entry creation checks native create permission before insertion.

The native staging integration proved:

```text
10 submitted Present Attendance days
× SSA.base Tk350
= native Additional Salary Tk3,500
= native draft Salary Slip Daily Wage earning Tk3,500
retry = EXISTING; no duplicate batch/input
```

Global Payroll Settings remains unchanged (`payroll_based_on = Leave`), so
monthly Leave-based staff are not forced through site-wide Attendance payroll.
The native Payroll Entry `validate_attendance` flag follows that global setting;
Daily Wage completeness is separately gated by the finalized Attendance Period.

Current read-only staging inspection for September 2026:

```text
238 employees in scope
159 ATTENDANCE_UNMARKED blockers (all are the 159 explicit Daily Wage population)
0 monthly employees forced into Attendance completeness by the global setting
```

Phase B verification:

- Focused rerun on 2026-09-23: `FRAPPE_TEST_SITE=hrms-v16.localhost FRAPPE_TEST_SITES_PATH=/home/sanchita/frappe-bench-v16/sites env/bin/pytest apps/tradex_hr/tradex_hr/tests/test_native_payroll.py` from the bench root: **4 passed, 1 warning** (Frappe `txt` deprecation warning).
- Focused Phase A + Phase B tests: **28 passed, 3 warnings**.
- Full app suite: **214 passed, 2 skipped, 3 warnings**.
- Compilation: **passed** with `/home/sanchita/frappe-bench-v16/env/bin/python -m compileall -q tradex_hr`.
- `git diff --check`: **passed**.
- Staging test records: explicitly cleaned; no synthetic records remain.
- Production touched: **NO**.
- Submitted real Payroll Entry: **NO**.
- Submitted real Salary Slip: **NO**.

Remaining gates are operational/configuration work: resolve the 159 missing
Daily Wage Attendance records, replace the unsafe submitted legacy `TCL Daily
Wage` structure through a new effective-dated native structure/assignment, and
later complete tax/accounting/payment controls. LWP/PPL parity remains
delegated to native HRMS and needs real configured Leave Types before it can be
data-exercised on staging.


## Phase A hardening — staging change record

Target: hrms-v16.localhost only. Production remains untouched.

Verified pre-migration backup with files:
 /home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/20260923_052342-hrms-v16_localhost-*

- Database gzip test and both file tar listings passed.
- Database SHA-256: c14b67ae1d0a0b8a5b2db488d6e6a1b80911f95376ae66b064d9acccf4f25dc9
- Public files SHA-256: 407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532
- Private files SHA-256: 7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe
- Site config SHA-256: 904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73

Read-only staging preflight found the current Tradexcel Payroll Approval Workflow active with draft review states; no custom_tradex_run_key exists. Payroll Entry and Salary Slip counts are both zero. An attempted grouped aggregate through the Frappe query API was rejected as unsupported; it made no writes and was not used as evidence.

Hardening changes in progress: native submit/cancel Workflow states, review eligibility gated on native slip-job completion, managed monthly company identity, Payroll Entry and Salary Slip server guards, permission ordering, Daily Wage preflight/atomic materialization. No real payroll or Salary Slip is being submitted.

- First staging migration stopped safely in the app after-migrate Workflow setup because the action pre-pass still expected four-field transition tuples. Read-only checks show the managed fields were not yet installed and Payroll Entry/Salary Slip remain at zero. The valid Tradexcel HR Workspace still exists; the sync only removed a lowercase orphan slug. Corrected the tuple iteration before retrying migration.

- The second staging migration correctly rejected blank Workflow State allow_edit values as mandatory. Assigning the reviewer, director, and approver roles for those states; no records were created.

- The later migration attempt synchronized app metadata but stopped during Frappe's orphan Workspace deletion: the staging default queue already held over 550 delete_dynamic_links jobs and no workers were online. No payroll records were touched. Completed app-owned role/workflow/field convergence directly on staging after the pre-migration backup. The interrupted sync left the HR Workspace under its old title-based name; renamed it with Frappe to the app's canonical tradexcel-hr name and reran ensure_workspace().
- That convergence exposed a v16-required Workspace.type field missing from the existing installer; set it to Workspace before saving. The canonical workspace and report/workspace test set now pass.
- Focused Phase A suite: 17 passed. Full app suite: 225 passed, 2 skipped. Compile and final diff checks are run after review.
- Staging payroll population was unchanged. The synthetic lifecycle test cleaned its Payroll Entry, draft Salary Slip, derived Additional Salary, Attendance, Attendance Period, Salary Structure/Assignment, and three role-specific users with Company User Permissions. No real Salary Slip or accounting entry was submitted/created.


## Phase A lifecycle hardening and Phase B operator flow — 2026-09-23

### Phase A — PR #6 hardening

- Branch: `feat/native-payroll-draft-orchestration`
- Base: PR #5 `8434d0230a9aa8bc2e9e49c4cdfc2477594af467`
- Prior head: `f2a71e8`; hardened head: `a2edf9fb071da24e82e4829e188039202f042b1d`
- Lifecycle: preparation creates only a managed native Draft Payroll Entry. Its single native submit creates Salary Slips. Review and director approval remain submitted states; rejection uses native cancellation.
- Salary Slip `before_submit` blocks linked managed slips until the Payroll Entry is approved. Payroll Entry `before_submit` blocks an unmanaged or unprepared direct submission.
- Daily Wage inputs are authorized before writes, all known blockers are preflighted, and unexpected failures roll back to one savepoint. Payroll Manager does not gain arbitrary Additional Salary submit permission.
- Native queue state gates review and approval. Tests capture the native queue path, worker failure, and retry without adding a custom queue.
- Managed run identity binds company/month and verifies population and Attendance revision before reuse. Unsupported scopes and unmanaged or mismatched same-period entries block.
- The old manual `run_payroll_for_month` CLI path was found during the full repository audit. It previously created Salary Slips outside the native workflow. The runner now stops with a clear Payroll Readiness/native-workflow message; the manual slip builder and raw-checkin payroll helpers were removed. There is no remaining whitelisted or UI caller for the retired path.

### Phase B — Payroll Readiness operator flow

- Branch: `feat/payroll-readiness-operator-flow`, based on hardened PR #6 head `a2edf9f`. Final head: `e513a9ee86a278d912bb6ea0694c2adc6a4e37a1`.
- Stacked PR: [#7](https://github.com/shamrat05/tradexcel-hr-v16/pull/7), base `feat/native-payroll-draft-orchestration`; open and unmerged.
- Surface: standard app-owned Script Report `Tradexcel Payroll Readiness`, with Company and Payroll Month filters, one row per in-scope employee, human-readable blockers, and links to canonical Attendance, Attendance Request, and Salary Structure Assignment records.
- Readiness actions recalculate on the server and enforce named-user, role, company, employee, and native permission scope. The report client never supplies a trusted READY flag.
- The migration preview is read-only. It shows current SSA/structure/rate, Attendance and assignment conflicts, and a proposed zero/non-prorated Daily Wage and Overtime shape. No effective date is chosen automatically; absent an approved date it returns `DECISION_REQUIRED`.
- Workspace `Run Monthly Payroll` now opens the report. Native Payroll Entry remains accessible as `Payroll Entries (Advanced)`.
- Staging report evidence for TCL September 2026: 238 unique employees, 63 ready, 175 needing attention; findings include 159 unmarked Daily Wage Attendance records, 159 unsafe legacy Daily Wage structures, and 16 employees without applicable submitted SSAs. Findings may overlap. No employee data was auto-fixed.
- Report execution was approximately 1.4–1.9 seconds in the direct staging checks; query count was not measured.

### Staging backup and synchronization

Staging only: `hrms-v16.localhost`. Before report/workspace metadata synchronization, created and verified backup prefix:
`/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/20260923_063317-hrms-v16_localhost-*`

- Config SHA-256: `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`
- Database SHA-256: `82889d13ad3a93da895370ff5d21d0380cd1a0065a1892d613ecb2380bf9072d`
- Public files SHA-256: `407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532`
- Private files SHA-256: `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`

The complete `bench migrate` remains blocked in Frappe orphan Workspace cleanup because the staging default queue has over 550 pending deletion jobs and no workers online. No jobs were drained or removed. App-owned report and Workspace metadata were converged with targeted `ensure_standard_script_reports`, `ensure_workspace`, and cache clear commands; the installed report, script, and shortcuts were then checked directly. No Phase B schema change was needed.

Synthetic tests explicitly clean their named records. Staging remained at zero Payroll Entry, zero Salary Slip, and zero derived Daily Wage input after Phase A integration cleanup. Production was not touched; no real Salary Slip or accounting entry was submitted or created.

### Verification

- Phase A suite before operator work: 225 passed, 2 skipped.
- Phase B full suite before legacy-runner shutdown: 234 passed, 2 skipped.
- Legacy runner shutdown tests: 12 passed.
- Final full app suite: 233 passed, 2 skipped, 8 warnings (all existing Frappe v17 deprecation warnings).
- Final compilation, report JavaScript `node --check`, and `git diff --check`: passed.
- Index refreshed with codebase-memory MCP; it still discovers only project/folder nodes for this app, so implementation review used the repository diff and focused source reads.
- PR #6 remains open and unmerged; PR #7 is open and stacked on PR #6. Neither PR was merged.

Remaining operator gates: resolve Attendance, create a safe effective-dated Daily Wage structure only after business approval of its effective date, and test the native queued behavior in a clean synthetic environment. Tax, accounting, Salary Slip submission, and payment remain out of scope.
