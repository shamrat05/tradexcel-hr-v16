# White-label migration to Workforce Suite

This branch is the migration path from the original client-branded HR app to a
reusable Frappe/ERPNext/HRMS extension named **Workforce Suite**.

## Product boundary

The reusable product must not hardcode customer identity. Runtime code should
contain no client legal names, client abbreviations, client domains/emails,
branch codes, employee identities, wage amounts, salary splits, statutory
rates, device serials, or customer-specific report/workspace names.

Those values belong in native ERPNext/HRMS masters or explicit company-scoped
configuration.

The one-time migration files necessarily recognize the old app/database names.
That is the only intentional exception.

## Neutral target

| Concern | Target |
| --- | --- |
| Python/Frappe app | `workforce_suite` |
| Python package | `workforce_suite` |
| Frappe module | `Workforce Suite` |
| App DocTypes | `Workforce ...` |
| App roles | `Workforce ...` |
| App reports/pages/workspaces | neutral `Workforce ...` names |
| Custom-field prefix | `custom_workforce_...` |
| Customer legal/company names | database configuration only |

The repository can be renamed to `workforce-suite` after the source migration
has been validated. Repository renaming is separate from the database migration.

## Source conversion

Work only on the dedicated white-label branch/worktree.

```bash
python scripts/genericize_to_workforce_suite.py --check
python scripts/genericize_to_workforce_suite.py --apply
python scripts/genericize_to_workforce_suite.py --check
```

The codemod rewrites both file contents and paths. It is intentionally
deterministic so the same transformation can be reviewed and repeated.

After applying it, run at minimum:

```bash
python scripts/check_source.py
python -m compileall -q workforce_suite
git diff --check
```

Run the existing JavaScript syntax checks with Node 24 and then the complete
site-backed test suite. The previous branded release branch remains available
as the rollback/source-of-truth reference until migration acceptance.

## Fresh-site acceptance

A fresh neutral install must install:

```text
frappe
erpnext
hrms
workforce_suite
```

It must not manufacture customer business data. In particular it must not
create a Company, Employee, salary assignment, payroll transaction, leave
entitlement, tax/legal rule, branch, or device identity simply because the app
was installed.

Configure a synthetic Example Company only in test fixtures.

## Bench preparation (on an isolated restored copy only)

The current Git repository URL still has its historical slug. Only the Python
app/package name is renamed in this branch; do not assume a repository named
`shamrat05/workforce-suite` exists yet. The older AWS bootstrap on the
separate deployment branch is **not** a white-label installer.

Before running any database mutation, restore an existing site into a separate
Frappe v16 bench. Keep the original checkout and backups elsewhere. From the
bench root, stop web/worker processes during the one-time app identity change:

```bash
# Take and verify a real database + files backup before checking out new code.
bench --site YOUR_SITE backup --with-files
sha256sum sites/YOUR_SITE/private/backups/*database.sql.gz
# Verify you can restore this backup to an independent test site.

# In the isolated bench, not on the production source checkout:
cd apps/tradex_hr
git fetch origin
git checkout refactor/workforce-suite-white-label
cd ../..
mv apps/tradex_hr apps/workforce_suite
sed -i 's/^tradex_hr$/workforce_suite/' sites/apps.txt
bench pip install -e apps/workforce_suite
```

These commands are for Linux. If the working directory is already called
`apps/workforce_suite`, do not move it again. The bench's Python environment
and `sites/apps.txt` must both recognize `workforce_suite` before `prepare`.
The site's installed-app database entry must *still* be the legacy app until
`prepare` switches it.

The source rename and installed-app rename are coupled: simply running
`bench migrate` on the new code **without** `prepare` is unsupported.

## Existing database migration

**Never run this first on the only copy of a customer database.**

1. Take a fresh `bench backup --with-files`.
2. Verify the backup archives/checksums.
3. Restore to an isolated rehearsal site.
4. Keep the old app checkout available.
5. Run the two-phase migration below on the rehearsal site.
6. Run all tests and business-count verification.
7. Rehearse restore/rollback before touching a real customer site.

