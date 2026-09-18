# Packaging the payroll runtime and the unversioned tests — 2026-09-18

`~/frappe-bench/sync/` is **not a git repository**. Everything in it exists on one
machine only. This records what was moved into the app and what was deliberately
left behind.

## Payroll runtime — packaged

| Canonical (versioned) | Lines | Was |
| --- | --- | --- |
| `tradex_hr/tradexcel_hr/run_payroll.py` | 395 | `sync/run_payroll.py` |
| `tradex_hr/tradexcel_hr/payroll_rules.py` | 268 | `sync/payroll_rules.py` |

`run_payroll.py` imported a **local** module `payroll_rules.py` — the Bangladesh
Labour Law rules — which was itself unversioned. Both had to move together.

Only one line changed: the flat import of `payroll_rules` became app-absolute,
matching the module's own existing late imports of `deduction_rules`,
`component_exceptions` and `payroll_policy`.

`sync/run_payroll.py` and `sync/payroll_rules.py` are now **shims**.
`run_payroll.bat` invokes the shim path directly and keeps working; it is executed
through `runpy` so argparse behaves identically.

Verified: the `.bat` path returns the correct CLI (`--help` only — a real run
would compute payroll), flat imports resolve to the app, and 13 payroll tests
pass.

## Tests — 18 of 23 versioned

| | Count |
| --- | --- |
| Files named `test_*.py` in `sync/` | 31 |
| **Real pytest tests** (have `test_` functions) | **23** |
| Investigation scripts misnamed `test_*.py` | 8 |
| Versioned in the app now | **18** |
| Remaining | 5 — they test one-off migration helpers that are not part of the app |

The app suite is **120 tests passing**, up from 13.

Two tests were de-hardcoded: `test_report_templates.py` and
`test_tradexcel_identifiers.py` used absolute `/home/sanchita/...` paths, now
derived from `__file__`.

### A bug the packaging exposed

`test_tradexcel_identifiers.py` scans every app file for forbidden `Tradex...`
identifiers — **including itself**, since its fixture list contains them. It
therefore always failed the moment it moved inside the tree. It had only "passed"
because it lived in `sync/`, outside the scanned path. It now skips its own file
and is **negatively tested**: injecting a forbidden identifier into a real module
makes it fail.

### Correction to an earlier count

An earlier note said "31 test files, all unversioned". More accurately: **23 are
real tests and 8 are investigation scripts that print and assert nothing**. One of
them (`test_desk_route.py`) still references `tradex-hr-management`, a workspace
name that no longer exists, which is how stale they are. They are named `test_*`,
so running pytest inside `sync/` will try to import them and execute their
`frappe.init()` side effects. Renaming them is advisable but was not done, since
they are files on disk outside version control.

## What is still unversioned in `sync/`

- the 5 migration-helper tests (`test_audit_biometric_ids`, `test_branch_mapping`,
  `test_reconciliation`, `test_rebuild_tradex`, `test_extract_verified`,
  `test_reset_and_demo`) — they test one-off importers that are not part of the app
- the 8 misnamed investigation scripts
- the one-off migration/audit scripts themselves (`apply_selevo_logic.py`,
  `verified_importer.py`, `reconcile_payroll.py`, `finalize_tradex_hrms.py`, …)
- the 3 quarantined dangerous scripts (`cleanup_false_import_employees.py`,
  `source_staff_salary.py`, `purge_cancelled_salary_slips.py`), which sit inside
  the app's importable package and remain the highest-risk item on the register
  (see G1)

## Verified after packaging

| Check | Result |
| --- | --- |
| `run_payroll.py` + `payroll_rules.py` tracked in the app | yes |
| `.bat` invocation path (`--help`) | OK |
| flat imports resolve to the app | yes |
| app test suite | **120 passed** |
| versioned test files | 18 |
