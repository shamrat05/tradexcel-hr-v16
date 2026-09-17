"""Dynamic link-field search helpers for form and report filters."""

from __future__ import annotations

import frappe


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def departments_used_by_branch(doctype, txt, searchfield, start, page_len, filters):
    """Return departments actually used by employees, scoped by company and branch.

    Department has no native Branch link in Frappe HR, so the branch scope is
    derived from real Employee records instead of an invented mapping.
    """
    filters = filters or {}
    conditions = ["e.department IS NOT NULL", "e.department != ''", "d.name LIKE %(txt)s"]
    values = {"txt": f"%{txt}%", "start": start, "page_len": page_len}
    if filters.get("company"):
        conditions.append("e.company = %(company)s")
        values["company"] = filters["company"]
    if filters.get("branch"):
        conditions.append("e.branch = %(branch)s")
        values["branch"] = filters["branch"]

    return frappe.db.sql(
        f"""
        SELECT DISTINCT d.name, d.department_name
        FROM `tabEmployee` e
        JOIN `tabDepartment` d ON d.name = e.department
        WHERE {' AND '.join(conditions)}
        ORDER BY d.name
        LIMIT %(start)s, %(page_len)s
        """,
        values,
    )


@frappe.whitelist()
def scope_has_children(branch=None, department=None):
    """True when the selected nodes actually have children to include."""
    return {
        "branch_has_children": bool(branch) and bool(
            frappe.db.exists("Branch", {"parent_branch": branch})
        ),
        "department_has_children": bool(department) and bool(
            frappe.db.exists("Department", {"parent_department": department})
        ),
    }


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def designations_used_by_scope(doctype, txt, searchfield, start, page_len, filters):
    """Return designations actually used by employees inside the chosen scope.

    Designation has no native Branch/Department link, so the scope is derived
    from real Employee records instead of an invented mapping.
    """
    filters = filters or {}
    conditions = ["e.designation IS NOT NULL", "e.designation != ''", "e.designation LIKE %(txt)s"]
    values = {"txt": f"%{txt}%", "start": start, "page_len": page_len}
    for key in ("company", "branch", "department"):
        if filters.get(key):
            conditions.append(f"e.{key} = %({key})s")
            values[key] = filters[key]

    return frappe.db.sql(
        f"""
        SELECT DISTINCT e.designation
        FROM `tabEmployee` e
        WHERE {' AND '.join(conditions)}
        ORDER BY e.designation
        LIMIT %(start)s, %(page_len)s
        """,
        values,
    )
