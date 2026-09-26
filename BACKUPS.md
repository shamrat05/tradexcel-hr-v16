# BACKUP INDEX — read this before any destructive operation

Any agent or person about to delete, migrate, or bulk-edit data **must read this
first**. It lists every backup on this machine with exact timestamps, verified
file names, sizes and checksums.

Last updated: 2026-09-26 18:10 (Asia/Dhaka, UTC+6)

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

Historical backups are under `/home/sanchita/frappe-bench/sites/hrms.localhost/private/backups/`.
The current v16 staging backup is under
`/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/`.
Several older files are also mirrored under
`/mnt/c/Users/Sanchita/Desktop/tradex_hr_backup_20260918/`.

| Taken (Asia/Dhaka) | Database file | Bytes | SHA-256 (16) | Purpose |
| --- | --- | --- | --- | --- |
| **2026-09-26 09:20:27** | `20260926_092011-hrms-v16_localhost-database.sql.gz` | 38,067,024 | `3f01cac70816b9b0` | Before deleting verified orphan synthetic persona Contact/Notification Settings left by older test teardown; no real User/configuration cleanup |
| **2026-09-26 07:02:58** | `20260926_070248-hrms-v16_localhost-database.sql.gz` | 36,775,178 | `9506a3785f975d76` | Before standard Employee Data Gaps Report JavaScript metadata convergence; gzip and both file archives verified |
| **2026-09-26 01:43:48** | `20260926_014339-hrms-v16_localhost-database.sql.gz` | 34,392,005 | `6c0ee9336bf383c4` | Before scoped native Leave Control Panel DocPerm/hook migration; gzip and both file archives verified |
| **2026-09-26 01:27:50** | `20260926_012737-hrms-v16_localhost-database.sql.gz` | 34,020,564 | `349d60b17c00fe09` | Before standard portability/Workspace metadata migration; gzip and both file archives verified |
| **2026-09-25 22:00:38** | `20260925_220031-hrms-v16_localhost-database.sql.gz` | 29,500,665 | `15d9c3178f37676a` | Before native bulk SSA permissions and Workspace target migration; gzip and both file archives verified |
| **2026-09-25 23:53:24** | `20260925_235317-hrms-v16_localhost-database.sql.gz` | 31,385,027 | `2db1cf58ec51e498` | Before Attendance Correction Approver Employee read/select DocPerm convergence; gzip and both file archives verified |
| **2026-09-26 00:03:13** | `20260926_000304-hrms-v16_localhost-database.sql.gz` | 31,453,473 | `dde0ca2590d382d7` | Before removing Attendance Request cancel from custom approver and syncing report JavaScript; gzip and both file archives verified |
| **2026-09-25 20:54:37** | `20260925_205430-hrms-v16_localhost-database.sql.gz` | 28,547,805 | `c82369eea7a30dc4` | Before standard migration for scoped native Shift Assignment Tool permissions; gzip and both file archives verified |
| **2026-09-25 19:53:09** | `20260925_195302-hrms-v16_localhost-database.sql.gz` | 27,079,768 | `0d00492b22e2abdb` | Before adding explicit financial audience to Payroll Register after Workspace exposed it to an operational persona; gzip and both file archives verified |
| **2026-09-25 19:49:36** | `20260925_194930-hrms-v16_localhost-database.sql.gz` | 27,070,502 | `c7e0fef7c6eb1423` | Before adding Leave Approver Employee read and limiting Leave Allocation to read/report; gzip and both file archives verified |
| **2026-09-25 19:47:40** | `20260925_194734-hrms-v16_localhost-database.sql.gz` | 27,053,343 | `1fa3bba17a99d6bf` | Before adding Leave Approver Company read context after report endpoint reproduced scope denial; gzip and both file archives verified |
| **2026-09-25 19:45:07** | `20260925_194500-hrms-v16_localhost-database.sql.gz` | 27,040,979 | `83ae662e901fe4e3` | Before converging Leave Approver read-only Leave Allocation and Leave Balance Board access; gzip and both file archives verified |
| **2026-09-25 19:35:18** | `20260925_193512-hrms-v16_localhost-database.sql.gz` | 27,040,715 | `c9f9a7ec6241c098` | Before synthetic persona permission/Workspace UAT; database gzip and public/private archives verified |
| **2026-09-25 19:10** | `20260925_191022-hrms-v16_localhost-database.sql.gz` | 26,394,823 | `7075ff3213ade2c1` | Before removing four unreferenced synthetic Salary Components left by earlier report integration attempts; database gzip and public/private archives verified |
| **2026-09-25 18:46** | `20260925_184554-hrms-v16_localhost-database.sql.gz` | 26,018,221 | `d70869620fc37fd9` | Before converging read-only Company access for Tradexcel Payroll Approver, required for scoped financial reports; database gzip and public/private archives verified |
| **2026-09-25 18:36** | `20260925_183646-hrms-v16_localhost-database.sql.gz` | 26,007,069 | `e480a934feacdc6a` | Before converting Pay Component Register and Payroll Variance to standard Script Reports and retiring the app Query Report wrapper; database gzip and public/private archives verified |
| **2026-09-25 17:54** | `20260925_175417-hrms-v16_localhost-database.sql.gz` | 25,666,278 | `05dfbfaefb610c01` | Before converting Shift Coverage and Joiners/Leavers Report metadata to standard Script Reports; database gzip and public/private archives verified |
| **2026-09-25 17:03** | `20260925_170339-hrms-v16_localhost-database.sql.gz` | 24,670,590 | `b3244c0653d41c25` | Before removing unlinked Worker DocPerm access to native Employee-linked records; database gzip and public/private file archives verified |
| **2026-09-25 16:53** | `20260925_165337-hrms-v16_localhost-database.sql.gz` | 24,647,575 | `ea6b62ad992cbdd5` | Before Company read-only DocPerm convergence; database gzip and public/private file archives verified |
| **2026-09-25 16:51** | `20260925_165127-hrms-v16_localhost-database.sql.gz` | 24,634,604 | `27f66bf1c0c5d656` | Before standard report-role metadata migration; database gzip and public/private file archives verified |
| **2026-09-25 11:14** | `20260925_111432-hrms-v16_localhost-database.sql.gz` | 20,389,261 | `9dcac7c73acbd29e` | Before standard lifecycle-branch migration; gzip and both file archives verified |
| **2026-09-25 13:57** | `20260925_135751-hrms-v16_localhost-database.sql.gz` | 23,518,137 | `392607c1445ebdb3` | Before synthetic PR #20 lifecycle/payroll compatibility cleanup tests; `--with-files`, gzip and both file archives verified |
| **2026-09-25 10:26** | `20260925_102545-hrms-v16_localhost-database.sql.gz` | 20,389,491 | `49ed5d561ba4abe4` | Before synthetic Employee Lifecycle integration retry |

