"""Site-backed native User/Role/User Permission and Workspace persona contract."""

from __future__ import annotations

import json
import os
from datetime import date

import frappe
import pytest

from workforce_suite.tests.persona_uat import (
    PERSONA_ROLES,
    SyntheticPersonaHarness,
    assert_only_workforce_roles,
)


@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(
        site=os.environ.get("FRAPPE_TEST_SITE", "hrms-v16.localhost"),
        sites_path=os.environ.get(
            "FRAPPE_TEST_SITES_PATH", "/home/sanchita/frappe-bench-v16/sites"
        ),
        force=True,
    )
    frappe.connect()
    frappe.set_user("Administrator")
    yield
    frappe.set_user("Administrator")
    frappe.destroy()


def _expect_permission(user: str, doctype: str, ptype: str, expected: bool) -> None:
    actual = bool(frappe.has_permission(doctype, ptype=ptype, user=user, throw=False))
    assert actual is expected, f"{user} {ptype} {doctype}: expected {expected}, got {actual}"


def _report_run(report: str, user: str, company: str):
    from frappe.desk.query_report import run

    filters = {
        "company": company,
        "attendance_date": date.today().isoformat(),
        "as_of_date": date.today().isoformat(),
        "from_date": date.today().replace(day=1).isoformat(),
        "to_date": date.today().isoformat(),
        "employee_status": "All",
        "assignment_status": "All",
    }
    frappe.set_user(user)
    return run(report, filters=filters)


def _workspace_payload(user: str):
    from frappe.desk.desktop import get_desktop_page, get_workspaces

    frappe.set_user(user)
    pages = get_workspaces()["pages"]
    page = next((row for row in pages if row.get("name") == "workforce-suite"), None)
    if not page:
        return None
    return get_desktop_page(json.dumps(page))


