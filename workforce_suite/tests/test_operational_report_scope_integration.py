"""Site-backed authorization and native-source tests for operational reports."""

from __future__ import annotations

import os
from datetime import date, timedelta

import frappe
import pytest


@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(
        site=os.environ.get("FRAPPE_TEST_SITE", "test_workforce.localhost"),
        sites_path=os.environ.get(
            "FRAPPE_TEST_SITES_PATH", "./sites"
        ),
        force=True,
    )
    frappe.connect()
    previous_user = frappe.session.user
    frappe.set_user("Administrator")
    yield
    frappe.set_user(previous_user)
    frappe.destroy()


def _track(tracked, doctype, doc):
    tracked[doctype].append(doc.name)
    return doc


def _user(role, token, company, *, branch=None, department=None):
    user = frappe.get_doc({
        "doctype": "User",
        "email": f"op-report-{frappe.generate_hash(14)}@example.test",
        "first_name": f"TEST {token}",
        "enabled": 1,
        "user_type": "System User",
        "send_welcome_email": 0,
        "roles": [{"role": role}],
    }).insert(ignore_permissions=True)
    assert not {"HR User", "HR Manager", "System Manager"}.intersection(frappe.get_roles(user.name))
    permissions = []
    for allow, value in (("Company", company), ("Branch", branch), ("Department", department)):
        if value:
            permission = frappe.get_doc({
                "doctype": "User Permission",
                "user": user.name,
                "allow": allow,
                "for_value": value,
                "apply_to_all_doctypes": 1,
            }).insert(ignore_permissions=True)
            permissions.append(permission.name)
    return user.name, permissions


def _employee(company, branch, department, token, *, joining=None, relieving=None,
              status="Active", default_shift=None):
    return frappe.get_doc({
        "doctype": "Employee",
        "first_name": f"TEST {token}",
        "employee_name": f"TEST {token}",
        "company": company,
        "branch": branch,
        "department": department,
        "gender": frappe.db.get_value("Gender", {}, "name") or "Female",
        "date_of_birth": "1990-01-01",
        "date_of_joining": joining or "2020-01-01",
        "relieving_date": relieving,
        "status": status,
        "default_shift": default_shift,
    }).insert(ignore_permissions=True)


def _cleanup(tracked, original_multiple_shifts):
    frappe.set_user("Administrator")
    try:
        for name in reversed(tracked["Shift Assignment"]):
            if frappe.db.exists("Shift Assignment", name):
                doc = frappe.get_doc("Shift Assignment", name)
                if doc.docstatus == 1:
                    doc.cancel()
                frappe.delete_doc("Shift Assignment", name, force=True, ignore_permissions=True)
        for name in reversed(tracked["Employee"]):
            if frappe.db.exists("Employee", name):
                frappe.delete_doc("Employee", name, force=True, ignore_permissions=True)
        for name in reversed(tracked["Shift Type"]):
            if frappe.db.exists("Shift Type", name):
                frappe.delete_doc("Shift Type", name, force=True, ignore_permissions=True)
        for name in reversed(tracked["User Permission"]):
            if frappe.db.exists("User Permission", name):
                frappe.delete_doc("User Permission", name, force=True, ignore_permissions=True)
        for name in reversed(tracked["User"]):
            if frappe.db.exists("User", name):
                frappe.delete_doc("User", name, force=True, ignore_permissions=True)
    finally:
        frappe.db.set_single_value("HR Settings", "allow_multiple_shift_assignments", original_multiple_shifts)
        frappe.clear_cache()


def _result_names(result):
    return {row.employee for row in result["result"]}


