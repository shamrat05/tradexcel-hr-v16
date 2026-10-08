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

### Phase 0 — read-only migration preflight

From the bench root, replace the backup file placeholder with the exact
`bench backup` database archive you verified. Preflight does not modify the
database or installed-app registry:

```bash
env/bin/python apps/workforce_suite/scripts/migrate_legacy_site.py \
  --site YOUR_SITE --phase preflight \
  --backup-file sites/YOUR_SITE/private/backups/YOUR_VERIFIED-database.sql.gz
```

Review the listed planned DocType/role/workflow and patch-log renames. The tool
verifies the backup gzip stream and computes its SHA-256. It cannot itself
prove that the full site and files restore: rehearse that separately.

### Phase 1 — preserve and rename metadata

Only after a clean preflight and successful independent restore rehearsal:

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


## Rehearsal evidence — 2026-10-08

This rehearsal used an independent bench, separate MariaDB/Redis endpoints,
independent application clones and a restored **copy**. The original bench,
checkout, database and uncommitted backup documentation were not changed.
Private archives, record-level comparisons and logs remain outside Git.

### Exact environment

| Application | Version | Pinned source |
| --- | --- | --- |
| Frappe | 16.34.0 | `f1bdb53ac60cd96528b52de418f9459510acb5bd` |
| ERPNext | 16.35.0 | `12cd563fb9a79731f75ae2a45b1446a0a2dd9e74` |
| HRMS | 16.19.0 | `7e0fba4bf11a63ac7b21a717610e235310815c1a` |
| Legacy application | 0.1.0 | `bb48574050214e364c73a15e38dce6128bea2f80` |
| White-label starting branch | 0.1.0 | `fe4920da9faf1e571ae9f1b71f2a1c16502d3f90` |

Python was 3.14.4 and asset checks/builds used Node 24.15.0 explicitly.
The fixes and this evidence are in the enclosing branch commit. Its exact SHA
is recorded in the final operator report; no recursive self-SHA is embedded.

### Results and corrections

- Source validation, renamed wiring and deterministic white-label scan passed.
- Native fresh installation of all four applications passed without creating
  Companies, Employees, wage structures, assignments or financial transactions.
- Full database, public-file, private-file and configuration archives were
  verified by complete decompression/archive reads and SHA-256 checksums.
- A fresh pre-migration backup restored independently with matching protected
  record hashes and file hashes. Restoration was demonstrated, not inferred
  from gzip integrity.
- Read-only preflight, prepare, native `bench migrate`, finalize and verify all
  completed successfully on the independent restored site after corrections.
- The tool handles Single DocTypes as logical documents, unions explicit app
  and module ownership, and uses the installed v16 model-level rename API.
  Only the exact preflight-owned standard Module Def skips its custom-module
  rename restriction; other native validation remains enabled.
- The historical imported Employee reference receives a metadata-preserving
  generic Custom Field through Frappe's supported API. An incompatible field
  type or an unknown missing target field fails closed. No identity is invented.
- Thirty-three app-owned DocTypes, fifteen roles, nine renamed reports, two
  Pages, seven Workflows and their thirty-one states migrated. Forty-eight
  renamed custom-field value sets were copied and compared.
- Comparisons covered thirty-four protected native tables and all thirty-three
  app-owned documents. Counts, original values and relationships matched,
  allowing only explicit role/workflow/DocType identity translations. Native
  role synchronization regenerates child-row IDs; effective role membership
  was compared separately.
- The restored copy retained 277 Employees, 22,302 Employee Checkins, 16,080
  Attendance, 235 Salary Structure Assignments, 1,191 Leave Allocations and 268
  Shift Assignments. Existing Salary Slips, Payroll Entries and GL Entries were
  zero in this backup; synthetic native payroll integration provides the
  populated payroll-path evidence, not historical-payroll restoration evidence.
- Customer Company names, employee values, salary configuration and historical
  transactions were not rewritten. Old physical columns, retired dashboard
  records and `custom_cf_12319_card` were preserved.
- A new post-migration full backup restored successfully into a second copy:
  protected hashes, app counts, metadata counts, public/private file hashes and
  the historical Department column all matched.
- The copied database contains no encrypted secret rows requiring an absent
  encryption key. This is specific to the verified backup; other sites must
  supply their actual encryption-key recovery material.
- All thirty-three controllers, thirteen standard report entry points, one
  hundred unique app hook targets, ninety-nine native scheduled methods and
  seven Workflow definitions resolved. The old Python package was removed
  from the isolated environment and remained unnecessary. Original live Redis
  queues were not copied or executed; the isolated-worker regression passed.
- Complete native asset build for Frappe, ERPNext, HRMS and Workforce Suite
  passed. The initial missing ERPNext nested build dependency was corrected
  only in the isolated environment.

