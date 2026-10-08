"""Native Leave Control Panel scope and Workforce entitlement-role integration."""

from __future__ import annotations

import json

import frappe
import pytest

from workforce_suite.tests.persona_uat import PERSONA_ROLES, SyntheticPersonaHarness, assert_only_workforce_roles


@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(site="hrms-v16.localhost", sites_path="/home/sanchita/frappe-bench-v16/sites", force=True)
    frappe.connect()
    frappe.set_user("Administrator")
    yield
    frappe.set_user("Administrator")
    frappe.destroy()


def _call(method, payload, args):
    from frappe.handler import run_doc_method

    frappe.local.request = frappe._dict(method="POST")
    frappe.local.response.docs = []
    frappe.local.response.message = None
    result = run_doc_method(method=method, docs=json.dumps(payload, default=str), args=json.dumps(args))
    return result if result is not None else frappe.response.get("message")


def _payload(company, *, leave_type=None, policy=None, period=None):
    doc = frappe.get_doc("Leave Control Panel")
    doc.company = company
    doc.carry_forward = 0
    if policy:
        doc.dates_based_on = "Leave Period"
        doc.leave_period = period
        doc.allocate_based_on_leave_policy = 1
        doc.leave_policy = policy
    else:
        doc.dates_based_on = "Custom Range"
        doc.from_date = "2032-01-01"
        doc.to_date = "2032-12-31"
        doc.allocate_based_on_leave_policy = 0
        doc.leave_type = leave_type
        doc.no_of_days = 1  # disposable fixture, never a company entitlement
    return doc.as_dict()


def _allocations(employee, leave_type):
    return frappe.get_all(
        "Leave Allocation", filters={"employee": employee, "leave_type": leave_type},
        fields=["name", "docstatus"],
    )


def _workspace_shortcuts(user):
    from frappe.desk.desktop import get_desktop_page, get_workspaces

    frappe.set_user(user)
    page = next((row for row in get_workspaces()["pages"] if row.get("name") == "workforce-suite"), None)
    if not page:
        return set()
    payload = get_desktop_page(json.dumps(page))
    return {row.get("label") for row in payload.get("shortcuts", {}).get("items", [])}


