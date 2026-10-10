# Workforce Suite

**Workforce Suite** is a reusable Frappe v16 extension for ERPNext and Frappe HRMS.
It supplies configurable workforce operations while retaining native HRMS and
accounting documents as the authoritative records. The code must never infer a
customer's legal identity, payroll basis or permissions from a built-in company name.

## Stack

- Frappe v16
- ERPNext v16
- Frappe HRMS v16
- Python 3.14

The isolated white-label rehearsal uses Frappe 16.34.0, ERPNext 16.35.0 and
HRMS 16.19.0. Fresh installation, restored-copy migration, data comparisons and
post-migration recovery passed. The subsequent uninterrupted acceptance run
passed **813 tests, 0 failed, 0 skipped**. Actual isolated Desk checks completed
80 Administrator/scoped-HR combinations across fresh and migrated sites,
desktop/phone widths and light/dark themes, with no uncaught JavaScript errors
or document overflow. A stale migrated app-logo URL was corrected. Native
Frappe sidebar image/setup issues and an HRMS restricted-user Settings request
remain documented; physical-device and real staff UAT remain outstanding.
See the [acceptance evidence](docs/white_label_migration.md#acceptance-follow-up--2026-10-08).

Bangladesh statutory technical working copies now cover 35 catalog entries,
including separate prescribed variants and four original-evidence-only entries.
The expanded isolated application suite passed **936 tests, 2 skipped, 18
upstream warnings**; bilingual native A4 PDF and editable Word rendering,
backed-up migration and disposable fresh installation were verified. The
[coverage and field crosswalk](docs/bangladesh_statutory/coverage.md) and
[dated verification](docs/bangladesh_statutory/implementation_20261009.md)
distinguish technical evidence from official acceptance. Independent current-law
and translation approval, actual employer evidence and staff/filing acceptance
remain required; the original Rule 353 reference is still unavailable. No form
is automatically certified and no production deployment was performed.


## App name and module

| Item | Value |
| --- | --- |
| Frappe app / Python package | `workforce_suite` |
| Frappe module | `Workforce Suite` |
| App UI label | `Workforce Suite` |
| Database document prefix for app-owned records | `Workforce ...` |
| Frappe custom-field prefix | `custom_workforce_...` |

The app supplies attendance/biometric integrations, operational boards and
reports, secure bulk workflows, scoped approvals and permission controls,
payroll validation, lifecycle safeguards, working-time and statutory rule
frameworks. It **does not** replace native Employee, Attendance, Leave,
Payroll Entry, Salary Slip, Salary Structure Assignment or accounting records.

## Per-customer configuration

Set up Companies, Branches, Departments, Holidays, Shifts, salary structures
and components, pay basis, statutory rules, roles, users and biometric devices
per site. All customer-identifying values and regulatory settings belong in
native records or company-scoped configuration, never in shared source.

An optional historical salary specification remains for explicit,
operator-approved migration; it is **not** installed automatically.
Do not run it as a generic onboarding default.

## New installation

Start with a clean Frappe/ERPNext/HRMS v16 bench and install this repository
as an app named `workforce_suite`. The current Git repository slug remains
historical; the package and module inside this branch use neutral identifiers.
After the app is available in `sites/apps.txt` and the bench Python environment:

```bash
bench --site YOUR_SITE install-app workforce_suite
bench --site YOUR_SITE migrate
bench --site YOUR_SITE list-apps
```

New installations must be tested with a synthetic company before any
live employee, device or payroll data is entered.

## Existing-site upgrade

**Do not just run `bench migrate` on an existing installed legacy app.**
An app identity change also renames DocTypes, backing tables, role/workflow
metadata, patch-log entries and custom fields.

Follow [the two-phase migration runbook](docs/white_label_migration.md) on an
isolated restored database, and keep a verified backup and the original branch.

## Quality gates

The `White-label QA` GitHub Actions workflow checks Python compilation,
JSON/TOML/YAML parsing, JavaScript syntax, neutral branding and pure migration
mapping. The isolated renamed-app test and migration results are documented
separately from remote CI. They do not establish production certification or
replace outstanding browser/device/staff UAT.

The original source branch retains the historical customer-specific audit
notes and backup inventory. They are intentionally excluded from this
customer-distributable branch.

## Distributing the generic product

Do **not** make this original development repository public. Removing
customer-specific notes from the current branch does **not** remove them from
older Git commits. For commercial distribution, create a new clean-history
repository containing only the reviewed generic snapshot and its approved
license, excluding the legacy migration tools and customer-history branches.

## License

The app currently declares `MIT` in its Frappe hooks, but this repository
does not yet include a reviewed root license file. Decide and document your
commercial distribution terms before selling licenses or sharing source.
Verify the independent upstream Frappe/ERPNext/HRMS license obligations.
