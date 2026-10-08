"""Statutory tenant checks reuse native permissions; no permission grants."""
import frappe
from workforce_suite.workforce_suite.company_context import assert_company_access


def check_company(company):
    return assert_company_access(
        company, require_explicit_scope=True,
        additional_explicit_roles={"Workforce Compliance Auditor"},
    )


def statutory_query_conditions(user=None, doctype=None):
    """Restrict native lists/REST too, not only the custom exporter."""
    user = user or frappe.session.user
    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        return ""
    companies = frappe.get_all("User Permission", filters={"user": user, "allow": "Company"}, pluck="for_value")
    if not companies:
        return "1=0"
    table = frappe.qb.DocType(doctype)
    condition = table.company.isin(companies)
    if doctype == "Workforce Statutory Export":
        condition &= table.generated_by == user
    if doctype == "Workforce Statutory Record":
        condition &= table.layout.isin(frappe.qb.get_query(
            "Workforce Statutory Print Layout", fields=["name"], ignore_permissions=False,
            user=user, db_query_compat=True))
    return condition.get_sql(quote_char="`", with_namespace=True)


def statutory_has_permission(doc, ptype=None, user=None, **kwargs):
    user = user or frappe.session.user
    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        return True  # Native DocPerm and User Permissions still apply.
    if doc.get("company") and not frappe.db.exists("User Permission", {
        "user": user, "allow": "Company", "for_value": doc.company,
    }):
        return False
    if doc.doctype == "Workforce Statutory Export" and doc.generated_by != user:
        return False
    if doc.doctype == "Workforce Statutory Record" and doc.get("layout"):
        if not frappe.has_permission("Workforce Statutory Print Layout", "read", doc.layout, user=user):
            return False
        if doc.get("employee") and not frappe.has_permission("Employee", "read", doc.employee, user=user):
            return False
    return True


def checked_profile(layout, start="", end="", language="en"):
    if not layout.get("statutory_profile"):
        return None
    profile = frappe.get_doc("Workforce Statutory Profile", layout.statutory_profile)
    profile.check_permission("read")
    check_company(profile.company)
    if profile.company != layout.company or (profile.branch or "") != (layout.branch or ""):
        frappe.throw("Establishment profile must match the layout Company and Branch.")
    if profile.docstatus != 1:
        frappe.throw("Use an independently reviewed establishment profile.")
    from frappe.utils import getdate
    from datetime import date
    first, last = getdate(start) if start else date.today(), getdate(end) if end else date.today()
    if first < getdate(profile.effective_from) or (profile.effective_to and last > getdate(profile.effective_to)):
        frappe.throw("The establishment profile does not cover the complete reporting period.")
    if language == "bn" and not (profile.establishment_bn and profile.address_bn):
        frappe.throw("Complete the Bangla establishment name and address before Bangla export.")
    if language == "bn" and profile.signatory_en and not profile.signatory_bn:
        frappe.throw("Complete the Bangla signatory before Bangla export.")
    return profile