def test_native_persona_access_report_and_workspace_contract():
    company_a = "Example Company A"
    company_b = "Example Company B"
    assert frappe.db.exists("Company", company_a) and frappe.db.exists("Company", company_b)
    branches_a = frappe.get_all("Branch", filters={"company": company_a}, pluck="name", order_by="name")
    branches_b = frappe.get_all("Branch", filters={"company": company_b}, pluck="name", order_by="name")
    departments_a = frappe.get_all(
        "Department", filters={"company": company_a}, pluck="name", order_by="name"
    )
    departments_b = frappe.get_all(
        "Department", filters={"company": company_b}, pluck="name", order_by="name"
    )
    assert len(branches_a) >= 2 and len(departments_a) >= 2 and branches_b and departments_b

    workspace_doc = frappe.get_doc("Workspace", "workforce-suite")
    from workforce_suite.workforce_suite.action_board import BOARD_ROLES
    assert workspace_doc.public
    assert {row.role for row in workspace_doc.roles} == set(BOARD_ROLES)
    payroll_register_roles = {
        "Workforce Owner/Director", "Workforce Suite Manager", "Workforce Payroll Manager",
        "Workforce Payroll Approver", "Workforce Finance/Accounts Officer",
        "Workforce Compliance Auditor",
    }
    assert {row.role for row in frappe.get_doc("Report", "Workforce Payroll Register").roles} == payroll_register_roles
    assert "Workforce Employee/Worker" not in payroll_register_roles
    total_shortcuts = len(workspace_doc.shortcuts)
    token = f"PUAT{frappe.generate_hash(10).upper()}"
    personas = SyntheticPersonaHarness(token)
    user_map = {}
    employees = {}

    try:
        # One System User per approved Workforce persona. The no-scope and
        # Company-B variants prove that native User Permissions are the scope.
        persona_scopes = {
            "owner": (company_a, None, None),
            "hr_manager": (company_a, None, None),
            "attendance_officer": (company_a, None, None),
            "factory_supervisor": (company_a, branches_a[0], None),
            "branch_manager": (company_a, branches_a[0], None),
            "department_manager": (company_a, None, departments_a[0]),
            "payroll_manager": (company_a, None, None),
            "payroll_approver": (company_a, None, None),
            "finance": (company_a, None, None),
            "compliance": (company_a, None, None),
            "device_admin": (company_a, None, None),
            "attendance_correction_approver": (company_a, None, None),
            "leave_approver": (company_a, None, None),
            "import_reviewer": (company_a, None, None),
            "worker_unlinked": (company_a, None, None),
        }
        for key, (company, branch, department) in persona_scopes.items():
            role_key = "worker" if key == "worker_unlinked" else key
            user_map[key] = personas.create_user(
                key,
                [PERSONA_ROLES[role_key]],
                company=company,
                branch=branch,
                department=department,
            )

        user_map["owner_two_company"] = personas.create_user(
            "owner-two-company", [PERSONA_ROLES["owner"]], company=company_a
        )
        # second Company permission is a separate native User Permission row
        permission = frappe.get_doc({
            "doctype": "User Permission", "user": user_map["owner_two_company"],
            "allow": "Company", "for_value": company_b, "apply_to_all_doctypes": 1,
        }).insert(ignore_permissions=True)
        personas.permissions.append(permission.name)
        user_map["company_b_hr"] = personas.create_user(
            "company-b-hr", [PERSONA_ROLES["hr_manager"]], company=company_b
        )
        user_map["unscoped_hr"] = personas.create_user(
            "unscoped-hr", [PERSONA_ROLES["hr_manager"]]
        )
        user_map["combined_scope"] = personas.create_user(
            "combined-scope", [PERSONA_ROLES["branch_manager"]],
            company=company_a, branch=branches_a[0], department=departments_a[1],
        )
        user_map["hr_payroll_combo"] = personas.create_user(
            "hr-payroll-combo", [PERSONA_ROLES["hr_manager"], PERSONA_ROLES["payroll_manager"]],
            company=company_a,
        )
        user_map["payroll_approver_combo"] = personas.create_user(
            "payroll-approver-combo", [PERSONA_ROLES["payroll_manager"], PERSONA_ROLES["payroll_approver"]],
            company=company_a,
        )
        user_map["owner_hr_combo"] = personas.create_user(
            "owner-hr-combo", [PERSONA_ROLES["owner"], PERSONA_ROLES["hr_manager"]],
            company=company_a,
        )
        user_map["worker_linked"] = personas.create_user(
            "worker-linked", [PERSONA_ROLES["worker"], "Employee"], company=company_a
        )

        assert set(PERSONA_ROLES.values()).issubset(
            {row.name for row in frappe.get_all("Role", fields=["name"])}
        )
        for key, user in user_map.items():
            assert_only_workforce_roles(user)

        # Scoped synthetic Employees span both Companies, two Branches and two
        # Departments. The linked Worker is deliberately its own separate row.
        employees["a"] = personas.create_employee(company_a, company_a, branches_a[0], departments_a[0])
        employees["b"] = personas.create_employee(company_a, company_a, branches_a[1], departments_a[1])
        employees["c"] = personas.create_employee(company_b, company_b, branches_b[0], departments_b[0])
        employees["worker"] = personas.create_employee(
            "worker", company_a, branches_a[0], departments_a[0], user=user_map["worker_linked"]
        )

        # Synthetic persona contract: actual Frappe permission evaluation, not
        # role-name assumptions. This also tests key operation distinctions.
        checks = {
            "owner": [("Employee", "read", True), ("Salary Slip", "read", True)],
            "hr_manager": [("Employee", "create", True), ("Employee Transfer", "submit", True),
                           ("Employee Separation", "create", True),
                           ("Salary Structure Assignment", "create", True),
                           ("Salary Structure Assignment", "submit", False)],
            "attendance_officer": [("Attendance", "write", True),
                                   ("Employee Checkin", "create", False),
                                   ("Salary Slip", "read", False)],
            "factory_supervisor": [("Workforce Field Duty", "create", True),
                                   ("Attendance", "read", True), ("Salary Slip", "read", False)],
            "branch_manager": [("Employee", "read", True), ("Attendance", "read", True),
                               ("Salary Slip", "read", False)],
            "department_manager": [("Employee", "read", True), ("Attendance", "read", True),
                                   ("Salary Slip", "read", False)],
            "payroll_manager": [("Salary Structure Assignment", "create", True),
                                ("Salary Slip", "submit", True), ("Payroll Entry", "submit", True),
                                ("Attendance", "write", False)],
            "payroll_approver": [("Salary Structure Assignment", "submit", True),
                                 ("Payroll Entry", "submit", True),
                                 ("Salary Slip", "submit", False)],
            "finance": [("Salary Slip", "read", True), ("Salary Slip", "write", False),
                        ("Full and Final Statement", "submit", True)],
            "compliance": [("Salary Slip", "read", True), ("Salary Slip", "write", False),
                           ("Workforce Wage Floor Classification", "read", True)],
            "device_admin": [("Workforce Biometric Device", "write", True),
                             ("Employee", "write", False), ("Salary Slip", "read", False)],
            "attendance_correction_approver": [("Attendance Request", "submit", True),
                                               ("Attendance Request", "cancel", False),
                                               ("Employee", "read", True),
                                               ("Salary Slip", "read", False)],
            "leave_approver": [("Leave Application", "submit", True),
                               ("Company", "read", True),
                               ("Employee", "read", True),
                               ("Leave Allocation", "read", True),
                               ("Leave Allocation", "report", True),
                               ("Leave Allocation", "export", False),
                               ("Leave Allocation", "print", False),
                               ("Leave Allocation", "create", False)],
            "import_reviewer": [("Workforce Employee Biometric", "write", True),
                                ("Employee", "write", False)],
            "worker_unlinked": [("Employee", "read", False),
                                ("Employee Checkin", "read", False),
                                ("Leave Allocation", "read", False),
                                ("Salary Slip", "read", False)],
            "worker_linked": [("Employee", "read", True),
                              ("Employee Checkin", "read", True),
                              ("Leave Application", "create", True),
                              ("Attendance Request", "create", True),
                              ("Employee Checkin", "create", False),
                              # Native Employee grants the DocType read bit;
                              # User Permission still has to restrict each row.
                              ("Salary Slip", "read", True)],
        }
        for persona, assertions in checks.items():
            for doctype, ptype, expected in assertions:
                _expect_permission(user_map[persona], doctype, ptype, expected)

        # Native company/branch/department User Permissions apply as filters
        # on actual get_list and direct document authorization.
        all_employee_names = list(employees.values())
        for persona, expected_names in (
            ("branch_manager", {employees["a"], employees["worker"]}),
            ("department_manager", {employees["a"], employees["worker"]}),
            ("company_b_hr", {employees["c"]}),
            ("combined_scope", set()),
            ("hr_manager", {employees["a"], employees["b"], employees["worker"]}),
            ("owner_two_company", set(all_employee_names)),
        ):
            user = user_map[persona]
            frappe.set_user(user)
            actual = set(frappe.get_list(
                "Employee", filters={"name": ["in", all_employee_names]}, pluck="name"
            ))
            assert actual == expected_names, f"{persona} native scope expected {expected_names}, got {actual}"

        # Without a Company User Permission, Frappe does not infer a Company
        # restriction from the Workforce role. This is a real provisioning gate.
        frappe.set_user(user_map["unscoped_hr"])
        unscoped_rows = set(frappe.get_list(
            "Employee", filters={"name": ["in", all_employee_names]}, pluck="name"
        ))
        assert unscoped_rows == set(all_employee_names)

        worker = user_map["worker_linked"]
        frappe.set_user(worker)
        worker_rows = set(frappe.get_list("Employee", filters={"name": ["in", all_employee_names]}, pluck="name"))
        assert worker_rows == {employees["worker"]}
        own_employee = frappe.get_doc("Employee", employees["worker"])
        own_employee.check_permission("read")
        with pytest.raises(frappe.PermissionError):
            frappe.get_doc("Employee", employees["a"]).check_permission("read")
        own_attendance = frappe.get_doc({
            "doctype": "Attendance", "employee": employees["worker"], "company": company_a,
        })
        other_attendance = frappe.get_doc({
            "doctype": "Attendance", "employee": employees["a"], "company": company_a,
        })
        assert frappe.has_permission(own_attendance, ptype="read", user=worker, throw=False)
        assert not frappe.has_permission(other_attendance, ptype="read", user=worker, throw=False)
        own_checkin = frappe.get_doc({
            "doctype": "Employee Checkin", "employee": employees["worker"],
        })
        other_checkin = frappe.get_doc({"doctype": "Employee Checkin", "employee": employees["a"]})
        assert frappe.has_permission(own_checkin, ptype="read", user=worker, throw=False)
        assert not frappe.has_permission(other_checkin, ptype="read", user=worker, throw=False)
        own_slip = frappe.get_doc({
            "doctype": "Salary Slip", "employee": employees["worker"], "company": company_a,
        })
        other_slip = frappe.get_doc({
            "doctype": "Salary Slip", "employee": employees["a"], "company": company_a,
        })
        assert frappe.has_permission(own_slip, ptype="read", user=worker, throw=False)
        assert not frappe.has_permission(other_slip, ptype="read", user=worker, throw=False)
        own_leave = frappe.get_doc({"doctype": "Leave Application", "employee": employees["worker"]})
        other_leave = frappe.get_doc({"doctype": "Leave Application", "employee": employees["a"]})
        assert frappe.has_permission(own_leave, ptype="create", user=worker, throw=False)
        assert not frappe.has_permission(other_leave, ptype="create", user=worker, throw=False)
        own_correction = frappe.get_doc({"doctype": "Attendance Request", "employee": employees["worker"]})
        other_correction = frappe.get_doc({"doctype": "Attendance Request", "employee": employees["a"]})
        assert frappe.has_permission(own_correction, ptype="create", user=worker, throw=False)
        assert not frappe.has_permission(other_correction, ptype="create", user=worker, throw=False)

        # Role combinations union their native DocPerm, while existing service
        # guards remain responsible for maker/checker separation.
        assert frappe.has_permission("Salary Slip", "submit", user=user_map["hr_payroll_combo"])
        assert frappe.has_permission("Salary Structure Assignment", "submit", user=user_map["payroll_approver_combo"])
        assert frappe.has_permission("Employee", "write", user=user_map["owner_hr_combo"])
        # Actual Report endpoint checks representative operational and money
        # surfaces; report-role metadata is independently tested per persona.
        endpoint_expectations = (
            ("Workforce Daily Attendance Board", "attendance_officer", True),
            ("Workforce Shift Coverage", "factory_supervisor", True),
            ("Workforce Joiners and Leavers", "branch_manager", True),
            ("Workforce Leave Balance Board", "leave_approver", True),
            ("Workforce Salary Coverage Board", "payroll_manager", True),
            ("Workforce Salary Coverage Board", "factory_supervisor", False),
            ("Workforce Pay Component Register", "payroll_manager", True),
            ("Workforce Payroll Variance", "payroll_approver", True),
            ("Workforce Payroll Register", "finance", True),
            ("Workforce Payroll Register", "payroll_manager", True),
            ("Workforce Payroll Register", "factory_supervisor", False),
            ("Workforce Payroll Variance", "factory_supervisor", False),
            ("Workforce Daily Attendance Board", "worker_unlinked", False),
            ("Workforce Pay Component Register", "worker_linked", False),
        )
        endpoint_results = {}
        for report, persona, expected in endpoint_expectations:
            try:
                result = _report_run(report, user_map[persona], company_a)
                endpoint_results[(report, persona)] = "allowed"
                assert expected, f"{persona} unexpectedly executed {report}"
                assert isinstance(result, dict)
            except frappe.PermissionError as exc:
                endpoint_results[(report, persona)] = "denied"
                assert not expected, f"{persona} was denied {report}: {exc}"

        # Workspace is public, but Frappe DeskViews filters each shortcut by
        # the user's actual DocType/Report/Page access before returning it.
        sensitive = {
            "Salary Slips", "Salary Structures", "Salary Assignments", "Salary Components",
            "Extra Pay & Deductions", "Payroll Register", "Payroll Variance",
            "Pay Component Register", "Salary Setup Coverage", "Run Monthly Payroll",
        }
        workspace_results = {}
        for persona, user in user_map.items():
            payload = _workspace_payload(user)
            shortcuts = (payload or {}).get("shortcuts", {}).get("items", [])
            chart_items = (payload or {}).get("charts", {}).get("items", [])
            number_card_items = (payload or {}).get("number_cards", {}).get("items", [])
            visible_sensitive = sorted(item.get("label") for item in shortcuts if item.get("label") in sensitive)
            workspace_results[persona] = {
                "workspace_accessible": payload is not None,
                "visible_shortcut_count": len(shortcuts),
                "sensitive_shortcuts": visible_sensitive,
                "inaccessible_shortcut_count": total_shortcuts - len(shortcuts),
                "card_count": len((payload or {}).get("cards", {}).get("items", [])),
                "number_card_count": len(number_card_items),
                "chart_count": len(chart_items),
                "visible_charts": sorted(item.get("chart_name") for item in chart_items),
            }
        assert workspace_results["factory_supervisor"]["workspace_accessible"]
        assert not workspace_results["factory_supervisor"]["sensitive_shortcuts"]
        assert not workspace_results["branch_manager"]["sensitive_shortcuts"]
        assert not workspace_results["department_manager"]["sensitive_shortcuts"]
        assert not workspace_results["attendance_officer"]["sensitive_shortcuts"]
        assert not workspace_results["attendance_correction_approver"]["sensitive_shortcuts"]
        assert not workspace_results["leave_approver"]["sensitive_shortcuts"]
        assert not workspace_results["worker_unlinked"]["sensitive_shortcuts"]
        for persona in ("hr_manager", "payroll_manager", "payroll_approver", "finance", "compliance"):
            assert "Payroll Register" in workspace_results[persona]["sensitive_shortcuts"]
        for persona in (
            "attendance_officer", "factory_supervisor", "branch_manager",
            "department_manager", "attendance_correction_approver", "leave_approver",
        ):
            assert "Workforce Payroll by Month" not in workspace_results[persona]["visible_charts"]
        print("PERSONA_WORKSPACE_AUDIT=" + json.dumps(workspace_results, sort_keys=True))
        print("PERSONA_REPORT_ENDPOINTS=" + json.dumps({f"{r}|{p}": v for (r, p), v in endpoint_results.items()}, sort_keys=True))

    finally:
        personas.cleanup()
