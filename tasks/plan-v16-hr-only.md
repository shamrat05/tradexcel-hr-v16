# Frappe HRMS v16 HR-only Migration Plan

## Scope

Create a separate Frappe/ERPNext/HRMS v16 staging bench and site, migrate a verified copy of the current HR data, and make the Tradexcel HR workspace/navigation usable without changing the current v15 site. ERPNext remains installed as an HRMS dependency, but the visible product surface is HR-focused. No production cutover is included in this phase.

## Safety boundaries

- Current `hrms.localhost` v15 remains untouched.
- Use a separate bench and site, with separate database and ports.
- Take and record a fresh source-site backup before copying data.
- Never copy credentials, token files, raw snapshots, or employee exports into Git.
- Preserve the existing v15 app changes in Git before v16 compatibility work.
- Treat migration as successful only after counts and critical HR flows reconcile.

## Architecture decisions

1. Use Frappe/ERPNext/HRMS v16 branches with matching major versions.
2. Keep `tradex_hr` as a separate custom app, with a v16 dependency branch and no duplicated native HR ledgers.
3. Keep ERPNext installed but hide non-HR workspaces and restrict non-HR roles; HRMS payroll still relies on ERPNext services.
4. Use the existing Workspace as the HR command center and add a persistent 248px navigation rail with a 64px icon-only mode through the custom app bundle.
5. Make navigation data-driven and route only to verified DocTypes, reports, pages, and workspaces.

## Tasks

### Phase 1: Source preservation and v16 bench

- [ ] Record a fresh source-site backup and checksum in `BACKUPS.md`.
- [ ] Create and push the dedicated custom-app branch `feature/hrms-v16-hr-only`.
- [ ] Update only the custom app's Frappe/ERPNext dependency range for v16 and add compatibility tests.
- [ ] Provision a separate v16 bench/site with Python 3.14 and Node 24; do not touch `hrms.localhost`.
- [ ] Install matching Frappe, ERPNext, HRMS, and `tradex_hr` v16 branches.

### Checkpoint: v16 foundation

- [ ] `bench version` reports all v16 major versions.
- [ ] Site login, Desk boot, HRMS install, and custom app migration succeed.
- [ ] Current v15 site remains healthy and unchanged.

### Phase 2: Data migration and reconciliation

- [ ] Restore the source backup into the isolated v16 site.
- [ ] Run migration patches and record failures without skipping them.
- [ ] Reconcile employees, companies, branches, departments, designations, checkins, attendance, shifts, leave, salary structures, assignments, and draft payroll.
- [ ] Verify device mappings and mobile attendance without contacting physical devices.
- [ ] Produce a migration report with source count, target count, mismatch, and disposition for every canonical HR ledger.

### Phase 3: HR-only information architecture

- [ ] Implement grouped navigation: Home, People, Time & Attendance, Leave, Payroll, Operations, Devices, Analytics, Administration.
- [ ] Use verified Frappe routes and native DocTypes; missing features must show a clear disabled/coming-soon state, never a dead link.
- [ ] Add fixed 248px rail, 64px collapse mode, keyboard-accessible toggle, active-route highlighting, and mobile fallback.
- [ ] Improve the HR workspace with grouped sections, meaningful icons, compact shortcuts, and drill-down links.
- [ ] Hide non-HR workspaces from normal HR users without removing ERPNext from the bench.

### Checkpoint: desk usability

- [ ] Navigation remains visible on workspaces, lists, reports, forms, attendance, and payroll routes.
- [ ] Expanded/collapsed state persists per user and does not cover content.
- [ ] Keyboard navigation and responsive widths work at 320px, 768px, 1024px, and 1440px.
- [ ] Browser console has no new errors.

### Phase 4: Validation and handoff

- [ ] Run the app's focused and full test suites.
- [ ] Run v16 migration smoke tests and critical HR flow checks.
- [ ] Verify no secrets or raw employee data are staged.
- [ ] Commit atomic changes and push the branch.
- [ ] Provide a go/no-go report; do not claim production readiness until separate UAT and rollback rehearsal pass.

## Risks

| Risk | Mitigation |
|---|---|
| v16 API/schema incompatibility | Isolated site, matching branches, migration logs, focused tests |
| Data loss or count drift | Fresh backup, checksum, per-ledger reconciliation, no live writes |
| Custom app branch mismatch | Pin branch/commit in v16 bench and record it in the migration report |
| Dead or misleading shortcuts | Route registry and navigation smoke tests |
| ERPNext UI clutter | Hide non-HR workspaces by role; do not remove dependency |
| Unsupported custom code | Run the complete existing test suite before claiming stability |

## Success definition

The v16 staging site boots cleanly, preserves reconciled HR data, supports the critical attendance/leave/payroll flows, and presents a coherent HR-only Desk. The current v15 site remains an intact rollback reference.
