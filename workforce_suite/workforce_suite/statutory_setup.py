"""Explicit draft layout setup. Never an installation or migration hook."""
from copy import deepcopy
import hashlib

import frappe
from frappe import _
from frappe.utils import getdate

from workforce_suite.workforce_suite.statutory_access import check_company
from workforce_suite.workforce_suite.statutory_forms import spec_for


@frappe.whitelist(methods=["POST"])
def prepare_draft_layout(company, form_code, effective_from, branch=""):
    """Reuse readable existing configurations without changing administrator edits.

    Dates and establishment are selected by the operator. No legal applicability,
    salary mapping, registration, translation or approval is inferred.
    """
    if not frappe.has_permission("Workforce Statutory Print Layout", "create"):
        frappe.throw(_("You cannot configure statutory layouts."), frappe.PermissionError)
    branch = branch or ""
    check_company(company)
    frappe.get_doc("Company", company).check_permission("read")
    if not effective_from:
        frappe.throw(_("Select the draft effective date explicitly."))
    date = getdate(effective_from)
    if branch:
        doc = frappe.get_doc("Branch", branch)
        doc.check_permission("read")
        if doc.get("company") != company:
            frappe.throw(_("Branch must belong to the selected Company."))
    source = spec_for(form_code)
    if source["kind"] == "Evidence Only":
        frappe.throw(_("This source is external evidence, not an employer-generated form."))
    # Serialize the explicit setup action across users/tabs, without creating a
    # new completion/state table or retaining private information in Redis keys.
    key = hashlib.sha256(f"{company}\0{branch}\0{form_code}".encode()).hexdigest()
    with frappe.cache.lock("workforce_statutory_setup:" + key, timeout=60, blocking_timeout=10):
        table = frappe.qb.DocType("Workforce Statutory Print Layout")
        from frappe.query_builder.functions import IfNull
        existing = (frappe.qb.from_(table).select(table.name)
                    .where((table.company == company) & (IfNull(table.branch, "") == branch)
                           & (table.form_code == form_code) & (table.docstatus != 2))
                    .orderby(table.creation).for_update().run(as_dict=True))
        if existing:
            for item in existing:
                frappe.get_doc("Workforce Statutory Print Layout", item.name).check_permission("read")
            return {"created": False, "layouts": [item.name for item in existing]}
        doc = frappe.get_doc({
            "doctype": "Workforce Statutory Print Layout", "company": company,
            "branch": branch or "", "form_code": form_code,
            "title": source["ui_title"], "title_en": source["ui_title"],
            "form_family": source["kind"], "data_source": source["data_source"],
            "orientation": source["orientation"], "effective_from": date,
            "template_version": "draft-1", "layout_style": "Minimal Black and White",
            "columns": deepcopy(source["columns"]),
        }).insert()
        # A second request must see this new draft after the lock is released.
        # This explicit action changes configuration only, never business data.
        frappe.db.commit()
        return {"created": True, "layouts": [doc.name]}
