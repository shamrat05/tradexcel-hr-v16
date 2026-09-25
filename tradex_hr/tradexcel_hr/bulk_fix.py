"""Narrow field resolvers for Employee Data Gaps.

Shift scheduling is handled by the native HRMS Shift Assignment Tool.
"""

from __future__ import annotations

import frappe
from frappe import _

FIELD_RESOLVERS = {
    "Missing Department": "department",
    "Missing Designation": "designation",
    "Missing Holiday List": "holiday_list",
}

def _parse(value):
    return frappe.parse_json(value) if isinstance(value, str) else value


@frappe.whitelist()
def resolve_gap(gap, employees, values=None):
    """Apply a supported Employee field resolver to the selected Employees."""
    employees = list(dict.fromkeys(_parse(employees) or []))
    values = _parse(values) or {}
    if gap == "No Shift Assignment":
        frappe.throw(_("Use Bulk Shift Assignment for this gap."), frappe.ValidationError)
    if not frappe.has_permission("Employee", "write"):
        frappe.throw(_("Not permitted to update employees"), frappe.PermissionError)
    if not employees:
        frappe.throw(_("No employees selected"))

    fieldname = FIELD_RESOLVERS.get(gap)
    if not fieldname:
        frappe.throw(_("No bulk resolver for gap: {0}").format(gap))
    value = values.get(fieldname)
    if not value:
        frappe.throw(_("A value is required to resolve: {0}").format(gap))

    updated = skipped = 0
    errors = []
    for index, name in enumerate(employees):
        savepoint = f"tradex_bulk_fix_{index}"
        frappe.db.savepoint(savepoint)
        try:
            if not frappe.has_permission("Employee", "write", name):
                frappe.throw(_("Not permitted to update Employee {0}").format(name), frappe.PermissionError)
            doc = frappe.get_doc("Employee", name)
            if doc.get(fieldname):
                skipped += 1
                continue
            doc.set(fieldname, value)
            doc.save()
            updated += 1
        except Exception as exc:
            frappe.db.rollback(savepoint)
            frappe.log_error(frappe.get_traceback(), "Tradexcel bulk employee fix")
            errors.append({"employee": name, "error": str(exc)})
    frappe.db.commit()
    return {"updated": updated, "skipped": skipped, "exceptions": 0, "errors": errors}
