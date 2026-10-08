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

The tested pre-refactor version pins Frappe 16.34.0, ERPNext 16.35.0 and
HRMS 16.19.0. The renamed package still requires its **own** fresh-install and
restored-database integration acceptance before production rollout.

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
mapping. The historical full integration-suite result predates this refactor;
do not describe the renamed app as production-certified until a fresh v16 site
and restored legacy site pass complete integration tests and UAT.

The original source branch retains the historical customer-specific audit
notes and backup inventory. They are intentionally excluded from this
customer-distributable branch.

## License

See the included license and `app_license` hook before commercial
distribution. The upstream framework and ERPNext/HRMS licenses apply
independently; verify software licensing and support terms for your offering.
