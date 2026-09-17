# Tradexcel HR operations roadmap

The comprehensive proposed delivery plan is now `tasks/plan.md` with `tasks/capability-map.md`, `tasks/todo.md`, and `tasks/opencode_handoff.md` at the bench root. This file records the earlier implementation slice; use the new task checklist for remaining work.

Status: in progress, 17 September 2026. This is an implementation ledger, not a claim of production readiness.

First-slice verification: 12 focused pytest checks pass, including Frappe Desk report endpoints, live SQL against both companies, workspace links, and payroll-report role denial. Browser visual validation remains outstanding because Chrome DevTools is not configured. New raw-SQL reports are System-Manager-only until explicit company/branch row scoping is implemented; the report filters alone are not an access-control boundary.

## Guardrails

- Scope every run by company and optional branch/department/designation/category/tenure; show the exact employee count and per-person before/after values.
- Default effective date is future. Past dates or any date with payroll/attendance already processed require a separate, explicit reconciliation preview.
- Preview is read-only; apply requires an HR role, an unchanged source snapshot, an idempotency key, and a saved audit document. Batch errors must identify individual rows without silently skipping them.
- Draft first for money, separation, fines, leave balance, and disciplinary actions; a different authorized approver submits. No automatic Bangladesh tax/PF/gratuity/fines without a company-approved policy.
- Native HRMS documents own their data. The custom app adds orchestration, preview, exceptions, and reporting; it must not fork native payroll, leave, or shift engines.

## Capability map and delivery order

| Area | Native record/tool | Missing Tradexcel layer | State |
| --- | --- | --- | --- |
| Shift bulk/rotation | Shift Assignment Tool, Shift Schedule, roster | conflict preview, scoped patterns, exception overrides, old-assignment closure, 90-day regeneration | Native Desk links and read-only overlap/missing coverage board added; custom layer pending |
| Leave annual allocation | Leave Control Panel, Leave Policy Assignment, Leave Allocation | policy cohorts, preview, exceptions, year-end carry/expiry/encashment | Native Desk link added; custom layer pending |
| Salary revision | Salary Structure Assignment Tool, Salary Structure Assignment | percent/amount cohort preview, tenure/individual exceptions, letters | Native Desk link added; custom layer pending |
| Bonus/arrears/deduction | Additional Salary | bulk draft run, component/period checks, integration with custom draft payroll | Pending; do not pay from this yet |
| Attendance correction | Attendance Request, Employee Checkin | row-level upload validation, duplicate/punch evidence, approval | Native Desk link added; upload pending |
| Transfer/separation/F&F | Employee Transfer, Employee Separation, Full and Final Statement | effective-date batch, clearance, payout approval | Native Desk links added; batch pending |
| Master data | Data Import | export-to-fill template, field validation, mismatch/duplicate review | Native Desk link added; guided template pending |
| Payslips | Payroll Entry, Salary Slip | connect existing drafts or safely regenerate in Payroll Entry; approval/email/print batch | Pending; 474 current drafts must not be auto-submitted |
| Registers | native reports + custom query reports | OT hours/rate, muster, late/fine decision, leave card, bonus/arrears/deductions, bank advice | Pay component line register implemented; remaining registers pending |
| Variance/movement | Salary Slip, Employee | monthly comparison, joiner/leaver visibility | Implemented and endpoint-tested |
| Letters | Employment Contract, Letter Head, Print Format | approved templates for appointment/confirmation/increment/promotion/warning/show-cause/termination/certificates/NOC | Pending |
| Calendar | scheduler + native HRMS | probation, document expiry, annual increment, leave year-end and monthly pack review queue | Pending |

## Acceptance gates for every batch action

1. Test empty scope, mixed companies, overlapping effective dates, stale preview, duplicate retry, partial invalid rows, and role denial.
2. Verify in Desk with Administrator and a least-privilege role. A visible button is not evidence of permission correctness.
3. Reconcile sample totals and all exceptions against real documents; export a review CSV and retain who approved.
4. Back up before historical changes; never delete submitted/cancelled data or submit payroll as part of a UI/navigation migration.

## Open production blockers

- 124 August/September worker drafts have zero gross pay and require attendance/wage reconciliation.
- No approved tax/PF/gratuity rules or payment/bank/GL configuration; these must be optional per company, not invented.
- No role assignments to real users beyond Administrator. The approval workflow cannot operate for staff until assigned.
- Existing custom draft payroll is not wired to native Payroll Entry; adding Additional Salary alone does not guarantee it appears in those drafts.
