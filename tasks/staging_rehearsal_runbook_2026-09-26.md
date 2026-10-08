# Staging rehearsal — 2026-09-26

1. Approve Business Configuration Gate; provision reviewed test personas only.
2. Confirm target site/DB endpoint, exact app/framework/bridge SHAs. Production
   credentials/devices are not used. Keep scheduler disabled during engineering.
3. Take `bench --site hrms-v16.localhost backup --with-files`; verify gzip/tars,
   sizes/SHA-256 and record BACKUPS.md. Standard migrate and clear-cache only.
4. Run `bash apps/workforce_suite/scripts/run_release_integration.sh` from v16 bench.
   This executes native synthetic domain E2E, all persona negatives and live
   isolated 31-row queue coverage. Explicit cleanup is mandatory.
5. Execute browser/device checklist in `release_uat_2026-09-27.md`. Record actual
   person, environment, timestamp, expected/actual result, evidence and defects.
6. On a separate authorized production-like clone, HR/Finance reconcile real
   roster/authority/attendance/leave and accounting configuration. No engineering
   test is permission to submit real payroll.
7. Record delta totals and compare backups; review all exceptions before parallel
   payroll. Failure blocks promotion; do not bypass readiness with Administrator.
