# BACKUP INDEX — read this before any destructive operation

Any agent or person about to delete, migrate, or bulk-edit data **must read this
first**. It lists every backup on this machine with exact timestamps, verified
file names, sizes and checksums.

Last updated: 2026-09-24 08:15 (Asia/Dhaka, UTC+6)

---

## 1. MOST IMPORTANT — the pre-payroll-purge backup

This is the restore point for the **2026-09-18 payroll/wage purge**, in which all
pre-production salary data was hard-deleted.

| Field | Value |
| --- | --- |
| **Taken at** | **2026-09-18 20:02:22 (Asia/Dhaka)** — `bench --site hrms.localhost backup --with-files` |
| **Contents at time of backup** | 474 Salary Slips, 459 Salary Structure Assignments, 6 Salary Structures, 1 submitted Payroll Entry |
| **Canonical location** | `/home/sanchita/frappe-bench/sites/hrms.localhost/private/backups/` |
| **Desktop copy** | `/mnt/c/Users/Sanchita/Desktop/tradex_hr_backup_20260918/site_backup_before_payroll_purge/` |

Files (identical names in both locations):

| File | Bytes | SHA-256 (first 16) |
| --- | --- | --- |
| `20260918_200222-hrms_localhost-database.sql.gz` | 2,879,266 | `00360386d5ae09a5` |
| `20260918_200222-hrms_localhost-private-files.tar` | 942,080 | — |
| `20260918_200222-hrms_localhost-files.tar` | 10,240 | — |
| `20260918_200222-hrms_localhost-site_config_backup.json` | 212 | — |

Verify integrity with:
```bash
gzip -t /home/sanchita/frappe-bench/sites/hrms.localhost/private/backups/20260918_200222-hrms_localhost-database.sql.gz
sha256sum  /home/sanchita/frappe-bench/sites/hrms.localhost/private/backups/20260918_200222-hrms_localhost-database.sql.gz
```

---

## 2. Every site backup, newest first

All under `/home/sanchita/frappe-bench/sites/hrms.localhost/private/backups/`.
Several are also mirrored under
`/mnt/c/Users/Sanchita/Desktop/tradex_hr_backup_20260918/`.

