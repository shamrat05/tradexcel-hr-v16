# Workforce Suite — Native action placement policy (phase 1)

Status: **independent review branch** `feat/workforce-native-actions`.
Based on the observed v16 Desk report/form implementation and native
`frappe.ui.Page` /`frm.add_custom_button` APIs.

## Usability goals

1. The next common task should need one action click once the user has
   reached the appropriate page. Keep exactly one relevant high-frequency
   custom button visible where practical.
2. Don't stretch the report toolbar. A single short native group label
   (e.g. **More actions**, **Employee workflows**, **Device actions**)
   replaces multiple individual custom buttons.
3. Never hide or delete an existing capability to reduce the button count.
   Keep all callbacks, required prompts, confirm dialogs, roles, site scope,
   and backend permission enforcement.
4. Do not take ownership of the native Report **Refresh**, built-in export,
   print, auto-save, form Save/Submit/Cancel or Desk navigation actions.
5. Keep dangerous operations behind a descriptive label and the same server
   validation and confirmation steps they already have.
6. Existing users should be able to discover unfamiliar actions by their
   textual name, not an unlabeled icon or hover-only menu.
7. Native menu groups must work by keyboard, with Frappe's built-in
   mobile overflow behavior, at 125%-200% browser zoom, and in light/dark mode.

## Action inventory and final placement

| Page | One-click visible | Native group / secondary | When it appears |
| --- | --- | --- | --- |
| Employee Data Gaps | **Review Employees** | **More actions**: Open Salary Assignment Tool; Open Bulk Shift Assignment; Create Employee Transfer; Create Employee Promotion; View Employee Onboardings | Role-specific items retain their existing HR/attendance role checks; one-Employee validation on Transfer and Promotion |
| Biometric ID Audit | **Assign Biometric ID** | **Device actions**: Copy Biometric to Device | Existing server permissions and transfer confirmation |
| Joiners and Leavers report | Native report toolbar | **Employee workflows**: View Employee Onboardings; View Employee Separations | HR-maker roles only |
| Payroll Readiness report | **Prepare Payroll** (existing native primary action) | **More actions**: Review Structure Migration; **Open Payroll Entry for retry** stays visible when a failed run needs attention | Payroll Manager only; existing readiness disable checks remain authoritative |
| Payroll Entry form | **Finalize Payroll**, **Retry Unsubmitted Salary Slips** or **Prepare Payment** (stage-specific) | **Payment records**: Open Payment Entry; Open Bank Transaction | Native readiness responses and already established state/permission checks |
| Biometric Device form | **Check Bridge Health** | **Device actions**: Push Configuration to Bridge | Existing form state and backend guard |
| Employee form | **Calendar** | **Onboarding** and **Separation** existing groups | Existing role/employee lifecycle rules |
| Employee Checkin | Native form actions | **Evidence Review** existing group: Approve Evidence / Reject Evidence | Quarantined evidence and authorized reviewer only |
| Attendance Period | State-specific **Finalize Attendance** or **Reopen Attendance** | Native form actions | Existing write permissions, confirmation and finalization safeguards |
| Daily Attendance Board | **Prepare Attendance Corrections** | Native report controls | Existing scope and bulk preview |
| Shift Coverage | **Review / Assign Shift** | Native report controls | Existing eligible state |
| Overtime Slip list | **Prepare Overtime Drafts** | Native list controls | Existing Manager role and preview before creation |
| All remaining reports/forms | Native Refresh, Save, Submit, filter/export/menu controls | Any existing single custom action remains in its present location | No broad global UI rewrite |

On pages without a custom primary action, native Refresh and other native
controls retain their original order and semantics.

## Why this is resilient to framework updates

- Report actions use the supported `report.page.add_inner_button(label, callback, group)` API.
- Form actions use `frm.add_custom_button(label, callback, group)`.
- The existing payroll readiness primary action continues to use
  `page.set_primary_action`, and its safety disable logic is unchanged.
- No core Frappe/ERPNext/HRMS files, global event listeners, DOM selectors,
  toolbar CSS overrides or monkey patches are introduced.
- The grouped-button API already handles narrow-screen action-menu behavior
  in Frappe v16. Actual WCAG keyboard, touch and zoom behavior still needs
  browser testing after deployment.
- Source-level action-contract tests invoke the actual JS action registrations
  without Frappe; Frappe v16 browser verification remains a release gate.

## Next phases — intentionally not part of the first action-layout commit

- Curate the native Workspace Sidebar navigation without losing any route.
  Strict "opening one section closes the others" is not an established native
  configuration contract in v16. Prefer tested native sections, or separate
  native module Workspaces rather than intercepting Desk sidebar events.
- Provide a contextual `Fix this issue` workflow in app-owned work queues
  (do not replace native DocType forms or the report data table).
- Review high-density table column order, filter prominence, sticky important
  identifiers, light/dark contrast and responsive behavior separately.
- Audit navigation and complete tasks with keyboard only and at 200% zoom.
- Validate that role-restricted users never see unauthorized action links;
  server permissions remain the final enforcement layer.

See: https://github.com/frappe/frappe/blob/version-16/frappe/public/js/frappe/ui/page.js
and https://github.com/frappe/frappe/wiki/Migrating-to-version-16.
