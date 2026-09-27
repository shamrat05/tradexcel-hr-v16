# Tradexcel Field Attendance v1

## Objective

Provide one production attendance flow for terminal punches, mobile field duty, occasional outside work, and approved work-from-home. All sources create standard `Employee Checkin` records. Standard HRMS auto-attendance remains the attendance calculator.

## Capability map

| Module | Responsibility | Depends on |
|---|---|---|
| policy | Effective-dated attendance/location/travel rules | existing policy exceptions |
| duty | Daily/roster field, outside, and WFH assignments | policy, Shift Location |
| mobile | GPS, selfie, offline-safe check-in/out | policy, duty |
| evidence | GPS quality, selfie, face match, audit | mobile, Employee Checkin |
| travel | approved zone/km/manual allowance | duty, evidence, payroll |
| visibility | calendar, live-last-location, exceptions, allowance reports | all modules |

Build order: policy -> duty -> mobile/evidence -> travel -> visibility.

## Rules

1. Terminal punches never require GPS or selfie.
2. Mobile check-ins use the same Employee Checkin doctype and feed standard Attendance.
3. Office Only, Field Only, Hybrid, and Work From Home are configurable policy modes.
4. Outside work is accepted and flagged by default; it does not silently erase attendance.
5. Automated face matching is advisory evidence, never the sole attendance/payroll decision.
6. Continuous tracking is opt-in and limited to an active Field Duty session.
7. Allowances are payable only from an approved Field Duty/Travel record and are written to payroll as an auditable Additional Salary.
8. Policy changes are future-effective by default; historical recalculation requires explicit date-bounded preview and confirmation.

## Acceptance criteria

- A SenseFace terminal punch succeeds without latitude/longitude.
- A mobile employee can check in/out with GPS, optional selfie, and a policy snapshot.
- A roster location and a temporary Field Duty location are both evaluated.
- Multiple active locations are evaluated; no first-row-only behavior.
- GPS outside the permitted area creates a visible flag according to policy.
- GPS quality and timestamp integrity are evaluated server-side. Stale events inside the maximum acceptance age may be quarantined; events beyond it are blocked. Duplicate sync IDs remain idempotent.
- An approved configured per-km/fixed-area policy and released duty evidence may produce one idempotent draft native Additional Salary; Manual mode does not automatically create money.
- A user with permission can view the last known location and selfie evidence with timestamp and audit trail.
- Face-match score/model/threshold are recorded when enabled; a mismatch does not automatically deduct pay.
- Existing terminal and payroll tests remain green.

## Security and privacy defaults

- Server-side validation is authoritative; browser validation is only UX.
- Location/selfie access requires explicit role permission and is logged.
- No public bridge endpoint or unauthenticated live-location endpoint.
- Raw GPS evidence and selfies use configurable retention; no always-on tracking by default.
- Offline submissions preserve device time, server receipt time, and sync status.

## Non-goals for the first implementation slice
