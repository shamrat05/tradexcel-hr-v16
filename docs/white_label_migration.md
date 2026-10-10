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

Finalize also retargets the exact legacy packaged Desktop Icon logo URL on
icons recorded as app-owned in the preflight snapshot. Native JSON sync can
leave that URL unchanged when the database record is newer than the source.
Customer-uploaded/external logos and unrelated icons are preserved; changed
ownership or a missing packaged asset fails closed. The native document save
runs in import mode so it cannot export site metadata into application source.

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
| Historical full run after corrections | 807 passed, 3 failed, 0 skipped | 810 collected tests; remaining failures identified precisely. |
| Final fixed-regression run | 6 passed, 0 failed, 0 skipped | All three remaining failures plus the new jurisdiction regression and affected wage-floor integrations. |
| Changed migration metadata regression without Frappe installed | 1 passed | Confirms the new pure test retains source-only CI portability. |

The final three failures were two unit mocks accidentally querying site
metadata and a native onboarding email render missing the isolated asset
manifest. The mocks were isolated and the complete native assets were built;
the failed cases then passed. Tests were not deleted or skipped to improve
counts. At the owner's earlier instruction, the full suite was **not run again**
immediately after that focused correction. Those were separate historical
runs. The later explicit acceptance instruction authorized the uninterrupted
full rerun recorded below; focused results were not substituted for it.

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

The first browser attempt did not establish stable Desk verification. Its
initial interpretation of `/undefined` as a navigation destination was
incorrect; the instrumented follow-up below distinguishes the image request
from actual main-frame navigation. This historical attempt is not acceptance
evidence. No framework files were patched to hide the limitation.

Remote workflow results must be read for the exact pushed head; local tests do
not constitute a remote CI pass. Commercial licensing, clean-history
packaging, customer deployment parity and physical-device/UAT acceptance remain
separate release gates. This rehearsal is not production certification.

## Acceptance follow-up — 2026-10-08

This follow-up began at `0c82dbc4683af9ab8b5e1b1b9dfc62010df6507e`
in the existing independent rehearsal bench. The original bench, checkout,
database, customer backups and dirty backup documentation remained untouched.
All three framework pins in the environment table above remained unchanged.

### Navigation diagnosis and confirmed correction

Chromium captured console errors, failed requests, response status/resource
types, CDP request initiators, main-frame navigation and screenshots. Private
server logs were retained alongside those captures. Comparison covered:

- a clean Frappe/ERPNext/HRMS site without this app;
- a fresh Workforce Suite site;
- the migrated restored copy.

On all three configured sites, login reached `/desk`. `/undefined` was a
404 **Image** request, never a main-frame redirect. Instrumentation traced the
generated `<img src="undefined">` to installed Frappe's
`SidebarHeader.populate_dropdown_menu()` passing `{is_divider: true}` entries
to `add_app_item()`, which expects an ordinary item with an icon URL. This is
reproducible without Workforce Suite. Default App settings, native Desktop
Icon/Sidebar routes, permission-filtered boot data and asset manifests did not
establish an app redirect defect. No redirect shim or core patch was added.
The native-only site selected `/desk` as its default path; both four-app sites
selected native `/apps`, whose login flow reached Desk. System/User Default App
values were blank and no stale legacy User Default App values were present.
Each four-app site had exactly one app-owned Desktop Icon and Sidebar.

A separate app migration defect **was** confirmed: the renamed Desktop Icon
retained `/assets/tradex_hr/images/tradex-hr.svg`. The narrow finalize correction
described above was applied to the backed-up restored copy and verified by
actual Desk navigation. The packaged Workforce Suite logo loads, and its
native Desktop Icon opens the existing Workforce Suite Workspace/Sidebar.
Two pure regressions cover retry idempotence, customer/unrelated-logo
preservation, import-mode save and fail-closed ownership/asset checks.

Before native setup completion, clean HRMS and fresh Workforce Suite also
reproduced a Frappe `Sidebar.toggle()` exception: its constructor returns early
when `boot.setup_complete` is false, but the toggle then uses an absent sidebar
element. Acceptance comparison used the supported native setup-completion
procedure with explicit synthetic Company/country/currency configuration;
it did not force boot flags or add a redirect. The initial wizard exception
remains an upstream fresh-setup limitation, not a proven clean wizard journey.

Development realtime initially used the wrong port/site identity. Restarting
only the isolated services with the native development-server environment and
using each site's own hostname resolved the Socket.IO request/namespace errors.
No application or framework realtime code was changed.

### Actual served-browser evidence