The **2026-09-26 09:20:27** backup was taken with `--with-files` before
cleanup of verified orphan `persona-puat…@example.test` Contact and Notification
Settings records left by the older synthetic fixture. Files are under
`/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/`.
`gzip -t` and public/private `tar -tf` passed. Exact sizes and SHA-256:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `20260926_092011-hrms-v16_localhost-database.sql.gz` | 38,067,024 | `3f01cac70816b9b0d5736fd592fb05ae5a34b364fdf495bd910e022431de408d` |
| `20260926_092011-hrms-v16_localhost-files.tar` | 10,240 | `407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532` |
| `20260926_092011-hrms-v16_localhost-private-files.tar` | 38,932,480 | `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe` |
| `20260926_092011-hrms-v16_localhost-site_config_backup.json` | 245 | `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73` |

The **2026-09-26 07:02:58** backup was taken with `--with-files` before
standard Report metadata migration for Employee Data Gaps. Files are under
`/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/`
with prefix `20260926_070248-hrms-v16_localhost-`. `gzip -t` and both
public/private `tar -tf` listings passed. Exact sizes and SHA-256:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `20260926_070248-hrms-v16_localhost-database.sql.gz` | 36,775,178 | `9506a3785f975d76bee5b1aaed18bc84a6c242477bc62d1e7ec4caf465ac12db` |
| `20260926_070248-hrms-v16_localhost-files.tar` | 10,240 | `407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532` |
| `20260926_070248-hrms-v16_localhost-private-files.tar` | 38,932,480 | `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe` |
| `20260926_070248-hrms-v16_localhost-site_config_backup.json` | 245 | `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73` |

