"""Gap-driven bulk resolvers. One entry point so every surface (reports, lists) can fix in place.

Safety: never blind-applies. The caller sends the exact selected employees; the resolver is
idempotent (skips already-resolved rows) and can attach an existing Tradexcel Policy Exception
scoped to each employee.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate, now, today

FIELD_RESOLVERS = {
    "Missing Department": "department",
    "Missing Designation": "designation",
    "Missing Holiday List": "holiday_list",
}

EXCEPTION_CLONE_FIELDS = (
    "exception_type", "rule_name", "employee_category", "include_child_scope",
    "min_tenure_months", "field_name", "value", "salary_component",
    "component_action", "component_amount", "attendance_setting", "attendance_value",
    "tax_action", "holiday_list", "shift_type", "leave_type", "extra_days",
    "effective_to", "enforcement_note",
)


def _parse(value):
    return frappe.parse_json(value) if isinstance(value, str) else value


@frappe.whitelist()
def resolve_gap(gap, employees, values=None):
    """Apply the resolver for a gap to the selected employees only."""
    employees = list(dict.fromkeys(_parse(employees) or []))
    values = _parse(values) or {}
    if not frappe.has_permission("Employee", "write"):
        frappe.throw(_("Not permitted to update employees"), frappe.PermissionError)
    if not employees:
        frappe.throw(_("No employees selected"))

    if gap == "No Shift Assignment":
        return _assign_shifts(employees, values)

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


def _assign_shifts(employees, values):
    shift_type = values.get("shift_type")
    start_date = getdate(values.get("start_date") or today())
    exception_name = values.get("exception") or None
    if not shift_type:
        frappe.throw(_("Shift Type is required"))
    if not frappe.db.exists("Shift Type", shift_type):
        frappe.throw(_("Unknown Shift Type: {0}").format(shift_type))
    if not frappe.has_permission("Shift Assignment", "create"):
        frappe.throw(_("Not permitted to create Shift Assignments"), frappe.PermissionError)
    if not frappe.has_permission("Shift Assignment", "submit"):
        frappe.throw(_("Not permitted to submit Shift Assignments"), frappe.PermissionError)
    if exception_name and not frappe.db.exists("Tradexcel Policy Exception", exception_name):
        frappe.throw(_("Unknown policy exception: {0}").format(exception_name))

    created = skipped = exceptions = 0
    errors = []
    for index, name in enumerate(employees):
        savepoint = f"tradex_bulk_shift_{index}"
        frappe.db.savepoint(savepoint)
        try:
            if not frappe.has_permission("Employee", "write", name):
                frappe.throw(_("Not permitted to update Employee {0}").format(name), frappe.PermissionError)
            existing = frappe.get_all(
                "Shift Assignment",
                filters={"employee": name, "docstatus": 1, "start_date": ["<=", start_date]},
                fields=["name"],
                order_by="start_date desc, creation desc",
                limit=1,
            )
            if existing:
                skipped += 1
                continue
            doc = frappe.get_doc({
                "doctype": "Shift Assignment",
                "employee": name,
                "shift_type": shift_type,
                "start_date": start_date,
                "company": frappe.db.get_value("Employee", name, "company"),
            })
            doc.insert()
            doc.submit()
            created += 1
            if exception_name and _clone_exception(exception_name, name, start_date, doc.name):
                exceptions += 1
        except Exception as exc:
            frappe.db.rollback(savepoint)
            frappe.log_error(frappe.get_traceback(), "Tradexcel bulk shift fix")
            errors.append({"employee": name, "error": str(exc)})
    frappe.db.commit()
    return {"updated": created, "skipped": skipped, "exceptions": exceptions, "errors": errors}


def _clone_exception(exception_name, employee, effective_from, reference):
    """Scope the chosen exception to one employee, tied to the created shift assignment."""
    if frappe.db.exists("Tradexcel Policy Exception",
                        {"employee": employee, "shift_type": frappe.db.get_value(
                            "Tradexcel Policy Exception", exception_name, "shift_type")}):
        return None
    src = frappe.get_doc("Tradexcel Policy Exception", exception_name)
    doc = frappe.new_doc("Tradexcel Policy Exception")
    for field in EXCEPTION_CLONE_FIELDS:
        doc.set(field, src.get(field))
    doc.company = frappe.db.get_value("Employee", employee, "company")
    doc.employee = employee
    doc.branch = doc.department = doc.designation = None
    doc.employee_category = None
    doc.effective_from = effective_from
    doc.reason = _("Bulk fix via Employee Data Gaps: {0}").format(src.rule_name or src.name)
    doc.applied_reference = reference
    doc.preview_summary = _("Shift exception applied with bulk shift assignment")
    doc.previewed_at = now()
    doc.preview_signature = "bulk-fix"
    doc.insert()
    return doc.name
