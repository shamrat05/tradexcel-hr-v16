# Production cutover — 2026-09-26

**PRODUCTION ONLY; not executed or authorized by this engineering campaign.**

Prerequisites: reviewed integrated release, Business Configuration Gate signed,
real persona/browser/device UAT, parallel payroll reconciliation, tested off-box
restore, approved downtime/rollback owner and reconciliation checkpoints.

Provision supported MariaDB, Redis, workers (short/default/long), scheduler,
Socket.IO, reverse proxy/HTTPS, least-privileged service/database accounts, managed
secrets, TLS/allowlisted authenticated bridge connectivity, log rotation/alerts,
backup retention/off-box copies and resource monitoring. Pin Node 24.15.0 and
Python 3.14 for this tested v16 family; do not upgrade to v17 during cutover.

Freeze writes; capture final source/config/data versions and verified database,
public/private files and securely escrowed encryption key. Deploy pinned sources,
install dependencies, build assets, standard migrate/cache clear, then smoke,
role checks, bridge dry-run/idempotency and native financial reconciliation.
Enable workers/scheduler deliberately only after owner approval.

Rollback means restore the compatible database/files/config together to the
approved point, not merely git checkout older code after schema migration.
Reconcile all post-checkpoint punches/payments before resuming; prevent duplicate
external ingestion. Never silently discard committed financial history.