The **2026-09-26 01:43:48** backup was taken with `--with-files` before
standard staging migration for native Leave Control Panel scope and custom
HR entitlement permissions. Files are under
`/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/`
with prefix `20260926_014339-hrms-v16_localhost-`. `gzip -t` and both tar
listings passed. Exact sizes and SHA-256:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `20260926_014339-hrms-v16_localhost-database.sql.gz` | 34,392,005 | `6c0ee9336bf383c4025c024e40141b5483c96344be5ed5692a94f73854cda83d` |
| `20260926_014339-hrms-v16_localhost-files.tar` | 10,240 | `407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532` |
| `20260926_014339-hrms-v16_localhost-private-files.tar` | 38,932,480 | `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe` |
| `20260926_014339-hrms-v16_localhost-site_config_backup.json` | 245 | `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73` |

The **2026-09-26 01:27:50** backup was taken with `--with-files` before the
standard staging migration that removes hardcoded company Number Cards and
converges neutral Branch metadata. Files are under
`/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/`
with prefix `20260926_012737-hrms-v16_localhost-`. `gzip -t` passed and both
public/private `tar -tf` listings passed. Exact sizes and SHA-256:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `20260926_012737-hrms-v16_localhost-database.sql.gz` | 34,020,564 | `349d60b17c00fe0928c05c3a43f6688769e3cbfcd097924e60d04a8fe095f994` |
| `20260926_012737-hrms-v16_localhost-files.tar` | 10,240 | `407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532` |
| `20260926_012737-hrms-v16_localhost-private-files.tar` | 38,932,480 | `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe` |
| `20260926_012737-hrms-v16_localhost-site_config_backup.json` | 245 | `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73` |

The **2026-09-25 22:00:38** backup was taken with `--with-files` before the
native Bulk Salary Structure Assignment role and Workspace shortcut convergence.
Files are under
`/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/`
with prefix `20260925_220031-hrms-v16_localhost-`. Database gzip and public and
private tar listings all verified. Exact sizes and SHA-256:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `20260925_220031-hrms-v16_localhost-database.sql.gz` | 29,500,665 | `15d9c3178f37676a5d58830a8fb1e6f9d55fa69045fcab6639b91e9f29fddc87` |
| `20260925_220031-hrms-v16_localhost-files.tar` | 10,240 | `407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532` |
| `20260925_220031-hrms-v16_localhost-private-files.tar` | 38,932,480 | `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe` |
| `20260925_220031-hrms-v16_localhost-site_config_backup.json` | 245 | `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73` |

The **2026-09-25 23:53:24** backup was taken with `--with-files` before
granting the Attendance Correction Approver the minimum permission-aware
Employee list context needed for submit-time scope validation. Database gzip
and public/private archives all verified. SHA-256: database
`2db1cf58ec51e4987ff3d1d37ec24615ceeb02d7e53da2f18dd8866cd2886b6e`, public
files `407aa11be1920d8b2022cb054d30fb752d6a8a40fd28b560744a5f4df7fef0532`,
private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`,
config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`.
Files are under `/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/`
with prefix `20260925_235317-hrms-v16_localhost-`; sizes: database 31,385,027
bytes, public files 10,240 bytes, private files 38,932,480 bytes, config 245
bytes.

