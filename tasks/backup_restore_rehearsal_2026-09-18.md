# Backup / restore rehearsal — 2026-09-18

## What was rehearsed

The full `bench restore` rehearsal (restore into a separate site, then boot it)
**could not be performed**, and the reason is a finding in itself.

`restore` needs to create a database. The site user cannot:

```
GRANT USAGE ON *.* TO `hrms_db`@`localhost`
GRANT ALL PRIVILEGES ON `hrms_db`.* TO `hrms_db`@`localhost`
```

and no `root`/superuser credential is available:

- `sudo -n` works, so the sudo path is open
- but `sudo mariadb` fails with `Access denied for user 'root'@'localhost' (using password: NO)`
- `/etc/mysql/debian.cnf` is present yet explicitly marked **obsolete** and its
  socket-auth expectation does not hold here
- `common_site_config.json` stores no administrator DB password

So the environment currently has **no usable database superuser**. That blocks not
only the rehearsal but any future site provisioning on this machine — worth
fixing before Contabo, since a restore is the one procedure you need when
everything else has gone wrong.

## What was verified instead

Partial rehearsal — can the backup be read, is it intact, and does it contain the
real data? This catches the most common failure (a dump that is truncated, empty,
or schema-only) without needing a second site.

| Check | Result |
| --- | --- |
| Backup file | `20260918_185348-hrms_localhost-database.sql.gz`, 2.8 MiB |
| `gzip -t` integrity | **OK, not corrupt** |
| Critical tables present as `CREATE TABLE` | Employee, Attendance, Salary Slip, Tradexcel Employee Biometric, Tradexcel Biometric Device — all **present** |

### Contents verified by counting rows inside the dump

| Table | Rows in backup | Live now | Verdict |
| --- | --- | --- | --- |
| `tabCompany` | 2 | 2 | matches |
| `tabEmployee` | 241 | 241 | matches |
| `tabTradexcel Biometric Device` | 2 | 2 | matches |
| `tabTradexcel Employee Biometric` | **0** | 221 | expected — the dump predates the import |

So the dump holds the real data, not just the schema.

### A counting mistake worth recording

The first count reported Employee 242, Attendance 16083, Checkin 22299 — i.e.
*more* rows than live, which looked like a serious discrepancy. It was a bug in
the counting script: `line.count("),(")` also matches those characters **inside
string values**. A tuple-aware scan that tracks quoting and escaping returned the
exact figures above. The backup was never wrong; the measurement was.

Lesson for any future verification: never count SQL rows with a substring search.

## Status: PARTIAL

- Verified: the backup is intact, complete and faithful — a restore would have
  real data to work from.
- **Not verified: that a restore actually boots.** That requires a database
  superuser, which this machine does not currently have.

H2 therefore remains **open**. Do not read this document as "restore rehearsed".

## Follow-up rehearsal — isolated v16 restore, 2026-09-23

The earlier 2026-09-18 result remains accurate for that original host: it was a partial archive-integrity check because no usable DB superuser was available there. A later v16 staging rehearsal used a disposable isolated MariaDB instance with a temporary root credential and did complete a real restore.

- Source: a verified v16 staging backup with database, public files, private files, and site configuration.
- Target: payroll-migration-check-20260923.localhost in the disposable v16 bench database.
- Restore: completed through the normal bench restore path.
- Migration: completed through standard bench migrate with a normal worker running; after_migrate completed.
- Smoke: app and report metadata loaded. Three file-backed Tradexcel Script Reports were standard/module-owned; four retained Query Report definitions. HTTP report calls passed for the three reports with empty filters and for all seven with their declared filters.
- No manual ensure_* calls, queue deletion, production-site operation, real payroll submission, or accounting entry creation was part of the rehearsal.

The staging and disposable-site migration evidence, including the verified fresh backup checksums, is recorded in v16_migration_execution_2026-09-22.md. This later rehearsal closes the restore boot/migrate gap for the v16 staging environment only; it does not certify production recovery readiness.

\r\n