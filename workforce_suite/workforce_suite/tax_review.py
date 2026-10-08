"""Controlled source review of native HRMS Income Tax Slabs."""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import now_datetime


def _require_reviewer():
    roles = set(frappe.get_roles(frappe.session.user))
    if frappe.session.user == "Guest" or (
        frappe.session.user != "Administrator"
        and not roles.intersection({"System Manager", "Workforce Owner/Director"})
    ):
        frappe.throw(_("A System Manager or Workforce Owner/Director must review native tax configuration."), frappe.PermissionError)


@frappe.whitelist()
def approve_income_tax_slab(name: str, source_reference: str, notes: str = ""):
    _require_reviewer()
    source_reference = (source_reference or "").strip()
    if not source_reference:
        frappe.throw(_("Enter the authoritative tax source reference before approval."))
    slab = frappe.get_doc("Income Tax Slab", name)
    from workforce_suite.workforce_suite.company_context import assert_company_access

    assert_company_access(slab.company, require_explicit_scope=True)
    if slab.docstatus != 1:
        frappe.throw(_("Submit the native Income Tax Slab before reviewing it."))
    slab.flags.workforce_tax_review_action = True
    slab.custom_workforce_review_status = "Approved"
    slab.custom_workforce_source_reference = source_reference
    slab.custom_workforce_review_notes = (notes or "").strip()
    slab.custom_workforce_reviewed_by = frappe.session.user
    slab.custom_workforce_reviewed_at = now_datetime()
    slab.save(ignore_permissions=True)
    return {"name": slab.name, "status": slab.custom_workforce_review_status}


def validate_income_tax_slab_review(doc, method=None):
    provenance_fields = (
        "custom_workforce_review_status", "custom_workforce_source_reference",
        "custom_workforce_reviewed_by", "custom_workforce_reviewed_at", "custom_workforce_review_notes",
    )
    previous = frappe.db.get_value(
        "Income Tax Slab", doc.name, list(provenance_fields), as_dict=True
    ) if doc.name else None
    changed = previous and any(previous.get(field) != doc.get(field) for field in provenance_fields)
    approved = doc.get("custom_workforce_review_status") == "Approved"
    if changed or approved:
        _require_reviewer()
        from workforce_suite.workforce_suite.company_context import assert_company_access

        assert_company_access(doc.company, require_explicit_scope=True)
    if changed and not doc.flags.get("workforce_tax_review_action"):
        frappe.throw(_("Use the Approve Tax Configuration action to change tax review provenance."))
    if approved:
        if doc.docstatus != 1:
            frappe.throw(_("Submit the native Income Tax Slab before reviewing it."))
        if not doc.custom_workforce_source_reference:
            frappe.throw(_("Enter the authoritative tax source reference before approval."))
        if changed:
            doc.custom_workforce_reviewed_by = frappe.session.user
            doc.custom_workforce_reviewed_at = now_datetime()
    elif changed:
        frappe.throw(_("Tax review provenance can only be changed through the controlled review action."))