The **2026-09-26 00:03:13** backup was taken with `--with-files` before removing
Attendance Request cancellation from the custom Attendance Correction
Approver (native cancellation also needs Attendance write) and syncing the
updated Daily Attendance Board report JavaScript. Database gzip and both file
archives verified. SHA-256: database
`dde0ca2590d382d73f266ae87efb53b938766f4b5b4382301dfdea043b0913ee`, public
files `407aa11be1920d8b2022cb054d30fb752d6a8a40fd28b560744a5f4df7fef0532`,
private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`,
config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`.
Files are under `/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/`
with prefix `20260926_000304-hrms-v16_localhost-`; sizes: database 31,453,473
bytes, public files 10,240 bytes, private files 38,932,480 bytes, config 245
bytes.
| **2026-09-25 10:29** | `20260925_042901-hrms-v16_localhost-database.sql.gz` | 19,262,541 | `1eac1fc84f418807` | **Before standard maternity DocType migration** |
| **2026-09-25 15:14** | `20260925_091421-hrms-v16_localhost-database.sql.gz` | 19,413,925 | `7e877a8fa3b9e042` | **After maternity schema migration; before synthetic integration cleanup and migration retry** |
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

The **2026-09-25 13:57:51** backup was taken with `--with-files` before synthetic
PR #20 lifecycle/payroll compatibility tests. `gzip -t` and both public/private
`tar -tf` checks passed. SHA-256: database
`392607c1445ebdb356494fcc8285def850d6ef2e00974efdbbce6a38b2b66a11`, public
files `407aa11be1920d8b2022cb054d30fb752d6a8a40fd28b560744a5f4df7fef0532`,
private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`,
config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`.
Files are under `/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/`
with prefix `20260925_135751-hrms-v16_localhost-`; sizes: database 23,518,137
bytes, public files 10,240 bytes, private files 38,932,480 bytes, config 245 bytes.

The **2026-09-25 16:51:27** backup was taken with `--with-files` before the
report authorization role metadata migration. `gzip -t` and both public/private
`tar -tf` checks passed. SHA-256: database
`27f66bf1c0c5d65682625e0418fbe20ea2f9c0130020bf9ec5340bb1c05812bc`, public
files `407aa11be1920d8b2022cb054d30fb752d6a8a40fd28b560744a5f4df7fef0532`,
private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`,
config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`.
Files are under `/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/`
with prefix `20260925_165127-hrms-v16_localhost-`; sizes: database 24,634,604
bytes, public files 10,240 bytes, private files 38,932,480 bytes, config 245
bytes.

The **2026-09-25 16:53:37** backup was taken with `--with-files` before the
Company read-only DocPerm convergence required by the report Company context
check. `gzip -t` and both public/private `tar -tf` checks passed. SHA-256:
database `ea6b62ad992cbdd532980867be280f5edde473ec4fe0c14dbe8795cae9093da7`,
public files `407aa11be1920d8b2022cb054d30fb752d6a8a40fd28b560744a5f4df7fef0532`,
private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`,
config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`.
Files are under `/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/`
with prefix `20260925_165337-hrms-v16_localhost-`; sizes: database 24,647,575
bytes, public files 10,240 bytes, private files 38,932,480 bytes, config 245
bytes.

The **2026-09-25 17:03:39** backup was taken with `--with-files` before removing
unlinked Worker access to Employee Checkin, Leave Allocation, Leave Application,
and Attendance Request. `gzip -t` and both public/private `tar -tf` checks
passed. SHA-256: database
`b3244c0653d41c25e5f0a9230cb4e1b0d9b1f5717cbf5c4cc09de5f75f8f18fc`, public
files `407aa11be1920d8b2022cb054d30fb752d6a8a40fd28b560744a5f4df7fef0532`,
private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`,
config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`.
Files are under `/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/`
with prefix `20260925_170339-hrms-v16_localhost-`; sizes: database 24,670,590
bytes, public files 10,240 bytes, private files 38,932,480 bytes, config 245
bytes.

