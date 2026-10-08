"""Scoped native Overtime Slip draft preparation, using disposable records only."""

from __future__ import annotations
import os

import frappe
import pytest

from workforce_suite.tests.persona_uat import PERSONA_ROLES, SyntheticPersonaHarness
from workforce_suite.workforce_suite import overtime_bulk


@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(site=os.environ.get("FRAPPE_TEST_SITE", "test_workforce.localhost"), sites_path=os.environ.get("FRAPPE_TEST_SITES_PATH", "./sites"), force=True)
    frappe.connect()
    frappe.set_user("Administrator")
    yield
    frappe.set_user("Administrator")
    frappe.destroy()


def test_scoped_overtime_drafts_partial_results_retry_and_queue(monkeypatch):
    company = "Example Company A"
    other_company = "Example Company B"
    branches = frappe.get_all("Branch", filters={"company": company}, pluck="name", order_by="name")
    departments = frappe.get_all("Department", filters={"company": company}, pluck="name", order_by="name")
    other_branch = frappe.db.get_value("Branch", {"company": other_company}, "name")
    other_department = frappe.db.get_value("Department", {"company": other_company}, "name")
    assert len(branches) > 1 and len(departments) > 1 and other_branch and other_department

    token = "SOLOT" + frappe.generate_hash(6).upper()[:6]
    personas = SyntheticPersonaHarness(token)
    tracked = {doctype: [] for doctype in (
        "Salary Structure Assignment", "Attendance", "Overtime Slip", "Overtime Type", "Salary Component"
    )}
    employees = {}
    component = None
    overtime_type = None
    original_user = frappe.session.user
    before = {doctype: frappe.db.count(doctype) for doctype in
              ("Additional Salary", "Payroll Entry", "Salary Slip", "Arrear")}
    start, end, day = "2026-08-01", "2026-08-31", "2026-08-17"
    try:
        frappe.set_user("Administrator")
        maker = personas.create_user("maker", [PERSONA_ROLES["hr_manager"]],
                                    company=company, branch=branches[0], department=departments[0])
        denied = personas.create_user("branch-manager", [PERSONA_ROLES["branch_manager"]], company=company)
        approver = personas.create_user("approver", [PERSONA_ROLES["payroll_approver"]], company=company)
        for key, row_company, branch, department in (
            ("allowed", company, branches[0], departments[0]),
            ("partial_ok", company, branches[0], departments[0]),
            ("partial_fail", company, branches[0], departments[0]),
            ("branch", company, branches[1], departments[0]),
            ("department", company, branches[0], departments[1]),
            ("company", other_company, other_branch, other_department),
            ("no_authority", company, branches[0], departments[0]),
        ):
            employees[key] = personas.create_employee(key, row_company, branch, department)

        component = frappe.get_doc({
            "doctype": "Salary Component", "salary_component": token,
            "salary_component_abbr": token[:5], "type": "Earning",
        }).insert(ignore_permissions=True)
        tracked["Salary Component"].append(component.name)
        overtime_type = frappe.get_doc({
            "doctype": "Overtime Type", "name": token,
            "overtime_salary_component": component.name,
            "overtime_calculation_method": "Fixed Hourly Rate",
            "hourly_rate": 1, "maximum_overtime_hours_allowed": 2,
            "standard_multiplier": 1,
        }).insert(ignore_permissions=True)
        tracked["Overtime Type"].append(overtime_type.name)
        monthly_structure = frappe.db.get_value("Salary Structure", {
            "company": company, "docstatus": 1, "custom_workforce_pay_basis": "Monthly Salary",
        }, "name")
        other_structure = frappe.db.get_value("Salary Structure", {
            "company": other_company, "docstatus": 1,
            "custom_workforce_pay_basis": ["in", ["Monthly Salary", "Daily Wage"]],
        }, "name")
        assert monthly_structure and other_structure
        for key, employee in employees.items():
            if key != "no_authority":
                row_company = other_company if key == "company" else company
                assignment = frappe.get_doc({
                    "doctype": "Salary Structure Assignment", "employee": employee,
                    "company": row_company,
                    "salary_structure": other_structure if key == "company" else monthly_structure,
                    "from_date": start, "base": 100,  # disposable fixture, not a wage policy
                }).insert(ignore_permissions=True)
                assignment.submit()
                tracked["Salary Structure Assignment"].append(assignment.name)
            attendance = frappe.get_doc({
                "doctype": "Attendance", "employee": employee,
                "company": other_company if key == "company" else company,
                "attendance_date": day, "status": "Present", "working_hours": 10,
                "standard_working_hours": 8, "actual_overtime_duration": 2,
                "overtime_type": overtime_type.name,
            }).insert(ignore_permissions=True)
            attendance.submit()
            tracked["Attendance"].append(attendance.name)

        frappe.db.commit()
        assert frappe.has_permission("Overtime Slip", "create", user=maker)
        assert not frappe.has_permission("Overtime Slip", "submit", user=maker)
        assert not frappe.has_permission("Overtime Slip", "create", user=approver)
        assert frappe.has_permission("Overtime Slip", "submit", user=approver)
        assert not frappe.has_permission("Payroll Entry", "write", user=maker)

        frappe.set_user(denied)
        with pytest.raises(frappe.PermissionError):
            overtime_bulk.preview_overtime_drafts(company, start, end)
        with pytest.raises(frappe.PermissionError):
            overtime_bulk.prepare_overtime_drafts(company, start, end, [employees["allowed"]])
        frappe.set_user(maker)
        preview = overtime_bulk.preview_overtime_drafts(company, start, end)
        visible = {row["employee"]: row for row in preview["rows"]}
        assert employees["allowed"] in visible and visible[employees["allowed"]]["eligible"]
        assert employees["no_authority"] in visible and not visible[employees["no_authority"]]["eligible"]
        for key in ("branch", "department", "company"):
            assert employees[key] not in visible
            with pytest.raises(frappe.PermissionError):
                overtime_bulk.prepare_overtime_drafts(company, start, end, [employees[key]])
        with pytest.raises(frappe.PermissionError):
            overtime_bulk.prepare_overtime_drafts(other_company, start, end, [employees["company"]])
        with pytest.raises(frappe.ValidationError):
            overtime_bulk.prepare_overtime_drafts(company, start, end, [employees["allowed"]] * 2)
        assert not frappe.get_all("Overtime Slip", filters={"employee": ["in", list(employees.values())]})

        blocked = overtime_bulk.prepare_overtime_drafts(company, start, end, [employees["no_authority"]])
        assert blocked["rows"][0]["status"] == "Blocked"
        assert not frappe.get_all("Overtime Slip", filters={"employee": employees["no_authority"]})
        created = overtime_bulk.prepare_overtime_drafts(company, start, end, [employees["allowed"]])
        assert created["rows"][0]["status"] == "Draft"
        slip_name = created["rows"][0]["overtime_slip"]
        tracked["Overtime Slip"].append(slip_name)
        slip = frappe.get_doc("Overtime Slip", slip_name)
        assert slip.docstatus == 0 and slip.employee == employees["allowed"] and slip.company == company
        assert len(slip.overtime_details) == 1
        assert slip.overtime_details[0].reference_document == tracked["Attendance"][0]
        assert not frappe.get_all("Additional Salary", filters={"ref_doctype": "Overtime Slip", "ref_docname": slip_name})
        with pytest.raises(frappe.PermissionError):
            overtime_bulk.prepare_overtime_drafts(company, start, end, [employees["allowed"]])

        from hrms.hr.doctype.overtime_slip.overtime_slip import OvertimeSlip
        native_method = OvertimeSlip.get_emp_and_overtime_details

        def fail_one(doc):
            if doc.employee == employees["partial_fail"]:
                frappe.throw("Synthetic draft failure", frappe.ValidationError)
            return native_method(doc)

        monkeypatch.setattr(OvertimeSlip, "get_emp_and_overtime_details", fail_one)
        try:
            mixed = overtime_bulk.prepare_overtime_drafts(
                company, start, end, [employees["partial_ok"], employees["partial_fail"]]
            )
        finally:
            monkeypatch.setattr(OvertimeSlip, "get_emp_and_overtime_details", native_method)
        assert [row["status"] for row in mixed["rows"]] == ["Draft", "Failed"]
        tracked["Overtime Slip"].append(mixed["rows"][0]["overtime_slip"])
        assert not frappe.get_all("Overtime Slip", filters={"employee": employees["partial_fail"]})

        # Simulate an enqueued selection whose User Permission changes before
        # execution. The worker must recheck the current native Employee scope.
        frappe.set_user("Administrator")
        branch_permission = frappe.db.get_value("User Permission", {
            "user": maker, "allow": "Branch", "for_value": branches[0],
        }, "name")
        frappe.db.set_value("User Permission", branch_permission, "for_value", branches[1])
        frappe.clear_cache(user=maker)
        frappe.set_user(maker)
        try:
            with pytest.raises(frappe.PermissionError):
                overtime_bulk._prepare_now(company, start, end, [employees["partial_fail"]], requested_by=maker)
        finally:
            frappe.set_user("Administrator")
            frappe.db.set_value("User Permission", branch_permission, "for_value", branches[0])
            frappe.clear_cache(user=maker)
        frappe.set_user(maker)
        with pytest.raises(frappe.PermissionError):
            overtime_bulk._prepare_now(company, start, end, [employees["partial_fail"]], requested_by="Administrator")

        queued = {}
        original_eligible = overtime_bulk._eligible_rows
        monkeypatch.setattr(overtime_bulk, "_eligible_rows", lambda *_args: [
            {"employee": str(index)} for index in range(31)
        ])
        monkeypatch.setattr(frappe, "enqueue", lambda *args, **kwargs: queued.update(kwargs))
        try:
            result = overtime_bulk.prepare_overtime_drafts(
                company, start, end, [str(index) for index in range(31)]
            )
        finally:
            monkeypatch.setattr(overtime_bulk, "_eligible_rows", original_eligible)
        assert result["status"] == "Queued" and queued["requested_by"] == maker
        assert queued["enqueue_after_commit"] and queued["queue"] == "long"
        assert queued["employees"] == [str(index) for index in range(31)]
        assert {doctype: frappe.db.count(doctype) for doctype in before} == before
    finally:
        frappe.set_user("Administrator")
        for employee in employees.values():
            for name in frappe.get_all("Overtime Slip", filters={"employee": employee}, pluck="name"):
                if name not in tracked["Overtime Slip"]:
                    tracked["Overtime Slip"].append(name)
        for doctype in ("Overtime Slip", "Attendance", "Salary Structure Assignment", "Overtime Type", "Salary Component"):
            for name in reversed(tracked[doctype]):
                if not frappe.db.exists(doctype, name):
                    continue
                doc = frappe.get_doc(doctype, name)
                if doc.docstatus == 1:
                    doc.cancel()
                frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
        personas.cleanup()
        assert not any(frappe.db.exists(doctype, name) for doctype, names in tracked.items() for name in names)
        frappe.db.commit()
        frappe.set_user(original_user)