def test_operational_script_reports_are_scoped_and_use_native_sources():
    from frappe.desk.query_report import run
    from workforce_suite.install import STANDARD_SCRIPT_REPORT_NAMES
    from workforce_suite.workforce_suite.report.workforce_joiners_and_leavers.workforce_joiners_and_leavers import execute as execute_movements
    from workforce_suite.workforce_suite.report.workforce_shift_coverage.workforce_shift_coverage import execute as execute_coverage

    company_a = "Example Company A"
    company_b = "Example Company B"
    branches_a = frappe.get_all("Branch", filters={"company": company_a}, pluck="name", order_by="name")
    departments_a = frappe.get_all("Department", filters={"company": company_a}, pluck="name", order_by="name")
    branches_b = frappe.get_all("Branch", filters={"company": company_b}, pluck="name", order_by="name")
    departments_b = frappe.get_all("Department", filters={"company": company_b}, pluck="name", order_by="name")
    assert len(branches_a) >= 2 and len(departments_a) >= 2 and branches_b and departments_b

    role_policy = {
        "Workforce Shift Coverage": {
            "Workforce Owner/Director", "Workforce Suite Manager",
            "Workforce Suite/Attendance Officer", "Workforce Factory Supervisor",
            "Workforce Branch Manager", "Workforce Department Manager",
            "Workforce Compliance Auditor",
        },
        "Workforce Joiners and Leavers": {
            "Workforce Owner/Director", "Workforce Suite Manager",
            "Workforce Suite/Attendance Officer", "Workforce Branch Manager",
            "Workforce Department Manager", "Workforce Compliance Auditor",
        },
    }
    for report_name, expected_roles in role_policy.items():
        report = frappe.get_doc("Report", report_name)
        assert report.report_type == "Script Report"
        assert report.is_standard == "Yes"
        assert report.module == "Workforce Suite"
        assert report.ref_doctype == "Employee"
        actual_roles = {row.role for row in report.roles}
        assert actual_roles == expected_roles
        assert "Workforce Employee/Worker" not in actual_roles
        assert report_name in STANDARD_SCRIPT_REPORT_NAMES

    token = f"OPRPT{frappe.generate_hash(8).upper()}"
    tracked = {key: [] for key in (
        "User", "User Permission", "Employee", "Shift Type", "Shift Assignment",
    )}
    original_multiple_shifts = frappe.db.get_single_value("HR Settings", "allow_multiple_shift_assignments")
    today = date.today()
    start = today - timedelta(days=1)
    end = today + timedelta(days=1)
    try:
        users = {}
        for key, role, branch, department, company in (
            ("hr", "Workforce Suite Manager", None, None, company_a),
            ("attendance", "Workforce Suite/Attendance Officer", None, None, company_a),
            ("supervisor", "Workforce Factory Supervisor", None, None, company_a),
            ("branch", "Workforce Branch Manager", branches_a[0], None, company_a),
            ("department", "Workforce Department Manager", None, departments_a[0], company_a),
            ("combined", "Workforce Branch Manager", branches_a[0], departments_a[0], company_a),
            ("auditor", "Workforce Compliance Auditor", None, None, company_a),
            ("worker", "Workforce Employee/Worker", None, None, company_a),
            ("company_b", "Workforce Suite Manager", None, None, company_b),
        ):
            users[key] = _user(role, token + key.upper(), company, branch=branch, department=department)
            tracked["User"].append(users[key][0])
            tracked["User Permission"].extend(users[key][1])

        shifts = []
        for suffix, start_time, end_time in (
            ("A", "06:00:00", "14:00:00"),
            ("B", "14:00:00", "22:00:00"),
        ):
            shift = frappe.get_doc({
                "doctype": "Shift Type",
                "name": f"TEST {token} {suffix}",
                "start_time": start_time,
                "end_time": end_time,
                "begin_check_in_before_shift_start_time": 0,
                "allow_check_out_after_shift_end_time": 0,
                "enable_auto_attendance": 0,
            }).insert(ignore_permissions=True)
            _track(tracked, "Shift Type", shift)
            shifts.append(shift.name)

        employees = {}
        employees["assigned"] = _track(tracked, "Employee", _employee(
            company_a, branches_a[0], departments_a[0], token + "AS",
            joining=today.isoformat(),
        ))
        employees["missing"] = _track(tracked, "Employee", _employee(
            company_a, branches_a[0], departments_a[0], token + "MI",
            joining="2020-01-01",
        ))
        employees["default"] = _track(tracked, "Employee", _employee(
            company_a, branches_a[0], departments_a[0], token + "DF",
            default_shift=shifts[0],
        ))
        employees["overlap"] = _track(tracked, "Employee", _employee(
            company_a, branches_a[0], departments_a[0], token + "OV",
        ))
        employees["other_branch"] = _track(tracked, "Employee", _employee(
            company_a, branches_a[1], departments_a[0], token + "BR",
        ))
        employees["other_department"] = _track(tracked, "Employee", _employee(
            company_a, branches_a[0], departments_a[1], token + "DP",
        ))
        employees["blank_branch"] = _track(tracked, "Employee", _employee(
            company_a, None, departments_a[0], token + "BB", joining=today.isoformat(),
        ))
        employees["blank_department"] = _track(tracked, "Employee", _employee(
            company_a, branches_a[0], None, token + "BD", joining=today.isoformat(),
        ))
        employees["company_b"] = _track(tracked, "Employee", _employee(
            company_b, branches_b[0], departments_b[0], token + "CB",
            joining=today.isoformat(),
        ))
        employees["leaver"] = _track(tracked, "Employee", _employee(
            company_a, branches_a[0], departments_a[0], token + "LV",
            joining=today.isoformat(), relieving=today.isoformat(), status="Left",
        ))

        frappe.db.set_single_value("HR Settings", "allow_multiple_shift_assignments", 1)
        for employee_key, shift_name in (
            ("assigned", shifts[0]), ("overlap", shifts[0]), ("overlap", shifts[1]),
        ):
            assignment = frappe.get_doc({
                "doctype": "Shift Assignment",
                "employee": employees[employee_key].name,
                "shift_type": shift_name,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "status": "Active",
            }).insert(ignore_permissions=True)
            _track(tracked, "Shift Assignment", assignment)
            assignment.submit()

        base_filters = {
            "company": company_a,
            "as_of_date": today.isoformat(),
            "branch": "",
            "department": "",
            "coverage": "All",
        }
        movement_filters = {
            "company": company_a,
            "from_date": today.isoformat(),
            "to_date": today.isoformat(),
            "branch": "",
            "department": "",
        }

        frappe.set_user(users["hr"][0])
        coverage = run("Workforce Shift Coverage", filters=base_filters)
        hr_names = _result_names(coverage)
        assert {employees[k].name for k in (
            "assigned", "missing", "default", "overlap", "other_branch", "other_department",
        )} <= hr_names
        assert employees["company_b"].name not in hr_names
        movements = run("Workforce Joiners and Leavers", filters=movement_filters)["result"]
        events = [(row.employee, row.movement) for row in movements]
        assert (employees["assigned"].name, "Joined") in events
        assert (employees["leaver"].name, "Joined") in events
        assert (employees["leaver"].name, "Left") in events
        assert (employees["missing"].name, "Joined") not in events

        frappe.set_user(users["attendance"][0])
        officer_rows = run("Workforce Joiners and Leavers", filters=movement_filters)["result"]
        assert any(row.employee == employees["assigned"].name for row in officer_rows)

        frappe.set_user(users["supervisor"][0])
        supervisor_rows = run("Workforce Shift Coverage", filters=base_filters)["result"]
        assert any(row.employee == employees["assigned"].name for row in supervisor_rows)
        with pytest.raises(frappe.PermissionError):
            run("Workforce Joiners and Leavers", filters=movement_filters)

        coverage_by_employee = {row.employee: row.coverage for row in coverage["result"]}
        assert coverage_by_employee[employees["assigned"].name] == "Assigned"
        assert coverage_by_employee[employees["missing"].name] == "No shift assigned — review"
        assert coverage_by_employee[employees["default"].name] == "Default shift only"
        assert coverage_by_employee[employees["overlap"].name] == "Multiple active assignments — review"
        missing_rows = run("Workforce Shift Coverage", filters={**base_filters, "coverage": "Missing"})["result"]
        assert employees["missing"].name in {row.employee for row in missing_rows}
        assert all("No shift assigned" in row.coverage for row in missing_rows)

        frappe.set_user(users["branch"][0])
        branch_names = _result_names(run("Workforce Shift Coverage", filters=base_filters))
        assert employees["other_branch"].name not in branch_names
        assert employees["assigned"].name in branch_names
        # Frappe's native User Permission matching includes blank Link values
        # while apply_strict_user_permissions is disabled on this staging site.
        assert employees["blank_branch"].name in branch_names
        assert _result_names(run("Workforce Shift Coverage", filters={
            **base_filters, "branch": branches_a[1],
        })) == set()
        branch_events = run("Workforce Joiners and Leavers", filters=movement_filters)["result"]
        assert all(row.branch in (None, "", branches_a[0]) for row in branch_events)
        assert run("Workforce Joiners and Leavers", filters={
            **movement_filters, "branch": branches_a[1],
        })["result"] == []

        frappe.set_user(users["department"][0])
        department_names = _result_names(run("Workforce Shift Coverage", filters=base_filters))
        assert employees["other_department"].name not in department_names
        assert employees["assigned"].name in department_names
        assert employees["blank_department"].name in department_names
        assert _result_names(run("Workforce Shift Coverage", filters={
            **base_filters, "department": departments_a[1],
        })) == set()
        department_events = run("Workforce Joiners and Leavers", filters=movement_filters)["result"]
        assert all(row.department in (None, "", departments_a[0]) for row in department_events)
        assert run("Workforce Joiners and Leavers", filters={
            **movement_filters, "department": departments_a[1],
        })["result"] == []

        frappe.set_user(users["combined"][0])
        combined_names = _result_names(run("Workforce Shift Coverage", filters=base_filters))
        assert employees["assigned"].name in combined_names
        assert employees["other_branch"].name not in combined_names
        assert employees["other_department"].name not in combined_names

        frappe.set_user(users["auditor"][0])
        auditor_coverage = run("Workforce Shift Coverage", filters=base_filters)["result"]
        assert any(row.employee == employees["assigned"].name for row in auditor_coverage)
        assert all(row.company == company_a for row in auditor_coverage)
        auditor_rows = run("Workforce Joiners and Leavers", filters=movement_filters)["result"]
        assert any(row.employee == employees["leaver"].name for row in auditor_rows)
        assert all(row.company == company_a for row in auditor_rows)

        frappe.set_user(users["company_b"][0])
        company_b_coverage = run("Workforce Shift Coverage", filters={
            **base_filters, "company": company_b,
        })["result"]
        assert employees["company_b"].name in {row.employee for row in company_b_coverage}
        assert all(row.company == company_b for row in company_b_coverage)
        company_b_rows = run("Workforce Joiners and Leavers", filters={
            **movement_filters, "company": company_b,
        })["result"]
        assert (employees["company_b"].name, "Joined") in {
            (row.employee, row.movement) for row in company_b_rows
        }
        assert all(row.company == company_b for row in company_b_rows)
        with pytest.raises(frappe.PermissionError):
            run("Workforce Shift Coverage", filters=base_filters)

        frappe.set_user(users["worker"][0])
        for report_name, filters in (("Workforce Shift Coverage", base_filters),
                                     ("Workforce Joiners and Leavers", movement_filters)):
            with pytest.raises(frappe.PermissionError):
                run(report_name, filters=filters)

        # Internal server callers bypass Desk role metadata, so execute itself
        # must still resolve and enforce the caller's Employee population.
        frappe.set_user(users["branch"][0])
        _, direct_coverage = execute_coverage(base_filters)
        assert employees["other_branch"].name not in {row.employee for row in direct_coverage}
        _, direct_events = execute_movements(movement_filters)
        assert all(row.branch in (None, "", branches_a[0]) for row in direct_events)
        _, empty_rows = execute_coverage({**base_filters, "branch": branches_a[1]})
        assert empty_rows == []
        _, empty_events = execute_movements({**movement_filters, "department": departments_a[1]})
        assert empty_events == []
    finally:
        _cleanup(tracked, original_multiple_shifts)
        for doctype, names in tracked.items():
            assert all(not frappe.db.exists(doctype, name) for name in names), (
                f"Synthetic {doctype} records remained after cleanup"
            )
