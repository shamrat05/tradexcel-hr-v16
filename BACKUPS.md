# BACKUP INDEX — read this before any destructive operation

Any agent or person about to delete, migrate, or bulk-edit data **must read this
first**. It lists every backup on this machine with exact timestamps, verified
file names, sizes and checksums.

Last updated: 2026-09-22 20:37 (Asia/Dhaka, UTC+6)

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
| **2026-09-22 12:17** | `20260922_121725-...-database.sql.gz` | 2,959,372 | `8e62a570fe6a6c43` | **Before v16 staging migration** |
| **2026-09-22 16:48** | `20260922_164856-hrms-v16_localhost-database.sql.gz` | 3,248,003 | `9d45b229d7caf76f` | **Before v16 staging production-readiness fixes/migrate** |
| **2026-09-22 20:37** | `20260922_203730-hrms-v16_localhost-database.sql.gz` | 3,272,843 | `f95eae64b85d7c99` | **Before v16 offline-event-time schema migration** |
| **2026-09-18 20:02** | `20260918_200222-...-database.sql.gz` | 2,879,266 | `00360386d5ae09a5` | **Before payroll/wage purge** (see §1) |
| 2026-09-18 18:53 | `20260918_185348-...-database.sql.gz` | 2,861,011 | `b461fba3f4ef29f7` | Before biometric mapping import |
| 2026-09-18 16:14 | `20260918_161454-...-database.sql.gz` | 2,874,880 | `d7c48e9c2bccdcf2` | Before demo-data removal |

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

## 6. Known limitation — restores are NOT rehearsed

A `bench restore` has **never been proven** on this machine. No database
superuser is reachable:

```
sudo mariadb                                       -> Access denied for 'root'@'localhost'
/etc/mysql/debian.cnf                              -> marked OBSOLETE; socket auth does not hold
common_site_config.json                            -> no admin DB password
```

So the backups are **verified readable and complete**, but **not verified
restorable**. See `tasks/backup_restore_rehearsal_2026-09-18.md`. Treat this as
the top operational risk: there is a verified backup and no proven way to use it.

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
