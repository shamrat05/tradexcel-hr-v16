# Tradexcel HR source-only agent rules

- This repository contains the Frappe custom app, **not** the live bench/site or the standalone SenseFace listener. Never read or copy `sites/`, `sync/data/`, tokens, backups, payroll exports or employee records into this repository or an agent prompt.
- Frappe HR/ERPNext native Employee, Checkin, Attendance, Leave, Shift and Payroll documents are canonical. Build guided previews and audited actions around them; do not duplicate ledgers.
- No agent may run migrations, import employees, alter salary slips, submit payroll, or issue device commands against the live site. Coordinator owns staging verification and live cutover.
- The current app checkout is **not yet deployable on its own**: verified payroll and biometric worker runtime/tests remain under the bench's `sync/`. Complete packaging tasks before claiming release readiness.
- Local one-off false-import cleanup, prototype salary importer, and cancelled-slip purge scripts are intentionally excluded from the remote baseline. Do not reintroduce or execute them without a separate data review and owner authorization.
- Keep the SenseFace bridge in its own pinned repository. Its current receiver and JSON attendance API exist, but Frappe's device-configuration call has no matching bridge endpoint; do not claim that UI action works until implemented and tested.
- For each slice: use a dedicated worktree, change only assigned files, add negative permission/idempotency/date tests, review the diff for secrets, and report what remains unverified. Do not invent statutory rates or user identities.
