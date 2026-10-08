# Field attendance production runbook

## Non-negotiable invariants

1. Keep `HR Settings.allow_geolocation_tracking` disabled. Native HRMS applies
   that switch to every `Employee Checkin`; enabling it would reject SenseFace
   punches because terminals do not send GPS.
2. Terminal/bridge rows must carry a device id or an explicit `Terminal` or
   `Bridge` source. They bypass mobile policy enrichment.
3. Employee users do not receive direct `Employee Checkin` create/write/delete
   permission. Mobile check-ins use the audited server method and standard
   `Employee Checkin` storage.
4. Captured time is retained for event/shift semantics; server receipt time,
   skew and original integrity reason are separate evidence. The receipt-time
   policy decides trust. Untrusted evidence is quarantined from Attendance.
5. Face matching is disabled until OpenCV, pinned models, reference photos,
   and a local validation set are ready. Provider failure is fail-closed for a
   face-match-enabled policy; it never becomes an unreviewed “match”.

## HR setup order

1. Create named employee users and link `Employee.user_id`.
2. Create `Shift Location` records with real coordinates/radii.
3. Submit one `Workforce Attendance Policy` per scope. Prefer future-effective
   dates; changing history requires an explicit bounded recalculation.
4. Create/submit `Workforce Field Duty` for a field day or office errand. A
   temporary duty can include multiple locations and active-duty tracking.
5. Open the Mobile Attendance page. It requests browser GPS and creates the
   same standard check-in used by terminal attendance.
6. For active tracking, keep the page open while the duty is in progress. The
   browser sends pings at the policy interval; the server enforces the duty
   window and interval.
7. Only trusted or explicitly approved mobile OUT evidence under an approved
   per-km/fixed-area policy may queue one draft
   `Additional Salary`. It is idempotent by field-duty key and remains a draft
   for payroll preparation.

## Device acceptance test

- Punch IN and OUT on each SenseFace device with no GPS.
- Verify a new `Employee Checkin` has the terminal/bridge source and device id.
- Verify no mobile policy, selfie, or GPS validation was invoked.
- Verify auto-attendance links the punch to the expected shift.
- Repeat the same bridge payload and confirm the bridge's existing duplicate
  protection still prevents a second check-in.

## Mobile acceptance test

- Check in inside the assigned zone; expect `Inside Zone`.
- Check in inside a farther overlapping permitted zone; expect the matching
  zone, not a false outside result.
- Test outside behavior for `Accept`, `Flag`, and `Block`.
- Submit an invalid/low-accuracy fix under `Block`; expect rejection.
- Re-send the same sync id; expect the original record, not a duplicate.
- Submit an existing sync id as another employee; expect permission denial and
  no record disclosure.
- Check out from an approved duty and verify exactly one draft allowance.

## Face-match acceptance test

- Install the optional face-match dependency and verify both model SHA-256
  values in `docs/face_match_setup.md`.
- Configure `Workforce Face Match Settings`, upload a single-face reference photo,
  and test same-person, different-person, no-face, and multi-face selfies.
- Confirm the score, threshold, provider, and result are recorded.
- Confirm a provider outage blocks a face-match-enabled check-in instead of
  marking it matched.
- Treat face matching as evidence, not perfect liveness/authentication. Do not
  make an automatic pay deduction from a mismatch alone.

## Verification commands

```bash
cd /home/sanchita/frappe-bench-v16
env/bin/python -m pytest apps/workforce_suite/workforce_suite/tests -q
```

Do not expose the Frappe mobile API or live-location page without HTTPS,
authenticated users, private file storage, backups, and a tested restore.

## Receipt-time integrity and review (release correction, 2026-09-27)

Mobile API timestamp strings require `Z` or an explicit timezone offset. UTC is
converted to the configured site timezone before storage. Default automatic
trust window is five minutes around receipt; configurable range 0–1440. Outside
that window, `Flag` creates Pending evidence and `Block` rejects. Missing capture
time is never Trusted. The maximum offline age (default 72 hours, range 1–720)
is a hard rejection boundary in both past and future directions.

Pending evidence keeps `skip_auto_attendance=1`; it cannot create payable native
Attendance, satisfy bulk correction evidence or settle travel allowance. An
authorized scoped reviewer opens the native Employee Checkin and chooses Approve
Evidence or Reject Evidence with a reason. Approval reloads the stored receipt
policy and separately resolves historical business policy, rerunning all evidence
checks. Approval releases native auto-attendance; rejection keeps quarantine.
Final decisions cannot be reversed through these endpoints. Reviewers do not
receive broad Checkin write permission.

Test delayed replay, missing time, timezone rollover, hard expiry and both final
review states. Verify Pending blocks Attendance Correction and allowance, while
approved OUT may queue existing settlement after commit. Offline selfie Blobs
are removed after replay success, rejection or expiry at the next application
opportunity; deletion while a closed browser never runs is not guaranteed.

Schema deployment requires BACKUPS.md, a fresh verified `--with-files` backup,
then standard staging `bench migrate` and `clear-cache`. Never copy these steps
to production without its separately approved release/cutover procedure.
