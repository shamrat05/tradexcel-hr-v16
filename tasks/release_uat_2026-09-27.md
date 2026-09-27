# Release browser / physical-device contract — 2026-09-27

Backend tests are not browser/device acceptance. Earlier campaign automation
proved HR Manager (Bangla), Department Manager and Worker at 1440/390 widths,
native sidebar, no rail/overflow/page errors, and report checkbox → preview →
DRAFT Attendance Request → native review list with zero Attendance mutation.
The release rehearsal repeats this smoke on the final engineering tree.
This does not replace real staff sign-off or every native dialog/export.

## Persona browser checklist

For each: log in as the actual reviewed persona; verify Company context, permitted
Branch/Department results, empty/error states, keyboard focus and back navigation.
Try a known out-of-scope synthetic URL/API, not a real employee identifier.
Verify reports/print/export against native permission bits; a hidden button alone
is not authorization. Record browser/viewport, release SHA, actor and evidence.

| Persona | Expected work | Must not expose |
| --- | --- | --- |
| Owner/Director | Company overview, exceptions, approved financial review | Other unauthorized Company |
| HR Manager | Joiners, Employee, shifts, draft attendance/SSA/OT/leave setup | Self-approval of protected money/corrections |
| Attendance Officer | Daily board, correction drafts, shift assignment, mobile review | Salary/bank fields and financial reports |
| Factory Supervisor | Scoped work/attendance evidence | Salary and bulk payroll mutation |
| Branch Manager | Branch-scoped operational review | Other Branch or salary amounts |
| Department Manager | Department-scoped operational review | Other Department or salary amounts |
| Payroll Manager | SSA preparation, readiness, draft payroll | Independent self-approval bypass |
| Payroll Approver | Review/submit protected native drafts | Maker action solely from approver role |
| Finance | Payment/accrual/reconciliation and bank work | Unrelated Company |
| Compliance | Reviewed statutory evidence/read scope | Unreviewed legal assumptions or operational mutation |
| Device Admin | Device/mapping diagnosis, scoped Employee select | Employee financial form or payroll mutation |
| Attendance Correction Approver | Native request list review/bulk submit | Creating own protected corrections |
| Leave Approver | Native Leave Application review | Entitlement administration by implication |
| Import Reviewer | Approved import review | Unrestricted Employee/lifecycle salary import |
| Worker linked/unlinked | Own supported ESS; unlinked fails closed | Directory, other worker evidence, management Action Board |

Test correct disabled-user logout/denial, dual-role maker/checker, explicit native
shares, stale preview, permission change while queued, retry after partial error,
actual print/export and all role-relevant native tools. Shares/approver assignments
must be reviewed when Company/Branch/Department scope changes.

Phone-critical: attendance capture/review, leave request/approval, supervisor
exceptions and supported own ESS. Phone-useful: Action Board/drill-through and
joiner/exit status. Desktop-first: payroll, salary setup, large imports, bank and
accounting reconciliation. Do not approve payroll phone usability from one narrow
viewport test. Bangla operator text uses Frappe translation; native technical
setup remains English where translation would obscure meaning.

## Physical Android / biometric acceptance — NOT EXECUTED

No physical device was contacted in this campaign. Use a separate test device,
synthetic employee mapping and approved network, never production terminals.

| Scenario | Expected chain / pass condition |
| --- | --- |
| Airplane mode → delayed sync within limit | Captured time retained, received time separate; one checkin/evidence event; no automatic payable money |
| Delay beyond configured offline limit | Configured Flag/Block applied; quarantined/review evidence, no silent payable Attendance |
| Future/old device clock | Timing review/block; server receipt cannot disguise captured time |
| Replay same event / biometric backlog | Idempotent ingress; no duplicate Checkin/Attendance/payroll effect |
| Device outage/reconnect | Health/backlog visible; bounded retry/authentication; no lost/duplicated identity mapping |
| Midnight shift | Native timestamp/Shift Assignment resolution; correct work date, no hand-coded calendar shortcut |
| Transferred Employee | Serial+PIN/Employee scope correct; historical Company/time preserved |
| Deactivated/relieved Employee | Captured employment date checked; post-relief payable work blocked |
| Ambiguous mapping | Explicit exception queue; no guessed Employee |
| Configure endpoint | Auth required; bridge profile saved is NOT proof terminal configuration applied |

Record device → bridge → Employee Checkin → review → Attendance → payroll blocker
for every case. Raw punches never authorize money. HTTPS/authentication/limits,
physical terminal setting confirmation and actual owner policy remain release
gates. Optional face matching needs OpenCV/model/acceptance evidence only when
company policy enables it; its absence alone does not block basic attendance.
