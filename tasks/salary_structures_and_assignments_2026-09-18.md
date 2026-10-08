# Salary structures and assignments — 2026-09-18

Rebuilt the salary side from the Selevo VPS backup using a shared-component
design, and assigned every employee.

## Why not the VPS shape

The VPS held **28 salary structures named after individual people**
(`abdullah`, `alim`, `miraz`, `kaiyum`...). They existed only because Selevo had
nowhere else to store a personal amount.

In Frappe the personal figure lives on the **Salary Structure Assignment's
`base`**, so one structure serves everyone on the same pay basis. Result: **3
structures instead of 28**, and one place to change a split.

## What was created

### Components (7, global — reused by every structure)

| Component | Abbr | Tax | Note |
| --- | --- | --- | --- |
| Basic Salary | BS | applicable | 60% of gross |
| House Rent Allowance | HRA | exempt | 30% |
| Medical Allowance | MED | exempt | 5% |
| Conveyance Allowance | CON | exempt | 5% |
| Entertainment Allowance | ENT | — | present, zero by default |
| Daily Wage | DW | — | `base × payment_days`, gross daily rate |
| Overtime Pay | OT | — | per Payroll Policy |

A Salary Component is a **global master**; a structure references it. That is why
adding `Example Secondary Monthly` required no new components — only a second wrapper.

### Structures (3)

| Structure | Company | Pay basis | Earnings |
| --- | --- | --- | --- |
| `Example Monthly` | Example Company A | Monthly | BS 60% · HRA 30% · MED 5% · CON 5% · ENT 0 |
| `Example Secondary Monthly` | Example Company B | Monthly | identical split, same components |
| `Example Daily Wage` | Example Company A | Daily | DW `base × payment_days` · OT |

**Why a separate COMPANY_B structure when the arithmetic is identical:** Frappe
validates that a structure's company matches the employee's. A shared structure
is rejected for the two Example Company B staff. The components remain shared;
only the wrapper differs. This costs nothing and avoids falsifying their company.

### Assignments (226)

| Structure | Company | Count | Base range |
| --- | --- | --- | --- |
| `Example Daily Wage` | Example Company A | **159** | 350 (flat gross daily rate) |
| `Example Monthly` | Example Company A | **65** | 10,000 – 90,000 |
| `Example Secondary Monthly` | Example Company B | **2** | 40,000 – 130,000 |

Verified: **226 assignments, 226 distinct employees, 0 duplicates.**

## Artefacts

| File | Purpose |
| --- | --- |
| `workforce_suite/salary_setup.yaml` | single source of truth — components, structures, formulas |
| `workforce_suite/salary_setup.py` | idempotent installer; converges, never duplicates |
| `workforce_suite/salary_excel.py` | Xcel export + assignment importer |
| `Desktop/.../workforce_salary.xlsx` | README, Structures, Staff, Workers, Excluded sheets |

## How this stays maintainable

The layering, each level narrowing the last:

```
Salary Component     global master, created once
      ↓
Salary Structure     template — 3 of them, no personal amounts
      ↓
Payroll Policy       pay_basis, daily_wage, overtime rules, by scope
      ↓
Policy Exception     dated override for people/groups, preview-verified
      ↓
Assignment           base = the individual figure
```

Anything that differs for one person is an **exception** or an **Additional
Salary** — never a new structure. Both are dated, reasoned, and visible in the
app, and `resolve_values()` reports which rule produced a value. The exception
doctype requires a `preview_signature` before submit, so a change cannot be made
without the preview having been run.

## Two defects found and fixed during implementation

1. **Back-dated assignments were rejected.** Six employees joined after
   2026-08-01, and Frappe refuses an assignment dated before the joining date.
   `effective_from` is now a **floor**, not a fixed date, so a late joiner gets
   their joining date. Verified: Shirina Akter (joined 08-11) has `from_date`
   2026-08-11, not 08-01.
2. **The error handler cascaded.** `frappe.db.rollback()` inside the per-row
   `except` discarded structures created earlier in the same transaction, so one
   failure caused every later row to fail with "structure does not exist". Now
   uses a **savepoint**, so a failing row undoes only itself.

## Field mapping: Selevo flags with no Frappe equivalent

The Selevo model had `is_basic` and `is_gratuity_base`. **Frappe has neither.**
Rather than invent custom fields, the installer refuses a field that does not
exist on `Salary Component`:

```python
if not meta.has_field(field):
    raise frappe.ValidationError(...)
```

so the spec cannot silently reference a phantom field. Only real fields are set:
`is_tax_applicable`, `exempted_from_income_tax`, `depends_on_payment_days`,
`remove_if_zero_valued`.

## Two employees excluded

`COMPANY_A-0026` (Tania Akter, 15,000) and `COMPANY_A-0038` (Rifat Hossain, 25,000) have a
gross in the VPS but **no component breakdown**, so their split cannot be
derived. Excluded by owner instruction and listed on the workbook's `Excluded`
sheet.

## Tax treatment needs confirmation

The spec sets HRA / Medical / Conveyance as `exempted_from_income_tax`, matching
the VPS (`is_taxable = f`). This is a **statutory decision, not a technical one**,
and the register still shows **0 Income Tax Slabs** configured. Confirm before
relying on it.

## Safety

- Backup taken immediately before the import:
  `20260918_215210-hrms_localhost-database.sql.gz` (2,812,235 bytes,
  sha256 `9ceb1d2ee0ca8e73`), copied to
  `Desktop/workforce_suite_backup_20260918/site_backup_before_salary_import/`.
- The live write was one deliberate operation. Earlier dry runs used
  `commit=False` — see the mistake recorded below.

## A mistake worth recording

During development a test called `import_assignments(commit=True)` believing a
later `frappe.db.rollback()` would undo it. It did not: `commit=True` commits
internally, so the rollback was a no-op and **214 assignments were written to the
live site**. Detected immediately by checking counts, then fully reverted
(assignments cancelled and deleted, the two test structures removed, the added
component removed, and the tax/abbr changes to four components restored).
Verified back to `assignments 0 · structures 0 · components 17`.

Lesson: never call a committing function inside something described as a dry run.
All constructive testing must use `commit=False`.
