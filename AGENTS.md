# Workforce Suite contributor and coding-agent rules

## Source of truth
- Read `README.md` and `docs/white_label_migration.md` before changing the app identity, schema or setup hooks.
- Work only in an isolated branch. Do not merge code that has not passed the full required checks.
- The Python app is `workforce_suite`; the Frappe module is `Workforce Suite`.
- Keep Frappe, ERPNext and HRMS native business documents authoritative.
- Extend through supported hooks/mixins, not modifications of upstream framework files.

## Portability and tenant safety
- Never add customer legal names, branch abbreviations, device addresses,
  salary splits, tax/pension rates, default Company records or real employee
  data to shared source or test fixtures.
- Set company context explicitly and enforce Frappe permissions in SQL reports,
  queued actions, mutations and API methods.
- Store configurable policy parameters per Company/Branch/effective date.
- Only use synthetic records in tests and public documentation.
- Never include secrets, access keys, payroll exports, backups or site files.

## Database migrations
- Take a verified backup and rehearse a restore before modifying an existing site.
- Follow the prepare -> bench migrate -> finalize -> verify sequence in the
  migration runbook; never uninstall the old app to perform this rename.
- Frappe DocType renames may commit database DDL. A transaction rollback alone
  cannot undo a failed partial migration.
- Never alter legal Company names or employee/payroll/accounting business data
  during an internal package rename.
- Preserve old physical custom-field columns for recovery until a separate,
  explicitly reviewed cleanup.

## Tests
- Run `python scripts/check_source.py`.
- Run `python scripts/genericize_to_workforce_suite.py --check`.
- Run the repository's dedicated white-label QA workflow.
- Run the full Frappe site-backed integration suite on a fresh neutral site.
- Rehearse a restored database migration with pre/post business-record checks.
- Do not claim production readiness solely from static/pure tests.
