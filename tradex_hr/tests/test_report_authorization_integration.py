"""Site-backed authorization tests for company-sensitive Tradexcel reports."""

from __future__ import annotations

import os
from datetime import date, timedelta

import frappe
import pytest


@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(
        site=os.environ.get("FRAPPE_TEST_SITE", "hrms-v16.localhost"),
        sites_path=os.environ.get("FRAPPE_TEST_SITES_PATH", "/home/sanchita/frappe-bench-v16/sites"),
        force=True,
    )
    frappe.connect()
    previous_user = frappe.session.user
    frappe.set_user("Administrator")
    yield
    frappe.set_user(previous_user)
    frappe.destroy()


def _user(role: str, token: str, company: str, *, branch: str | None = None,
          department: str | None = None) -> tuple[str, list[str]]:
    user = frappe.get_doc({
        "doctype": "User",
        "email": f"{token.lower()}-{frappe.generate_hash(8)}@example.test",
        "first_name": f"TEST {token} {role[-8:]}",
        "enabled": 1,
        "user_type": "System User",
        "send_welcome_email": 0,
        "roles": [{"role": role}],
    }).insert(ignore_permissions=True)
    permissions = []
    for allow, value in (("Company", company), ("Branch", branch), ("Department", department)):
        if not value:
            continue
        permission = frappe.get_doc({
            "doctype": "User Permission",
            "user": user.name,
            "allow": allow,
            "for_value": value,
            "apply_to_all_doctypes": 1,
        }).insert(ignore_permissions=True)
        permissions.append(permission.name)
    return user.name, permissions


def _employee(company: str, branch: str, department: str, token: str,
              user: str | None = None, employment_type: str | None = None) -> str:
    employee = frappe.get_doc({
        "doctype": "Employee",
        "first_name": f"TEST {token}",
        "employee_name": f"TEST {token}",
        "company": company,
        "branch": branch,
        "department": department,
        "gender": frappe.db.get_value("Gender", {}, "name") or "Female",
        "date_of_birth": "1990-01-01",
        "date_of_joining": "2020-01-01",
        "status": "Active",
        "employment_type": employment_type,
        "user_id": user,
        "create_user_permission": 1 if user else 0,
    }).insert(ignore_permissions=True)
    return employee.name


def _report(report_name: str, company: str, date_filter: str, token: str, **extra):
    from frappe.desk.query_report import run

    filters = {"company": company, date_filter: date.today().isoformat(), **extra}
    return run(report_name, filters=filters)