def test_native_leave_bulk_scope_roles_policy_and_cleanup(monkeypatch):
    company_a = "Example Company A"
    company_b = "Example Company B"
    branches_a = frappe.get_all("Branch", filters={"company": company_a}, pluck="name", order_by="name")
    branches_b = frappe.get_all("Branch", filters={"company": company_b}, pluck="name", order_by="name")
    departments_a = frappe.get_all("Department", filters={"company": company_a}, pluck="name", order_by="name")
    departments_b = frappe.get_all("Department", filters={"company": company_b}, pluck="name", order_by="name")
    assert len(branches_a) >= 2 and len(departments_a) >= 2 and branches_b and departments_b

    token = "BULKLEAVE" + frappe.generate_hash(8).upper()
    personas = SyntheticPersonaHarness(token)
    users = {}
    employees = {}
    tracked = {doctype: [] for doctype in ("Leave Allocation", "Leave Policy Assignment", "Leave Policy", "Leave Period", "Leave Type")}
    error_before = set(frappe.get_all("Error Log", pluck="name"))
    payroll_entry_before = frappe.db.count("Payroll Entry")
    try:
        frappe.set_user("Administrator")
        users["manager"] = personas.create_user("manager", [PERSONA_ROLES["hr_manager"]],
            company=company_a, branch=branches_a[0], department=departments_a[0])
        users["officer"] = personas.create_user("officer", [PERSONA_ROLES["attendance_officer"]], company=company_a)
        users["approver"] = personas.create_user("approver", [PERSONA_ROLES["leave_approver"]], company=company_a)
        users["branch_manager"] = personas.create_user("branch-manager", [PERSONA_ROLES["branch_manager"]], company=company_a)
        users["worker"] = personas.create_user("worker", [PERSONA_ROLES["worker"]], company=company_a)
        users["native_hr"] = personas.create_user("native-hr", ["HR User"],
            company=company_a, branch=branches_a[0], department=departments_a[0])
        users["mixed_hr"] = personas.create_user("mixed-hr", ["HR User", PERSONA_ROLES["hr_manager"]],
            company=company_a, branch=branches_a[0], department=departments_a[0])
        for key in ("manager", "officer", "approver", "branch_manager", "worker"):
            assert_only_workforce_roles(users[key])

        for key, company, branch, department in (
            ("allowed", company_a, branches_a[0], departments_a[0]),
            ("branch", company_a, branches_a[1], departments_a[0]),
            ("department", company_a, branches_a[0], departments_a[1]),
            ("company", company_b, branches_b[0], departments_b[0]),
            ("policy", company_a, branches_a[0], departments_a[0]),
            ("partial_ok", company_a, branches_a[0], departments_a[0]),
            ("partial_fail", company_a, branches_a[0], departments_a[0]),
            ("native", company_a, branches_a[0], departments_a[0]),
            ("native_policy", company_a, branches_a[0], departments_a[0]),
            ("future", company_a, branches_a[0], departments_a[0]),
            ("relieved", company_a, branches_a[0], departments_a[0]),
        ):
            employees[key] = personas.create_employee(key, company, branch, department)
        employees["inactive"] = personas.create_employee("inactive", company_a, branches_a[0], departments_a[0])
        frappe.db.set_value("Employee", employees["inactive"], "status", "Inactive")
        frappe.db.set_value("Employee", employees["future"], "date_of_joining", "2033-01-01")
        frappe.db.set_value("Employee", employees["relieved"], "relieving_date", "2031-12-31")

        leave_type = frappe.get_doc({"doctype": "Leave Type", "leave_type_name": "TEST " + token,
            "max_leaves_allowed": 0}).insert(ignore_permissions=True)
        tracked["Leave Type"].append(leave_type.name)
        period = frappe.get_doc({"doctype": "Leave Period", "company": company_a,
            "from_date": "2032-01-01", "to_date": "2032-12-31", "is_active": 1}).insert(ignore_permissions=True)
        tracked["Leave Period"].append(period.name)
        other_period = frappe.get_doc({"doctype": "Leave Period", "company": company_b,
            "from_date": "2034-01-01", "to_date": "2034-12-31", "is_active": 1}).insert(ignore_permissions=True)
        tracked["Leave Period"].append(other_period.name)
        policy = frappe.get_doc({"doctype": "Leave Policy", "title": "TEST " + token,
            "leave_policy_details": [{"leave_type": leave_type.name, "annual_allocation": 1}]}).insert(ignore_permissions=True)
        policy.submit()
        tracked["Leave Policy"].append(policy.name)
        draft_policy = frappe.get_doc({"doctype": "Leave Policy", "title": "TEST Draft " + token,
            "leave_policy_details": [{"leave_type": leave_type.name, "annual_allocation": 1}]}).insert(ignore_permissions=True)
        tracked["Leave Policy"].append(draft_policy.name)
        payload = _payload(company_a, leave_type=leave_type.name)

        for key in ("manager", "native_hr", "mixed_hr"):
            assert frappe.has_permission("Leave Control Panel", "read", user=users[key])
        assert "Bulk Leave Allocation" in _workspace_shortcuts(users["manager"])
        for key in ("officer", "approver", "branch_manager", "worker"):
            assert not frappe.has_permission("Leave Control Panel", "read", user=users[key], throw=False)
            assert "Bulk Leave Allocation" not in _workspace_shortcuts(users[key])
            frappe.set_user(users[key])
            with pytest.raises(frappe.PermissionError):
                _call("allocate_leave", payload, {"employees": [employees["allowed"]]})

        frappe.set_user(users["manager"])
        preview = _call("get_employees", payload, {"advanced_filters": []})
        preview_names = {row.employee for row in preview}
        assert employees["allowed"] in preview_names
        assert employees["policy"] in preview_names
        for key in ("branch", "department", "company", "inactive", "future", "relieved"):
            assert employees[key] not in preview_names
        for field, value in (("branch", branches_a[1]), ("department", departments_a[1]), ("company", company_b)):
            tampered = dict(payload, **{field: value})
            try:
                rows = _call("get_employees", tampered, {"advanced_filters": []})
            except frappe.PermissionError:
                rows = []
            assert not {employees["branch"], employees["department"], employees["company"]}.intersection(
                row.employee for row in rows
            )
        for key in ("branch", "department", "company", "inactive", "future", "relieved"):
            with pytest.raises(frappe.PermissionError):
                _call("allocate_leave", payload, {"employees": [employees[key]]})
            assert not _allocations(employees[key], leave_type.name)

        _call("allocate_leave", payload, {"employees": [employees["allowed"]]})
        created = _allocations(employees["allowed"], leave_type.name)
        assert len(created) == 1 and created[0].docstatus == 1
        tracked["Leave Allocation"].append(created[0].name)
        with pytest.raises(frappe.PermissionError):
            _call("allocate_leave", payload, {"employees": [employees["allowed"]]})
        assert len(_allocations(employees["allowed"], leave_type.name)) == 1

        from hrms.hr.doctype.leave_allocation.leave_allocation import LeaveAllocation
        native_validate = LeaveAllocation.validate

        def fail_one(doc):
            if doc.employee == employees["partial_fail"]:
                frappe.throw("Synthetic leave allocation failure", frappe.ValidationError)
            return native_validate(doc)

        monkeypatch.setattr(LeaveAllocation, "validate", fail_one)
        try:
            _call("allocate_leave", payload, {"employees": [employees["partial_ok"], employees["partial_fail"]]})
        finally:
            monkeypatch.setattr(LeaveAllocation, "validate", native_validate)
        partial = _allocations(employees["partial_ok"], leave_type.name)
        assert len(partial) == 1 and partial[0].docstatus == 1
        tracked["Leave Allocation"].append(partial[0].name)
        assert not _allocations(employees["partial_fail"], leave_type.name)

        policy_payload = _payload(company_a, policy=policy.name, period=period.name)
        _call("allocate_leave", policy_payload, {"employees": [employees["policy"]]})
        assignment = frappe.get_all("Leave Policy Assignment", filters={"employee": employees["policy"]},
            fields=["name", "docstatus"])
        assert len(assignment) == 1 and assignment[0].docstatus == 1
        tracked["Leave Policy Assignment"].append(assignment[0].name)
        policy_alloc = _allocations(employees["policy"], leave_type.name)
        assert len(policy_alloc) == 1 and policy_alloc[0].docstatus == 1
        tracked["Leave Allocation"].append(policy_alloc[0].name)
        with pytest.raises(frappe.PermissionError):
            _call("allocate_leave", policy_payload, {"employees": [employees["branch"]]})
        mismatched_period = _payload(company_a, policy=policy.name, period=other_period.name)
        with pytest.raises(frappe.PermissionError):
            _call("get_latest_leave_period", dict(payload, company=company_b), {})
        with pytest.raises((frappe.PermissionError, frappe.ValidationError)):
            _call("get_employees", mismatched_period, {"advanced_filters": []})
        with pytest.raises((frappe.PermissionError, frappe.ValidationError)):
            _call("allocate_leave", mismatched_period, {"employees": [employees["native"]]})
        frappe.set_user("Administrator")
        frappe.db.set_value("Leave Period", period.name, "is_active", 0)
        frappe.set_user(users["manager"])
        try:
            with pytest.raises(frappe.ValidationError, match="active Leave Period"):
                _call("allocate_leave", policy_payload, {"employees": [employees["native"]]})
        finally:
            frappe.set_user("Administrator")
            frappe.db.set_value("Leave Period", period.name, "is_active", 1)
            frappe.set_user(users["manager"])
        unapproved_policy = _payload(company_a, policy=draft_policy.name, period=period.name)
        with pytest.raises(frappe.ValidationError, match="submitted Leave Policy"):
            _call("allocate_leave", unapproved_policy, {"employees": [employees["native"]]})
        assert not frappe.get_all("Leave Policy Assignment", filters={"employee": employees["native"]})
        direct_draft = frappe.get_doc({
            "doctype": "Leave Policy Assignment", "employee": employees["native"],
            "leave_policy": draft_policy.name, "assignment_based_on": "Leave Period",
            "leave_period": period.name, "carry_forward": 0,
        }).insert()
        tracked["Leave Policy Assignment"].append(direct_draft.name)
        with pytest.raises(frappe.ValidationError, match="Submit the Leave Policy"):
            direct_draft.submit()
        assert frappe.db.get_value("Leave Policy Assignment", direct_draft.name, "docstatus") == 0
        frappe.set_user("Administrator")
        frappe.delete_doc("Leave Policy Assignment", direct_draft.name, force=True, ignore_permissions=True)
        tracked["Leave Policy Assignment"].remove(direct_draft.name)

        for key in ("native_hr", "mixed_hr"):
            frappe.set_user(users[key])
            with pytest.raises(frappe.PermissionError):
                _call("get_latest_leave_period", dict(payload, company=company_b), {})
            _call("allocate_leave", payload, {"employees": [employees["native"]]})
            result = _allocations(employees["native"], leave_type.name)
            assert len(result) == 1 and result[0].docstatus == 1
            tracked["Leave Allocation"].append(result[0].name)
            frappe.set_user("Administrator")
            doc = frappe.get_doc("Leave Allocation", result[0].name)
            doc.cancel()
            frappe.delete_doc("Leave Allocation", doc.name, force=True, ignore_permissions=True)
            tracked["Leave Allocation"].remove(result[0].name)
        frappe.set_user(users["native_hr"])
        _call("allocate_leave", policy_payload, {"employees": [employees["native_policy"]]})
        native_policy_assignment = frappe.get_all("Leave Policy Assignment",
            filters={"employee": employees["native_policy"]}, fields=["name", "docstatus"])
        assert len(native_policy_assignment) == 1 and native_policy_assignment[0].docstatus == 1
        tracked["Leave Policy Assignment"].append(native_policy_assignment[0].name)
        native_policy_allocation = _allocations(employees["native_policy"], leave_type.name)
        assert len(native_policy_allocation) == 1 and native_policy_allocation[0].docstatus == 1
        tracked["Leave Allocation"].append(native_policy_allocation[0].name)

        assert not frappe.get_all("Salary Slip", filters={"employee": ["in", list(employees.values())]})
        assert not frappe.get_all("Additional Salary", filters={"employee": ["in", list(employees.values())]})
        assert frappe.db.count("Payroll Entry") == payroll_entry_before
    finally:
        frappe.set_user("Administrator")
        # A failed row may have inserted before validation; include every
        # token-owned allocation and assignment in explicit cleanup.
        for key in employees:
            if tracked["Leave Type"]:
                tracked["Leave Allocation"].extend(
                    row.name for row in _allocations(employees[key], tracked["Leave Type"][0])
                    if row.name not in tracked["Leave Allocation"]
                )
            tracked["Leave Policy Assignment"].extend(name for name in frappe.get_all("Leave Policy Assignment", filters={"employee": employees[key]}, pluck="name") if name not in tracked["Leave Policy Assignment"])
        for doctype in ("Leave Allocation", "Leave Policy Assignment", "Leave Policy"):
            for name in reversed(tracked[doctype]):
                if frappe.db.exists(doctype, name):
                    doc = frappe.get_doc(doctype, name)
                    if doc.docstatus == 1:
                        doc.cancel()
                    frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
        for name in tracked["Leave Period"]:
            if frappe.db.exists("Leave Period", name):
                frappe.delete_doc("Leave Period", name, force=True, ignore_permissions=True)
        for name in tracked["Leave Type"]:
            if frappe.db.exists("Leave Type", name):
                frappe.delete_doc("Leave Type", name, force=True, ignore_permissions=True)
        for name in set(frappe.get_all("Error Log", pluck="name")) - error_before:
            log = frappe.get_doc("Error Log", name)
            if any(employee in (str(log.method) + str(log.error)) for employee in employees.values()):
                frappe.delete_doc("Error Log", name, force=True, ignore_permissions=True)
        personas.cleanup()
        assert not any(frappe.db.exists(doctype, name) for doctype, names in tracked.items() for name in names)
        assert not frappe.get_all("Leave Ledger Entry", filters={"transaction_type": "Leave Allocation",
            "transaction_name": ["in", tracked["Leave Allocation"]]}, pluck="name")
        frappe.db.commit()
