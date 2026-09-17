# DeepSeek V4.1 Flash handoff — Tradexcel HR

Date: 2026-09-17. Status: implementation plan, **not** production acceptance. Private app repository: `shamrat05/tradexcel-hr`, baseline tag `baseline-source-2026-09-17`. SenseFace bridge is a separate private repository. Frappe 15.118.0 / ERPNext 15.119.3 / HRMS 15.63.3 / custom app 0.1.0. This versioned handoff and its audit register supersede older bench-level OpenCode notes wherever those still say the app has no Git baseline or the four read-only DeepSeek audits have not run.

## Outcome and non-negotiables

Build an understandable, production-grade HR system for Tradexcel Ceramics Ltd. (headquarters and factory) and Elegance Footwear Ltd. as **separate legal employers**. Native Employee, Checkin, Attendance, Shift Schedule/Assignment, Leave, Salary Structure/Assignment, Additional Salary, Payroll Entry/Slip, Employee Transfer and F&F documents are the records of truth. Custom code adds safe guided bulk operations, effective-dated exceptions, reconciliation, device mapping, scoped reports and a small daily Action Board. Selevo was a prototype: retain useful evidence, never let its values silently overwrite reviewed Frappe records.

Default policy changes apply to future dates. A historical change needs date range, impact preview, reason, separate approval and processed-period guard. Never auto-submit, cancel or delete payroll/leave/attendance. Never invent tax, PF/gratuity, leave encashment, disciplinary deduction, bank format, employee email or legal classification. Factory workers currently have an intended Tk 350 per paid 8-hour day; final cohort and samples still need HR/Finance sign-off. Worker ESS starts **supervisor-assisted**, with actor and approver separation, not fabricated accounts or impersonation.

## Current source/site baseline (do not overclaim)

The previous site read-only audit recorded 241 active Employees, 474 draft Salary Slips, 124 zero-gross worker drafts, 3 unsubmitted Leave Policies, no linked employee Users/emails and no custom role assignments. Recheck all counts before acting; they are a snapshot. F01 private app-only Git baseline and 13 focused tests were completed. Backup/restore rehearsal, app packaging of bench-local `sync/run_payroll.py` and `sync/reliable_bridge_worker.py`, CI/staging, real role tests and device pilot are **not** complete. The bridge does not implement the device-configuration endpoint called by the app. No Contabo go-live claim.

## Work order and acceptance

| Gate | Thin slices, in dependency order | Evidence required before next gate |
| --- | --- | --- |
| 0: recoverability | F02 separate-site backup/restore rehearsal; F03 six-persona role/company/branch matrix; F05a runtime inventory; F05b package audited payroll; F05c package/pin bridge adapter and separate listener; F04 clean-checkout CI and staging. Correct critical findings in `audit_findings_2026-09-17.md` first. | Restored counts, clean checkout, tests independent of `sync/`, denied cross-company access, no live data writes. No write-capable parallel agents before this gate. |
| 1: trust/core | D01 immutable Employee/source identity and duplicate review; D02 device-specific `(serial, PIN)` map and idempotent incremental punches from 2026-09-17; D03 guided missing-field fill template; B01 company-required cohort selector with include/exclude and snapshot; B02 preview/hash/draft-only apply with per-row savepoint/retry; B03 effective-dated intersecting-scope exception resolver. | Wrong company/duplicate/missing PIN, 1/250/1,000-row previews, stale preview, retry and historical-boundary tests. |
| 2: time/people | A01–A02 use native Shift Schedule/Assignment and roster for rotation, preview and overlap repair; A03 approved missed-punch Attendance Requests, never fake checkins; A04 daily OT/muster evidence; L01–L02 approved leave policy allocation and year-end review; H01–H03 transfer/exit/F&F, branded letters, probation/document alerts. | Per-day money/time edge cases (50/60/110/120 minutes), cross-midnight/transfer, leave balance conservation, scoped manager views, sample documents. |
| 3: pay/ESS | P01 reconcile each staff salary and assignment without Tk 18,000 fallback; P02 resolve zero-gross drafts and signed worker wage/OT samples; P03 one-time Additional Salary bonuses/arrears/deductions; P04 increments/letters; P05 native Payroll Entry, approval, payment/GL/bank output; E00 supervisor-assisted worker requests; E01–E02 verified individual ESS pilot later. | Two-company totals and employee-period reconciliation; no zero-pay submission; preparer cannot approve; no private salary exposure; signed Finance samples. |
| 4: insight/launch | R01 role-scoped Script Reports; R02 OT/muster/leave/bonus/variance/register print pack; R03 bank/cash output after approved bank format; U01 grouped click-through Action Board; U02 branded print; O01 staged Contabo HTTPS/ADMS deployment; O02 final delta sync, cutover/rollback runbook. | Real-browser 360/768/desktop checks, report/export denial, PDF review, live device pilot, alerts, backup restore and signed go/no-go. |

Keep scope small: one S/M slice per agent, normally at most five owned files, failing test first, review after each slice, coordinator merges. Shared `install.py`, schemas and site migrations have one coordinator; no two agents write the same worktree or database. Parallelize **read-only** review now; later independent shift vs leave, lifecycle vs payroll, and reports vs workspace only after prerequisites. Do not duplicate native Frappe HRMS engines.

## OpenCode dispatch contract

Model: `opencode-go/deepseek-v4.1-flash` on OpenCode 1.18.31. Use `--pure` and a custom permission-checked agent in a sanitized, isolated app-only worktree. For audit, allow only read/glob/grep/list and deny edit/bash/task/external directory/network, including secrets, site data and `.env`. Verify effective permissions before dispatch. The audited CLI used PowerShell even for WSL UNC paths; do not assume Bash. A prompt is **not** a sandbox. Never run default unrestricted Build or `--auto` against the live bench.

Task brief template (attach only the specific task excerpt and relevant code, never raw site data):

```text
TASK: <gate ID and one outcome>.
CONTEXT: Frappe/ERPNext/HRMS v15 versions above. Native records canonical. Separate companies. Supervisor-assisted workers first.
OWNERSHIP: <exact isolated-worktree paths, <=5>. Shared installer/schema proposals go to coordinator, not this agent.
ACCEPTANCE: <three testable criteria, including role/company/date/retry as relevant>.
RULES: failing test first; smallest slice; future default and preview/approval for historical changes; no live site, secret, external data, auto-submit/cancel/delete, invented legal rates/users; stop on ambiguity.
OUTPUT <=500 words: status; files; tests to run; migration/data effect; risks or exact owner question. Never claim runtime success from source-only inspection.
```

Coordinator runs tests on source/staging, independently reviews diff and migration, checks secrets/scope, commits one slice, then updates completion evidence. Audit-only agents may be run concurrently; implementation agents wait for Gate 0. Preserve the detailed coordinator checklist in `/home/sanchita/frappe-bench/tasks/todo.md`, capability map and `opencode_handoff.md` as planning references; they are outside this app-only Git repository and must be copied in sanitized form before external handoff.

## Human decisions before enabling modules

HR/Finance must approve individual salaries, factory worker cohort and OT examples, tax/PF/gratuity, leave carry/encashment, disciplinary process, letterheads/signatories, bank file specifications, actual role assignments, worker identity proof and Contabo domain/device serials. Until then, controls stay disabled or draft-only. A successful unit test, visible button or source snapshot is never production acceptance.
