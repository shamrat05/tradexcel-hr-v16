# 06 — Security, privacy, roles and segregation of duties

## Security model

Navigation visibility is not authorization.

Every sensitive action requires all of:

~~~text
authenticated named user
+
role capability
+
record scope
+
workflow state
+
server-side permission check
~~~

## Named users only for privileged work

Shared privileged accounts destroy accountability.

Prohibit shared accounts for:

- HR edits;
- attendance corrections;
- payroll changes;
- salary assignments;
- approvals;
- live-location access;
- face-reference management;
- imports;
- statutory-rule approval;
- payment/accounting actions.

Kiosk/device identities may be shared devices, but they must not become shared
human approver identities.

## Role capability vs record scope

Example:

~~~text
Tradexcel Factory Supervisor
  capability: review attendance / field duty
  scope:
    company: Tradexcel Ceramics Ltd.
    branch: TCL Factory
    departments: [Kiln, Packing]
~~~

A direct API call outside scope must fail even if the button is hidden.

Use native Frappe User Permissions or an explicitly tested server-side scope
service. Do not rely on client filters.

## Segregation of duties

Minimum maker/checker separation for financial-impact changes:

| Action | Maker | Checker/approver |
|---|---|---|
| salary assignment / pay-basis change | HR/Payroll maker | independent payroll approver |
| backdated compensation | payroll maker | payroll approver/director per policy |
| attendance correction affecting pay | attendance maker | correction approver |
| OT manual correction | supervisor/HR maker | OT/payroll approver |
| manual deduction | payroll maker | authorized checker |
| bank/payment destination change | authorized maker | finance checker where policy requires |
| payroll submission | Payroll Manager | Payroll Approver / Director workflow |
| payroll cancellation/correction | restricted maker | higher approval |
| statutory rule activation | compliance/admin maker | authorized compliance/legal/accounting approver |
| mass operational override | HR/operations maker | independent approver |

Current workflows already set allow_self_approval = 0 for attendance, leave and
payroll. Preserve that property and extend it to new money-impacting workflows.

## Session and credential controls

For privileged roles:

- MFA/strong authentication where operationally practical;
- session revocation when user is disabled/terminated;
- rate limiting and secure recovery;
- no secrets in repo, logs, screenshots or agent prompts;
- credentials/tokens stored in Frappe secrets/environment, not Data fields where a
  Password/secret mechanism exists;
- audit role changes and User Permission changes.

## Import security

Imports must not bypass normal validation.

Pattern:

~~~text
upload
-> parse
-> validate through domain service
-> preview old/new values
-> permission/scope check
-> maker/checker if high risk
-> commit
-> immutable result log
~~~

Never grant broad Data Import access merely to make onboarding easier.

## Sensitive personal data

Current Bangladesh law must be reviewed before production processing. The
Bangladesh Personal Data Protection Act, 2026 treats biometric data and real-time
geolocation as sensitive personal data. The app currently processes both categories
through face/selfie and live-location features.

Therefore the system needs explicit governance for:

- purpose;
- lawful processing basis / consent where required;
- minimum necessary fields;
- collection notice;
- role-based access;
- retention period;
- secure storage;
- export/download restrictions;
- deletion/archival;
- incident/breach response;
- processor/vendor contracts where applicable;
- employee grievance/review route.

Do not turn on face matching or active-duty location tracking just because the
feature exists.

## Data minimization

### Biometric terminals

Prefer storing identity mapping and event metadata rather than raw biometric
templates in the HRMS when the device/bridge can keep template data outside the
site.

### Face matching

Store only what is needed for the approved purpose. Evaluate whether the source
selfie must be retained after verification; if retained, document why and for how
long.

### Live location

Do not continuously track employees who are not on an approved duty requiring it.
A manager dashboard should not expose historical movement by default.

## Retention

Current Attendance Policy has retention_days. That setting is incomplete until a
scheduled retention process exists.

Retention job requirements:

1. select records strictly older than the effective retention cutoff;
2. never delete a record under legal hold, open dispute, audit hold or unresolved
   payroll/reconciliation case;
3. detach/delete private evidence safely;
4. leave a minimal audit tombstone if policy/law requires;
5. log counts and failures;
6. support dry-run;
7. test restore/replay implications;
8. require separate retention classes for checkin evidence, selfies, live
   location, audit/security logs and financial records.

Do not apply one 90-day number to every HR record.

## Live-location access

The existing service uses a supervisor-role set. Harden it with:

- company/branch/department scope;
- current approved/in-progress Field Duty filter;
- only employees whose policy permits tracking;
- bounded result count;
- no organization-wide historical trail for ordinary supervisors;
- audit of sensitive location reads if required by policy;
- optional explicit "last known location age" warning.

## Face-match safety

Face recognition introduces false positives/false negatives and sensitive-data risk.

Rules:

- face mismatch never equals misconduct;
- no automatic payroll deduction/absence solely from face score;
- threshold/model version recorded;
- poor image/no face/provider failure has distinct states;
- authorized alternative verification path exists;
- reference image change is high-risk and audited;
- model update requires validation data and approval;
- image files are private and scoped.

## Audit trail

For each high-risk action record at least:

~~~yaml
actor_user:
actor_roles:
request_id:
timestamp:
source_ip_or_session_context:
doctype:
document:
action:
old_values:
new_values:
effective_date:
reason:
evidence_refs:
approval_refs:
rule_version:
~~~

Do not put passwords, biometric templates or unnecessary sensitive payloads in
audit text.

## Grievance / dispute

An employee must have a route to challenge attendance/payroll evidence that does
not depend exclusively on the same supervisor whose action is disputed.

The system should support:

- dispute/reference number;
- confidentiality-aware access;
- evidence attachment;
- reviewer outside direct chain where policy requires;
- no automatic retaliation labels;
- linkage to correction/reconciliation outcome.

## Security test minimum

- unauthorized role hits API directly -> denied;
- supervisor reads another department live location -> denied;
- employee submits checkin for another employee -> denied;
- reused sync ID for another employee -> denied;
- maker self-approves controlled action -> denied;
- disabled user/session cannot continue privileged work;
- report role list never silently becomes unrestricted;
- import cannot write out-of-scope employee;
- private selfie URL cannot be attached by another user;
- path traversal for model/evidence file rejected;
- XSS/HTML escaping on evidence/reason fields;
- CSRF and POST method enforcement on writes.
