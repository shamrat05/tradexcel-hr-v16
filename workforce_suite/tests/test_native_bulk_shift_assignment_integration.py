"""Site-backed permission and execution tests for HRMS' native bulk tool."""

from __future__ import annotations

import json

import frappe
import pytest
from frappe.utils import add_days, getdate

from workforce_suite.tests.persona_uat import PERSONA_ROLES, SyntheticPersonaHarness, assert_only_workforce_roles


@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(
        site="hrms-v16.localhost",
        sites_path="/home/sanchita/frappe-bench-v16/sites",
        force=True,
    )
    frappe.connect()
    frappe.set_user("Administrator")
    yield
    frappe.set_user("Administrator")
    frappe.destroy()


def _tool_payload(action, company, shift_type, start_date, end_date=None):
    doc = frappe.get_doc("Shift Assignment Tool")
    doc.action = action
    doc.company = company
    doc.shift_type = shift_type
    doc.status = "Active"
    doc.start_date = start_date
    doc.end_date = end_date
    return doc.as_dict()


def _run_tool_method(method, payload, *, args=None):
    from frappe.handler import run_doc_method

    frappe.local.request = frappe._dict(method="POST")
    frappe.local.response.docs = []
    result = run_doc_method(
        method=method,
        docs=json.dumps(payload, default=str),
        args=json.dumps(args, default=str) if args is not None else None,
    )
    return result if result is not None else frappe.response.get("message")


def _workspace_shortcuts(user):
    from frappe.desk.desktop import get_desktop_page, get_workspaces

    frappe.set_user(user)
    page = next(
        (row for row in get_workspaces()["pages"] if row.get("name") == "workforce-suite"),
        None,
    )
    if not page:
        return set()
    payload = get_desktop_page(json.dumps(page))
    return {row.get("label") for row in payload.get("shortcuts", {}).get("items", [])}