### Fresh-schema and authorization corrections

Native v16 Attendance does not require site-customized Branch/Department
columns. Financial provenance now selects those columns only when installed;
operational scope uses one batched native Employee lookup when absent, while
preserving existing Attendance snapshot values when present. No financial
calculation, stored timestamp or finalized Attendance value changed.

Fresh-install Attendance access now uses the existing Employee-linked query
and direct-document scope hooks. This closes a branch-scope privacy gap rather
than making browser visibility an authorization boundary.

The source permission matrix now matches the copied site's existing Payroll
Approver Additional Salary create/write/submit grant, required by native
Overtime Slip submission. Existing native-provenance, scope and independent
approval checks remain authoritative; cancel/delete/share are not added.
This is a source permission-parity correction, not a claim that no permission
metadata changed. Original-site permissions were untouched.

Statutory and wage-floor jurisdiction fields no longer default to a country.
An operator must explicitly configure jurisdiction; existing customer values
and supported reviewed legal frameworks remain intact.

### Test accounting

The historical 653-test result is not evidence for this package. The renamed
package was exercised on the isolated synthetic v16 site:

| Run | Result | Interpretation |
| --- | --- | --- |
| Initial full run | 750 passed, 53 failed, 0 skipped | Exposed migration/test portability and fresh-schema defects; not acceptance. |
| Last full run after corrections | 807 passed, 3 failed, 0 skipped | 810 collected tests; remaining failures identified precisely. |
| Final fixed-regression run | 6 passed, 0 failed, 0 skipped | All three remaining failures plus the new jurisdiction regression and affected wage-floor integrations. |
| Changed migration metadata regression without Frappe installed | 1 passed | Confirms the new pure test retains source-only CI portability. |

The final three failures were two unit mocks accidentally querying site
metadata and a native onboarding email render missing the isolated asset
manifest. The mocks were isolated and the complete native assets were built;
the failed cases then passed. Tests were not deleted or skipped to improve
counts. At the owner's instruction, the already completed full suite was **not
run again** after this focused correction. These are separate runs, not a
fabricated final all-green full-suite result.

Tests now select explicit disposable sites and sibling installed-source paths
instead of the original workstation site, real employee fixture or bench path.
`tests/conftest.py` rejects cross-site initialization during explicit rehearsal
runs. Manual fixture setup also requires `workforce_rehearsal` and is not an
install hook. Synthetic Company/currency/policy choices are test inputs only.

For a new isolated integration run, configure the disposable site marker and
explicit site path before invoking the suite:

```bash
bench --site YOUR_DISPOSABLE_SITE set-config workforce_rehearsal true
export FRAPPE_TEST_SITE=YOUR_DISPOSABLE_SITE
export FRAPPE_TEST_SITES_PATH="$PWD/sites"
# On an empty disposable site only:
bench --site "$FRAPPE_TEST_SITE" execute workforce_suite.tests.seed_integration_site.seed
bench --site "$FRAPPE_TEST_SITE" execute workforce_suite.tests.seed_integration_site.extend
bash apps/workforce_suite/scripts/run_release_integration.sh
```

Fixture setup is an explicitly invoked engineering utility, not generic
product initialization. Keep scheduler/mail delivery disabled, use separate
Redis and clean the disposable site after the run. The synthetic test site was
backed up and reset natively after this rehearsal; restored migration evidence
sites and private diagnostic backups were retained.

### Backup evidence

Detailed private manifests record all four artifact paths, timestamps, sizes
and SHA-256 values. Representative database restore points are:

| Purpose | Database archive | SHA-256 |
| --- | --- | --- |
| Independent pre-migration rehearsal | `20261008_100817-workforce-legacy_localhost-database.sql.gz` | `cb337a62be97559d74e325b3ae20869e640109ec504406c6ebb61bc3baf20682` |
| Verified post-migration recovery | `20261008_110300-workforce-recovery_localhost-database.sql.gz` | `25623d177a3ebd6e6beccd5a08e280bb67e66edb2e80cfd4e783af3bb57be487` |

These are isolated copies, not authorization to restore or migrate the original
site. No backup, secret, employee export or private configuration is committed.

### Remaining acceptance gates

Actual isolated Desk browser verification was attempted with Chromium against
the served application, not a mocked harness. Login succeeded, but repeated
native setup/Desk navigation reached `/undefined`; stable page/layout/theme
verification was not established. Native Desk setup/navigation diagnosis and
real operator/browser/device UAT remain pending. No framework files were
patched to hide this limitation.

Remote workflow results must be read for the exact pushed head; local tests do
not constitute a remote CI pass. Commercial licensing, clean-history
packaging, customer deployment parity and physical-device/UAT acceptance remain
separate release gates. This rehearsal is not production certification.