The **2026-09-25 11:14:32** backup was taken with `--with-files` before the
Employee Lifecycle branch migration. `gzip -t` and both public/private
`tar -tf` checks passed. SHA-256: database
`9dcac7c73acbd29e7558ffc52ddbbfa0662f156033d3b593d5e5a9a004e2c41a`, public
files `407aa11be1920d8b2022cb054d30fb752d6a8a40fd28b560744a5f4df7fef0532`,
private files
`7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`, config
`904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`. Files
are under `/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/`
with prefix `20260925_111432-hrms-v16_localhost-`; sizes: database 20,389,261
bytes, public files 10,240 bytes, private files 38,932,480 bytes, config 245
bytes.

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


The 2026-09-24 15:41:56 backup was taken with `--with-files` before the Flexible Factory Work schema migration. Database gzip and both public/private tar archives passed integrity checks. SHA-256: database `0255986892466118b468d9a8b1daa168096f6400c6eb5f32f3edb928d5e4d23c` (15,940,427 bytes), public files `407aa11be1920d8b2022cb054d30fb7526d8a40fd28a5f4df7fef0532` (10,240 bytes), private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe` (38,932,480 bytes), config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73` (245 bytes).

The 2026-09-24 15:42:37 backup was taken with `--with-files` after the first standard migration stopped while importing the new child DocType controller. It records the partial standard-migration state before retry. Database gzip and both public/private tar archives passed integrity checks. SHA-256: database `ece81b7a2e4bae4db36016b618c80267567a385f7edb75e7ad2d032b2749052b` (15,940,427 bytes), public files `407aa11be1920d8b2022cb054d30fb7526d8a40fd28a5f4df7fef0532` (10,240 bytes), private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe` (38,932,480 bytes), config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73` (245 bytes). Files are under `/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/`.


The 2026-09-24 15:52:04 backup was taken with `--with-files` after the first standard schema migration completed and before applying the final approver-cancel permission updates. Database gzip and both public/private tar archives passed integrity checks. SHA-256: database `8a273d27d8d15ecd50b643cb9d51c447389683a43690836c9ce71c9ddd9017ed` (15,954,031 bytes), public files `407aa11be1920d8b2022cb054d30fb7526d8a40fd28a5f4df7fef0532` (10,240 bytes), private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe` (38,932,480 bytes), config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73` (245 bytes). Files are under `/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/`.

The 2026-09-25 10:29 backup for the maternity DocType migration was taken with `--with-files`; database `gzip -t` and public/private `tar -tf` checks passed. SHA-256: database `1eac1fc84f4188078123ab25950ce41a86e9c097a865e3579411daa44724aa14`, public files `407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532`, private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`, config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`. Files are under `/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/` with prefix `20260925_042901-hrms-v16_localhost-`; sizes: database 19,262,541 bytes, public files 10,240 bytes, private files 38,932,480 bytes, config 245 bytes.

The 2026-09-25 15:14 backup was taken with `--with-files` after the standard maternity schema migration and before synthetic integration cleanup/migration retry. Database `gzip -t` and both public/private `tar -tf` checks passed. SHA-256: database `7e877a8fa3b9e0425b193f83689eaec5897bb5956626c3e3f6e9d59b69d82248`, public files `407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532`, private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`, config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`. Files are under `/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/` with prefix `20260925_091421-hrms-v16_localhost-`; sizes: database 19,413,925 bytes, public files 10,240 bytes, private files 38,932,480 bytes, config 245 bytes.

The 2026-09-25 10:26 backup was taken with `--with-files` before the Employee Lifecycle synthetic integration retry. Database `gzip -t` and public/private `tar -tf` checks passed. SHA-256: database `49ed5d561ba4abe42df8b517c1018c84d14ca5ca54290604f919829ecc64a2f1`, public files `407aa11be1920d8b2022cb054d30fb752d6a8a40fd28b560744a5f4df7fef0532`, private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`, config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`. Files are under `/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/` with prefix `20260925_102545-hrms-v16_localhost-`; sizes: database 20,389,491 bytes, public files 10,240 bytes, private files 38,932,480 bytes, config 245 bytes.

