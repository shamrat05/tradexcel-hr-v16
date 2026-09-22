# Mobile attendance time integrity

## Production rule

Mobile timestamps arrive as ISO-8601 instants. The service converts an aware
timestamp to the Frappe system timezone (`Asia/Dhaka` on the Tradexcel site)
before removing timezone metadata for MariaDB's naive `Datetime` field. A UTC
event at `18:30` therefore becomes Dhaka `00:30` on the following date.

The server receipt timestamp is retained as evidence. The captured timestamp is
trusted automatically only inside the current receipt-time policy's **Online
Clock Trust Window** (default: 5 minutes). The separate **Maximum Offline
Acceptance Age** (default: 72 hours) controls how old an event may be received;
it is not a trust window.

## Quarantine boundary

Events outside the trust window, missing captured time, or outside the maximum
acceptance age are either rejected when the policy says `Block` or created as
`Flagged` evidence with:

- native HRMS `skip_auto_attendance = 1`;
- Tradexcel Evidence Review = `Pending`;
- Location Status = `Time Review Required`;
- captured time, receipt time, skew and the integrity reason retained.

Flagged events do not resolve historical business policy, create Attendance, or
settle field-duty allowances until released. This prevents a browser clock from
choosing weaker historical GPS, selfie, face-match, shift, or allowance rules.

Authorized HR/supervisor users use the Employee Checkin form's **Evidence
Review** actions. Approval records reviewer and note, sets native
`skip_auto_attendance = 0`, and releases an OUT duty event for allowance
settlement. Rejection keeps native auto-attendance disabled. Both actions are
idempotent and server-authorized; manually editing a label is not a release.

## Validation checklist

1. Run the focused service tests and the full app suite.
2. Run `bench migrate` on the staging site so custom fields and policy fields
   exist.
3. Test a trusted online punch, a delayed punch, a missing-time punch, a
   rejected punch, and an approved punch.
4. Test UTC/Dhaka midnight rollover and an overnight shift.
5. Run Android airplane-mode E2E: queue IN/OUT, reconnect, verify the same
   `sync_id`, captured time, quarantine status, and no allowance before review.

The Android airplane-mode test remains a release gate; it must be run against
the connected device before merging.
