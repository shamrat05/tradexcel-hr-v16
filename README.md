# Workforce Suite — start here

## Current v16 engineering status — 2026-09-27

The active repository is `/home/sanchita/frappe-bench-v16/apps/workforce_suite`,
stacked on open draft PRs. The isolated staging site is `hrms-v16.localhost`
with MariaDB on `127.0.0.1:3307`. The latest accepted full suite passed **653 tests, 0 skipped**. The integrated mobile/lineage correction is documented in
[`release security closure`](tasks/release_lineage_security_closure_2026-09-27.md). Native bulk
workflows, scoped Action Board/native navigation, privacy controls and measured
report improvements are implemented. Neutral install and isolated restore passed;
real configuration, device and staff UAT remain gated. The current
engineering campaign and resume point are in
[`tasks/sol_completion_state_2026-09-26.md`](tasks/sol_completion_state_2026-09-26.md).

Native Employee, Attendance Request/Attendance, Leave, Shift, Salary Structure
Assignment, Payroll Entry/Salary Slip, and accounting records remain the
authorities. Pay basis comes from the effective submitted assignment's Salary
Structure field `custom_workforce_pay_basis`; no Employment Type or Branch
heuristic may decide pay. The app's payroll and biometric worker source is
versioned here; the SenseFace listener is a separate repository.

Current evidence: [roadmap](tasks/roadmap_current_2026-09-27.md),
[release contract](tasks/release_readiness_contract_2026-09-27.md),
[business configuration gate](tasks/business_configuration_gate_2026-09-26.md).

**Production is not approved.** The release audit also preserves a pre-existing
ERPNext banking lockfile delta for separate dependency review; whole-bench source
pinning is not yet complete. PF/Progoti activation stays blocked by the installed
native accounting capability. Real staff roles, pay-authority gaps,
company/legal/finance configuration, physical device and browser UAT,
parallel payroll, and cutover evidence remain gates. The table and counts
below are the preserved **2026-09-18 historical snapshot**. They are not
current staging counts or current architecture. See newer dated task notes
and live read-only audits before using any number below.

---

**Frappe custom app for Example Company A and Example Company B**
Replaced a previous custom system (Selevo). This README is the entry point: it
says where things are and **exactly what is done and what is not.**

Last updated: **2026-09-18**. State figures below were read from the live site on
that date — re-read them before trusting them (see *Checking current state*).

---

## Read these first

| Document | Why |
| --- | --- |
| **`README.md`** (this file) | Status, checklist, where everything is |
| **`BACKUPS.md`** | Every backup with timestamps, sizes and checksums. **Read before deleting anything** |
| **`AGENTS.md`** | Rules for agents working in this repo, incl. the canonical checkout |
| `tasks/` | The detailed record of every change, with evidence |
| `docs/` | Operating model, launch readiness, bridge contract |

---

## The one-screen status

### ✅ Done and verified

| Area | Evidence |
| --- | --- |
| **Biometric mapping** | **221** employee↔PIN assignments across 2 devices. Verified through the worker's real code: 221 resolved, 0 ambiguous, 0 mis-attributed |
| **Salary components** | 7 global components, created once and reused |
| **Salary structures** | 3 templates: `Example Monthly`, `Example Secondary Monthly`, `Example Daily Wage` |
| **Salary assignments** | **226** assignments, 226 distinct employees, 0 duplicates |
| **Payroll split** | Verified against the VPS: 60/30/5/5. `structure_earnings()` produces exact figures |
| **Attendance pipeline** | 16,077 Attendance, 22,293 Checkins. Auto-attendance enabled on both shift types |
| **Pay property setters** | Now reproducible via `ensure_property_setters()` — proven by delete-and-recreate |
| **Test suite** | **126 passing**, 2 skipped |
| **Runtime packaged** | payroll + biometric runtime now in the repo, not only on disk |

### ❌ Not done — these block production

| # | Blocker | What is missing |
| --- | --- | --- |
| **1** | **Nobody can log in** | 0 enabled non-admin users. Only `Administrator` exists |
| **2** | **No roles assigned** | 0 role grants. Permissions are unproven — Administrator bypasses everything |
| **3** | **Payroll has never run** | 0 salary slips, 0 submitted. The money path is untested end-to-end |
| **4** | **No tax configured** | 0 Income Tax Slabs; no deductions on any structure |
| **5** | **Restore never rehearsed** | Backup verified readable, never restored. No DB superuser on this machine |
| **6** | **Leave not in force** | 3 Leave Policies still draft; 0 Leave Periods |

### ⚠️ Open decisions — only the owner can answer

| # | Question | Why it matters |
| --- | --- | --- |
| **7** | **The 46 "Workers" on monthly salaries** | `employment_type = Worker` but they hold monthly structures (Foreman 30,000; Shift Incharge 23,000). Payroll would resolve them to the **350/day** policy. Monthly or daily? |
| **8** | **Tax / PF / gratuity policy** | Nothing configured. Net pay is knowingly incomplete until decided |
| **9** | **Two employees with no split** | COMPANY_A-0026 Tania Akter (15,000), COMPANY_A-0038 Rifat Hossain (25,000) — gross known, components unknown |
| **10** | **Link structures to policies** | All 5 policies have `salary_structure = NULL`, so nothing derives the structure |

---

## Checking current state

For starting and stopping the local v16 site, see
[`tasks/local_v16_start_stop_guide.md`](tasks/local_v16_start_stop_guide.md).