The 2026-09-25 12:31 backup was taken with `--with-files` before the PR #20 lifecycle role-permission migration. Database `gzip -t` and both public/private `tar -tf` checks passed. SHA-256: database `8d9ec41802b8dc4f9d02a03a2eb2b103375ad93fc98f2423ba8292a5a32edefd`, public files `407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532`, private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`, config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`. Sizes: database 21,042,747 bytes, public files 10,240 bytes, private files 38,932,480 bytes, config 245 bytes. Files are under `/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/` with prefix `20260925_123055-hrms-v16_localhost-`.

The 2026-09-25 13:04 backup was taken with `--with-files` before cleanup of two confirmed synthetic payroll-test Companies left by earlier integration runs. Database `gzip -t` and both public/private `tar -tf` checks passed. SHA-256: database `879f5db0ed4883d655ae995dbeb2e99dd5edb1c146697939b1536a4cb42f9a42`, public files `407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532`, private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`, config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`. Sizes: database 21,854,634 bytes, public files 10,240 bytes, private files 38,932,480 bytes, config 245 bytes. Files are under `/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/` with prefix `20260925_130433-hrms-v16_localhost-`.

The 2026-09-25 17:54:24 backup was taken with `bench --site hrms-v16.localhost backup --with-files` before converting Tradexcel Shift Coverage and Tradexcel Joiners and Leavers from Query Reports to standard Script Reports. `gzip -t` and both public/private `tar -tf` checks passed. SHA-256: config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`, database `05dfbfaefb610c017ed4ba114836a213c31c838769dad066ef0bcc5f60b2aa82`, public files `407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532`, private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`. Files are under `/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/` with prefix `20260925_175417-hrms-v16_localhost-`; sizes: config 245 bytes, database 25,666,278 bytes, public files 10,240 bytes, private files 38,932,480 bytes.

The **2026-09-25 18:36:52** backup was taken with `bench --site hrms-v16.localhost backup --with-files` before converting Tradexcel Pay Component Register and Tradexcel Payroll Variance from Query Reports to standard Script Reports and retiring the app-wide report-run override. `gzip -t` and both public/private `tar -tf` checks passed. SHA-256: database `e480a934feacdc6a9ce1fdfae43b35edcc70368721e0cf5426ac98b91494fedb`, public files `407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532`, private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`, config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`. Files are under `/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/` with prefix `20260925_183646-hrms-v16_localhost-`; sizes: database 26,007,069 bytes, public files 10,240 bytes, private files 38,932,480 bytes, config 245 bytes.

The **2026-09-25 18:46:00** backup was taken with `bench --site hrms-v16.localhost backup --with-files` before converging read-only Company access for `Tradexcel Payroll Approver`, required by the report's permission-aware company guard. `gzip -t` and both public/private `tar -tf` checks passed. SHA-256: database `d70869620fc37fd9db27f463567b88f1d66761e9d8407c3d1bdbb03b385d39a3`, public files `407aa11be1920d8b2022cb054d30fb752d6a8a40fd28b560744a5f4df7fef0532`, private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`, config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`. Files are under `/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/` with prefix `20260925_184554-hrms-v16_localhost-`; sizes: database 26,018,221 bytes, public files 10,240 bytes, private files 38,932,480 bytes, config 245 bytes.

The **2026-09-25 19:10:28** backup was taken with `bench --site hrms-v16.localhost backup --with-files` before deleting four unreferenced test-only Salary Components left by earlier report integration attempts. `gzip -t` and both public/private `tar -tf` checks passed. SHA-256: database `7075ff3213ade2c147e6e6b7a5c99179313ef30867916e5461f612cf81398a93`, public files `407aa11be1920d8b2022cb054d30fb752d6a8a40fd28b560744a5f4df7fef0532`, private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`, config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`. Files are under `/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/` with prefix `20260925_191022-hrms-v16_localhost-`; sizes: database 26,394,823 bytes, public files 10,240 bytes, private files 38,932,480 bytes, config 245 bytes.

