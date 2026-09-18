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