def _cleanup(tracked):
    frappe.set_user("Administrator")
    for name in reversed(tracked.get("Salary Structure Assignment", [])):
        if frappe.db.exists("Salary Structure Assignment", name):
            doc = frappe.get_doc("Salary Structure Assignment", name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Salary Structure Assignment", name, force=True, ignore_permissions=True)
    for name in reversed(tracked.get("Salary Structure", [])):
        if frappe.db.exists("Salary Structure", name):
            doc = frappe.get_doc("Salary Structure", name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Salary Structure", name, force=True, ignore_permissions=True)
    for doctype in ("Leave Application", "Leave Allocation", "Employee Checkin", "Attendance"):
        for name in reversed(tracked[doctype]):
            if frappe.db.exists(doctype, name):
                doc = frappe.get_doc(doctype, name)
                if doc.docstatus == 1:
                    doc.cancel()
                frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
    for name in reversed(tracked["Employee"]):
        if frappe.db.exists("Employee", name):
            frappe.delete_doc("Employee", name, force=True, ignore_permissions=True)
    for name in reversed(tracked["User Permission"]):
        if frappe.db.exists("User Permission", name):
            frappe.delete_doc("User Permission", name, force=True, ignore_permissions=True)
    for name in reversed(tracked["User"]):
        if frappe.db.exists("User", name):
            frappe.delete_doc("User", name, force=True, ignore_permissions=True)
    frappe.clear_cache()


def _track(tracked, doctype, doc):
    tracked[doctype].append(doc.name)
    return doc


def test_report_roles_and_company_branch_department_scope():
    company_a = "Tradexcel Ceramics Ltd."
    company_b = "Elegance Footwear Ltd."
    assert frappe.db.exists("Company", company_a) and frappe.db.exists("Company", company_b)
    branches = frappe.get_all("Branch", filters={"company": company_a}, pluck="name", order_by="name")
    departments = frappe.get_all("Department", filters={"company": company_a}, pluck="name", order_by="name")
    other_branches = frappe.get_all("Branch", filters={"company": company_b}, pluck="name", order_by="name")
    other_departments = frappe.get_all("Department", filters={"company": company_b}, pluck="name", order_by="name")
    assert len(branches) >= 2 and len(departments) >= 2 and other_branches and other_departments

    token = f"RPT{frappe.generate_hash(8).upper()}"
    tracked = {key: [] for key in (
        "User", "User Permission", "Employee", "Attendance", "Employee Checkin",
        "Leave Allocation", "Leave Application",
    )}
    users = {}
    employees = {}
    try:
        users["branch"] = _user("Tradexcel Branch Manager", token + "B", company_a, branch=branches[0])
        tracked["User"].append(users["branch"][0]); tracked["User Permission"].extend(users["branch"][1])
        users["department"] = _user("Tradexcel Department Manager", token + "D", company_a, department=departments[0])
        tracked["User"].append(users["department"][0]); tracked["User Permission"].extend(users["department"][1])
        users["combined"] = _user("Tradexcel Branch Manager", token + "X", company_a,
                                   branch=branches[0], department=departments[0])
        tracked["User"].append(users["combined"][0]); tracked["User Permission"].extend(users["combined"][1])
        users["company"] = _user("Tradexcel HR/Attendance Officer", token + "H", company_a)
        tracked["User"].append(users["company"][0]); tracked["User Permission"].extend(users["company"][1])
        users["hr_manager"] = _user("Tradexcel HR Manager", token + "M", company_a)
        tracked["User"].append(users["hr_manager"][0]); tracked["User Permission"].extend(users["hr_manager"][1])
        users["supervisor"] = _user("Tradexcel Factory Supervisor", token + "S", company_a)
        tracked["User"].append(users["supervisor"][0]); tracked["User Permission"].extend(users["supervisor"][1])
        users["company_b"] = _user("Tradexcel HR/Attendance Officer", token + "E", company_b)
        tracked["User"].append(users["company_b"][0]); tracked["User Permission"].extend(users["company_b"][1])
        users["auditor"] = _user("Tradexcel Compliance Auditor", token + "C", company_a)
        tracked["User"].append(users["auditor"][0]); tracked["User Permission"].extend(users["auditor"][1])
        users["worker"] = _user("Tradexcel Employee/Worker", token + "W", company_a)
        tracked["User"].append(users["worker"][0]); tracked["User Permission"].extend(users["worker"][1])

        employees["a"] = _employee(company_a, branches[0], departments[0], token + "A", users["worker"][0])
        employees["b"] = _employee(company_a, branches[1], departments[1], token + "B")
        employees["c"] = _employee(company_b, other_branches[0], other_departments[0], token + "C")
        tracked["Employee"].extend(employees.values())

        day = date.today()
        for key, employee in employees.items():
            attendance = _track(tracked, "Attendance", frappe.get_doc({
                "doctype": "Attendance", "employee": employee,
                "employee_name": frappe.db.get_value("Employee", employee, "employee_name"),
                "company": company_a if key != "c" else company_b,
                "attendance_date": day, "status": "Present",
            }).insert(ignore_permissions=True))
            checkin = _track(tracked, "Employee Checkin", frappe.get_doc({
                "doctype": "Employee Checkin", "employee": employee,
                "time": f"{day.isoformat()} 08:00:00", "log_type": "IN",
            }).insert(ignore_permissions=True))
            assert attendance.name and checkin.name

        leave_type = frappe.db.get_value("Leave Type", {}, "name")
        assert leave_type, "Site needs an existing native Leave Type for synthetic access proof"
        for employee in employees.values():
            allocation = _track(tracked, "Leave Allocation", frappe.get_doc({
                "doctype": "Leave Allocation", "employee": employee,
                "employee_name": frappe.db.get_value("Employee", employee, "employee_name"),
                "leave_type": leave_type, "from_date": day,
                "to_date": day + timedelta(days=30), "new_leaves_allocated": 1,
            }).insert(ignore_permissions=True))
            allocation.submit()
            assert allocation.name

        expected_report_roles = {
            "Tradexcel Daily Attendance Board": {
                "Tradexcel Owner/Director", "Tradexcel HR Manager",
                "Tradexcel HR/Attendance Officer", "Tradexcel Factory Supervisor",
                "Tradexcel Branch Manager", "Tradexcel Department Manager",
                "Tradexcel Attendance Correction Approver", "Tradexcel Compliance Auditor",
            },
            "Tradexcel Leave Balance Board": {
                "Tradexcel Owner/Director", "Tradexcel HR Manager",
                "Tradexcel HR/Attendance Officer", "Tradexcel Factory Supervisor",
                "Tradexcel Branch Manager", "Tradexcel Department Manager",
                "Tradexcel Compliance Auditor",
            },
        }
        for report_name, expected_roles in expected_report_roles.items():
            report = frappe.get_doc("Report", report_name)
            assert {row.role for row in report.roles} == expected_roles

        frappe.set_user(users["branch"][0])
        # Reproduce the prior Script Report's Company-only SQL boundary: direct
        # SQL does not apply User Permissions and returns the out-of-Branch row.
        raw_rows = frappe.db.sql(
            "SELECT e.name, COUNT(c.name) AS punches FROM `tabEmployee` e "
            "LEFT JOIN `tabAttendance` a ON a.employee=e.name AND a.attendance_date=%(day)s AND a.docstatus<2 "
            "LEFT JOIN `tabEmployee Checkin` c ON c.employee=e.name AND DATE(c.time)=%(day)s "
            "WHERE e.company=%(company)s GROUP BY e.name, a.name",
            {"company": company_a, "day": date.today()}, as_dict=True,
        )
        old_report_rows = {row.name: row for row in raw_rows}
        assert employees["b"] in old_report_rows and old_report_rows[employees["b"]].punches == 1
        attendance = _report("Tradexcel Daily Attendance Board", company_a, "attendance_date", token)
        assert employees["a"] in {row.employee for row in attendance["result"]}
        assert employees["b"] not in {row.employee for row in attendance["result"]}
        assert all(row.branch in (None, "", branches[0]) for row in attendance["result"])
        # Caller-supplied filters can only narrow the already permitted set.
        assert _report("Tradexcel Daily Attendance Board", company_a, "attendance_date", token,
                       branch=branches[1])["result"] == []

        frappe.set_user(users["combined"][0])
        combined = _report("Tradexcel Daily Attendance Board", company_a, "attendance_date", token)
        assert employees["a"] in {row.employee for row in combined["result"]}
        assert employees["b"] not in {row.employee for row in combined["result"]}
        assert all(row.branch in (None, "", branches[0]) for row in combined["result"])
        assert all(row.department in (None, "", departments[0]) for row in combined["result"])

        frappe.set_user(users["department"][0])
        leave = _report("Tradexcel Leave Balance Board", company_a, "as_of_date", token)
        assert employees["a"] in {row.employee for row in leave["result"]}
        assert employees["b"] not in {row.employee for row in leave["result"]}
        assert all(row.department in (None, "", departments[0]) for row in leave["result"])
        assert _report("Tradexcel Leave Balance Board", company_a, "as_of_date", token,
                       department=departments[1])["result"] == []

        frappe.set_user(users["company"][0])
        attendance = _report("Tradexcel Daily Attendance Board", company_a, "attendance_date", token)
        company_rows = {row.employee for row in attendance["result"]}
        assert {employees["a"], employees["b"]} <= company_rows
        assert employees["c"] not in company_rows
        assert all(row.company == company_a for row in attendance["result"])
        with pytest.raises(frappe.PermissionError):
            _report("Tradexcel Daily Attendance Board", company_b, "attendance_date", token)

        for persona in ("hr_manager", "supervisor"):
            frappe.set_user(users[persona][0])
            scoped = _report("Tradexcel Daily Attendance Board", company_a, "attendance_date", token)
            scoped_names = {row.employee for row in scoped["result"]}
            assert {employees["a"], employees["b"]} <= scoped_names
            assert employees["c"] not in scoped_names

        frappe.set_user(users["company_b"][0])
        company_b_rows = _report("Tradexcel Daily Attendance Board", company_b, "attendance_date", token)
        company_b_names = {row.employee for row in company_b_rows["result"]}
        assert employees["c"] in company_b_names
        assert not ({employees["a"], employees["b"]} & company_b_names)

        frappe.set_user(users["auditor"][0])
        leave = _report("Tradexcel Leave Balance Board", company_a, "as_of_date", token)
        company_rows = {row.employee for row in leave["result"]}
        assert {employees["a"], employees["b"]} <= company_rows
        assert employees["c"] not in company_rows

        frappe.set_user(users["worker"][0])
        raw_rows = frappe.db.sql(
            "SELECT e.name FROM `tabLeave Allocation` la "
            "JOIN `tabEmployee` e ON e.name=la.employee WHERE e.company=%(company)s",
            {"company": company_a}, as_dict=True,
        )
        assert employees["b"] in {row.name for row in raw_rows}
        from frappe.desk.query_report import run
        with pytest.raises(frappe.PermissionError):
            run("Tradexcel Leave Balance Board", filters={
                "company": company_a, "as_of_date": day.isoformat(),
            })
        with pytest.raises(frappe.PermissionError):
            run("Tradexcel Daily Attendance Board", filters={
                "company": company_a, "attendance_date": day.isoformat(),
            })
        # Direct server-side execution remains Employee-scoped even when the
        # Desk Report-role gate is bypassed by an internal caller.
        from tradex_hr.tradexcel_hr.report.tradexcel_leave_balance_board.tradexcel_leave_balance_board import execute
        _, direct_rows = execute({"company": company_a, "as_of_date": day.isoformat()})
        assert {row.employee for row in direct_rows} == {employees["a"]}
        from tradex_hr.tradexcel_hr.report.tradexcel_daily_attendance_board.tradexcel_daily_attendance_board import execute as attendance_execute
        _, direct_attendance_rows = attendance_execute({"company": company_a, "attendance_date": day.isoformat()})
        assert {row.employee for row in direct_attendance_rows} == {employees["a"]}
    finally:
        _cleanup(tracked)


def test_worker_native_doctype_access_is_own_employee_scoped():
    company = "Tradexcel Ceramics Ltd."
    branches = frappe.get_all("Branch", filters={"company": company}, pluck="name", order_by="name")
    departments = frappe.get_all("Department", filters={"company": company}, pluck="name", order_by="name")
    assert branches and len(departments) >= 2
    token = f"OWN{frappe.generate_hash(8).upper()}"
    tracked = {key: [] for key in (
        "User", "User Permission", "Employee", "Attendance", "Employee Checkin",
        "Leave Allocation", "Leave Application",
    )}
    try:
        worker, permissions = _user("Tradexcel Employee/Worker", token, company)
        tracked["User"].append(worker); tracked["User Permission"].extend(permissions)
        unlinked_worker, unlinked_permissions = _user("Tradexcel Employee/Worker", token + "U", company)
        tracked["User"].append(unlinked_worker); tracked["User Permission"].extend(unlinked_permissions)
        own = _employee(company, branches[0], departments[0], token + "A", worker)
        other = _employee(company, branches[0], departments[1], token + "B")
        tracked["Employee"].extend([own, other])
        day = date.today()
        records = {}
        for doctype, employee, extra in (
            ("Attendance", own, {"company": company, "attendance_date": day, "status": "Present"}),
            ("Attendance", other, {"company": company, "attendance_date": day, "status": "Present"}),
            ("Employee Checkin", own, {"time": f"{day.isoformat()} 08:00:00", "log_type": "IN"}),
            ("Employee Checkin", other, {"time": f"{day.isoformat()} 08:00:00", "log_type": "IN"}),
        ):
            doc = frappe.get_doc({"doctype": doctype, "employee": employee, **extra}).insert(ignore_permissions=True)
            _track(tracked, doctype, doc)
            records[(doctype, employee)] = doc.name
        leave_type = frappe.db.get_value("Leave Type", {}, "name")
        assert leave_type
        for employee in (own, other):
            allocation = frappe.get_doc({
                "doctype": "Leave Allocation", "employee": employee,
                "employee_name": frappe.db.get_value("Employee", employee, "employee_name"),
                "leave_type": leave_type, "from_date": day,
                "to_date": day + timedelta(days=30), "new_leaves_allocated": 1,
            }).insert(ignore_permissions=True)
            allocation.submit()
            _track(tracked, "Leave Allocation", allocation)
            records[("Leave Allocation", employee)] = allocation.name
            leave_application = frappe.get_doc({
                "doctype": "Leave Application", "employee": employee,
                "leave_type": leave_type, "from_date": day + timedelta(days=2),
                "to_date": day + timedelta(days=2), "company": company,
                "leave_approver": "Administrator",
                "description": f"Synthetic authorization fixture {token}",
            }).insert(ignore_permissions=True)
            _track(tracked, "Leave Application", leave_application)
            records[("Leave Application", employee)] = leave_application.name

        frappe.set_user(worker)
        expected = {
            "Employee": own,
            "Employee Checkin": records[("Employee Checkin", own)],
            "Attendance": records[("Attendance", own)],
            "Leave Allocation": records[("Leave Allocation", own)],
            "Leave Application": records[("Leave Application", own)],
        }
        other_names = {
            "Employee": other,
            "Employee Checkin": records[("Employee Checkin", other)],
            "Attendance": records[("Attendance", other)],
            "Leave Allocation": records[("Leave Allocation", other)],
            "Leave Application": records[("Leave Application", other)],
        }
        native_employee_scoped = {"Employee", "Employee Checkin", "Attendance", "Leave Application"}
        for doctype, own_name in expected.items():
            if doctype not in native_employee_scoped:
                assert not frappe.has_permission(doctype, "read", own_name)
                assert not frappe.has_permission(doctype, "read", other_names[doctype])
                with pytest.raises(frappe.PermissionError):
                    frappe.get_list(doctype, filters={"name": ["in", [own_name, other_names[doctype]]]}, pluck="name")
                for name in (own_name, other_names[doctype]):
                    with pytest.raises(frappe.PermissionError):
                        frappe.get_doc(doctype, name).check_permission("read")
                    with pytest.raises(frappe.PermissionError):
                        frappe.client.get(doctype, name)
                continue
            assert frappe.has_permission(doctype, "read", own_name)
            assert not frappe.has_permission(doctype, "read", other_names[doctype])
            listed = frappe.get_list(doctype, filters={"name": ["in", [own_name, other_names[doctype]]]}, pluck="name")
            assert listed == [own_name]
            # get_doc itself is a trusted internal fetch. Its normal permission
            # check still denies direct document/API access to another Employee.
            assert frappe.get_doc(doctype, other_names[doctype]).name == other_names[doctype]
            with pytest.raises(frappe.PermissionError):
                frappe.get_doc(doctype, other_names[doctype]).check_permission("read")
            with pytest.raises(frappe.PermissionError):
                frappe.client.get(doctype, other_names[doctype])

        # Pre-fix reproduction: the custom role's broad DocPerm applied even
        # to a Worker user that was not linked to an Employee. Company User
        # Permission does not transitively scope these Employee-linked doctypes.
        frappe.set_user(unlinked_worker)
        for doctype in ("Employee Checkin", "Leave Allocation", "Leave Application"):
            name = records[(doctype, own)]
            assert not frappe.has_permission(doctype, "read", name)
            with pytest.raises(frappe.PermissionError):
                frappe.get_list(doctype, filters={"employee": ["in", [own, other]]}, pluck="name")
    finally:
        _cleanup(tracked)


def test_salary_coverage_matches_canonical_explicit_pay_basis():
    from frappe.desk.query_report import run
    from tradex_hr.tradexcel_hr.pay_basis import DAILY, MONTHLY, UNRESOLVED, resolve_pay_basis

    company = "Tradexcel Ceramics Ltd."
    branch = frappe.get_value("Branch", {"company": company}, "name")
    department = frappe.get_value("Department", {"company": company}, "name")
    currency = frappe.db.get_value("Company", company, "default_currency") or "BDT"
    payable = frappe.db.get_value("Company", company, "default_payroll_payable_account")
    cost_center = frappe.db.get_value("Company", company, "cost_center")
    component = frappe.db.get_value("Salary Component", {}, "name")
    assert branch and department and payable and cost_center and component

    token = f"PAY{frappe.generate_hash(8).upper()}"
    tracked = {key: [] for key in (
        "User", "User Permission", "Employee", "Attendance", "Employee Checkin",
        "Leave Allocation", "Leave Application", "Salary Structure", "Salary Structure Assignment",
    )}
    try:
        employee_map = {
            "monthly": _employee(company, branch, department, token + "M", employment_type="Worker"),
            "daily": _employee(company, branch, department, token + "D", employment_type="Intern"),
            "missing": _employee(company, branch, department, token + "N"),
            "no_assignment": _employee(company, branch, department, token + "X"),
        }
        tracked["Employee"].extend(employee_map.values())
        from_date = (date.today() - timedelta(days=1)).isoformat()
        basis_values = {"monthly": MONTHLY, "daily": DAILY, "missing": ""}
        for key, basis in basis_values.items():
            structure = frappe.get_doc({
                "doctype": "Salary Structure",
                "name": f"TEST Report Basis {token} {key}",
                "company": company,
                "currency": currency,
                "payroll_frequency": "Monthly",
                "is_active": "Yes",
                "custom_tradex_pay_basis": basis,
                "earnings": [{"salary_component": component, "amount": 1000}],
            }).insert(ignore_permissions=True)
            structure.submit()
            tracked["Salary Structure"].append(structure.name)
            assignment = frappe.get_doc({
                "doctype": "Salary Structure Assignment",
                "employee": employee_map[key],
                "company": company,
                "currency": currency,
                "salary_structure": structure.name,
                "from_date": from_date,
                "base": 1000,
                "payroll_payable_account": payable,
                "payroll_cost_centers": [{"cost_center": cost_center, "percentage": 100}],
            }).insert(ignore_permissions=True)
            assignment.submit()
            tracked["Salary Structure Assignment"].append(assignment.name)

        user, permissions = _user("Tradexcel HR Manager", token, company)
        tracked["User"].append(user); tracked["User Permission"].extend(permissions)
        frappe.set_user(user)
        filters = {"company": company, "as_of_date": date.today().isoformat(), "employee_status": "All"}
        result = run("Tradexcel Salary Coverage Board", filters=filters)
        rows = {row.employee: row for row in result["result"] if row.employee in employee_map.values()}
        assert set(rows) == set(employee_map.values())
        expected = {
            "monthly": MONTHLY,
            "daily": DAILY,
            "missing": "Pay Basis Missing",
            "no_assignment": "Pay Basis Missing",
        }
        for key, employee in employee_map.items():
            canonical = resolve_pay_basis(employee, date.today())
            row = rows[employee]
            assert row.salary_basis == expected[key]
            if key == "monthly":
                assert canonical["status"] == MONTHLY and row.salary_basis == canonical["status"]
                assert row.assignment_status == "Assigned"
            elif key == "daily":
                assert canonical["status"] == DAILY and row.salary_basis == canonical["status"]
                assert row.assignment_status == "Assigned"
            elif key == "missing":
                assert canonical["status"] == UNRESOLVED and row.assignment_status == "Assigned"
            else:
                assert canonical["status"] == UNRESOLVED and row.assignment_status == "Missing"
    finally:
        _cleanup(tracked)