The **2026-09-25 19:35:18** backup was taken with `bench --site hrms-v16.localhost backup --with-files` before creating synthetic persona Users, User Permissions, and Employee records for permission/Workspace UAT. `gzip -t` and both public/private `tar -tf` checks passed. SHA-256: database `c9f9a7ec6241c0988f7431e9588ee145f8fa591bd9938f502096af3158eaa718`, public files `407aa11be1920d8b2022cb054d30fb7526d8a40fd28a5f4df7fef0532`, private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`, config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`. Files are under `/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/` with prefix `20260925_193512-hrms-v16_localhost-`; sizes: database 27,040,715 bytes, public files 10,240 bytes, private files 38,932,480 bytes, config 245 bytes.

The **2026-09-25 19:45:07** backup was taken with `bench --site hrms-v16.localhost backup --with-files` before converging the narrowly required read-only native Leave Allocation and Leave Balance Board access for Tradexcel Leave Approver. `gzip -t` and both public/private `tar -tf` checks passed. SHA-256: database `83ae662e901fe4e320f99da46cdfa16eaa508bd3c8cfc1b40cf2976adbe9a01f`, public files `407aa11be1920d8b2022cb054d30fb7526d8a40fd28a5f4df7fef0532`, private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`, config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`. Files are under `/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/` with prefix `20260925_194500-hrms-v16_localhost-`; sizes: database 27,040,979 bytes, public files 10,240 bytes, private files 38,932,480 bytes, config 245 bytes.

The **2026-09-25 19:47:40** backup was taken with `bench --site hrms-v16.localhost backup --with-files` before adding the required read-only Company context permission for Tradexcel Leave Approver, after the real report endpoint showed that explicit Company authorization is also required. `gzip -t` and both public/private `tar -tf` checks passed. SHA-256: database `1fa3bba17a99d6bf3ab6ff7207d9a811743388cd2687ef1632f63d46a8d37c67`, public files `407aa11be1920d8b2022cb054d30fb7526d8a40fd28a5f4df7fef0532`, private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`, config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`. Files are under `/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/` with prefix `20260925_194734-hrms-v16_localhost-`; sizes: database 27,053,343 bytes, public files 10,240 bytes, private files 38,932,480 bytes, config 245 bytes.

The **2026-09-25 19:49:36** backup was taken with `bench --site hrms-v16.localhost backup --with-files` before adding Employee read to the scoped Leave Approver persona and restricting its Leave Allocation grants to read/report only. `gzip -t` and both public/private `tar -tf` checks passed. SHA-256: database `c7e0fef7c6eb14233787892cb50be0e53a14feb13909ceb9a323df2a09419071`, public files `407aa11be1920d8b2022cb054d30fb7526d8a40fd28a5f4df7fef0532`, private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`, config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`. Files are under `/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/` with prefix `20260925_194930-hrms-v16_localhost-`; sizes: database 27,070,502 bytes, public files 10,240 bytes, private files 38,932,480 bytes, config 245 bytes.

The **2026-09-25 19:53:09** backup was taken with `bench --site hrms-v16.localhost backup --with-files` before adding explicit financial-role rows to the Payroll Register report after Workspace testing showed it otherwise rendered to an operational persona. `gzip -t` and both public/private `tar -tf` checks passed. SHA-256: database `0d00492b22e2abdb12f19c422730af2c0097dfb20453dd3fbf6c2cdaf735851f`, public files `407aa11be1920d8b2022cb054d30fb7526d8a40fd28a5f4df7fef0532`, private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`, config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`. Files are under `/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/` with prefix `20260925_195302-hrms-v16_localhost-`; sizes: database 27,079,768 bytes, public files 10,240 bytes, private files 38,932,480 bytes, config 245 bytes.

The **2026-09-25 20:54:37** backup was taken with `bench --site hrms-v16.localhost backup --with-files` before standard migration for native Shift Assignment Tool permissions. `gzip -t` and both public/private `tar -tf` checks passed. SHA-256: database `c82369eea7a30dc470f8eb5fad525dbd61715723805d15e87a71b446eabcb700`, public files `407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532`, private files `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe`, config `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73`. Files are under `/home/sanchita/frappe-bench-v16/sites/hrms-v16.localhost/private/backups/` with prefix `20260925_205430-hrms-v16_localhost-`; sizes: database 28,547,805 bytes, public files 10,240 bytes, private files 38,932,480 bytes, config 245 bytes.