### Phase 1 — preserve and rename metadata

From the bench root:

```bash
env/bin/python apps/workforce_suite/scripts/migrate_legacy_site.py \
  --site YOUR_SITE --phase prepare --yes \
  --backup-file sites/YOUR_SITE/private/backups/YOUR_VERIFIED-database.sql.gz
```

The prepare phase:

- stores pre-migration business and app-owned row counts in the site's private
  directory;
- renames the app Module Def;
- renames app-owned DocTypes through Frappe's supported `rename_doc` path;
- renames app-owned roles/reports/pages/workspaces and related metadata;
- switches `installed_apps` to `workforce_suite`;
- preserves Company/Employee/Branch/payroll/attendance/leave business records.

Frappe v16's DocType rename path also renames the backing database table and
updates Link/Table metadata. DDL may commit even if a subsequent migration
step fails; a Python rollback is **not** a substitute for a tested full backup.
The script now checks an explicit backup file and refuses pre-existing rename
conflicts before the first rename.

### Phase 2 — sync generic source

```bash
bench --site YOUR_SITE migrate
```

This loads the new generic model, hooks, custom fields, reports, pages,
workspaces, roles and assets.

### Phase 3 — copy renamed field values

```bash
env/bin/python apps/workforce_suite/scripts/migrate_legacy_site.py \
  --site YOUR_SITE --phase finalize --yes

env/bin/python apps/workforce_suite/scripts/migrate_legacy_site.py \
  --site YOUR_SITE --phase verify
```

Finalize only copies a legacy-named column when the corresponding new generic
field exists after model sync. It then checks business and app-owned row counts
against the pre-migration snapshot.

Old physical database columns are retained by default for rollback safety.
Do not drop them on the first migration rehearsal.

Old physical columns stay in place for recovery. This migration script has
**no drop-column option**; do not delete them as part of the initial cutover.


## Required tests before this becomes a sellable product

The generic branch should not be released merely because the source compiles.
Acceptance requires all of the following:

- source scan reports no old client identifiers outside migration tooling;
- Python/JSON/JavaScript/shell source checks pass;
- all existing pure tests are ported and pass;
- full Frappe/ERPNext/HRMS integration suite passes on a fresh generic site;
- an isolated copy of the existing database migrates successfully;
- pre/post counts match for Company, Employee, Branch, attendance, leave,
  salary assignments, payroll, Additional Salary, shifts, separation and
  recruitment records;
- role/permission/persona tests pass after role renaming;
- reports/workspace/navigation resolve after metadata renaming;
- scheduler/workers/background jobs resolve the new Python import paths;
- backup restore works after migration;
- physical device/mobile/browser UAT remains a separate customer deployment
  gate.

## Multi-company rule going forward

Do not reintroduce customer defaults into source.

Examples of things that must remain configuration:

- Company/legal name;
- branches/factories/locations;
- payroll split and wage basis;
- statutory/tax/PF/gratuity values;
- holidays and shifts;
- approval roles assigned to actual users;
- biometric device serials/endpoints;
- branding/logo/support email;
- mobile/attendance policy settings.

The app should provide capabilities, validations, reusable workflows and
company-scoped configuration—not a second copy of a specific customer's data.


## Current evidence and release limitation

The branch has dedicated GitHub Actions source validation (compilation,
structured-file parsing, JS syntax and white-label source contracts). Those
checks are necessary but **not sufficient** for a production-grade rename.

The original 653-test acceptance run occurred on the previous branded code,
**not** on this renamed package. The code must still be exercised on both a
fresh Frappe/ERPNext/HRMS site and an isolated restored legacy database to
validate migrations, DocType controllers, workflows, integrations, background
jobs and permissions.

A company record whose legal name contains the old brand stays in the
customer's database. The migration intentionally limits metadata renames to
app-owned records. It does not rewrite employee, company, payroll, accounting
or customer-entered descriptions.
