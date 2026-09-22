# v16 role, mobile attendance, and face-match audit

Date: 2026-09-22

Scope: v16 staging site `hrms-v16.localhost` only. The v15 site and any live
environment were not changed.

## Findings

- All 15 `Tradexcel *` roles exist.
- All 15 have zero assignments to real Frappe Users (`Has Role.parenttype =
  User`). Role rows attached to Reports and Pages are not user assignments.
- `Tradex Mobile Event`, `Tradexcel Attendance Policy`, and the
  `tradexcel-mobile-attendance` Page exist.
- `Tradex Face Match Settings` is a Single DocType. It was present in source
  but had not been migrated into the staging schema before this audit.
- The staging site had no face model files. A test policy named
  `LOCAL FACE DISTANCE TEST - DELETE` and the single face-match setting were
  therefore disabled to prevent unusable face verification from affecting
  attendance.

## Safe staging operations

1. Created backup:
   `sites/hrms-v16.localhost/private/backups/20260922_153546-hrms-v16_localhost-*`
2. Ran `bench --site hrms-v16.localhost migrate`.
3. Disabled the stale test attendance policy and face-match setting.
4. Cleared the site cache.

## Implementation guard

Saving enabled `Tradex Face Match Settings` now validates all of the following:

- the optional OpenCV provider is installed in the active bench environment;
- both configured model paths are site-relative;
- both detector and recognizer model files exist inside the site directory.

Missing runtime prerequisites are reported when the setting is saved instead
of appearing later as a mobile check-in failure. Runtime matching also remains
fail-closed and records a clear error.

## Verification

- Face-match unit tests: `1 passed` for the staging-focused test invocation.
- Python compilation: passed.
- Mobile page and DocTypes: present after migration.
- Face matching is disabled until verified model files are installed and
  tested against an approved validation set.

## Go-live role action

An Administrator must assign real named users through the User form's Roles
table before removing broad administrative access. Do not assign every role to
everyone and do not make ordinary employees System Managers. Start with the
smallest role set for HR, attendance, payroll, finance, device operations,
approvals, and audit; add branch or department scope using User Permissions
after testing it with a non-admin account.

## Face-match deployment action

Install the optional app extra in the production bench, upload the two pinned
ONNX models, verify their documented SHA-256 values, create a single-face
reference image, and run a small acceptance set before enabling any policy.
Plain selfie capture does not require this optional dependency. Face matching
must not be treated as a mathematically perfect liveness or identity proof.
