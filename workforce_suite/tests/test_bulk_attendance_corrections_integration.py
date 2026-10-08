"""Site-backed tests for native, one-day Attendance Request correction drafts."""

from __future__ import annotations

import os
from datetime import date, timedelta

import frappe
import pytest

from workforce_suite.tests.persona_uat import PERSONA_ROLES, SyntheticPersonaHarness
from workforce_suite.workforce_suite.attendance_payroll_boundary import attendance_period_hash
from workforce_suite.workforce_suite import attendance_corrections


@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(
        site=os.environ.get("FRAPPE_TEST_SITE", "hrms-v16.localhost"),
        sites_path=os.environ.get("FRAPPE_TEST_SITES_PATH", "/home/sanchita/frappe-bench-v16/sites"),
        force=True,
    )
    frappe.connect()
    previous = frappe.session.user
    frappe.set_user("Administrator")
    yield
    frappe.set_user(previous)
    frappe.destroy()


def _active_day(employee, start=None):
    from erpnext.setup.doctype.employee.employee import is_holiday

    current = start or date.today() - timedelta(days=1)
    for _ in range(45):
        if not is_holiday(employee, current):
            return current
        current -= timedelta(days=1)
    raise AssertionError("No non-holiday synthetic attendance date was found")


def _attendance(employee, day, status):
    doc = frappe.get_doc({
        "doctype": "Attendance",
        "employee": employee,
        "employee_name": frappe.db.get_value("Employee", employee, "employee_name"),
        "company": frappe.db.get_value("Employee", employee, "company"),
        "attendance_date": day,
        "status": status,
    }).insert(ignore_permissions=True)
    doc.submit()
    return doc