The final matrix contains **80 checks**: fresh and migrated sites, Administrator
and a synthetic Company-scoped Workforce Suite Manager without System Manager,
1365px and 375px, light and dark, across Home, Employee List, unsaved Employee
Form, unsaved Attendance Request Form and Employee Data Gaps report. Native
Desktop Icon clicks opened the Workspace; native theme selection and Sidebar
controls were used. Reports received an explicit permitted Company through
native route options. No business form was saved.

All 80 checks completed with zero uncaught JavaScript errors and zero
document-level horizontal overflow. Administrator captures retain the upstream
`/undefined` image 404. The ordinary HR user's native Employee form retains a
403 from HRMS's unconditional `frappe.db.get_single_value("HR Settings",
"emp_created_by")` call; the form remains accessible, but this is not an
error-free ordinary-user console. Extra Settings permission was not granted.
Both synthetic browser users and their Company User Permissions were deleted
and their absence verified.

### Uninterrupted full integration result

After browser verification, the native release runner executed the entire test
directory on the explicitly guarded disposable fresh site, without interruption,
selection or skipping:

```bash
bash apps/workforce_suite/scripts/run_release_integration.sh \
  --junitxml=/PRIVATE_EVIDENCE_DIRECTORY/full-integration.xml
```

The result was **813 passed, 0 failed, 0 errors, 0 skipped**, exit code **0**,
in **676.30 seconds**. One warning was recorded by the runner, whose normal
`--disable-warnings` option suppresses warning detail. The private full stdout/
stderr and JUnit XML preserve the exact result. This includes the earlier three
failed cases, the jurisdiction regression and both new logo-migration tests.
No test was removed or skipped to obtain acceptance.

The final restored-copy comparison passed across all **34 protected native
tables** and **33 app-owned documents**: all counts matched, app records matched
exactly, and there were no unexpected changed fields. Only one isolated
Administrator's native `last_active`, `last_login` and `modified` fields changed
during actual browser login. Customer records, roles and User Permissions were
preserved. Original checkout/configuration hashes and all three upstream source
worktrees remained unchanged.

After retaining and verifying a fresh full backup of the synthetic test site,
native reinstall removed its integration fixtures. A post-cleanup read-only
check found all four apps installed and zero Company, Employee, Checkin,
Attendance, Salary Component/Structure/Assignment, Additional Salary, Payroll
Entry, Salary Slip, GL Entry, Leave Allocation and Shift Assignment records,
plus zero temporary browser users/User Permissions. Scheduler remained paused
and mail muted. The first cleanup invocation stopped at an empty-root-password
CLI prompt; supplying the isolated server's empty password through stdin
completed cleanup. Both command logs were retained. The migrated evidence copy
and recovery archives were preserved; no original site was reset.

Logs, screenshots, navigation/boot captures and test XML are private under
`/home/sanchita/workforce-suite-rehearsal-20261008/acceptance-20261008/` and
the sibling `logs/` directory. Customer data, passwords and raw diagnostics
are not committed.

### Upstream reproduction and safe resolution

Use the exact pinned Frappe version in a disposable three-app site, finish
native setup, log in as Administrator and inspect `/desk` with Chromium's
Network filter `undefined`. Record resource type Image/404 and the unchanged
main-frame route, then inspect the divider entries and rendering methods in
`frappe/public/js/frappe/ui/sidebar/sidebar_header.js`. This independently
reproduces the remaining asset defect. For the wizard issue, use an unconfigured
clean site and retain its `Sidebar.toggle` stack before completing setup.

Frappe's reported v16 sidebar-icon and workspace-navigation issues are related
investigation leads, not proof that their root causes match this capture.
The installed resolver already includes its multi-candidate fallback. The safe
next step is an upstream divider/setup lifecycle correction followed by a
separately pinned framework upgrade rehearsal, including this same browser
matrix. Do not change core locally, suppress failures, invent `/undefined`
redirects or broaden Settings access to make screenshots appear clean.

Pinned source proof: [sidebar divider rendering](https://github.com/frappe/frappe/blob/f1bdb53ac60cd96528b52de418f9459510acb5bd/frappe/public/js/frappe/ui/sidebar/sidebar_header.js),
[sidebar setup and resolution](https://github.com/frappe/frappe/blob/f1bdb53ac60cd96528b52de418f9459510acb5bd/frappe/public/js/frappe/ui/sidebar/sidebar.js),
and [HRMS Employee settings request](https://github.com/frappe/hrms/blob/7e0fba4bf11a63ac7b21a717610e235310815c1a/hrms/public/js/erpnext/employee.js).
Related reports examined: [v16 sidebar icons](https://github.com/frappe/frappe/issues/40074)
and [workspace resolution](https://github.com/frappe/frappe/issues/39667).

Physical devices, real staff UAT, customer deployment parity, clean-history
packaging and commercial licensing remain separate acceptance gates.
