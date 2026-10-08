> Historical proposal/checklist. Current code and dated evidence supersede unchecked boxes here. See [current roadmap](roadmap_current_2026-09-27.md) and [campaign ledger](sol_completion_state_2026-09-26.md). No new generic bulk engine, competing dashboard or custom rail is required. Old letters/reminder/template proposals outside the current 1–40 contract are OUT_OF_CURRENT_ROADMAP.

# Workforce Suite delivery gates

Status: proposed, not production complete. This app serves Example Company A (HO and factory) and Example Company B as distinct Frappe Companies. Native Frappe HR/ERPNext records remain canonical; prototype Selevo snapshots are evidence for review, not an overwrite source.

1. **Source and recovery:** private app-only Git baseline, secret/PII exclusion, backup and separate-site restore rehearsal. Package audited payroll/bridge worker code and tests out of bench-local `sync/`; pin the standalone SenseFace bridge separately. Verify a clean app checkout and staging installation. No parallel write agents before this gate.
2. **Identity and data trust:** reconcile Employee identity, device-specific serial+PIN mapping and source provenance. Incremental punch replay from 2026-09-17 must be idempotent and preserve each worker's home branch; ambiguous mappings go to a review queue.
3. **Safe batch core:** company-required cohort scope, effective-dated policy/exception selection, read-only per-row preview, stale-preview check, role separation, audit and retryable draft-only apply. Historical recalculation requires explicit range, reason and approval.
4. **Operational slices:** native shift roster/rotation, leave assignment/year-end, attendance regularization, people lifecycle and branded documents, worker/staff salary reconciliation, wages/OT, one-time pay, payroll approvals, scoped reports and print packs. Each slice needs money/date/permission tests and real staging proof.
5. **Desk and access:** one clear Workforce Suite Action Board with grouped queues and working drill-down. For workers without verified login contacts, provide supervisor-assisted requests first with separate approver and no impersonation; individual ESS follows verified identity.
6. **Go-live:** finance-approved payroll samples, two-company UAT, staged SenseFace replay and real-device test, HTTPS/ADMS hardening, monitoring, backup/restore, final delta reconciliation and signed cutover/rollback.

Current blockers: draft payroll includes zero-gross worker slips; leave policies are unsubmitted; ESS has no linked employee users; the bridge repository does **not** yet implement the app's `/api/v1/devices/{serial}/configure` call. Do not call these features ready merely because a UI link or test exists.

Bridge audit and exact compatibility gap: [SenseFace bridge contract](../docs/senseface_bridge_contract.md).

The coordinator's detailed capability map, ordered checklist and OpenCode handoff live in the bench-level `tasks/` directory until reviewed for inclusion here. Never attach raw site data or credentials to agent briefs.
