"""Idempotent role and custom-DocType permission setup for Tradexcel HR."""

from __future__ import annotations

from collections.abc import Mapping

import frappe
from frappe.permissions import add_permission, setup_custom_perms, update_permission_property


ROLE_NAMES = (
    "Tradexcel Owner/Director",
    "Tradexcel HR Manager",
    "Tradexcel HR/Attendance Officer",
    "Tradexcel Payroll Manager",
    "Tradexcel Finance/Accounts Officer",
    "Tradexcel Factory Supervisor",
    "Tradexcel Branch Manager",
    "Tradexcel Department Manager",
    "Tradexcel Device/IT Administrator",
    "Tradexcel Compliance Auditor",
    "Tradexcel Employee/Worker",
    "Tradexcel Attendance Correction Approver",
    "Tradexcel Leave Approver",
    "Tradexcel Payroll Approver",
    "Tradexcel Import Reviewer",
)

PERMISSION_FIELDS = (
    "select",
    "read",
    "write",
    "create",
    "delete",
    "submit",
    "cancel",
    "amend",
    "report",
    "export",
    "import",
    "share",
    "print",
    "email",
)

# These permissions cover Tradexcel HR's custom operational records. Standard
# HRMS permissions remain managed by HR User/Manager and can be narrowed with
# User Permissions for a specific company, branch, or department.
READ_ONLY_PERMS = {"select", "read", "report", "export", "print"}
EDIT_PERMS = READ_ONLY_PERMS | {"write", "create"}
SUBMIT_PERMS = EDIT_PERMS | {"submit"}
APPROVE_PERMS = READ_ONLY_PERMS | {"write", "submit", "cancel"}

CUSTOM_PERMISSION_MATRIX: Mapping[str, Mapping[str, set[str]]] = {
    "Tradexcel Biometric Device": {
        "Tradexcel Owner/Director": {"read", "report", "export", "print"},
        "Tradexcel HR Manager": {"read", "report", "export", "print"},
        "Tradexcel HR/Attendance Officer": {"read", "report", "export", "print"},
        "Tradexcel Device/IT Administrator": set(PERMISSION_FIELDS) - {"delete", "import"},
        "Tradexcel Compliance Auditor": {"read", "report", "export", "print"},
        "Tradexcel Import Reviewer": {"read", "report", "export", "print"},
    },
    "Tradexcel Employee Biometric": {
        "Tradexcel Owner/Director": {"read", "report", "export", "print"},
        "Tradexcel HR Manager": set(PERMISSION_FIELDS) - {"delete", "submit", "cancel", "amend"},
        "Tradexcel HR/Attendance Officer": {"read", "write", "create", "report", "export", "print"},
        "Tradexcel Device/IT Administrator": {"read", "write", "create", "report", "export", "print"},
        "Tradexcel Compliance Auditor": {"read", "report", "export", "print"},
        "Tradexcel Import Reviewer": {"read", "write", "report", "export", "print"},
    },
    "Tradexcel Attendance Policy": {
        "Tradexcel Owner/Director": READ_ONLY_PERMS,
        "Tradexcel HR Manager": EDIT_PERMS | {"submit", "cancel"},
        "Tradexcel HR/Attendance Officer": EDIT_PERMS,
        "Tradexcel Compliance Auditor": READ_ONLY_PERMS,
    },
    "Tradexcel Field Duty": {
        "Tradexcel Owner/Director": READ_ONLY_PERMS,
        "Tradexcel HR Manager": EDIT_PERMS | {"submit", "cancel"},
        "Tradexcel HR/Attendance Officer": EDIT_PERMS,
        "Tradexcel Factory Supervisor": EDIT_PERMS | {"submit"},
        "Tradexcel Branch Manager": EDIT_PERMS | {"submit"},
        "Tradexcel Compliance Auditor": READ_ONLY_PERMS,
    },
    "Tradexcel Location Ping": {
        "Tradexcel Owner/Director": READ_ONLY_PERMS,
        "Tradexcel HR Manager": READ_ONLY_PERMS,
        "Tradexcel HR/Attendance Officer": READ_ONLY_PERMS,
        "Tradexcel Compliance Auditor": READ_ONLY_PERMS,
    },
    "Tradex Mobile Event": {
        "Tradexcel Compliance Auditor": READ_ONLY_PERMS,
    },
    "Tradex Face Match Settings": {
        "Tradexcel Owner/Director": READ_ONLY_PERMS,
        "Tradexcel HR Manager": EDIT_PERMS,
        "Tradexcel Compliance Auditor": READ_ONLY_PERMS,
    },
}