## Older report boundary migration — 2026-09-26 10:11:24

Fresh `bench --site hrms-v16.localhost backup --with-files` before standard
migration clears stale Daily Attendance Summary/Workforce Anomaly Radar
JavaScript metadata. Database `gzip -t` and both public/private `tar -tf`
checks passed. No real payroll/employee configuration is being reconciled.

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `20260926_101050-hrms-v16_localhost-database.sql.gz` | 39,107,231 | `fe9b9f10667bab84ebc34372f74f4a86b07935af6a6c51f56f76ad47c99af938` |
| `20260926_101050-hrms-v16_localhost-files.tar` | 10,240 | `407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532` |
| `20260926_101050-hrms-v16_localhost-private-files.tar` | 38,932,480 | `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe` |
| `20260926_101050-hrms-v16_localhost-site_config_backup.json` | 245 | `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73` |

## Employee-linked permission convergence — 2026-09-26 17:35:09

Fresh `bench --site hrms-v16.localhost backup --with-files` before standard
migration for native Employee identity selection and employee-linked permission
hooks. Database `gzip -t` and both public/private `tar -tf` checks passed.
Only app permission metadata is converged; real HR/payroll data is not edited.

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `20260926_173459-hrms-v16_localhost-database.sql.gz` | 40,143,805 | `c27dafd2262348ece28bfcef54c0969f4d37e111c386bd43a8c65c8dfbd35f02` |
| `20260926_173459-hrms-v16_localhost-files.tar` | 10,240 | `407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532` |
| `20260926_173459-hrms-v16_localhost-private-files.tar` | 38,932,480 | `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe` |
| `20260926_173459-hrms-v16_localhost-site_config_backup.json` | 245 | `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73` |

## Action Board Workspace convergence — 2026-09-26 18:05:14

Fresh standard `backup --with-files` before installing the native Workspace
Custom HTML Block and removing overview cards/charts from that Workspace.
Database `gzip -t` and both archive `tar -tf` checks passed. No business data
reconciliation or production operation.

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `20260926_180505-hrms-v16_localhost-database.sql.gz` | 40,866,146 | `7b525415cac3a6e0421ae8933cd8d5789cdf5204d730583690213d0844f9caa6` |
| `20260926_180505-hrms-v16_localhost-files.tar` | 10,240 | `407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532` |
| `20260926_180505-hrms-v16_localhost-private-files.tar` | 38,932,480 | `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe` |
| `20260926_180505-hrms-v16_localhost-site_config_backup.json` | 245 | `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73` |

## Final Action Board script convergence — 2026-09-26 18:10:41

Fresh standard backup before repeating migration for the final source-backed
Workspace script. A post-migration parity test caught the newly added suppression
of denied-source drill-through buttons missing from the installed block. This
is a required source/metadata update, not a repeated business-data migration.
Gzip and both tar integrity checks passed.

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `20260926_181032-hrms-v16_localhost-database.sql.gz` | 40,960,003 | `c5fe28049615e71c2bcc8b1992472c1a5b5fa14b38cf3d0ffe1d4b04f38fc73a` |
| `20260926_181032-hrms-v16_localhost-files.tar` | 10,240 | `407aa11be1920d8b2022cb054d30fb7526d8a40fd28b560744a5f4df7fef0532` |
| `20260926_181032-hrms-v16_localhost-private-files.tar` | 38,932,480 | `7e39f916ff51d67098777943ebc7c8ab3e21e4e40e3c15a239a5745dccea65fe` |
| `20260926_181032-hrms-v16_localhost-site_config_backup.json` | 245 | `904f5adc249a1b178eb7f108ddb38b88c9ba13766931e7dd6de4b6837eeddd73` |