| Taken (Asia/Dhaka) | Database file | Bytes | SHA-256 (16) | Purpose |
| --- | --- | --- | --- | --- |
| 2026-09-24 10:49 | `20260924_044901-hrms-v16_localhost-database.sql.gz` | 13,174,769 | `f98108cfe1439da1` | Before standard staging migration for versioned PF trigger parameters |
| 2026-09-24 10:40 | `20260924_044050-hrms-v16_localhost-database.sql.gz` | 13,135,247 | `f2f84912e2574296` | Before standard staging migration for reviewed PF demand count field |
| 2026-09-24 10:31 | `20260924_043109-hrms-v16_localhost-database.sql.gz` | 13,061,103 | `af4c7cac0cdd2114` | **Before statutory-benefit DocType and permission migration** |
| 2026-09-24 10:08 | `20260924_040836-hrms-v16_localhost-database.sql.gz` | 12,976,640 | `ff925bf16f9830df` | Before standard staging migration for Tradexcel HR Manager Task Share permission |
| **2026-09-24 08:15** | `20260924_021507-hrms-v16_localhost-database.sql.gz` | 11,354,058 | `23c8b694aad2b71b` | **Before statutory wage-floor DocType migration** |
| **2026-09-22 12:17** | `20260922_121725-...-database.sql.gz` | 2,959,372 | `8e62a570fe6a6c43` | **Before v16 staging migration** |
| **2026-09-22 16:48** | `20260922_164856-hrms-v16_localhost-database.sql.gz` | 3,248,003 | `9d45b229d7caf76f` | **Before v16 staging production-readiness fixes/migrate** |
| **2026-09-22 20:37** | `20260922_203730-hrms-v16_localhost-database.sql.gz` | 3,272,843 | `f95eae64b85d7c99` | **Before v16 offline-event-time schema migration** |
| **2026-09-23 22:28** | `20260923_222857-hrms-v16_localhost-database.sql.gz` | 8,270,802 | `bcd9b6f39b9b1618` | Before legal review workflow self-approval transition update |
| **2026-09-24 07:16** | `20260924_011653-hrms-v16_localhost-database.sql.gz` | 10,487,917 | `4ace73be405404b0` | **Before recruitment DocPerm provisioning / standard migrate** |
| **2026-09-24 07:36** | `20260924_013604-hrms-v16_localhost-database.sql.gz` | 10,873,778 | `e62bfae0000c6b0d` | **Before final recruitment DocPerm provisioning / standard migrate** |
| **2026-09-23 22:26** | `20260923_222608-hrms-v16_localhost-database.sql.gz` | 8,231,514 | `ca0f6f4bb9f22a50` | Before statutory review-date field migration |
| **2026-09-23 22:10** | `20260923_221017-hrms-v16_localhost-database.sql.gz` | 8,206,959 | `85cbbef2dff81a5c` | Before statutory exit rule-set schema/workflow migration |
| **2026-09-23 18:46** | `20260923_184653-hrms-v16_localhost-database.sql.gz` | 5,800,185 | `1e7797d321840954` | Before normal migrate removing Payroll Approver Salary Slip mutation rights |
| 2026-09-23 18:39 | `20260923_183900-hrms-v16_localhost-database.sql.gz` | 5,629,472 | `8f902f24151a4936` | Before normal migrate proving Payroll Approver salary-structure read scope |
| 2026-09-23 18:37 | `20260923_183720-hrms-v16_localhost-database.sql.gz` | 5,600,899 | `c1144ef8d76ca10c` | Before normal migrate proving Salary Slip preview-create permission |
| 2026-09-23 18:32 | `20260923_183206-hrms-v16_localhost-database.sql.gz` | 5,554,167 | `5f461d670b4b0034` | Before normal migrate with Payroll Approver Employee read permission |
| 2026-09-23 18:20 | `20260923_182028-hrms-v16_localhost-database.sql.gz` | 5,471,465 | `6134484ff37d5784` | Before first normal workflow migration; queued cleanup jobs recovered with worker |
| 2026-09-23 17:10 | `20260923_171033-hrms-v16_localhost-database.sql.gz` | 5,012,814 | `d16474ca660a1c35` | Before further synthetic Payroll Correction/Arrear integration cleanup; `gzip -t` passed |
| **2026-09-18 20:02** | `20260918_200222-...-database.sql.gz` | 2,879,266 | `00360386d5ae09a5` | **Before payroll/wage purge** (see §1) |
| 2026-09-18 18:53 | `20260918_185348-...-database.sql.gz` | 2,861,011 | `b461fba3f4ef29f7` | Before biometric mapping import |
| 2026-09-18 16:14 | `20260918_161454-...-database.sql.gz` | 2,874,880 | `d7c48e9c2bccdcf2` | Before demo-data removal |

2026-09-23 v16 workflow-migration backups were taken with `--with-files`; each database passed `gzip -t`, and each public/private archive passed `tar -tf`. Full SHA-256 values for database archives:

- 18:20 — `6134484ff37d57845c1ea1296a2990c15982135c247c9f91aadd86b176e0c70a`
- 18:32 — `5f461d670b4b00349441c7c717383d1636048811b62d6c69fc76dd31300949c1`
- 18:37 — `c1144ef8d76ca10cba83b6be417d47b9e8f71e474872771576ab297acc23414b`
- 18:39 — `8f902f24151a49366539d6abed6f9485deedaa130ec30904714679eb5cac90fe`
- 18:46 — `1e7797d321840954892588ec126ca08990dc6070e852009541550ba3c66e5a88`

