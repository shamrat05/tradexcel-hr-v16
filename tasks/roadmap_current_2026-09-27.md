# Current roadmap reconciliation — 2026-09-27

Current evidence supersedes old unchecked migration-era proposals. Labels below
are concise domain descriptions of the campaign's 1–40 checklist, not new product
requirements. Steps 21–22 group the report/persona foundations; 31–40 distinguish
release engineering from unexecuted real-world gates. COMPLETE is not synonymous
with production approval. No known unaddressed reproduced engineering defect is
being relabeled as a company decision. Annual-leave legal accrual and native
employer-contribution benefit activation remain explicitly gated capability/UAT
limitations; no automatic legal money has been implemented to hide them.

| Step | Domain | Status | Evidence/PR | Remaining work | Type |
| --- | --- | --- | --- | --- | --- |
| 1 | v16 source/runtime | ENGINEERING_COMPLETE_REAL_UAT_REMAINS | #2, #29, release contract | Pinned source installs; production deployment/recovery separate | release/production |
| 2 | Reports/basic readiness | ENGINEERING_COMPLETE_REAL_UAT_REMAINS | #21–23, #33 | 13 scoped Script Reports; real operator/export UAT | browser/configuration |
| 3 | Mobile/offline evidence | ENGINEERING_COMPLETE_REAL_UAT_REMAINS | #3, #37–39 | Physical clock/offline/replay/device UAT | physical device |
| 4 | Attendance/payroll boundary | SCOPED_COMPLETE_CONFIGURATION_REMAINS | #4, #28 | Review/submit real Attendance and finalize periods | configuration/data |
| 5 | Explicit pay basis | SCOPED_COMPLETE_CONFIGURATION_REMAINS | #5, #21, #26 | Resolve 17 missing effective SSAs; owner-approved amounts | HR/finance |
| 6 | Native payroll drafts | ENGINEERING_COMPLETE_REAL_UAT_REMAINS | #6 | Real configured-company payroll rehearsal | configuration/UAT |
| 7 | Payroll readiness/operator flow | ENGINEERING_COMPLETE_REAL_UAT_REMAINS | #7, #26, #28, #35 | Real operator/configured payroll UAT | configuration/UAT |
| 8 | Financial readiness | SCOPED_COMPLETE_CONFIGURATION_REMAINS | #8 | Approved tax/account/period setup | finance |
| 9 | Submit/accrual | ENGINEERING_COMPLETE_REAL_UAT_REMAINS | #9, #40 | Real Finance comparison and approved account mapping | finance/UAT |
| 10 | Payment/reconciliation | ENGINEERING_COMPLETE_REAL_UAT_REMAINS | #10, #40 | Bank configuration, authorized real payment reconciliation | finance/UAT |
| 11 | Corrections/arrears | ENGINEERING_COMPLETE_REAL_UAT_REMAINS | #11 | Reviewed historical adjustment cases | HR/finance UAT |
| 12 | Separation/F&F | SCOPED_COMPLETE_CONFIGURATION_REMAINS | #12 | Real settlement/access shutdown review | HR/finance |
| 13 | Statutory exit | SCOPED_COMPLETE_CONFIGURATION_REMAINS | #13 | Approved legal regime/classification/source rules | legal |
| 14 | Recruitment/joiners | ENGINEERING_COMPLETE_REAL_UAT_REMAINS | #14 | Real HR onboarding/direct-hire UAT | configuration/UAT |
| 15 | Wage floors | SCOPED_COMPLETE_CONFIGURATION_REMAINS | #15 | Approved Gazette/category/location/effective rules | legal |
| 16 | Benefits | PARTIAL | #16 | Installed HRMS lacks native employer-contribution accrual; PF/Progoti money remains blocked. Applicability also requires legal/Finance decision | native capability + legal/finance |
| 17 | Working time/OT/holiday/leave | SCOPED_COMPLETE_CONFIGURATION_REMAINS | #17, #30–31 | Approved limits/OT types/leave entitlements/holidays | owner/legal |
| 18 | Factory attendance policy | SCOPED_COMPLETE_CONFIGURATION_REMAINS | #18 | Approved flexible/early-release policy; no automatic assumption | owner/legal |
| 19 | Maternity/welfare | SCOPED_COMPLETE_CONFIGURATION_REMAINS | #19 | Approved effective rules and review applicability | legal/HR |
| 20 | Employee lifecycle | ENGINEERING_COMPLETE_REAL_UAT_REMAINS | #20 | Native per-record workflow; real HR browser UAT | UAT |
| 21 | Operational/financial report foundation | ENGINEERING_COMPLETE_REAL_UAT_REMAINS | #21–23, #33 | Actual staff/export UAT; no Query override remains | UAT |
| 22 | Persona access foundation | ENGINEERING_COMPLETE_REAL_UAT_REMAINS | #24, #34, #39 | Real staff identities/scopes/shares not provisioned | configuration/UAT |
| 23 | Bulk operations | ENGINEERING_COMPLETE_REAL_UAT_REMAINS | #25–32, #37, #41 | One route/domain; native per-record lifecycle intentional; configured real volume UAT | configuration/UAT |
| 24 | Action Board | ENGINEERING_COMPLETE_REAL_UAT_REMAINS | #35, #38, #41 | Role/scoped existing readiness adapters; broader actual-persona UAT | UAT |
| 25 | Native navigation | ENGINEERING_COMPLETE_REAL_UAT_REMAINS | #36, #38 | Native sidebar; rail removed; broader staff UAT | UAT |
| 26 | Operator usability/localization | ENGINEERING_COMPLETE_REAL_UAT_REMAINS | #38 | Bangla/key workflows proven; actual operators/native dialogs/export UAT | UAT |
| 27 | Security/privacy | ENGINEERING_COMPLETE_REAL_UAT_REMAINS | #21–24, #33–34, #37, #39 | Native shares, real role assignment, retention approval and export UAT | configuration/UAT |
| 28 | Accounting reconciliation | ENGINEERING_COMPLETE_REAL_UAT_REMAINS | #9–12, #40 | Actual accounts/bank configuration and Finance reconciliation | finance/UAT |
| 29 | Compliance/payroll reports | ENGINEERING_COMPLETE_REAL_UAT_REMAINS | #15–23, #33, #40 | Legal classifications and actual Finance/export review | configuration/UAT |
| 30 | Measured performance/async | ENGINEERING_COMPLETE_REAL_UAT_REMAINS | #41 | 240-row read measurements/live 31-row worker; real payroll concurrency capacity remains | volume UAT |
| 31 | Source/deploy reproducibility | PARTIAL | release contract | App neutral source install passed; pre-existing ERPNext banking/yarn.lock drift requires external dependency review and clean target build | external source/release evidence |
| 32 | Migration/restore contract | ENGINEERING_COMPLETE_REAL_UAT_REMAINS | release contract/BACKUPS.md | Separate 3307 restore passed; off-box production disaster/key restore remains | production recovery |
| 33 | Synthetic E2E/CI contract | PARTIAL | release contract | 629 local native tests and 11 isolated pure tests passed; GitHub runner blocked by account billing before execution | external CI account + release/UAT |
| 34 | Physical device/browser acceptance | BLOCKED_PHYSICAL_DEVICE_BROWSER | release_uat_2026-09-27.md | 3 synthetic browser personas proven; physical terminals/Android and full staff UAT remain | physical/browser |
| 35 | Business configuration approval | BLOCKED_OWNER_LEGAL_FINANCE | business_configuration_gate_2026-09-26.md | Owner/HR/Finance/legal approve roster/policies/accounts/scopes | business |
| 36 | Stack review/merge authorization | PRODUCTION_ONLY | pr_merge_runbook_2026-09-26.md | Human review and explicit merge authorization; no PR merged | release approval |
| 37 | Production-like staging rehearsal | BLOCKED_OWNER_LEGAL_FINANCE | staging_rehearsal_runbook_2026-09-26.md | Approved business configuration and actual staff UAT | business/UAT |
| 38 | Parallel payroll sign-off | BLOCKED_OWNER_LEGAL_FINANCE | parallel_payroll_runbook_2026-09-26.md | Independent real payroll/accrual/payment reconciliation | finance |
| 39 | Production cutover | PRODUCTION_ONLY | production_cutover_runbook_2026-09-26.md | Infrastructure, restore, freeze/delta/rollback and signed go-live | production |
| 40 | Post-go-live controls | PRODUCTION_ONLY | post_go_live_controls_2026-09-26.md | Operate monitoring/backups/access/payroll controls | production |
