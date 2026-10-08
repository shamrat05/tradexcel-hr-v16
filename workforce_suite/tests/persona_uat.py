"""Synthetic native Frappe personas shared by site-backed access tests.

This is test support only. User, Role, Has Role, User Permission, and the
Employee.user_id link remain the identity and scope authorities.
"""

from __future__ import annotations

from unittest.mock import patch

import frappe


PERSONA_ROLES = {
    "owner": "Workforce Owner/Director",
    "hr_manager": "Workforce Suite Manager",
    "attendance_officer": "Workforce Suite/Attendance Officer",
    "factory_supervisor": "Workforce Factory Supervisor",
    "branch_manager": "Workforce Branch Manager",
    "department_manager": "Workforce Department Manager",
    "payroll_manager": "Workforce Payroll Manager",
    "payroll_approver": "Workforce Payroll Approver",
    "finance": "Workforce Finance/Accounts Officer",
    "compliance": "Workforce Compliance Auditor",
    "device_admin": "Workforce Device/IT Administrator",
    "attendance_correction_approver": "Workforce Attendance Correction Approver",
    "leave_approver": "Workforce Leave Approver",
    "import_reviewer": "Workforce Import Reviewer",
    "worker": "Workforce Employee/Worker",
}


class SyntheticPersonaHarness:
    """Creates disposable System Users and native User Permissions for tests."""

    def __init__(self, token: str):
        self.token = token.upper()
        self.users: dict[str, str] = {}
        self.permissions: list[str] = []
        self.employees: list[str] = []
        self.user_emails: list[str] = []
        self.employee_marker = f"TEST PERSONA {self.token}"

    def create_user(self, key: str, roles: list[str], *, company: str | None = None,
                    branch: str | None = None, department: str | None = None) -> str:
        email = f"persona-{self.token.lower()}-{key}@example.test"
        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": f"TEST PERSONA {key}",
            "enabled": 1,
            "user_type": "System User",
            "send_welcome_email": 0,
            "roles": [{"role": role} for role in roles],
        })
        # Native User.on_update creates Contact asynchronously outside tests.
        # Complete that test-owned work before teardown can delete the User.
        # Actual authorization assertions run after this setup-only context.
        with patch.object(frappe, "in_test", True):
            user.insert(ignore_permissions=True)
        self.users[key] = user.name
        self.user_emails.append(email)

        for allow, value in (("Company", company), ("Branch", branch), ("Department", department)):
            if value:
                permission = frappe.get_doc({
                    "doctype": "User Permission",
                    "user": user.name,
                    "allow": allow,
                    "for_value": value,
                    "apply_to_all_doctypes": 1,
                }).insert(ignore_permissions=True)
                self.permissions.append(permission.name)
        frappe.clear_cache(user=user.name)
        return user.name

    def create_employee(self, key: str, company: str, branch: str, department: str,
                        *, user: str | None = None) -> str:
        employee = frappe.get_doc({
            "doctype": "Employee",
            "first_name": f"{self.employee_marker} {key}",
            "employee_name": f"{self.employee_marker} {key}",
            "company": company,
            "branch": branch,
            "department": department,
            "gender": frappe.db.get_value("Gender", {}, "name") or "Female",
            "date_of_birth": "1990-01-01",
            "date_of_joining": "2020-01-01",
            "status": "Active",
            "user_id": user,
            "create_user_permission": 1 if user else 0,
        })
        # Linking an Employee saves its User and creates/updates Contact too.
        # Keep that native fixture side effect synchronous, as in create_user.
        with patch.object(frappe, "in_test", True):
            employee.insert(ignore_permissions=True)
        self.employees.append(employee.name)
        if user:
            self.permissions.extend(frappe.get_all(
                "User Permission", filters={"user": user}, pluck="name"
            ))
        return employee.name

    def cleanup(self) -> None:
        """Remove only marker-owned records and verify their absence."""
        frappe.set_user("Administrator")
        for name in reversed(self.employees):
            if frappe.db.exists("Employee", name):
                frappe.delete_doc("Employee", name, force=True, ignore_permissions=True)
        for name in reversed(list(dict.fromkeys(self.permissions))):
            if frappe.db.exists("User Permission", name):
                frappe.delete_doc("User Permission", name, force=True, ignore_permissions=True)
        for name in reversed(list(self.users.values())):
            if frappe.db.exists("User", name):
                # Contacts created automatically for these synthetic users are
                # test-owned too. Delete them explicitly so User.on_trash does
                # not bulk-update Contact rows after earlier fixture commits.
                for contact in frappe.get_all("Contact", filters={"user": name}, pluck="name"):
                    frappe.delete_doc("Contact", contact, force=True, ignore_permissions=True)
                assert not frappe.get_all("Contact", filters={"user": name}, pluck="name")
                frappe.db.commit()
                # Keep native notification/auth cleanup. This MariaDB build
                # can report a Contact snapshot conflict (1020), which Frappe
                # classifies as QueryDeadlockError. Retry the entire native
                # User teardown in a fresh transaction, never skip its hooks.
                for attempt in range(3):
                    try:
                        frappe.delete_doc("User", name, force=True, ignore_permissions=True)
                        break
                    except frappe.QueryDeadlockError:
                        frappe.db.rollback()
                        if attempt == 2:
                            raise
                frappe.db.commit()
        frappe.clear_cache()
        frappe.db.commit()

        leftovers = {
            "users": frappe.get_all("User", filters={"name": ["in", self.user_emails]}, pluck="name") if self.user_emails else [],
            "employees": frappe.get_all(
                "Employee", filters={"employee_name": ["like", f"{self.employee_marker}%"]}, pluck="name"
            ),
            "permissions": frappe.get_all(
                "User Permission", filters={"user": ["in", list(self.users.values())]}, pluck="name"
            ) if self.users else [],
            "contacts": frappe.get_all(
                "Contact", filters={"user": ["in", self.user_emails]}, pluck="name"
            ) if self.user_emails else [],
            "roles": frappe.get_all(
                "Has Role", filters={"parent": ["in", self.user_emails]}, pluck="name"
            ) if self.user_emails else [],
            "notification_settings": frappe.get_all(
                "Notification Settings", filters={"name": ["in", self.user_emails]}, pluck="name"
            ) if self.user_emails else [],
        }
        assert not any(leftovers.values()), f"synthetic persona cleanup incomplete: {leftovers}"


def assert_only_workforce_roles(user: str) -> None:
    """Guard against accidental native HR/System Manager test privileges."""
    forbidden = {"HR User", "HR Manager", "System Manager"}
    assert not forbidden.intersection(frappe.get_roles(user))
