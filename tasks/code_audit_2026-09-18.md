# Code audit — findings and fixes, 2026-09-18

Read every module in the app and reported honestly. This records what was found,
what was fixed, what is still open, and — importantly — **what the audit got
wrong earlier** so nobody re-fixes a non-problem.

Biometric devices were excluded from the audit by request (no terminal connected).

## Fixed in this pass

### 1 + 12 — Two sources of truth for the same salary figure

`run_payroll.py` took the monthly staff amount from
`~/frappe-bench/sync/data/selevo_employee_compensation.json` — a file **outside
the repository**, existing only on this machine. The assignment we maintain held
the same number.

They happened to agree (67/67 compared on `workforce_source_employee_id`, 0
disagreements), so no wage was ever wrong. But two homes for one number is a
defect regardless: on a clean checkout payroll would have reported "staff source
salary is missing" for everyone.

**Fixed.** The assignment is the source of truth. The file survives only as an
explicit fallback seed when an assignment has no base, and logs when it is used.
`_source_earnings()` — which parsed the split out of the file — was deleted.

### 7 — Three different component splits in the codebase

| Source | Split | Verdict |
| --- | --- | --- |
| Selevo VPS, `workforce` org (67 employees' latest rows) | **Basic 59.92 / HRA 29.96 / Medical 4.99 / Conveyance 4.99 / ENT 0.13** | **the truth** |
| `Example Monthly` structure | 60/30/5/5 | ✅ correct |
| `payroll_rules.DEFAULT_COMPONENTS` | 50/25/10/10/5 **+ Food Allowance** | ❌ **fabricated** |
| `run_payroll._source_earnings` abbrs | `BASIC` / `CONV` | ❌ inconsistent with the components (`BS` / `CON`) |

**66 of 67 employees used exactly the 5-component set.** The VPS contains other
splits (`Basic`, `Travel`, `PF`, `Adv`) but those are **historical revisions from
earlier periods**, not current — the latest-row analysis is unambiguous.

**Fixed two ways:**

1. `DEFAULT_COMPONENTS` corrected to 60/30/5/5 and abbrs to `BS/HRA/MED/CON`,
   with a comment that this is a **fallback only**, verified against the VPS.
2. Added `structure_earnings()` — payroll now splits gross **from the structure**.
   There is no hardcoded split in the money path any more. A structure whose
   earnings do not total the base is **refused** rather than silently mis-paid,
   and any formula that is not `base * <factor>` (other than the attendance-based
   daily-wage case) raises instead of being guessed.

Verified: `Example Monthly` 130,000 → BS 78,000 / HRA 39,000 / MED 6,500 / CON 6,500,
total exactly 130,000.

### 8 — The payroll error handler discarded the whole batch

`except: frappe.db.rollback()` inside the per-employee loop rolled back **every
slip created earlier in that loop**, so one bad employee looked like a wholesale
failure. Now uses a **savepoint**, so a failing row undoes only itself. Same bug
class as the one fixed in the salary importer earlier the same day.

### 11 — Five Property Setters existed only in the database

Five rows on `Salary Structure Assignment` (list sorting and standard filters)
were created by hand on 2026-09-17. Nothing in the app recreated them, and there
were no fixtures — so a fresh install or Contabo deploy would **silently lose**
them.

**Fixed** with `install.py::ensure_property_setters()`, following the app's
existing `ensure_*` pattern. **Proven**: all five deleted, function re-run,
`created: 5` recreated.

### 13 — Dead code

- `WORKER_STRUCTURE = "Example Factory Daily Wage Worker Structure"` — a structure
  name that no longer exists. Defined and never referenced. Removed.
- `configured_components()` and the `calculate_wage` import — became unused once
  the structure took over the split. Removed.

### 14 — `app_email` and `app_description`

`app_email` was `admin@workforce.com` — the **retired Selevo's** address, and it
once accidentally became a device `device_code`. Now `support@example.com`.

`app_description` described the app as an *"integration for SelevoHR"*. Selevo is
retired and this app **is** the HR system, so it now says what it is.

### 16 — Print-only files masquerading as tests

Of 31 files named `test_*.py` in `sync/`, **8 contained no test function at all** —
they called `frappe.init()`, printed, and asserted **nothing**, while pytest
collected and executed them. One referenced `workforce-hr-management`, a workspace
name that no longer exists.

**Fixed:** all 8 moved to `sync/quarantine/investigation_scripts/`. Their useful
intent was rewritten as real assertions in
`tests/test_reports_and_workspace.py`, including a **dead-shortcut check** the
old scripts never made — the workspace can no longer point at a deleted report
without a test failing.

The 6 remaining unversioned tests deliberately stay unversioned: they test
**one-off migrators** that will be deleted, so versioning them would be waste.

## Verified false — do not "fix" these

| Earlier claim | Reality |
| --- | --- |
| **Double proration** in worker pay structures | **False.** HRMS computes `default_amount` from a copy whose `payment_days` is reset to `total_working_days`, then prorates once. Confirmed in 200 real slips: every Daily Wage is exactly `350 × payment_days` |
| **PIN casing** hazard (Unl/unl, Cf/CF) | **Not proven.** The variants are group prefixes, not duplicate PINs. All 221 PINs are distinct even lowercased |
| **Device registration not enforced** | **False positive from a grep matching imports.** The `/iclock/cdata` handler did trust the asserted serial — that part was real and has since been fixed |
| **`is_basic` / `is_gratuity_base`** | **No Frappe field exists.** Only in the Selevo model. The installer now **raises** if the spec names a non-existent field rather than inventing one |

## Still open — needs the owner

| # | Question |
| --- | --- |
| 9 | **46 employees have `employment_type = Worker` but hold monthly structures** (Foreman 30,000; Shift Incharge 23,000). Payroll would resolve them to the 350/day policy. Monthly or daily? |
| 5 | **Tax / PF / gratuity** — 0 Income Tax Slabs, no deductions configured |
| 10 | **All 5 payroll policies have `salary_structure = NULL`** — the link exists and is empty, so nothing derives the structure |
| — | **2 employees have no component split** (COMPANY_A-0026, COMPANY_A-0038) — gross known, split unknown |

## Still open — operational

| # | Issue |
| --- | --- |
| 4 | 0 enabled non-admin users and 0 role grants. Nobody can operate; no permission is proven |
| 2 | Payroll has never been submitted. 0 slips, 0 GL, 0 payments |
| 6 | Restore never rehearsed — no database superuser is reachable on this machine |

## Test suite

**126 passing, 2 skipped** (was 123). The two skips are honest — they cover report
paths that need salary data, and announce that the site has none.
