"""Explicit draft layout setup. Never an installation or migration hook."""
from copy import deepcopy
import hashlib

import frappe
from frappe import _
from frappe.utils import getdate

from workforce_suite.workforce_suite.statutory_access import check_company
from workforce_suite.workforce_suite.statutory_forms import spec_for


def _native_company_address(company: str) -> str:
    """Return the first readable native Address linked to Company, if any."""
    links = frappe.get_all(
        "Dynamic Link",
        filters={"link_doctype": "Company", "link_name": company, "parenttype": "Address"},
        pluck="parent",
        limit_page_length=1,
    )
    if not links:
        return ""
    address = frappe.get_doc("Address", links[0])
    address.check_permission("read")
    return address.get_display() or ""


@frappe.whitelist(methods=["POST"])
def prepare_draft_profile(company, branch="", effective_from=""):
    """Create an editable draft profile from native Company/Address data.

    Legal registration, applicability, translation and approval are never
    inferred. Missing values are returned as explicit review findings.
    """
    if not frappe.has_permission("Workforce Statutory Profile", "create"):
        frappe.throw(_("You cannot configure statutory profiles."), frappe.PermissionError)
    check_company(company)
    company_doc = frappe.get_doc("Company", company)
    company_doc.check_permission("read")
    effective_from = effective_from or frappe.utils.getdate()
    if branch:
        branch_doc = frappe.get_doc("Branch", branch)
        branch_doc.check_permission("read")
        if branch_doc.get("company") != company:
            frappe.throw(_("Branch must belong to the selected Company."))
    existing = frappe.get_all(
        "Workforce Statutory Profile",
        filters={"company": company, "branch": branch or "", "docstatus": ["!=", 2]},
        pluck="name",
        order_by="creation asc",
    )
    if existing:
        return {"created": False, "profiles": existing,
                "missing_requirements": profile_missing_requirements(existing[0])}
    address = _native_company_address(company)
    missing = []
    if not address:
        missing.append({"field": "address_en", "message": _("Link a native Address to the Company.")})
    missing.extend([
        {"field": "registration_no", "message": _("Enter the reviewed establishment registration number.")},
        {"field": "legal_reference", "message": _("Add the applicable law, gazette or evidence reference.")},
        {"field": "review_notes", "message": _("Record the applicability and independent review notes.")},
    ])
    doc = frappe.get_doc({
        "doctype": "Workforce Statutory Profile",
        "company": company,
        "branch": branch or "",
        "profile_version": "draft-1",
        "effective_from": effective_from,
        "establishment_en": company_doc.company_name,
        "address_en": address or "Pending native Company Address review",
        "legal_reference": "Pending legal applicability review",
        "review_notes": "Complete registration, applicability and evidence review before submission.",
    }).insert()
    frappe.db.commit()
    return {"created": True, "profiles": [doc.name], "missing_requirements": missing}


@frappe.whitelist()
def profile_missing_requirements(profile_name):
    doc = frappe.get_doc("Workforce Statutory Profile", profile_name)
    fields = (
        ("address_en", _("Link a native establishment Address.")),
        ("registration_no", _("Enter the reviewed registration number.")),
        ("legal_reference", _("Add the applicable law, gazette or evidence reference.")),
        ("review_notes", _("Record applicability and independent review notes.")),
    )
    missing = []
    for fieldname, message in fields:
        value = doc.get(fieldname)
        if not value or str(value).startswith("Pending "):
            missing.append({"field": fieldname, "message": message})
    if not doc.get("establishment_bn"):
        missing.append({"field": "establishment_bn", "message": _("Add the reviewed Bangla establishment name before Bangla export.")})
    if not doc.get("address_bn"):
        missing.append({"field": "address_bn", "message": _("Add the reviewed Bangla establishment address before Bangla export.")})
    if doc.docstatus != 1:
        missing.append({"field": "docstatus", "message": _("Submit only after independent review; draft output is not an official filing.")})
    return missing


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
        query = (frappe.qb.from_(table).select(table.name)
                 .where((table.company == company) & (IfNull(table.branch, "") == branch)
                        & (table.form_code == form_code) & (table.docstatus != 2))
                 .orderby(table.creation).for_update())
        try:
            existing = query.run(as_dict=True)
        except frappe.QueryDeadlockError:
            # MariaDB can reject a locking read when the pre-lock snapshot
            # predates the winning request. No writes have occurred here.
            # Retry this read once in a fresh transaction while retaining the
            # scope lock; never retry inserts or swallow a second failure.
            frappe.db.rollback()
            if not frappe.has_permission("Workforce Statutory Print Layout", "create"):
                frappe.throw(_("You cannot configure statutory layouts."), frappe.PermissionError)
            check_company(company)
            frappe.get_doc("Company", company, for_update=True).check_permission("read")
            if branch:
                branch_doc = frappe.get_doc("Branch", branch, for_update=True)
                branch_doc.check_permission("read")
                if branch_doc.get("company") != company:
                    frappe.throw(_("Branch must belong to the selected Company."))
            existing = query.run(as_dict=True)
        if existing:
            for item in existing:
                frappe.get_doc("Workforce Statutory Print Layout", item.name, for_update=True).check_permission("read")
            return {"created": False, "layouts": [item.name for item in existing]}
        doc = frappe.get_doc({
            "doctype": "Workforce Statutory Print Layout", "company": company,
            "branch": branch or "", "form_code": form_code,
            "title": source["ui_title"], "title_en": source["ui_title"],
            "form_family": source["kind"], "data_source": source["data_source"],
            "orientation": source["orientation"], "effective_from": date,
            "template_version": "draft-1", "layout_style": "Minimal Black and White",
            "statutory_profile": (frappe.get_all(
                "Workforce Statutory Profile",
                filters={"company": company, "branch": branch or "", "docstatus": 1},
                pluck="name", order_by="creation asc", limit_page_length=1
            ) or [None])[0],
            "columns": deepcopy(source["columns"]),
        }).insert()
        # A second request must see this new draft after the lock is released.
        # This explicit action changes configuration only, never business data.
        frappe.db.commit()
        return {"created": True, "layouts": [doc.name]}