# Core HRMS access for the custom roles. Record-level restriction is applied
# separately with Frappe User Permissions (company, branch, or department), so
# this matrix describes what a role may do, not which records it may see.
STANDARD_PERMISSION_MATRIX: Mapping[str, Mapping[str, set[str]]] = {
    "Employee": {
        "Tradexcel Owner/Director": READ_ONLY_PERMS,
        "Tradexcel HR Manager": EDIT_PERMS,
        "Tradexcel HR/Attendance Officer": READ_ONLY_PERMS,
        "Tradexcel Payroll Manager": READ_ONLY_PERMS,
        "Tradexcel Finance/Accounts Officer": READ_ONLY_PERMS,
        "Tradexcel Factory Supervisor": READ_ONLY_PERMS,
        "Tradexcel Branch Manager": READ_ONLY_PERMS,
        "Tradexcel Department Manager": READ_ONLY_PERMS,
        "Tradexcel Compliance Auditor": READ_ONLY_PERMS,
        # Explicitly revoke any previously provisioned broad directory access.
        # Add own-record access only after a tested row-level rule exists.
        "Tradexcel Employee/Worker": set(),
    },
    "Employee Checkin": {
        "Tradexcel Owner/Director": READ_ONLY_PERMS,
        "Tradexcel HR Manager": READ_ONLY_PERMS,
        "Tradexcel HR/Attendance Officer": READ_ONLY_PERMS,
        "Tradexcel Employee/Worker": READ_ONLY_PERMS,
        "Tradexcel Factory Supervisor": READ_ONLY_PERMS,
        "Tradexcel Branch Manager": READ_ONLY_PERMS,
        "Tradexcel Department Manager": READ_ONLY_PERMS,
        "Tradexcel Device/IT Administrator": READ_ONLY_PERMS,
        "Tradexcel Compliance Auditor": READ_ONLY_PERMS,
    },
    "Attendance": {
        "Tradexcel Owner/Director": READ_ONLY_PERMS,
        "Tradexcel HR Manager": EDIT_PERMS,
        "Tradexcel HR/Attendance Officer": EDIT_PERMS,
        "Tradexcel Factory Supervisor": READ_ONLY_PERMS,
        "Tradexcel Branch Manager": READ_ONLY_PERMS,
        "Tradexcel Department Manager": READ_ONLY_PERMS,
        "Tradexcel Attendance Correction Approver": READ_ONLY_PERMS,
        "Tradexcel Compliance Auditor": READ_ONLY_PERMS,
    },
    "Attendance Request": {
        "Tradexcel HR Manager": EDIT_PERMS,
        "Tradexcel HR/Attendance Officer": EDIT_PERMS,
        "Tradexcel Employee/Worker": EDIT_PERMS,
        "Tradexcel Factory Supervisor": READ_ONLY_PERMS,
        "Tradexcel Branch Manager": READ_ONLY_PERMS,
        "Tradexcel Department Manager": READ_ONLY_PERMS,
        "Tradexcel Attendance Correction Approver": APPROVE_PERMS,
        "Tradexcel Compliance Auditor": READ_ONLY_PERMS,
    },
    "Leave Application": {
        "Tradexcel HR Manager": EDIT_PERMS,
        "Tradexcel HR/Attendance Officer": EDIT_PERMS,
        "Tradexcel Employee/Worker": EDIT_PERMS,
        "Tradexcel Factory Supervisor": READ_ONLY_PERMS,
        "Tradexcel Branch Manager": READ_ONLY_PERMS,
        "Tradexcel Department Manager": READ_ONLY_PERMS,
        "Tradexcel Leave Approver": APPROVE_PERMS,
        "Tradexcel Compliance Auditor": READ_ONLY_PERMS,
    },
    "Leave Allocation": {
        "Tradexcel Owner/Director": READ_ONLY_PERMS,
        "Tradexcel HR Manager": EDIT_PERMS,
        "Tradexcel HR/Attendance Officer": EDIT_PERMS,
        "Tradexcel Employee/Worker": READ_ONLY_PERMS,
        "Tradexcel Factory Supervisor": READ_ONLY_PERMS,
        "Tradexcel Branch Manager": READ_ONLY_PERMS,
        "Tradexcel Department Manager": READ_ONLY_PERMS,
        "Tradexcel Compliance Auditor": READ_ONLY_PERMS,
    },
    "Salary Component": {
        "Tradexcel Owner/Director": READ_ONLY_PERMS,
        "Tradexcel HR Manager": EDIT_PERMS,
        "Tradexcel Payroll Manager": EDIT_PERMS,
        "Tradexcel Finance/Accounts Officer": READ_ONLY_PERMS,
        "Tradexcel Compliance Auditor": READ_ONLY_PERMS,
    },
    "Salary Structure": {
        "Tradexcel Owner/Director": READ_ONLY_PERMS,
        "Tradexcel HR Manager": EDIT_PERMS,
        "Tradexcel Payroll Manager": EDIT_PERMS,
        "Tradexcel Finance/Accounts Officer": READ_ONLY_PERMS,
        "Tradexcel Compliance Auditor": READ_ONLY_PERMS,
    },
    "Salary Structure Assignment": {
        "Tradexcel Owner/Director": READ_ONLY_PERMS,
        "Tradexcel HR Manager": EDIT_PERMS,
        "Tradexcel Payroll Manager": EDIT_PERMS,
        "Tradexcel Finance/Accounts Officer": READ_ONLY_PERMS,
        "Tradexcel Compliance Auditor": READ_ONLY_PERMS,
    },
    "Additional Salary": {
        "Tradexcel Owner/Director": READ_ONLY_PERMS,
        "Tradexcel HR Manager": EDIT_PERMS,
        "Tradexcel Payroll Manager": EDIT_PERMS,
        "Tradexcel Finance/Accounts Officer": READ_ONLY_PERMS,
        "Tradexcel Compliance Auditor": READ_ONLY_PERMS,
    },
    "Salary Slip": {
        "Tradexcel Owner/Director": READ_ONLY_PERMS | {"delete"},
        "Tradexcel HR Manager": READ_ONLY_PERMS,
        "Tradexcel Payroll Manager": EDIT_PERMS | {"submit"},
        "Tradexcel Finance/Accounts Officer": READ_ONLY_PERMS,
        "Tradexcel Payroll Approver": APPROVE_PERMS | {"delete"},
        "Tradexcel Compliance Auditor": READ_ONLY_PERMS,
    },
    "Payroll Entry": {
        "Tradexcel Owner/Director": APPROVE_PERMS,
        "Tradexcel HR Manager": READ_ONLY_PERMS,
        "Tradexcel Payroll Manager": EDIT_PERMS | {"submit"},
        "Tradexcel Finance/Accounts Officer": READ_ONLY_PERMS,
        "Tradexcel Payroll Approver": APPROVE_PERMS,
        "Tradexcel Compliance Auditor": READ_ONLY_PERMS,
    },
}