```bash
# health and counts
cd ~/frappe-bench && bench --site hrms.localhost mariadb -e "
select (select count(*) from tabEmployee) employees,
       (select count(*) from \`tabSalary Structure Assignment\`) assignments,
       (select count(*) from \`tabSalary Slip\`) slips,
       (select count(*) from \`tabWorkforce Employee Biometric\`) biometric;"

# the test suite
cd ~/frappe-bench && env/bin/python -m pytest apps/workforce_suite/workforce_suite/tests/ -q
```

Read `BACKUPS.md` before any destructive operation.

---

## Where things live

| What | Where |
| --- | --- |
| **Canonical checkout** | `/home/sanchita/frappe-bench/apps/workforce_suite` (WSL) — the only tree to edit |
| Windows mirror (read-only) | `Desktop/workforce-suite-audit-app` |
| Repositories | `github.com/shamrat05/workforce-suite`, `github.com/shamrat05/SenseFace-HRMS-Bridge` |
| Backups | `Desktop/workforce_suite_backup_20260918/`, indexed in `BACKUPS.md` |
| VPS source data | `Desktop/selevo_vps_backup_20260917/selevo_postgres_all.sql.gz` |
| Bridge | `Desktop/Projects/SenseFace-HRMS-Bridge` (canonical, on `main`) |

### Code map

| Module | What it does |
| --- | --- |
| `workforce_suite/salary_setup.yaml` | **Salary config source of truth** — components, structures, formulas |
| `workforce_suite/salary_setup.py` | Idempotent installer; converges, never duplicates |
| `workforce_suite/salary_excel.py` | Xcel export + assignment importer |
| `workforce_suite/run_payroll.py` | Creates draft salary slips from policy + assignment |
| `workforce_suite/payroll_rules.py` | Wage maths (fallback constants only — structure wins) |
| `workforce_suite/payroll_policy.py` | Resolves the policy for an employee |
| `workforce_suite/effective_policy_rules.py` | Deterministic override precedence |
| `workforce_suite/deduction_rules.py` | Deductions + totals (honours `do_not_include_in_total`) |
| `workforce_suite/biometric/worker.py` | Bridge punch → Employee Checkin |
| `workforce_suite/biometric/state_store.py` | Sync cursors and event log |
| `install.py` | `after_migrate`: roles, workflows, reports, charts, workspace, property setters |
| `api.py` | Whitelisted device RPCs |

---

## The design, in one picture

```
Salary Component      global master — created once, reused everywhere
        ↓
Salary Structure      template (3 of them) — holds the split, no personal amounts
        ↓
Payroll Policy        rules by scope: pay_basis, daily_wage, overtime
        ↓
Policy Exception      dated override for people/groups, preview-verified
        ↓
Assignment            base = the individual figure
```

**Why it matters:** the VPS held **28 structures named after individuals**
(`abdullah`, `alim`, `miraz`). Those existed because Selevo had nowhere else to
store a personal amount. In Frappe that value lives on the assignment's `base`,
so **one structure serves everyone on that basis**. Anything individual is an
exception or an Additional Salary — dated, reasoned, and visible.

---

## Known gaps and hazards

| Gap | Detail |
| --- | --- |
| Runtime history | The payroll and biometric runtimes were unversioned until 2026-09-18. `sync/` is **not a git repo**; it now holds thin shims delegating to the app |
| Bridge launcher | `start_biometric_bridge.bat` runs `Desktop\Projects\SenseFace-HRMS-Bridge`, which is now the canonical hardened copy on `main` |
| Deadlines leave no trace | `innodb_print_all_deadlocks = 0` — needs root to change |
| No DB superuser | Blocks site provisioning and any restore rehearsal |
| 6 unversioned tests | They test one-off **migrators** that will be deleted, so versioning them was pointless. They retire with the migrators |

---

## Change log of this workstream

Each has a full record in `tasks/`:

| Date | What |
| --- | --- |
| 2026-09-18 | Checkout consolidation — one canonical tree, LF pinning, CRLF phantom-diff removed |
| 2026-09-18 | Demo data removed (31 documents, 74 ledger rows); `Clear Demo Data` retired |
| 2026-09-18 | Desk layout fixed and **measured** with Playwright, not guessed |
| 2026-09-18 | Desk theme toggle added |
| 2026-09-18 | Bridge ingress hardened; two bridge lineages reconciled onto `main` |
| 2026-09-18 | Payroll runtime + 18 tests packaged |
| 2026-09-18 | All pre-production salary data purged (owner-confirmed) |
| 2026-09-18 | Section A biometric checklist — 221 mappings imported and verified |
| 2026-09-18 | Salary structures rebuilt from the VPS; 226 assignments created |

---

## Rules that must not be broken

1. **One source of truth for money.** The Salary Structure defines the split; the
   assignment defines the amount. Do **not** reintroduce a second home for either.
2. **Never hardcode a wage.** No percentages or rates in code. The VPS-based
   60/30/5/5 lives in `salary_setup.yaml` and the structures.
3. **A wrong assignment must never save.** Frappe validates company match on the
   server; keep that as the safety net and add filters as the guard rail.
4. **Dry runs must not commit.** All constructive testing uses `commit=False`.
   A development test once wrote 214 assignments to the live site believing a
   later rollback would undo it. It did not.
5. **Test the app, not the fixture.** A test that fails because data is absent
   should skip with a reason, never fail.
6. **Verify, then edit.** Several "defects" in the original audit proved false
   (double proration, PIN casing) and one real bug was found only by running the
   code (the worker's `employee["name"]`). Measure before changing.
