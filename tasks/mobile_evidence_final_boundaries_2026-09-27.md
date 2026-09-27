# Mobile evidence final boundaries — 2026-09-27

Parent: PR #44, `fix/release-lineage-security-closure`,
`ba403b36a42143a427559b0ee8dd5ec4c77f5687`. Correction branch:
`fix/mobile-evidence-final-boundaries`. PR #45 is open, draft, unmerged and
mergeable on the expected base.

## Reproduced before correction

- Executed the production offline cleanup functions in Node 24 with an
  in-memory IndexedDB boundary. With `context === null`, a retryable event
  captured 80 hours earlier was stripped by the implicit 72-hour fallback,
  including its selfie/GPS payload, before the server's configured 120-hour
  maximum could load.
- A site-backed test using synthetic scoped personas showed both a Tradexcel
  HR/Attendance Officer and Branch Manager could POST a mobile Checkin for a
  different scoped Employee. A second test showed `attach_selfie()` accepted
  another owned private File and changed the Checkin's canonical selfie URL.
- Installed permission checks show the ordinary attendance officer has no
  Employee Checkin write permission. The test matrix now checks HR Manager,
  attendance officer, Branch Manager and Attendance Correction Approver; none
  has native Checkin write. The controller hook nevertheless protects derived
  evidence if a future role is granted write.
- The prior approval route had no Checkin-owner independence check. With only
  that guard temporarily removed from a local source copy, the site integration
  reproduced `DID NOT RAISE` when the owner had gained the approver role. The
  corrected test creates flagged evidence as a linked Worker, adds the review
  role later, and proves that owner cannot approve it; an independent scoped
  reviewer succeeds. Self-rejection remains allowed: it cannot release
  evidence into payable Attendance, and rejected evidence remains skipped.

## Changes

Offline age expiry waits for a valid server-provided policy maximum. Final or
non-retryable items can still lose sensitive payload immediately. Malformed
capture times are retained until policy context exists. The upload URL is
persisted before the network-sensitive request and replay reuses it.

`mobile_checkin`, `location_ping` and `attach_selfie` now require the linked
Employee self identity (Administrator remains a control). Supervisor read,
review, live-location and Attendance Request workflows retain their own scoped
authority. Field-duty settlement has a separate employee-or-scoped-approver
actor check for its queued internal path.

Mobile selfies must resolve to a private `/private/files/` File owned by the
actor (Administrator control allowed), with a safe relative path. Attachment
finalization requires the mobile Checkin's already-recorded canonical URL and
only writes File attachment metadata. It is idempotent for the same Checkin,
rejects another record, and never changes the Checkin URL. An upload followed by
server rejection may leave an unattached private File; no unsafe automatic
File deletion was added.

The existing Mobile Checkin save guard now protects sync ID, GPS source,
location status, assigned location/distance, face result/score and integrity
note as immutable derived evidence. Native Shift/Attendance linkage remains
mutable for HRMS auto attendance. Explicit review actions retain their narrow
controlled updates.

No DocType, Custom Field, DocPerm, hook, or Workspace metadata changed; no
migration or backup was needed. No broad Checkin write permission was added.

## Validation

Focused: 51 passed across the mobile page, field attendance, correction and
release-security integration suites. The stale identity-helper test was updated
to call `_assert_employee_self`.

Full: 666 passed, 0 skipped, 109 warnings. Compileall passed; 61 tracked app
JSON files parsed; all app source checks passed (239 Python, 61 JSON, 30 JS).
Node 24.15.0 syntax check, `bench build --app tradex_hr`, staging release smoke
(13 standard reports, DB port 3307) and `git diff --check` passed.

Tests use unique synthetic Users, Files, Employees, Checkins, Field Duty and
Location Ping records and clean them through native document APIs. A queued
backlog was inspected by job method/target existence only: stale native
`delete_dynamic_links` jobs all referenced already-deleted test records and four
`create_contact` jobs referenced deleted synthetic persona Users. Those
synthetic cleanup jobs were completed/removed; unrelated route-index work was
left queued. No live company data or configuration was changed.

No browser/device UAT was performed. Physical Android/offline behavior remains a
release gate. GitHub Actions run `36308028426` for the correction head failed
before any job steps ran (`source-and-pure-tests`, zero steps); remote CI is not
claimed passed. Local validation remains the evidence for this correction.