def _remove_synthetic(tracked, personas):
    frappe.set_user("Administrator")
    for name in reversed(tracked.get("Leave Application", [])):
        if frappe.db.exists("Leave Application", name):
            doc = frappe.get_doc("Leave Application", name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Leave Application", name, force=True, ignore_permissions=True)
    for name in reversed(tracked.get("Workforce Attendance Period", [])):
        if frappe.db.exists("Workforce Attendance Period", name):
            frappe.delete_doc("Workforce Attendance Period", name, force=True, ignore_permissions=True)
    for name in reversed(tracked["Attendance Request"]):
        if frappe.db.exists("Attendance Request", name):
            request = frappe.get_doc("Attendance Request", name)
            if request.docstatus == 1:
                request.cancel()
            frappe.delete_doc("Attendance Request", name, force=True, ignore_permissions=True)
    for name in reversed(tracked["Attendance"]):
        if frappe.db.exists("Attendance", name):
            attendance = frappe.get_doc("Attendance", name)
            if attendance.docstatus == 1:
                attendance.cancel()
            frappe.delete_doc("Attendance", name, force=True, ignore_permissions=True)
    for name in reversed(tracked["Employee Checkin"]):
        if frappe.db.exists("Employee Checkin", name):
            frappe.delete_doc("Employee Checkin", name, force=True, ignore_permissions=True)
    for name in reversed(tracked.get("Holiday List Assignment", [])):
        if frappe.db.exists("Holiday List Assignment", name):
            assignment = frappe.get_doc("Holiday List Assignment", name)
            if assignment.docstatus == 1:
                assignment.cancel()
            frappe.delete_doc("Holiday List Assignment", name, force=True, ignore_permissions=True)
    for name in reversed(tracked.get("Leave Allocation", [])):
        if frappe.db.exists("Leave Allocation", name):
            doc = frappe.get_doc("Leave Allocation", name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Leave Allocation", name, force=True, ignore_permissions=True)
    for name in reversed(tracked.get("Leave Period", [])):
        if frappe.db.exists("Leave Period", name):
            frappe.delete_doc("Leave Period", name, force=True, ignore_permissions=True)
    personas.cleanup()
    for name in reversed(tracked.get("Holiday List", [])):
        if frappe.db.exists("Holiday List", name):
            frappe.delete_doc("Holiday List", name, force=True, ignore_permissions=True)
    for doctype in ("Leave Application", "Leave Allocation"):
        names = tracked.get(doctype, [])
        if names:
            assert not frappe.get_all(
                "Leave Ledger Entry",
                filters={"transaction_type": doctype, "transaction_name": ["in", names]},
                pluck="name",
            )
    frappe.db.commit()
    assert not any(frappe.db.exists(doctype, name) for doctype, names in tracked.items() for name in names)


def _masters(company):
    branches = frappe.get_all("Branch", filters={"company": company}, pluck="name", order_by="name")
    departments = frappe.get_all("Department", filters={"company": company}, pluck="name", order_by="name")
    assert branches and departments
    return branches, departments


def test_daily_board_distinguishes_actual_absence_from_missing_attendance():
    company = "Example Company A"
    branches, departments = _masters(company)
    assert len(branches) >= 2
    token = "BULKATT" + frappe.generate_hash(8).upper()
    personas = SyntheticPersonaHarness(token)
    tracked = {name: [] for name in ("Attendance Request", "Attendance", "Employee Checkin", "Workforce Attendance Period", "Holiday List Assignment", "Holiday List", "Leave Application", "Leave Allocation", "Leave Period")}
    user = personas.create_user("attendance", [PERSONA_ROLES["attendance_officer"]], company=company,
                                branch=branches[0])
    employees = {}
    try:
        employees["absent"] = personas.create_employee("absent", company, branches[0], departments[0])
        employees["missing"] = personas.create_employee("missing", company, branches[0], departments[0])
        employees["draft"] = personas.create_employee("draft", company, branches[0], departments[0])
        day = _active_day(employees["absent"])
        absent = _attendance(employees["absent"], day, "Absent")
        tracked["Attendance"].append(absent.name)
        draft = frappe.get_doc({
            "doctype": "Attendance", "employee": employees["draft"],
            "employee_name": frappe.db.get_value("Employee", employees["draft"], "employee_name"),
            "company": company, "attendance_date": day, "status": "Present",
        }).insert(ignore_permissions=True)
        tracked["Attendance"].append(draft.name)
        checkin = frappe.get_doc({
            "doctype": "Employee Checkin", "employee": employees["missing"],
            "time": f"{day} 08:00:00", "log_type": "IN",
        }).insert(ignore_permissions=True)
        tracked["Employee Checkin"].append(checkin.name)

        # Re-run the exact pre-fix projection over synthetic rows to capture the
        # original bug before asserting the corrected report contract.
        baseline = frappe.db.sql(
            """SELECT e.name AS employee, COALESCE(a.status, 'Absent') AS status
               FROM `tabEmployee` e LEFT JOIN `tabAttendance` a
                 ON a.employee=e.name AND a.attendance_date=%(day)s AND a.docstatus<2
               WHERE e.name IN %(employees)s""",
            {"day": day, "employees": (employees["absent"], employees["missing"])}, as_dict=True,
        )
        assert {row.employee: row.status for row in baseline} == {
            employees["absent"]: "Absent", employees["missing"]: "Absent"
        }

        frappe.set_user(user)
        from frappe.desk.query_report import run

        result = run("Workforce Daily Attendance Board", filters={
            "company": company, "attendance_date": str(day),
        })["result"]
        rows = {row["employee"]: row for row in result if row.get("employee") in employees.values()}
        assert rows[employees["absent"]]["status"] == "Absent"
        assert rows[employees["absent"]]["attendance_state"] == "Submitted Attendance"
        assert rows[employees["missing"]]["status"] == "Not Marked"
        assert rows[employees["missing"]]["attendance_state"] == "Not Marked"
        assert rows[employees["missing"]]["attendance"] in (None, "")
        assert rows[employees["missing"]]["punches"] == 1
        assert rows[employees["draft"]]["attendance_state"] == "Draft Attendance"
        assert rows[employees["draft"]]["attendance"] == draft.name

        # A caller-supplied Branch can only narrow an already scoped population.
        narrowed = run("Workforce Daily Attendance Board", filters={
            "company": company, "attendance_date": str(day), "branch": branches[1],
        })["result"]
        assert not {row.get("employee") for row in narrowed}.intersection(employees.values())
    finally:
        _remove_synthetic(tracked, personas)


def test_maker_drafts_are_scoped_independently_approved_and_native_attendance_is_final(monkeypatch):
    company = "Example Company A"
    other_company = "Example Company B"
    branches, departments = _masters(company)
    assert len(branches) >= 2 and len(departments) >= 2
    other_branches, other_departments = _masters(other_company)
    token = "BULKAPP" + frappe.generate_hash(8).upper()
    personas = SyntheticPersonaHarness(token)
    tracked = {name: [] for name in ("Attendance Request", "Attendance", "Employee Checkin", "Workforce Attendance Period", "Holiday List Assignment", "Holiday List", "Leave Application", "Leave Allocation", "Leave Period")}
    maker = personas.create_user("maker", [PERSONA_ROLES["attendance_officer"]], company=company,
                                 branch=branches[0], department=departments[0])
    dual = personas.create_user("dual", [PERSONA_ROLES["hr_manager"], PERSONA_ROLES["attendance_correction_approver"]],
                                company=company, branch=branches[0], department=departments[0])
    approver = personas.create_user("approver", [PERSONA_ROLES["attendance_correction_approver"]], company=company,
                                    branch=branches[0], department=departments[0])
    employees = {}
    try:
        employees["absent"] = personas.create_employee("absent", company, branches[0], departments[0])
        employees["missing"] = personas.create_employee("missing", company, branches[0], departments[0])
        employees["dual"] = personas.create_employee("dual", company, branches[0], departments[0])
        employees["pending"] = personas.create_employee("pending", company, branches[0], departments[0])
        employees["holiday"] = personas.create_employee("holiday", company, branches[0], departments[0])
        employees["on_leave"] = personas.create_employee("on-leave", company, branches[0], departments[0])
        employees["already_present"] = personas.create_employee("already-present", company, branches[0], departments[0])
        employees["other_branch"] = personas.create_employee("other-branch", company, branches[1], departments[0])
        employees["other_department"] = personas.create_employee("other-department", company, branches[0], departments[1])
        employees["other_company"] = personas.create_employee("other-company", other_company, other_branches[0], other_departments[0])
        employees["future"] = personas.create_employee("future", company, branches[0], departments[0])
        employees["inactive"] = personas.create_employee("inactive", company, branches[0], departments[0])
        employees["relieved"] = personas.create_employee("relieved", company, branches[0], departments[0])
        day = _active_day(employees["missing"])
        holiday_list = frappe.get_doc({
            "doctype": "Holiday List", "holiday_list_name": f"Bulk Attendance {token}",
            "from_date": day, "to_date": day,
            "holidays": [{"holiday_date": day, "description": "Synthetic correction preview holiday"}],
        }).insert(ignore_permissions=True)
        tracked["Holiday List"].append(holiday_list.name)
        holiday_assignment = frappe.get_doc({
            "doctype": "Holiday List Assignment", "applicable_for": "Employee",
            "assigned_to": employees["holiday"], "holiday_list": holiday_list.name,
            "from_date": day, "to_date": day,
        }).insert(ignore_permissions=True)
        tracked["Holiday List Assignment"].append(holiday_assignment.name)
        holiday_assignment.submit()

        leave_period = frappe.get_doc({
            "doctype": "Leave Period", "from_date": day - timedelta(days=1),
            "to_date": day + timedelta(days=1), "company": company, "is_active": 1,
        }).insert(ignore_permissions=True)
        tracked["Leave Period"].append(leave_period.name)
        allocation = frappe.get_doc({
            "doctype": "Leave Allocation", "employee": employees["on_leave"],
            "company": company, "leave_type": "Casual Leave", "leave_period": leave_period.name,
            "from_date": day - timedelta(days=1), "to_date": day + timedelta(days=1),
            "new_leaves_allocated": 1,
        }).insert(ignore_permissions=True)
        tracked["Leave Allocation"].append(allocation.name)
        allocation.submit()
        leave_application = frappe.get_doc({
            "doctype": "Leave Application", "employee": employees["on_leave"],
            "company": company, "leave_type": "Casual Leave", "from_date": day,
            "to_date": day, "status": "Approved", "leave_approver": "Administrator",
            "description": "Synthetic correction preview leave",
        }).insert(ignore_permissions=True)
        tracked["Leave Application"].append(leave_application.name)
        leave_application.submit()
        leave_attendance = frappe.get_all(
            "Attendance", filters={"employee": employees["on_leave"], "attendance_date": day, "docstatus": 1},
            pluck="name",
        )
        tracked["Attendance"].extend(leave_attendance)
        pending_checkin = frappe.get_doc({
            "doctype": "Employee Checkin", "employee": employees["pending"],
            "time": f"{day} 08:15:00", "log_type": "IN",
            "custom_workforce_review_status": "Pending",
        }).insert(ignore_permissions=True)
        tracked["Employee Checkin"].append(pending_checkin.name)
        frappe.db.set_value("Employee", employees["future"], "date_of_joining", day + timedelta(days=1))
        frappe.db.set_value("Employee", employees["inactive"], "status", "Inactive")
        frappe.db.set_value("Employee", employees["relieved"], "relieving_date", day - timedelta(days=1))
        frappe.db.set_value("Employee", employees["relieved"], "status", "Left")
        absent = _attendance(employees["absent"], day, "Absent")
        tracked["Attendance"].append(absent.name)
        already_present = _attendance(employees["already_present"], day, "Present")
        tracked["Attendance"].append(already_present.name)
        absent_before = absent.status

        assert frappe.has_permission("Attendance Request", "create", user=maker)
        assert not frappe.has_permission("Attendance Request", "submit", user=maker)
        assert not frappe.has_permission("Attendance Request", "create", user=approver)
        assert frappe.has_permission("Attendance Request", "submit", user=approver)
        assert frappe.has_permission("Attendance Request", "create", user=dual)
        assert frappe.has_permission("Attendance Request", "submit", user=dual)

        frappe.set_user(maker)
        preview = attendance_corrections.preview_attendance_corrections(
            company, str(day), [employees["absent"], employees["missing"], employees["other_branch"],
                                employees["already_present"],
                                employees["other_department"], employees["other_company"], employees["future"],
                                employees["inactive"], employees["relieved"], employees["pending"], employees["holiday"],
                                employees["on_leave"]],
            "Present", "Verified missed attendance", branch=branches[0], department=departments[0],
        )
        outcomes = {row["employee"]: row for row in preview["rows"]}
        assert outcomes[employees["absent"]]["outcome"] == "Will overwrite after approval"
        assert outcomes[employees["missing"]]["outcome"] == "Will create"
        assert outcomes[employees["already_present"]]["outcome"] == "Skipped"
        assert outcomes[employees["other_branch"]]["outcome"] == "Blocked — outside permitted scope"
        assert outcomes[employees["other_department"]]["outcome"] == "Blocked — outside permitted scope"
        assert outcomes[employees["other_company"]]["outcome"] == "Blocked — outside permitted scope"
        assert outcomes[employees["future"]]["outcome"] == "Blocked"
        assert outcomes[employees["inactive"]]["outcome"] == "Blocked"
        assert outcomes[employees["relieved"]]["outcome"] == "Blocked"
        assert outcomes[employees["pending"]]["outcome"] == "Blocked"
        assert "mobile review" in outcomes[employees["pending"]]["message"]
        assert outcomes[employees["holiday"]]["outcome"] == "Skipped"
        assert outcomes[employees["holiday"]]["message"] == "Skipped — holiday"
        assert outcomes[employees["on_leave"]]["outcome"] == "Skipped"
        assert outcomes[employees["on_leave"]]["message"] == "Skipped — approved leave"

        before_attendance_count = frappe.db.count("Attendance", {"employee": ["in", list(employees.values())]})
        prepared = attendance_corrections.prepare_attendance_corrections(
            company, str(day), [employees["absent"], employees["missing"], employees["other_branch"]],
            "Present", "Verified missed attendance", branch=branches[0], department=departments[0],
        )
        request_names = [row["attendance_request"] for row in prepared["created"]]
        tracked["Attendance Request"].extend(request_names)
        assert len(request_names) == 2 and len(prepared["results"]) == 1
        assert frappe.db.count("Attendance", {"employee": ["in", list(employees.values())]}) == before_attendance_count
        assert frappe.db.get_value("Attendance", absent.name, "status") == absent_before
        assert all(frappe.db.get_value("Attendance Request", name, "docstatus") == 0 for name in request_names)

        repeated = attendance_corrections.prepare_attendance_corrections(
            company, str(day), [employees["missing"]], "Present", "Verified missed attendance",
            branch=branches[0], department=departments[0],
        )
        assert not repeated["created"]
        assert repeated["results"][0]["outcome"] == "Blocked — existing request"

        # Native role union grants create+submit, but the server maker/checker
        # hook must prevent the combined account from submitting its own draft.
        frappe.set_user(dual)
        dual_result = attendance_corrections.prepare_attendance_corrections(
            company, str(day), [employees["dual"]], "Work From Home", "Reviewed mobile exception",
            branch=branches[0], department=departments[0],
        )
        dual_request_name = dual_result["created"][0]["attendance_request"]
        tracked["Attendance Request"].append(dual_request_name)
        dual_request = frappe.get_doc("Attendance Request", dual_request_name)

        # Reproduce the pre-guard behavior with only the Workforce server hook
        # disabled: Frappe's union of the maker + approver roles submits the
        # request and native HRMS creates Attendance for its owner.
        with monkeypatch.context() as baseline:
            baseline.setattr(attendance_corrections, "validate_attendance_request_before_submit", lambda *_args: None)
            dual_request.submit()
        assert frappe.db.get_value("Attendance Request", dual_request_name, "docstatus") == 1
        baseline_attendance = frappe.get_all(
            "Attendance", filters={"employee": employees["dual"], "attendance_date": day, "docstatus": 1},
            pluck="name",
        )
        assert len(baseline_attendance) == 1
        tracked["Attendance"].extend(baseline_attendance)
        frappe.set_user("Administrator")
        dual_request.reload().cancel()
        frappe.delete_doc("Attendance Request", dual_request_name, force=True, ignore_permissions=True)
        for attendance_name in baseline_attendance:
            frappe.delete_doc("Attendance", attendance_name, force=True, ignore_permissions=True)
        tracked["Attendance Request"].remove(dual_request_name)
        tracked["Attendance"].remove(baseline_attendance[0])

        # With the hook restored, the same dual-role user can still prepare,
        # but cannot submit its own request.
        frappe.set_user(dual)
        dual_result = attendance_corrections.prepare_attendance_corrections(
            company, str(day), [employees["dual"]], "Work From Home", "Reviewed mobile exception",
            branch=branches[0], department=departments[0],
        )
        dual_request_name = dual_result["created"][0]["attendance_request"]
        tracked["Attendance Request"].append(dual_request_name)
        dual_request = frappe.get_doc("Attendance Request", dual_request_name)
        with pytest.raises(frappe.PermissionError, match="different Attendance Correction Approver"):
            dual_request.submit()
        assert frappe.db.get_value("Attendance", {"employee": employees["missing"], "attendance_date": day}, "name") is None

        # An in-scope independent approver delegates the actual effect to HRMS.
        before_hash = attendance_period_hash(frappe.get_all(
            "Attendance", filters={"employee": employees["missing"], "docstatus": 1},
            fields=["employee", "attendance_date", "status", "leave_type", "leave_application", "half_day_status", "working_hours", "company", "branch", "department", "docstatus"],
        ))
        from workforce_suite.workforce_suite.attendance_payroll_boundary import current_attendance_period_hash

        finalized_hash = current_attendance_period_hash(company, day, day)
        period = frappe.get_doc({
            "doctype": "Workforce Attendance Period", "company": company,
            "from_date": day, "to_date": day, "status": "Finalized", "revision": 1,
            "attendance_hash": finalized_hash,
        })
        period._finalize_context = True
        period.insert(ignore_permissions=True)
        tracked["Workforce Attendance Period"].append(period.name)
        frappe.set_user(approver)
        request_absent = frappe.get_doc("Attendance Request", request_names[0])
        from workforce_suite.workforce_suite import maternity_welfare

        monkeypatch.setattr(
            maternity_welfare, "validate_maternity_attendance",
            lambda *_args: frappe.throw("synthetic protected-work regression"),
        )
        with pytest.raises(frappe.ValidationError, match="synthetic protected-work regression"):
            request_absent.submit()
        assert frappe.db.get_value("Attendance", absent.name, "status") == "Absent"
        assert frappe.db.get_value("Attendance Request", request_absent.name, "docstatus") == 0
        monkeypatch.undo()

        # This is the endpoint used by Frappe's native List View bulk Submit.
        from frappe.desk.doctype.bulk_update.bulk_update import submit_cancel_or_update_docs

        assert submit_cancel_or_update_docs("Attendance Request", request_names, "submit") == []
        request = frappe.get_doc("Attendance Request", request_names[1])
        assert frappe.db.get_value("Attendance Request", request.name, "docstatus") == 1
        created_attendance = frappe.get_all(
            "Attendance", filters={"employee": employees["missing"], "attendance_date": day},
            fields=["name", "status", "docstatus", "attendance_request"],
        )
        assert len(created_attendance) == 1
        tracked["Attendance"].append(created_attendance[0].name)
        assert created_attendance[0].status == "Present" and created_attendance[0].docstatus == 1
        assert created_attendance[0].attendance_request == request.name
        after_hash = attendance_period_hash(frappe.get_all(
            "Attendance", filters={"employee": employees["missing"], "docstatus": 1},
            fields=["employee", "attendance_date", "status", "leave_type", "leave_application", "half_day_status", "working_hours", "company", "branch", "department", "docstatus"],
        ))
        assert before_hash != after_hash
        assert current_attendance_period_hash(company, day, day) != period.attendance_hash
        period.reload()
        assert period.attendance_hash == finalized_hash

        # The existing Absent Attendance is updated in place by native HRMS.
        request_absent.reload()
        assert frappe.db.get_value("Attendance", absent.name, "status") == "Present"
        assert frappe.db.get_value("Attendance", absent.name, "docstatus") == 1

        # The scoped approver cannot submit a crafted request for another Branch.
        frappe.set_user("Administrator")
        foreign = frappe.get_doc({
            "doctype": "Attendance Request", "employee": employees["other_branch"], "company": company,
            "from_date": day, "to_date": day, "reason": "On Duty", "explanation": "Synthetic scope boundary",
        }).insert(ignore_permissions=True)
        tracked["Attendance Request"].append(foreign.name)
        frappe.set_user(approver)
        with pytest.raises(frappe.PermissionError, match="outside your permitted"):
            foreign.submit()
        assert frappe.db.get_value("Attendance Request", foreign.name, "docstatus") == 0

        # Native cancellation cancels Attendance linked to the request; the
        # app's payroll boundary must allow this only before submitted payroll.
        # The custom approver cannot cancel because HRMS' native on_cancel also
        # calls Attendance.cancel(), which would require broad Attendance write.
        assert not frappe.has_permission("Attendance Request", "cancel", user=approver)
        frappe.set_user("Administrator")
        request.cancel()
        assert frappe.db.get_value("Attendance", created_attendance[0].name, "docstatus") == 2
    finally:
        _remove_synthetic(tracked, personas)


def test_submitted_salary_slip_blocks_attendance_request_submit_and_cancel(monkeypatch):
    """Exercise the consumed-history guard against a genuinely submitted native slip."""
    from hrms.payroll.doctype.salary_structure.salary_structure import make_salary_slip
    from workforce_suite.tests.test_payroll_finalization_integration import (
        _component,
        _create_assignment,
        _create_employee,
        _create_synthetic_company,
        _create_structure,
        cleanup_synthetic_finalization_company,
    )

    token = frappe.generate_hash(8).upper()[:8]
    old_user = frappe.session.user
    company = None
    employee = None
    component_name = None
    structure_name = None
    assignment_name = None
    tracked_requests = []
    tracked_salary_slip = None
    try:
        frappe.set_user("Administrator")
        company, _abbr, payable, expense, cost_center, holiday_list = _create_synthetic_company(token, monkeypatch)
        component = _component(f"Attendance Consumption {token}", f"AC{token[:3]}", company, expense)
        component_name = component.name
        structure = _create_structure(
            f"Attendance Consumption {token}", company, "BDT", "Monthly Salary", component.name, 12000,
            depends_on_payment_days=0,
        )
        structure_name = structure.name
        employee = _create_employee(f"Attendance Consumption {token}", company, holiday_list)
        assignment = _create_assignment(employee.name, company, "BDT", payable, structure.name, 12000,
                                        cost_center, from_date="2026-01-01")
        assignment_name = assignment.name

        first_day = date(2026, 8, 10)
        second_day = date(2026, 8, 11)
        first_request = frappe.get_doc({
            "doctype": "Attendance Request", "employee": employee.name, "company": company,
            "from_date": first_day, "to_date": first_day, "reason": "On Duty",
            "explanation": "Synthetic payroll-consumption cancellation test",
        }).insert(ignore_permissions=True)
        tracked_requests.append(first_request.name)
        first_request.submit()

        second_request = frappe.get_doc({
            "doctype": "Attendance Request", "employee": employee.name, "company": company,
            "from_date": second_day, "to_date": second_day, "reason": "On Duty",
            "explanation": "Synthetic payroll-consumption submission test",
        }).insert(ignore_permissions=True)
        tracked_requests.append(second_request.name)

        salary_slip = make_salary_slip(structure.name, employee=employee.name, posting_date="2026-08-31")
        salary_slip.start_date = "2026-08-01"
        salary_slip.end_date = "2026-08-31"
        salary_slip.payroll_frequency = "Monthly"
        salary_slip.insert(ignore_permissions=True)
        tracked_salary_slip = salary_slip.name
        salary_slip.submit()
        assert frappe.db.get_value("Salary Slip", tracked_salary_slip, "docstatus") == 1

        with pytest.raises(frappe.ValidationError, match="already been consumed by submitted payroll"):
            second_request.reload().submit()
        with pytest.raises(frappe.ValidationError, match="already been consumed by submitted payroll"):
            first_request.reload().cancel()

        assert frappe.db.get_value("Salary Slip", tracked_salary_slip, "docstatus") == 1
        assert frappe.db.get_value("Attendance Request", second_request.name, "docstatus") == 0
        assert frappe.db.get_value("Attendance Request", first_request.name, "docstatus") == 1
    finally:
        frappe.set_user("Administrator")
        # The native request cancellation guard is deliberately tested above;
        # remove the synthetic payroll consumer first, then its linked requests.
        if tracked_salary_slip and frappe.db.exists("Salary Slip", tracked_salary_slip):
            slip = frappe.get_doc("Salary Slip", tracked_salary_slip)
            if slip.docstatus == 1:
                slip.cancel()
            frappe.delete_doc("Salary Slip", tracked_salary_slip, force=True, ignore_permissions=True)
        for name in reversed(tracked_requests):
            if frappe.db.exists("Attendance Request", name):
                request = frappe.get_doc("Attendance Request", name)
                if request.docstatus == 1:
                    request.cancel()
                frappe.delete_doc("Attendance Request", name, force=True, ignore_permissions=True)
        if assignment_name and frappe.db.exists("Salary Structure Assignment", assignment_name):
            assignment = frappe.get_doc("Salary Structure Assignment", assignment_name)
            if assignment.docstatus == 1:
                assignment.cancel()
            frappe.delete_doc("Salary Structure Assignment", assignment_name, force=True, ignore_permissions=True)
        if structure_name and frappe.db.exists("Salary Structure", structure_name):
            structure_doc = frappe.get_doc("Salary Structure", structure_name)
            if structure_doc.docstatus == 1:
                structure_doc.cancel()
            frappe.delete_doc("Salary Structure", structure_name, force=True, ignore_permissions=True)
        if component_name and frappe.db.exists("Salary Component", component_name):
            frappe.delete_doc("Salary Component", component_name, force=True, ignore_permissions=True)
        if company:
            cleanup_synthetic_finalization_company(company)
        if company:
            assert not frappe.db.exists("Company", company)
        if tracked_salary_slip:
            assert not frappe.db.exists("Salary Slip", tracked_salary_slip)
        assert all(not frappe.db.exists("Attendance Request", name) for name in tracked_requests)
        frappe.set_user(old_user)
