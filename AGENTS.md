# Tradexcel HR source-only agent rules

## Before deleting or migrating data

**Read `BACKUPS.md` in this repository root first.** It lists every backup with
exact timestamps, file names, sizes and SHA-256 checksums, including the restore
point for each destructive operation. Take a fresh `bench backup --with-files` and
add a row to it before changing data. Note that a `bench restore` has never been
rehearsed on this machine — see the limitation recorded there.

## Canonical checkout — do not work anywhere else

- **This checkout is the only one to edit:** `/home/sanchita/frappe-bench/apps/tradex_hr` (WSL). It is the app directory the live bench loads via `~/frappe-bench/sites/apps.txt`, so it is the only tree whose edits affect runtime.
- A second clone exists at `/mnt/c/Users/Sanchita/Desktop/tradexcel-hr-audit-app` (Windows, reached through `/mnt/c`). Treat it as a stale read-only reference. Do not edit, commit, or branch there. It holds no unique content.
- Line endings are pinned to LF by `.gitattributes`. If `git status` reports the entire tree modified with equal insertion and deletion counts, that is a CRLF artifact, not real work. Confirm with `git diff --ignore-cr-at-eol` before acting on it.

- This repository contains the Frappe custom app, **not** the live bench/site or the standalone SenseFace listener. Never read or copy `sites/`, `sync/data/`, tokens, backups, payroll exports or employee records into this repository or an agent prompt.
- Frappe HR/ERPNext native Employee, Checkin, Attendance, Leave, Shift and Payroll documents are canonical. Build guided previews and audited actions around them; do not duplicate ledgers.
- No agent may run migrations, import employees, alter salary slips, submit payroll, or issue device commands against the live site. Coordinator owns staging verification and live cutover.
- The current app checkout is **not yet deployable on its own**: verified payroll and biometric worker runtime/tests remain under the bench's `sync/`. Complete packaging tasks before claiming release readiness.
- Local one-off false-import cleanup, prototype salary importer, and cancelled-slip purge scripts are intentionally excluded from the remote baseline. Do not reintroduce or execute them without a separate data review and owner authorization.
- Keep the SenseFace bridge in its own pinned repository. Its current receiver and JSON attendance API exist, but Frappe's device-configuration call has no matching bridge endpoint; do not claim that UI action works until implemented and tested.
- For each slice: use a dedicated worktree, change only assigned files, add negative permission/idempotency/date tests, review the diff for secrets, and report what remains unverified. Do not invent statutory rates or user identities.