For the 18:39 and 18:46 backups, config SHA-256 is `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`, public files `407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532`, and private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`.
The 22:28 backup before updating the legal review routing transition was made with `--with-files`; `gzip -t` and both `tar -tf` checks passed. SHA-256: database `bcd9b6f39b9b16181ca7593aede49b9454aa66c6107feff1ed7844fb6d971728`, public files `407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532`, private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`, config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`.
The 2026-09-24 07:16 recruitment-permission backup was taken with `--with-files`; `gzip -t` and both `tar -tf` checks passed. SHA-256: database `4ace73be405404b0d945a53c3a73fbf3cd785b89dcfbf809a620a52fec5c6864`, public files `407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532`, private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`, config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`.
The 2026-09-24 07:36 final recruitment-permission backup was taken with `--with-files`; `gzip -t` and both `tar -tf` checks passed. SHA-256: database `e62bfae0000c6b0d92a6cfbd6c1b3e7ad9cd7522b8e1630ed90e42fbf4262715`, public files `407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532`, private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`, config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`.
The 2026-09-24 08:15 pre-wage-floor-migration backup was taken with `--with-files`; `gzip -t` and both `tar -tf` checks passed. SHA-256: database `23c8b694aad2b71bc69f6935960c226a0eaf44d91e81e913097bac58873af98a`, public files `407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532`, private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`, config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`.
The 22:26 backup before adding the reviewed statutory applicability-date field was made with `--with-files`; `gzip -t` and both `tar -tf` checks passed. SHA-256: database `ca0f6f4bb9f22a50dbdcfe204ad4e22d1fb29de99f26e5ff9cdd2c133bff1cfc`, public files `407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532`, private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`, config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`.
The 22:10 pre-statutory-migration backup was also made with `--with-files`; `gzip -t` and both `tar -tf` checks passed. SHA-256: database `85cbbef2dff81a5c430b9dd4ecc1eed2f0f830ff1331e5cc23ed30b9310d89e9`, public files `407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532`, private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`, config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`.

Mirrors on the Desktop:

| Desktop folder | Contains |
| --- | --- |
| `site_backup_before_payroll_purge/` | the 20:02 backup (§1) |
| `site_backup_before_biometric_mapping/` | the 18:53 database dump |
| `site_backup_before_demo_removal/` | the 16:14 full set (db + files + config) |

---

## 3. The VPS / Selevo source backup — the ultimate safety net

The prior custom HRMS. **This is the source of truth for anything the migration
may have lost.**

| Field | Value |
| --- | --- |
| **Taken** | 2026-09-17 15:40 (captured from VPS `vmi3249897`) |
| **Location** | `/mnt/c/Users/Sanchita/Desktop/selevo_vps_backup_20260917/` |
| **File** | `selevo_postgres_all.sql.gz` — 14,221,919 bytes |
| **Type** | PostgreSQL `pg_dumpall`, 4 databases: `selevo_dev`, `selevohr`, `senseface`, `twenty` |

⚠️ The other files in that folder are **not real backups** — `docker_db_dump.sql.gz`
(122 B), `mysql_dump.sql.gz` (20 B), `pg_dump.sql.gz` (20 B) are error messages
from a missing `pg_dumpall` binary inside the container. Only
`selevo_postgres_all.sql.gz` is valid.

Key contents (parsed): `selevohr.public.employee_biometric_mappings` — 261 rows
across 4 devices; `public.employees` — 361 rows. See
`tasks/biometric_mapping_checklist_2026-09-18.md`.

---

## 4. Repository backups

| Taken | Location | Contents |
| --- | --- | --- |
| 2026-09-18 15:22 | `tradex_hr_backup_20260918/tradex_hr-bench-20260918-152230.bundle` | full git bundle, all refs (`git bundle verify` = complete history) |
| 2026-09-18 19:11 | `tradex_hr_backup_20260918/bridge_clones_20260918/` | both bridge clones: full file mirrors, `*-allrefs.bundle`, `*-tracked-changes.patch` |

All repositories are also on GitHub (`shamrat05/tradexcel-hr`,
`shamrat05/SenseFace-HRMS-Bridge`).

---

## 5. Row-level audit of the payroll purge

Every row deleted on 2026-09-18 was exported to TSV **before** deletion, so the
operation is auditable even without restoring:

`/tmp/opencode/purge/` — `tabSalary_Slip.tsv` (474 rows), `tabSalary_Detail.tsv`
(1000), `tabSalary_Structure_Assignment.tsv` (459), `tabSalary_Structure.tsv`
(6), `tabPayroll_Entry.tsv`, `tabPayroll_Employee_Detail.tsv` (217).

⚠️ `/tmp` is cleared on reboot. Copy these somewhere durable if the audit record
matters.

---

## 6. Restore rehearsal status

The 2026-09-18 host rehearsal remains incomplete, as recorded in
`tasks/backup_restore_rehearsal_2026-09-18.md`. The later v16 isolated restore
rehearsal did complete a normal `bench restore`, normal migration with workers,
and smoke checks on `payroll-migration-check-20260923.localhost`; see the dated
follow-up in that task and `tasks/v16_migration_execution_2026-09-22.md`.

That proves the disposable v16 staging restore path for the tested backup and
branch. It does not certify production recovery. The 2026-09-23 workflow
permission changes were verified by fresh `--with-files` backups, normal
`bench migrate`, actual workflow integration, and suite tests; they were not a
new restore rehearsal.

---

## Housekeeping rules

1. **Before any destructive operation**, run `bench --site hrms.localhost backup --with-files`
   and add a row to §2 with the timestamp, size and checksum.
2. **Never** claim a restore works without rehearsing it on a separate site.
3. Do not delete anything in `tradex_hr_backup_20260918/` or
   `selevo_vps_backup_20260917/`. Those are the recovery path.
4. Verify a dump before trusting it: `gzip -t <file>` and a row count of a known
   table. Count SQL rows with a tuple-aware parser, never `line.count("),(")` —
   that substring also appears inside string values and produced a false
   discrepancy on 2026-09-18.
The 2026-09-24 10:08 backup was taken with `--with-files`; `gzip -t` and both public/private `tar -tf` checks passed. SHA-256: database `ff925bf16f9830df2046248145139765cfea991fe84083a574345047a1a388e3`, public files `407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532`, private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`, config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`.

The 2026-09-24 10:31 backup was taken with `--with-files`; `gzip -t` and both public/private `tar -tf` checks passed. SHA-256: database `af4c7cac0cdd21147706cb2189fa63d79d5176a992ed585264f1230cd2bf7361`, public files `407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532`, private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`, config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`.

The 2026-09-24 10:40 backup was taken with `--with-files`; `gzip -t` and both public/private `tar -tf` checks passed. SHA-256: database `f2f84912e2574296436ffffb3932ca4c210aaf5feecc645a3365ecc6c7d05442`, public files `407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532`, private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`, config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`.

The 2026-09-24 10:49 backup was taken with `--with-files`; `gzip -t` and both public/private `tar -tf` checks passed. SHA-256: database `f98108cfe1439da1c773ecdb478ed4be5ef8e2b59970e3944af82d902e137591`, public files `407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532`, private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`, config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`.

The 2026-09-24 12:48:45 backup before Working Time / Overtime / Holiday / Leave schema migration was taken with --with-files. gzip -t and both public/private tar -tf checks passed. SHA-256: database 393a8573f034dda56d1c1e71520ede58a7f2cea69a3cce5469b9847c7664504f, public files 407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532, private files 7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe, config 904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73. Files are under /home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/ and named with prefix 20260924_124845-hrms-v16_localhost-.


The 2026-09-24 12:50:06 backup was taken with --with-files after the first standard Working Time schema migration stopped on a missing child-DocType Python module, and before the standard migration retry. gzip -t and public/private tar -tf checks passed. SHA-256: database b5d917f23e348836f2755c4c40ebbe09c98cc58e0adc21f9618b4547e04068f7, public files 407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532, private files 7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe, config 904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73. Files are under /home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/ and named with prefix 20260924_125006-hrms-v16_localhost-.

The 2026-09-24 13:07:13 backup before removing the unused fixed-hourly OT checkbox from Working Time Rule Set metadata was taken with --with-files. gzip -t and both public/private tar -tf checks passed. SHA-256: database 4d3794432a6117bdc81b6ed165a3398832c04d8c810c1edc28181452f75cf05b, public files 407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532, private files 7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe, config 904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73. Files are under /home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/ and named with prefix 20260924_130713-hrms-v16_localhost-.
