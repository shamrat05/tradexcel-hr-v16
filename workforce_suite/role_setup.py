"""Idempotent role and custom-DocType permission setup for Workforce Suite."""

from __future__ import annotations

from collections.abc import Mapping

import frappe
from frappe.permissions import add_permission, setup_custom_perms, update_permission_property


ROLE_NAMES = (
    "Workforce Owner/Director",
    "Workforce Suite Manager",
    "Workforce Suite/Attendance Officer",
    "Workforce Payroll Manager",
    "Workforce Finance/Accounts Officer",
    "Workforce Factory Supervisor",
    "Workforce Branch Manager",
    "Workforce Department Manager",
    "Workforce Device/IT Administrator",
    "Workforce Compliance Auditor",
    "Workforce Employee/Worker",
    "Workforce Attendance Correction Approver",
    "Workforce Leave Approver",
    "Workforce Payroll Approver",
    "Workforce Import Reviewer",
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

# These permissions cover Workforce Suite's custom operational records. Standard
# HRMS permissions remain managed by HR User/Manager and can be narrowed with
# User Permissions for a specific company, branch, or department.
READ_ONLY_PERMS = {"select", "read", "report", "export", "print"}
EDIT_PERMS = READ_ONLY_PERMS | {"write", "create"}
SUBMIT_PERMS = EDIT_PERMS | {"submit"}
APPROVE_PERMS = READ_ONLY_PERMS | {"write", "submit", "cancel"}

CUSTOM_PERMISSION_MATRIX: Mapping[str, Mapping[str, set[str]]] = {
    "Workforce Biometric Device": {
        "Workforce Owner/Director": {"read", "report", "export", "print"},
        "Workforce Suite Manager": {"read", "report", "export", "print"},
        "Workforce Suite/Attendance Officer": {"read", "report", "export", "print"},
        "Workforce Device/IT Administrator": set(PERMISSION_FIELDS) - {"delete", "import"},
        "Workforce Compliance Auditor": {"read", "report", "export", "print"},
        "Workforce Import Reviewer": {"read", "report", "export", "print"},
    },
    "Workforce Employee Biometric": {
        "Workforce Owner/Director": {"read", "report", "export", "print"},
        "Workforce Suite Manager": set(PERMISSION_FIELDS) - {"delete", "submit", "cancel", "amend"},
        "Workforce Suite/Attendance Officer": {"read", "write", "create", "report", "export", "print"},
        "Workforce Device/IT Administrator": {"read", "write", "create", "report", "export", "print"},
        "Workforce Compliance Auditor": {"read", "report", "export", "print"},
        "Workforce Import Reviewer": {"read", "write", "report", "export", "print"},
    },
    "Workforce Attendance Policy": {
        "Workforce Owner/Director": READ_ONLY_PERMS,
        "Workforce Suite Manager": EDIT_PERMS | {"submit", "cancel"},
        "Workforce Suite/Attendance Officer": EDIT_PERMS,
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
    },
    "Workforce Field Duty": {
        "Workforce Owner/Director": READ_ONLY_PERMS,
        "Workforce Suite Manager": EDIT_PERMS | {"submit", "cancel"},
        "Workforce Suite/Attendance Officer": EDIT_PERMS,
        "Workforce Factory Supervisor": EDIT_PERMS | {"submit"},
        "Workforce Branch Manager": EDIT_PERMS | {"submit"},
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
    },
    "Workforce Location Ping": {
        "Workforce Owner/Director": READ_ONLY_PERMS,
        "Workforce Suite Manager": READ_ONLY_PERMS,
        "Workforce Suite/Attendance Officer": READ_ONLY_PERMS,
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
    },
    "Workforce Mobile Event": {
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
    },
    "Workforce Face Match Settings": {
        "Workforce Owner/Director": READ_ONLY_PERMS,
        "Workforce Suite Manager": EDIT_PERMS,
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
    },
}

# Core HRMS access for the custom roles. Record-level restriction is applied
# separately with Frappe User Permissions (company, branch, or department), so
# this matrix describes what a role may do, not which records it may see.
STANDARD_PERMISSION_MATRIX: Mapping[str, Mapping[str, set[str]]] = {
    # Company context validation performs a permission-aware Company lookup
    # before report SQL. User Permissions restrict these read-only rows to the
    # user's assigned Company; no Company maintenance rights are added.
    "Company": {
        "Workforce Owner/Director": {"read"},
        "Workforce Suite Manager": {"read"},
        "Workforce Suite/Attendance Officer": {"read"},
        "Workforce Payroll Manager": {"read"},
        # Payroll approvers run scoped Payroll Entry and salary reports; they
        # need Company read for the existing permission-aware company guard.
        "Workforce Payroll Approver": {"read"},
        "Workforce Finance/Accounts Officer": {"read"},
        "Workforce Factory Supervisor": {"read"},
        "Workforce Branch Manager": {"read"},
        "Workforce Department Manager": {"read"},
        "Workforce Attendance Correction Approver": {"read"},
        "Workforce Leave Approver": {"read"},
        "Workforce Compliance Auditor": {"read"},
    },
    "Department": {
        "Workforce Suite Manager": {"select", "read"},
        "Workforce Suite/Attendance Officer": {"select", "read"},
        "Workforce Branch Manager": {"select", "read"},
        "Workforce Department Manager": {"select", "read"},
        "Workforce Factory Supervisor": {"select", "read"},
        "Workforce Payroll Manager": {"select", "read"},
        "Workforce Compliance Auditor": {"select", "read"},
    },
    "Branch": {
        "Workforce Suite Manager": {"select", "read"},
        "Workforce Suite/Attendance Officer": {"select", "read"},
        "Workforce Branch Manager": {"select", "read"},
        "Workforce Department Manager": {"select", "read"},
        "Workforce Factory Supervisor": {"select", "read"},
        "Workforce Payroll Manager": {"select", "read"},
        "Workforce Compliance Auditor": {"select", "read"},
    },
    "Designation": {
        "Workforce Suite Manager": {"select", "read"},
        "Workforce Suite/Attendance Officer": {"select", "read"},
        "Workforce Branch Manager": {"select", "read"},
        "Workforce Department Manager": {"select", "read"},
        "Workforce Factory Supervisor": {"select", "read"},
        "Workforce Payroll Manager": {"select", "read"},
        "Workforce Compliance Auditor": {"select", "read"},
    },
    "Employee Grade": {
        "Workforce Suite Manager": {"select", "read"},
    },
    "Employee Group": {
        "Workforce Suite Manager": {"select", "read"},
    },
    "Holiday List": {
        "Workforce Suite Manager": {"select", "read"},
        "Workforce Suite/Attendance Officer": {"select", "read"},
    },
    "Holiday List Assignment": {
        "Workforce Suite Manager": EDIT_PERMS | {"submit"},
    },
    "Leave Block List": {
        "Workforce Suite Manager": {"select", "read"},
    },
    "Overtime Type": {
        "Workforce Suite Manager": {"select", "read"},
        "Workforce Suite/Attendance Officer": {"select", "read"},
    },
    "Expense Claim": {
        "Workforce Suite Manager": EDIT_PERMS,
    },
    "Expense Claim Type": {
        "Workforce Suite Manager": {"select", "read"},
    },
    "Purpose of Travel": {
        "Workforce Suite Manager": {"select", "read"},
    },
    "Compensatory Leave Request": {
        "Workforce Suite Manager": EDIT_PERMS | {"submit"},
    },
    # The native HRMS bulk SSA form is used only by the two preparation roles.
    # Its own permission is read/write; actual SSA creation remains on the
    # native Salary Structure Assignment DocType and approver submit policy.
    "Bulk Salary Structure Assignment": {
        "Workforce Suite Manager": {"read", "write", "create"},
        "Workforce Payroll Manager": {"read", "write", "create"},
    },
    # Makers may select a reviewed slab when a Salary Structure requires one;
    # they do not receive slab maintenance or submission permissions here.
    "Income Tax Slab": {
        "Workforce Suite Manager": {"read"},
        "Workforce Payroll Manager": {"read"},
    },
    "Workforce Flexible Work Policy": {
        "Workforce Suite Manager": EDIT_PERMS,
        "Workforce Suite/Attendance Officer": EDIT_PERMS,
        "Workforce Owner/Director": READ_ONLY_PERMS | {"write", "submit", "cancel"},
        "Workforce Payroll Manager": READ_ONLY_PERMS,
        "Workforce Payroll Approver": READ_ONLY_PERMS,
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
    },
    "Workforce Operational Day Override": {
        "Workforce Suite Manager": EDIT_PERMS,
        "Workforce Suite/Attendance Officer": EDIT_PERMS,
        "Workforce Factory Supervisor": EDIT_PERMS,
        "Workforce Payroll Approver": READ_ONLY_PERMS | {"write", "submit", "cancel"},
        "Workforce Payroll Manager": READ_ONLY_PERMS,
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
    },
    "Workforce Working Time Rule Set": {
        "Workforce Suite Manager": EDIT_PERMS,
        "Workforce Owner/Director": READ_ONLY_PERMS | {"write", "submit"},
        "Workforce Payroll Manager": READ_ONLY_PERMS,
        "Workforce Payroll Approver": READ_ONLY_PERMS,
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
    },
    "Workforce Working Time Classification": {
        "Workforce Suite Manager": EDIT_PERMS,
        "Workforce Owner/Director": READ_ONLY_PERMS | {"write", "submit"},
        "Workforce Payroll Manager": READ_ONLY_PERMS,
        "Workforce Payroll Approver": READ_ONLY_PERMS,
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
    },
    "Overtime Slip": {
        "Workforce Suite Manager": EDIT_PERMS,
        "Workforce Payroll Approver": READ_ONLY_PERMS | {"write", "submit"},
        "Workforce Payroll Manager": READ_ONLY_PERMS,
        "Workforce Owner/Director": READ_ONLY_PERMS,
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
    },
    "Workforce Statutory Benefit Rule Set": {
        "Workforce Suite Manager": EDIT_PERMS,
        "Workforce Owner/Director": READ_ONLY_PERMS | {"write", "submit"},
        "Workforce Payroll Manager": READ_ONLY_PERMS,
        "Workforce Finance/Accounts Officer": READ_ONLY_PERMS,
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
    },
    "Workforce Statutory Benefit Enrollment": {
        "Workforce Suite Manager": EDIT_PERMS,
        "Workforce Owner/Director": READ_ONLY_PERMS | {"write", "submit"},
        "Workforce Payroll Manager": READ_ONLY_PERMS,
        "Workforce Finance/Accounts Officer": READ_ONLY_PERMS,
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
    },
    "Workforce Wage Floor Rule Set": {
        "Workforce Suite Manager": EDIT_PERMS,
        "Workforce Owner/Director": READ_ONLY_PERMS | {"write", "submit"},
        "Workforce Payroll Manager": READ_ONLY_PERMS,
        "Workforce Payroll Approver": READ_ONLY_PERMS,
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
    },
    "Workforce Wage Floor Classification": {
        "Workforce Suite Manager": EDIT_PERMS,
        "Workforce Owner/Director": READ_ONLY_PERMS | {"write", "submit"},
        "Workforce Payroll Manager": READ_ONLY_PERMS,
        "Workforce Payroll Approver": READ_ONLY_PERMS,
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
    },
    "Job Opening": {
        "Workforce Suite Manager": EDIT_PERMS,
    },
    "Job Applicant": {
        "Workforce Suite Manager": EDIT_PERMS,
    },
    "Interview": {
        "Workforce Suite Manager": EDIT_PERMS | {"submit"},
    },
    "Interview Feedback": {
        "Workforce Suite Manager": READ_ONLY_PERMS,
    },
    "Job Offer": {
        "Workforce Suite Manager": EDIT_PERMS | {"submit"},
    },
    "Employee Onboarding": {
        "Workforce Suite Manager": EDIT_PERMS | {"submit"},
    },
    "Employee Onboarding Template": {
        "Workforce Suite Manager": READ_ONLY_PERMS,
    },
    # Native Job Opening validation checks Staffing Plan read permission when
    # enforcing vacancy limits; HR does not receive Staffing Plan write access.
    "Staffing Plan": {
        "Workforce Suite Manager": READ_ONLY_PERMS,
    },
    "Job Requisition": {
        "Workforce Suite Manager": EDIT_PERMS,
    },
    "Interview Type": {
        "Workforce Suite Manager": {"select", "read"},
    },
    "Employee Referral": {
        "Workforce Suite Manager": EDIT_PERMS | {"submit"},
    },
    "Appointment Letter": {
        "Workforce Suite Manager": EDIT_PERMS,
    },
    "Appointment Letter Template": {
        "Workforce Suite Manager": {"select", "read"},
    },
    # Native Employee BoardingController assigns generated Tasks through
    # Frappe's share API, which requires Task share permission. User Permissions
    # still scope both the Task and the resulting share to the operator's Company.
    "Task": {
        "Workforce Suite Manager": READ_ONLY_PERMS | {"write", "share"},
    },
    "Employee Grievance": {
        "Workforce Suite Manager": EDIT_PERMS | {"submit"},
    },
    "Grievance Type": {
        "Workforce Suite Manager": {"select", "read"},
    },
    "Training Program": {
        "Workforce Suite Manager": EDIT_PERMS,
    },
    "Training Event": {
        "Workforce Suite Manager": EDIT_PERMS | {"submit"},
    },
    "Training Feedback": {
        "Workforce Suite Manager": READ_ONLY_PERMS,
    },
    "Training Result": {
        "Workforce Suite Manager": EDIT_PERMS | {"submit"},
    },
    "Appraisal": {
        "Workforce Suite Manager": EDIT_PERMS | {"submit"},
    },
    "Appraisal Cycle": {
        "Workforce Suite Manager": EDIT_PERMS,
    },
    "Appraisal Template": {
        "Workforce Suite Manager": {"select", "read"},
    },
    "Goal": {
        "Workforce Suite Manager": EDIT_PERMS,
    },
    "Employee Skill Map": {
        "Workforce Suite Manager": EDIT_PERMS,
    },
    "Employee Separation": {
        "Workforce Owner/Director": READ_ONLY_PERMS,
        "Workforce Suite Manager": EDIT_PERMS | {"submit", "cancel"},
        "Workforce Payroll Manager": READ_ONLY_PERMS,
        "Workforce Finance/Accounts Officer": READ_ONLY_PERMS,
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
    },
    "Employee Separation Template": {
        "Workforce Suite Manager": EDIT_PERMS,
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
    },
    "Employee Transfer": {
        "Workforce Owner/Director": READ_ONLY_PERMS,
        "Workforce Suite Manager": EDIT_PERMS | {"submit", "cancel"},
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
    },
    "Employee Promotion": {
        "Workforce Owner/Director": READ_ONLY_PERMS,
        "Workforce Suite Manager": EDIT_PERMS | {"submit", "cancel"},
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
    },
    "Full and Final Statement": {
        "Workforce Owner/Director": READ_ONLY_PERMS,
        "Workforce Suite Manager": EDIT_PERMS,
        "Workforce Payroll Manager": READ_ONLY_PERMS,
        "Workforce Finance/Accounts Officer": READ_ONLY_PERMS | {"write", "submit", "cancel"},
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
    },
    "Employee": {
        # Device troubleshooting needs scoped Employee identity selection, not
        # the Employee form, compensation, bank details or HR mutation rights.
        "Workforce Device/IT Administrator": {"select"},
        "Workforce Owner/Director": READ_ONLY_PERMS,
        "Workforce Suite Manager": EDIT_PERMS,
        "Workforce Suite/Attendance Officer": READ_ONLY_PERMS,
        "Workforce Payroll Manager": READ_ONLY_PERMS,
        "Workforce Payroll Approver": READ_ONLY_PERMS,
        "Workforce Finance/Accounts Officer": READ_ONLY_PERMS,
        "Workforce Factory Supervisor": READ_ONLY_PERMS,
        "Workforce Branch Manager": READ_ONLY_PERMS,
        "Workforce Department Manager": READ_ONLY_PERMS,
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
        # Attendance Request approvers need a permission-aware Employee list
        # solely to revalidate Company/Branch/Department scope at submit time.
        "Workforce Attendance Correction Approver": {"select", "read"},
        # Explicitly revoke any previously provisioned broad directory access.
        # Add own-record access only after a tested row-level rule exists.
        "Workforce Employee/Worker": set(),
        # A leave approver must identify and scope the Employee whose native
        # leave balance is being reviewed; User Permissions bound the rows.
        "Workforce Leave Approver": {"read"},
    },
    "Employee Checkin": {
        "Workforce Owner/Director": READ_ONLY_PERMS,
        "Workforce Suite Manager": READ_ONLY_PERMS,
        "Workforce Attendance Correction Approver": {"read", "select"},
        "Workforce Suite/Attendance Officer": READ_ONLY_PERMS,
        # Linked employees keep HRMS's native Employee-role own-record access.
        # The Workforce role must not grant a directory to unlinked users.
        "Workforce Employee/Worker": set(),
        "Workforce Factory Supervisor": READ_ONLY_PERMS,
        "Workforce Branch Manager": READ_ONLY_PERMS,
        "Workforce Department Manager": READ_ONLY_PERMS,
        "Workforce Device/IT Administrator": READ_ONLY_PERMS,
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
    },
    "Attendance": {
        "Workforce Owner/Director": READ_ONLY_PERMS,
        "Workforce Suite Manager": EDIT_PERMS,
        "Workforce Suite/Attendance Officer": EDIT_PERMS,
        "Workforce Factory Supervisor": READ_ONLY_PERMS,
        "Workforce Branch Manager": READ_ONLY_PERMS,
        "Workforce Department Manager": READ_ONLY_PERMS,
        "Workforce Attendance Correction Approver": READ_ONLY_PERMS,
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
    },
    # The native Shift Assignment Tool exposes several bulk actions. The
    # Workforce operator action list is narrowed to Assign Shift; read on the
    # singleton is enough to open it and call its read-only preview method.
    "Shift Assignment Tool": {
        "Workforce Suite Manager": {"read"},
        "Workforce Suite/Attendance Officer": {"read"},
    },
    # Native bulk assignment creates and submits each Shift Assignment under
    # the caller. Keep this to the two scheduling operators and omit cancel,
    # delete, export, print, and import.
    "Shift Assignment": {
        "Workforce Suite Manager": {"read", "create", "write", "submit"},
        "Workforce Suite/Attendance Officer": {"read", "create", "write", "submit"},
    },
    "Shift Type": {
        "Workforce Suite Manager": {"read"},
        "Workforce Suite/Attendance Officer": {"read"},
    },
    "Shift Location": {
        "Workforce Suite Manager": {"read"},
        "Workforce Suite/Attendance Officer": {"read"},
    },
    "Attendance Request": {
        "Workforce Suite Manager": EDIT_PERMS,
        "Workforce Suite/Attendance Officer": EDIT_PERMS,
        "Workforce Employee/Worker": set(),
        "Workforce Factory Supervisor": READ_ONLY_PERMS,
        "Workforce Branch Manager": READ_ONLY_PERMS,
        "Workforce Department Manager": READ_ONLY_PERMS,
        # Native Attendance Request cancellation also cancels linked submitted
        # Attendance and therefore requires broad Attendance write permission.
        # Keep custom approvers on submit-only; native HR roles retain HRMS cancel.
        "Workforce Attendance Correction Approver": APPROVE_PERMS - {"cancel"},
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
    },
    "Leave Application": {
        "Workforce Suite Manager": EDIT_PERMS,
        "Workforce Suite/Attendance Officer": EDIT_PERMS,
        "Workforce Employee/Worker": set(),
        "Workforce Factory Supervisor": READ_ONLY_PERMS,
        "Workforce Branch Manager": READ_ONLY_PERMS,
        "Workforce Department Manager": READ_ONLY_PERMS,
        "Workforce Leave Approver": APPROVE_PERMS,
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
    },
    "Leave Allocation": {
        "Workforce Owner/Director": READ_ONLY_PERMS,
        # Entitlement administration stays with HR; Leave Approver only
        # decides individual Leave Applications.
        "Workforce Suite Manager": EDIT_PERMS | {"submit"},
        "Workforce Suite/Attendance Officer": EDIT_PERMS,
        # Leave approvers need the native balance evidence that informs their
        # Leave Application decision; Company/Branch/Department scope remains
        # the native User Permission boundary.
        "Workforce Leave Approver": {"read", "report"},
        # HRMS does not grant its native Employee role direct allocation
        # browsing; balance checks remain in native Leave Application flows.
        "Workforce Employee/Worker": set(),
        "Workforce Factory Supervisor": READ_ONLY_PERMS,
        "Workforce Branch Manager": READ_ONLY_PERMS,
        "Workforce Department Manager": READ_ONLY_PERMS,
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
    },
    "Leave Control Panel": {
        "Workforce Suite Manager": {"read"},
    },
    "Leave Policy Assignment": {
        "Workforce Suite Manager": EDIT_PERMS | {"submit"},
    },
    "Leave Policy": {
        "Workforce Suite Manager": {"select", "read"},
    },
    "Leave Period": {
        "Workforce Suite Manager": {"select", "read"},
    },
    "Leave Type": {
        "Workforce Suite Manager": {"select", "read"},
    },
    "Salary Component": {
        "Workforce Owner/Director": READ_ONLY_PERMS,
        "Workforce Suite Manager": EDIT_PERMS,
        "Workforce Payroll Manager": EDIT_PERMS,
        "Workforce Finance/Accounts Officer": READ_ONLY_PERMS,
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
    },
    "Salary Structure": {
        "Workforce Owner/Director": READ_ONLY_PERMS,
        "Workforce Suite Manager": EDIT_PERMS,
        "Workforce Payroll Manager": EDIT_PERMS,
        "Workforce Payroll Approver": READ_ONLY_PERMS,
        "Workforce Finance/Accounts Officer": READ_ONLY_PERMS,
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
    },
    "Salary Structure Assignment": {
        "Workforce Owner/Director": READ_ONLY_PERMS,
        "Workforce Suite Manager": EDIT_PERMS,
        "Workforce Payroll Manager": EDIT_PERMS,
        "Workforce Payroll Approver": READ_ONLY_PERMS | {"write", "submit", "cancel"},
        "Workforce Finance/Accounts Officer": READ_ONLY_PERMS,
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
    },
    "Additional Salary": {
        "Workforce Owner/Director": READ_ONLY_PERMS,
        "Workforce Suite Manager": EDIT_PERMS,
        "Workforce Payroll Manager": EDIT_PERMS,
        "Workforce Finance/Accounts Officer": READ_ONLY_PERMS,
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
    },
    "Payroll Correction": {
        "Workforce Suite Manager": EDIT_PERMS,
        "Workforce Payroll Manager": EDIT_PERMS,
        "Workforce Payroll Approver": READ_ONLY_PERMS | {"write", "submit"},
        "Workforce Owner/Director": READ_ONLY_PERMS | {"cancel"},
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
    },
    "Arrear": {
        "Workforce Suite Manager": EDIT_PERMS,
        "Workforce Payroll Manager": EDIT_PERMS,
        "Workforce Payroll Approver": READ_ONLY_PERMS | {"write", "submit"},
        "Workforce Owner/Director": READ_ONLY_PERMS | {"cancel"},
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
    },
    "Salary Slip": {
        "Workforce Owner/Director": READ_ONLY_PERMS | {"delete"},
        "Workforce Suite Manager": READ_ONLY_PERMS,
        "Workforce Payroll Manager": EDIT_PERMS | {"submit"},
        "Workforce Finance/Accounts Officer": READ_ONLY_PERMS,
        # Native Arrear approval recalculates a Salary Slip preview through
        # HRMS make_salary_slip(), whose mapper checks Salary Slip create
        # permission. No mutation or final submission is granted.
        "Workforce Payroll Approver": READ_ONLY_PERMS | {"create"},
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
    },
    "Payroll Entry": {
        "Workforce Owner/Director": APPROVE_PERMS,
        "Workforce Suite Manager": READ_ONLY_PERMS,
        "Workforce Payroll Manager": EDIT_PERMS | {"submit"},
        "Workforce Finance/Accounts Officer": READ_ONLY_PERMS,
        "Workforce Payroll Approver": APPROVE_PERMS,
        "Workforce Compliance Auditor": READ_ONLY_PERMS,
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



def ensure_employee_financial_privacy() -> None:
    """Native field permissions hide compensation/bank identifiers from operators."""
    from frappe.custom.doctype.property_setter.property_setter import make_property_setter

    for field in ("ctc", "bank_ac_no", "iban"):
        if not frappe.get_meta("Employee").has_field(field):
            continue
        if frappe.get_meta("Employee").get_field(field).permlevel != 1:
            make_property_setter("Employee", field, "permlevel", 1, "Int")
    readers = {
        "HR User", "HR Manager", "System Manager", "Workforce Owner/Director",
        "Workforce Suite Manager", "Workforce Payroll Manager", "Workforce Payroll Approver",
        "Workforce Finance/Accounts Officer", "Workforce Compliance Auditor",
    }
    writers = {"HR User", "HR Manager", "System Manager", "Workforce Suite Manager"}
    # Preserve native HR capability. A level-one row never grants Employee
    # document access on its own. Worker/operational role unions get no level one.
    setup_custom_perms("Employee")
    for role in sorted(readers):
        if not frappe.db.exists("Custom DocPerm", {"parent": "Employee", "role": role, "permlevel": 1}):
            add_permission("Employee", role, permlevel=1, ptype="read")
        for field in PERMISSION_FIELDS:
            allowed = field == "read" or (field == "write" and role in writers)
            update_permission_property("Employee", role, 1, field, int(allowed), validate=False)


def ensure_workforce_roles() -> dict[str, int]:
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

    ensure_employee_financial_privacy()
    frappe.clear_cache()
    return {
        "roles_created_or_updated": created_or_updated,
        "custom_permission_rules_created_or_updated": permission_count,
    }