def _ensure_role(role_name: str) -> str:
    if frappe.db.exists("Role", role_name):
        role = frappe.get_doc("Role", role_name)
    else:
        role = frappe.get_doc({"doctype": "Role", "role_name": role_name})
    role.is_custom = 1
    role.desk_access = 1
    role.disabled = 0
    role.save(ignore_permissions=True)
    return role.name


def _ensure_permission(doctype: str, role: str, allowed: set[str]) -> None:
    setup_custom_perms(doctype)
    if not frappe.db.exists(
        "Custom DocPerm",
        {"parent": doctype, "role": role, "permlevel": 0, "if_owner": 0},
    ):
        add_permission(doctype, role, permlevel=0, ptype="read")
    for fieldname in PERMISSION_FIELDS:
        update_permission_property(
            doctype,
            role,
            0,
            fieldname,
            int(fieldname in allowed),
            validate=False,
        )


def ensure_tradex_roles() -> dict[str, int]:
    """Create the approved roles and permissions without changing user roles."""
    created_or_updated = 0
    for role_name in ROLE_NAMES:
        _ensure_role(role_name)
        created_or_updated += 1

    permission_count = 0
    for permission_matrix in (CUSTOM_PERMISSION_MATRIX, STANDARD_PERMISSION_MATRIX):
        for doctype, role_permissions in permission_matrix.items():
            if not frappe.db.exists("DocType", doctype):
                continue
            for role_name, allowed in role_permissions.items():
                _ensure_permission(doctype, role_name, allowed)
                permission_count += 1

    # Native HRMS gives the standard Employee role direct Employee Checkin
    # creation. Mobile attendance must go through the server-side policy API;
    # the endpoint inserts only after identity and evidence checks.
    setup_custom_perms("Employee Checkin")
    for fieldname in ("create", "write", "delete"):
        update_permission_property(
            "Employee Checkin", "Employee", 0, fieldname, 0, validate=False
        )

    frappe.clear_cache()
    return {
        "roles_created_or_updated": created_or_updated,
        "custom_permission_rules_created_or_updated": permission_count,
    }
