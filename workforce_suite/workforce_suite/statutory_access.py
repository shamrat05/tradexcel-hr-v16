"""Statutory tenant checks reuse native permissions; no permission grants."""
import frappe
from workforce_suite.workforce_suite.company_context import assert_company_access


def check_company(company):
    return assert_company_access(
        company, require_explicit_scope=True,
        additional_explicit_roles={"Workforce Compliance Auditor"},
    )



def _manual_scope(user):
    from frappe.permissions import get_user_permissions
    scopes = get_user_permissions(user)
    narrowed = bool(scopes.get("Employee") or scopes.get("Department"))
    branches = [item.doc for item in scopes.get("Branch", [])]
    return narrowed, branches


def statutory_query_conditions(user=None, doctype=None):
    """Restrict native lists/REST too, not only the custom exporter."""
    user = user or frappe.session.user
    privileged = "System Manager" in frappe.get_roles(user)
    if user == "Administrator" or (privileged and doctype != "Workforce Statutory Record"):
        return ""
    companies = frappe.get_all("User Permission", filters={"user": user, "allow": "Company"}, pluck="for_value")
    if not companies and not privileged:
        return "1=0"
    table = frappe.qb.DocType(doctype)
    condition = table.company.isin(companies) if companies else table.company.isnotnull()
    if doctype == "Workforce Statutory Export":
        condition &= table.generated_by == user
    if doctype == "Workforce Statutory Record":
        narrowed, branches = _manual_scope(user)
        # Native layout access always applies. Employee-linked manual records
        # may use native worker scope; unlinked establishment returns cannot.
        condition &= table.layout.isin(frappe.qb.get_query(
            "Workforce Statutory Print Layout", fields=["name"], ignore_permissions=False,
            user=user, db_query_compat=True))
        if narrowed or branches:
            from workforce_suite.workforce_suite.report_scope import permitted_employee_query
            worker = table.employee.isin(permitted_employee_query(user)) if frappe.has_permission("Employee", "read", user=user) else table.name.isnull()
            nonmanual = table.layout.isin(frappe.qb.get_query(
                "Workforce Statutory Print Layout", fields=["name"], filters={"data_source": ["!=", "Manual"]},
                ignore_permissions=False, user=user, db_query_compat=True))
            allowed = nonmanual | worker
            if branches and not narrowed:
                allowed |= table.layout.isin(frappe.qb.get_query(
                    "Workforce Statutory Print Layout", fields=["name"], filters={"branch": ["in", branches]},
                    ignore_permissions=False, user=user, db_query_compat=True))
            condition &= allowed
    return condition.get_sql(quote_char="`", with_namespace=True)


def statutory_has_permission(doc, ptype=None, user=None, **kwargs):
    user = user or frappe.session.user
    privileged = "System Manager" in frappe.get_roles(user)
    if user == "Administrator" or (privileged and doc.doctype != "Workforce Statutory Record"):
        return True  # Native DocPerm and User Permissions still apply.
    if not privileged and doc.get("company") and not frappe.db.exists("User Permission", {
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
        layout = frappe.db.get_value("Workforce Statutory Print Layout", doc.layout,
                                   ["data_source", "branch"], as_dict=True)
        if layout and layout.data_source == "Manual" and not doc.get("employee"):
            narrowed, branches = _manual_scope(user)
            if narrowed or (branches and layout.branch not in branches):
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