def test_native_shift_assignment_tool_scopes_bulk_assignment_and_actions(monkeypatch):
    from hrms.hr.doctype.shift_assignment_tool.shift_assignment_tool import (
        ShiftAssignmentTool as NativeShiftAssignmentTool,
    )

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

    token = f"BULKSHIFT{frappe.generate_hash(9).upper()}"
    personas = SyntheticPersonaHarness(token)
    employees: dict[str, str] = {}
    users: dict[str, str] = {}
    shift_type = f"{token} Day Shift"
    shift_types = [shift_type, f"{token} Later Shift", f"{token} Overlap Shift"]
    later_shift = None
    overlap_shift = None
    preexisting_assignments: list[str] = []
    created_assignments: list[str] = []
    created_shift_requests: list[str] = []
    original_multiple = frappe.db.get_single_value("HR Settings", "allow_multiple_shift_assignments")
    error_log_names: set[str] = set()

    try:
        frappe.set_user("Administrator")
        users["hr_manager"] = personas.create_user(
            "hr-manager",
            [PERSONA_ROLES["hr_manager"]],
            company=company_a,
            branch=branches_a[0],
            department=departments_a[0],
        )
        users["attendance_officer"] = personas.create_user(
            "attendance-officer",
            [PERSONA_ROLES["attendance_officer"]],
            company=company_a,
            branch=branches_a[0],
        )
        users["factory_supervisor"] = personas.create_user(
            "factory-supervisor",
            [PERSONA_ROLES["factory_supervisor"]],
            company=company_a,
            branch=branches_a[0],
        )
        users["branch_manager"] = personas.create_user(
            "branch-manager",
            [PERSONA_ROLES["branch_manager"]],
            company=company_a,
            branch=branches_a[0],
        )
        users["department_manager"] = personas.create_user(
            "department-manager",
            [PERSONA_ROLES["department_manager"]],
            company=company_a,
            department=departments_a[0],
        )
        users["worker"] = personas.create_user(
            "worker", [PERSONA_ROLES["worker"]], company=company_a
        )
        users["native_hr_user"] = personas.create_user(
            "native-hr-user",
            ["HR User"],
            company=company_a,
            branch=branches_a[0],
            department=departments_a[0],
        )
        for key in ("hr_manager", "attendance_officer", "factory_supervisor", "branch_manager", "department_manager", "worker"):
            assert_only_workforce_roles(users[key])
        assert "HR User" in frappe.get_roles(users["native_hr_user"])

        employees["in_scope"] = personas.create_employee(
            "in-scope", company_a, branches_a[0], departments_a[0]
        )
        employees["other_branch"] = personas.create_employee(
            "other-branch", company_a, branches_a[1], departments_a[0]
        )
        employees["other_department"] = personas.create_employee(
            "other-department", company_a, branches_a[0], departments_a[1]
        )
        employees["cross_company"] = personas.create_employee(
            "cross-company",
            company_b,
            branches_b[0],
            departments_b[0],
        )
        employees["overlap"] = personas.create_employee(
            "overlap", company_a, branches_a[0], departments_a[0]
        )
        employees["nonoverlap"] = personas.create_employee(
            "nonoverlap", company_a, branches_a[0], departments_a[0]
        )
        employees["inactive"] = personas.create_employee(
            "inactive", company_a, branches_a[0], departments_a[0]
        )
        employees["left"] = personas.create_employee("left", company_a, branches_a[0], departments_a[0])
        employees["future_joiner"] = personas.create_employee(
            "future-joiner", company_a, branches_a[0], departments_a[0]
        )
        employees["default_only"] = personas.create_employee(
            "default-only", company_a, branches_a[0], departments_a[0]
        )
        employees["partial_failure"] = personas.create_employee(
            "partial-failure", company_a, branches_a[0], departments_a[0]
        )
        frappe.db.set_value("Employee", employees["inactive"], "status", "Inactive")
        frappe.db.set_value("Employee", employees["left"], "status", "Left")
        frappe.db.set_value("Employee", employees["left"], "relieving_date", add_days(getdate(), -1))
        frappe.db.set_value("Employee", employees["future_joiner"], "date_of_joining", add_days(getdate(), 1))
        frappe.db.set_value("Employee", employees["default_only"], "default_shift", shift_type)

        frappe.get_doc({
            "doctype": "Shift Type",
            "name": shift_type,
            "start_time": "08:00:00",
            "end_time": "12:00:00",
        }).insert(ignore_permissions=True)
        later_shift = frappe.get_doc({
            "doctype": "Shift Type",
            "name": shift_types[1],
            "start_time": "14:00:00",
            "end_time": "18:00:00",
        }).insert(ignore_permissions=True)
        overlap_shift = frappe.get_doc({
            "doctype": "Shift Type",
            "name": shift_types[2],
            "start_time": "10:00:00",
            "end_time": "14:00:00",
        }).insert(ignore_permissions=True)

        frappe.db.set_single_value("HR Settings", "allow_multiple_shift_assignments", 0)
        from hrms.hr.doctype.shift_assignment_tool.shift_assignment_tool import create_shift_assignment

        # The overlap row conflicts with the target shift. The non-overlap row
        # has an earlier native assignment which should not block this period.
        overlapping = create_shift_assignment(
            employees["overlap"], company_a, overlap_shift.name, getdate(), add_days(getdate(), 1), "Active"
        )
        prior = create_shift_assignment(
            employees["nonoverlap"], company_a, later_shift.name,
            add_days(getdate(), -4), add_days(getdate(), -2), "Active"
        )
        preexisting_assignments.extend([overlapping.name, prior.name])

        # Baseline reproduction against the installed HRMS controller: a
        # Branch-scoped native HR User can POST an Employee from another
        # Branch when Company and Department still match. The controller's
        # native preview excludes it, but its original bulk_assign trusts IDs.
        native_control = NativeShiftAssignmentTool({
            "doctype": "Shift Assignment Tool",
            "action": "Assign Shift",
            "company": company_a,
            "shift_type": shift_type,
            "start_date": getdate(),
            "end_date": add_days(getdate(), 1),
            "status": "Active",
        })
        frappe.set_user(users["native_hr_user"])
        native_preview = NativeShiftAssignmentTool.get_employees(native_control)
        assert employees["other_branch"] not in {row.employee for row in native_preview}
        NativeShiftAssignmentTool.bulk_assign(native_control, [employees["other_branch"]])
        native_bypass = frappe.get_value(
            "Shift Assignment",
            {"employee": employees["other_branch"], "shift_type": shift_type},
            ["name", "docstatus"],
            as_dict=True,
        )
        # The security follow-up also scopes native Shift Assignment itself.
        # The historical PR25 bypass is now denied downstream even when the
        # original HRMS tool class is called without its selection mixin.
        assert not native_bypass

        frappe.set_user(users["native_hr_user"])
        NativeShiftAssignmentTool.bulk_assign(native_control, [employees["cross_company"]])
        assert not frappe.get_all(
            "Shift Assignment",
            filters={"employee": employees["cross_company"], "shift_type": shift_type},
        )

        # Actual native Desk document-method endpoint: custom roles have only
        # native Workforce roles plus User Permissions, never HR User/Manager.
        endpoint_results = {}
        preview = {}
        for key in ("hr_manager", "attendance_officer"):
            user = users[key]
            for ptype, expected in (("read", True), ("create", False), ("write", False), ("cancel", False)):
                if ptype == "read":
                    assert frappe.has_permission("Shift Assignment Tool", ptype, user=user) is expected
            for ptype, expected in (
                ("read", True), ("create", True), ("write", True), ("submit", True),
                ("cancel", False), ("delete", False), ("export", False),
            ):
                assert frappe.has_permission("Shift Assignment", ptype, user=user) is expected
            frappe.set_user(user)
            payload = _tool_payload("Assign Shift", company_a, shift_type, getdate(), add_days(getdate(), 1))
            result = _run_tool_method("get_employees", payload)
            preview[key] = {row.employee: row for row in result}
            endpoint_results[key] = "allowed"
            assert employees["in_scope"] in preview[key]
            assert employees["other_branch"] not in preview[key]
            if key == "hr_manager":
                assert employees["other_department"] not in preview[key]
            else:
                assert employees["other_department"] in preview[key]
            assert employees["cross_company"] not in preview[key]
            assert employees["overlap"] not in preview[key]
            assert employees["nonoverlap"] in preview[key]  # earlier non-overlapping history is retained
            assert employees["inactive"] not in preview[key]
            assert employees["left"] not in preview[key]
            assert employees["future_joiner"] not in preview[key]
            assert employees["default_only"] in preview[key]
            assert preview[key][employees["default_only"]].default_shift == shift_type

        # Manual filters narrow the set; supplying an out-of-scope Branch,
        # Department, or Company cannot return an Employee from it.
        frappe.set_user(users["hr_manager"])
        for attack_filters in (
            {"branch": branches_a[1]},
            {"department": departments_a[1]},
            {"company": company_b},
        ):
            filtered_payload = _tool_payload(
                "Assign Shift", company_a, shift_type, getdate(), add_days(getdate(), 1)
            )
            filtered_payload.update(attack_filters)
            try:
                filtered_rows = _run_tool_method("get_employees", filtered_payload)
            except frappe.PermissionError:
                filtered_rows = []
            assert employees["other_branch"] not in {row.employee for row in filtered_rows}
            assert employees["other_department"] not in {row.employee for row in filtered_rows}
            assert employees["cross_company"] not in {row.employee for row in filtered_rows}

        # Multiple shifts are permitted only when native timings do not
        # overlap. A target 08:00-12:00 shift can coexist with 14:00-18:00.
        frappe.db.set_single_value("HR Settings", "allow_multiple_shift_assignments", 1)
        payload = _tool_payload("Assign Shift", company_a, shift_type, getdate(), add_days(getdate(), 1))
        frappe.set_user(users["hr_manager"])
        multiple_preview = _run_tool_method("get_employees", payload)
        multiple_names = {row.employee for row in multiple_preview}
        assert employees["nonoverlap"] in multiple_names
        assert employees["overlap"] not in multiple_names

        # Native HRMS' unextended controller exposes its Shift Request query
        # without checking Shift Request read permission. This is the
        # pre-fix behavior that the extension below must close for custom roles.
        request_employee = frappe.get_doc("Employee", employees["in_scope"])
        request_employee.shift_request_approver = "Administrator"
        request_employee.save(ignore_permissions=True)
        request = frappe.get_doc({
            "doctype": "Shift Request",
            "shift_type": shift_type,
            "employee": employees["in_scope"],
            "employee_name": request_employee.employee_name,
            "company": company_a,
            "from_date": getdate(),
            "to_date": add_days(getdate(), 1),
            "approver": "Administrator",
            "status": "Draft",
        }).insert(ignore_permissions=True)
        created_shift_requests.append(request.name)
        assert not frappe.has_permission("Shift Request", "read", user=users["hr_manager"], throw=False)
        native_tool = NativeShiftAssignmentTool({
            "doctype": "Shift Assignment Tool",
            "action": "Process Shift Requests",
            "company": company_a,
        })
        native_rows = NativeShiftAssignmentTool.get_employees(native_tool)
        assert request.name in {row.name for row in native_rows}
        with pytest.raises(frappe.PermissionError):
            _run_tool_method(
                "get_employees",
                {**payload, "action": "Process Shift Requests"},
            )
        with pytest.raises(frappe.PermissionError):
            _run_tool_method(
                "bulk_process_shift_requests",
                {**payload, "action": "Process Shift Requests"},
                args={"shift_requests": [{"shift_request": request.name, "employee": employees["in_scope"]}], "status": "Rejected"},
            )
        with pytest.raises(frappe.PermissionError):
            _run_tool_method(
                "get_employees",
                {**payload, "action": "Assign Shift Schedule", "shift_schedule": "not-authorized"},
            )

        # Desk shortcut filtering follows the native DocPerm target. The
        # scheduling operators see it; management and self-service personas do not.
        assert "Bulk Shift Assignment" in _workspace_shortcuts(users["hr_manager"])
        assert "Bulk Shift Assignment" in _workspace_shortcuts(users["attendance_officer"])
        for key in ("factory_supervisor", "branch_manager", "department_manager", "worker"):
            assert not frappe.has_permission("Shift Assignment Tool", "read", user=users[key], throw=False)
            assert not frappe.has_permission("Shift Assignment", "create", user=users[key], throw=False)
            assert "Bulk Shift Assignment" not in _workspace_shortcuts(users[key])
            frappe.set_user(users[key])
            denied_payload = _tool_payload(
                "Assign Shift", company_a, shift_type, getdate(), add_days(getdate(), 1)
            )
            with pytest.raises(frappe.PermissionError):
                _run_tool_method("get_employees", denied_payload)
            with pytest.raises(frappe.PermissionError):
                _run_tool_method(
                    "bulk_assign", denied_payload, args={"employees": [employees["in_scope"]]}
                )
        for role_user in (users["hr_manager"], users["attendance_officer"]):
            assert_only_workforce_roles(role_user)

        # Tampered Employee IDs are rejected before any row is applied.
        frappe.db.set_single_value("HR Settings", "allow_multiple_shift_assignments", 0)
        payload = _tool_payload("Assign Shift", company_a, shift_type, getdate(), add_days(getdate(), 1))
        events = []
        monkeypatch.setattr(
            frappe,
            "publish_realtime",
            lambda *args, **kwargs: events.append((args, kwargs)),
        )
        frappe.set_user(users["hr_manager"])
        for key in ("other_branch", "other_department", "cross_company"):
            with pytest.raises(frappe.PermissionError):
                _run_tool_method("bulk_assign", payload, args={"employees": [employees[key]]})
        assert not frappe.get_all(
            "Shift Assignment",
            filters={
                "employee": ["in", [employees["other_branch"], employees["other_department"], employees["cross_company"]]],
                "shift_type": shift_type,
            },
        )

        # HRMS still owns per-Employee partial failure handling for an eligible
        # set. Simulate one native save failure after eligibility validation.
        from hrms.hr.doctype.shift_assignment_tool import shift_assignment_tool as native_tool_module

        original_create = native_tool_module.create_shift_assignment

        def fail_one_employee(employee, *args, **kwargs):
            assignment = original_create(employee, *args, **kwargs)
            if employee == employees["partial_failure"]:
                # Fail only after native insert + submit so HRMS's savepoint
                # must remove the incomplete row while keeping the other
                # Employee's successful assignment.
                frappe.throw("Synthetic native Shift Assignment validation failure.", frappe.ValidationError)
            return assignment

        monkeypatch.setattr(native_tool_module, "create_shift_assignment", fail_one_employee)
        _run_tool_method(
            "bulk_assign",
            payload,
            args={"employees": [employees["in_scope"], employees["partial_failure"]]},
        )
        assigned = frappe.get_all(
            "Shift Assignment",
            filters={"employee": ["in", list(employees.values())], "shift_type": shift_type},
            fields=["name", "employee", "company", "docstatus"],
        )
        created_assignments.extend(row.name for row in assigned if row.name not in preexisting_assignments)
        by_employee = {row.employee: row for row in assigned}
        assert by_employee[employees["in_scope"]].docstatus == 1
        assert by_employee[employees["in_scope"]].company == company_a
        assert employees["partial_failure"] not in by_employee
        assert events and set(events[-1][1]["message"]["failure"]) == {
            employees["partial_failure"]
        }
        assert {row["employee"] for row in events[-1][1]["message"]["success"]} == {
            employees["in_scope"]
        }

        # Replaying the same POST is blocked by native overlap validation; the
        # existing submitted record remains the only one for that Employee.
        with pytest.raises(frappe.PermissionError):
            _run_tool_method("bulk_assign", payload, args={"employees": [employees["in_scope"]]})
        replay_rows = frappe.get_all(
            "Shift Assignment", filters={"employee": employees["in_scope"], "shift_type": shift_type, "docstatus": 1}
        )
        assert len(replay_rows) == 1

        # Capture the native 30-row synchronous and >30-row queued branches
        # without producing a large synthetic roster.
        sync_calls = []
        monkeypatch.setattr(
            NativeShiftAssignmentTool,
            "_bulk_assign",
            lambda self, rows: sync_calls.append(list(rows)),
        )
        thirty = [employees["default_only"]] * 30
        _run_tool_method("bulk_assign", payload, args={"employees": thirty})
        assert sync_calls == [thirty]
        queue_calls = []
        monkeypatch.setattr(
            frappe,
            "enqueue",
            lambda method, **kwargs: queue_calls.append((method, kwargs)),
        )
        thirty_one = [employees["default_only"]] * 31
        _run_tool_method("bulk_assign", payload, args={"employees": thirty_one})
        assert len(queue_calls) == 1
        assert queue_calls[0][1]["employees"] == thirty_one
        assert queue_calls[0][1]["timeout"] == 3000
        queued_method, queued_kwargs = queue_calls[0]
        frappe.set_user("Administrator")
        old_department_permission = frappe.get_value(
            "User Permission",
            {"user": users["hr_manager"], "allow": "Department", "for_value": departments_a[0]},
            "name",
        )
        assert old_department_permission
        frappe.delete_doc("User Permission", old_department_permission, force=True, ignore_permissions=True)
        personas.permissions.remove(old_department_permission)
        new_department_permission = frappe.get_doc({
            "doctype": "User Permission",
            "user": users["hr_manager"],
            "allow": "Department",
            "for_value": departments_a[1],
            "apply_to_all_doctypes": 1,
        }).insert(ignore_permissions=True)
        personas.permissions.append(new_department_permission.name)
        frappe.clear_cache(user=users["hr_manager"])
        frappe.set_user(users["hr_manager"])
        with pytest.raises(frappe.PermissionError):
            # `timeout` is an enqueue option, not an argument to the queued
            # native method. Frappe preserves the submitting user separately.
            queued_method(employees=queued_kwargs["employees"])

        # Shift scheduling creates only native Shift Assignment records.
        assert not frappe.get_all("Attendance", filters={"employee": ["in", list(employees.values())]})
        assert not frappe.get_all("Employee Checkin", filters={"employee": ["in", list(employees.values())]})
        assert not frappe.get_all("Salary Slip", filters={"employee": ["in", list(employees.values())]})
        assert not frappe.get_all("Salary Structure Assignment", filters={"employee": ["in", list(employees.values())]})

        # The synthetic native HR User control retains the unmodified full tool.
        frappe.set_user(users["native_hr_user"])
        assert "Process Shift Requests" in frappe.get_meta("Shift Assignment Tool").get_field("action").options
        native_request_calls = []
        monkeypatch.setattr(
            NativeShiftAssignmentTool,
            "bulk_process_shift_requests",
            lambda self, shift_requests, status: native_request_calls.append((shift_requests, status))
            or "native-request-processing",
        )
        assert _run_tool_method(
            "bulk_process_shift_requests",
            {**payload, "action": "Process Shift Requests"},
            args={"shift_requests": [{"shift_request": request.name, "employee": employees["in_scope"]}], "status": "Rejected"},
        ) == "native-request-processing"
        assert native_request_calls == [([{"shift_request": request.name, "employee": employees["in_scope"]}], "Rejected")]
        endpoint_results["native_hr_user"] = "native HR User control"
        print("NATIVE_BULK_SHIFT_PERSONAS=" + json.dumps(endpoint_results, sort_keys=True))

    finally:
        frappe.set_user("Administrator")
        frappe.db.set_single_value("HR Settings", "allow_multiple_shift_assignments", original_multiple)
        for name in created_shift_requests:
            if frappe.db.exists("Shift Request", name):
                frappe.delete_doc("Shift Request", name, force=True, ignore_permissions=True)
        for name in reversed(list(dict.fromkeys(created_assignments + preexisting_assignments))):
            if frappe.db.exists("Shift Assignment", name):
                doc = frappe.get_doc("Shift Assignment", name)
                if doc.docstatus == 1:
                    doc.cancel()
                frappe.delete_doc("Shift Assignment", name, force=True, ignore_permissions=True)
        for name in shift_types:
            if frappe.db.exists("Shift Type", name):
                frappe.delete_doc("Shift Type", name, force=True, ignore_permissions=True)
        # HRMS intentionally logs failed per-Employee rows. Remove only the
        # logs created for this synthetic run before verifying cleanup.
        failed_names = [
            employees[key]
            for key in ("partial_failure", "in_scope", "cross_company")
            if key in employees
        ]
        for employee in failed_names:
            method = f"Bulk Assignment - Shift Assignment failed for employee {employee}."
            error_log_names.update(frappe.get_all("Error Log", filters={"method": method}, pluck="name"))
        for name in error_log_names:
            if frappe.db.exists("Error Log", name):
                frappe.delete_doc("Error Log", name, force=True, ignore_permissions=True)
        personas.cleanup()
        # Native Error Log inserts and any future native bulk commits must not
        # leave synthetic fixtures behind, so commit only after explicit cleanup.
        frappe.db.commit()
        assert not frappe.get_all("Shift Assignment", filters={"employee": ["in", list(employees.values())]})
        assert not frappe.get_all("Shift Schedule Assignment", filters={"employee": ["in", list(employees.values())]})
        assert not frappe.get_all("Shift Request", filters={"employee": ["in", list(employees.values())]})
        assert not frappe.get_all("Shift Type", filters={"name": ["in", shift_types]})
        assert frappe.db.get_single_value("HR Settings", "allow_multiple_shift_assignments") == original_multiple
