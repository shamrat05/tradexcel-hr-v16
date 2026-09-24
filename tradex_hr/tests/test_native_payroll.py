from datetime import date, timedelta
import os

import frappe
import pytest
from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip
from frappe.model.workflow import apply_workflow, get_transitions

from tradex_hr.tradexcel_hr import daily_wage_input, financial_readiness, native_payroll
from tradex_hr.tradexcel_hr.report.tradexcel_payroll_readiness import tradexcel_payroll_readiness as payroll_readiness


@pytest.fixture(autouse=True)
def no_approved_working_time_rules(monkeypatch):
	from tradex_hr.tradexcel_hr import working_time_compliance

	monkeypatch.setattr(
		working_time_compliance,
		"inspect_working_time_compliance",
		lambda *_args, **_kwargs: {"employees": [], "findings": [], "status": "READY"},
	)


@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(
        site=os.environ.get("FRAPPE_TEST_SITE", "hrms-v16.localhost"),
        sites_path=os.environ.get("FRAPPE_TEST_SITES_PATH", "/home/sanchita/frappe-bench-v16/sites"),
        force=True,
    )
    frappe.connect()
    yield
    frappe.destroy()


def test_native_readiness_does_not_block_joiner_or_leaver_for_native_proration(monkeypatch):
    employees = [{
        "name": "EMP-JOIN",
        "employee_name": "Joiner",
        "company": "TCL",
        "status": "Active",
        "date_of_joining": date(2026, 9, 10),
        "relieving_date": None,
    }]
    monkeypatch.setattr(native_payroll, "_employees_for_period", lambda *_args: employees)
    monkeypatch.setattr(native_payroll, "resolve_pay_basis", lambda *_args: {"status": "Monthly Salary"})
    monkeypatch.setattr(native_payroll, "_period_attendance_gate", lambda *_args: [])
    monkeypatch.setattr(native_payroll, "_unapproved_overtime", lambda *_args: [])
    monkeypatch.setattr(native_payroll, "prepare_wage_floor_context", lambda *_args: {})
    monkeypatch.setattr(native_payroll, "inspect_wage_floor_for_employee", lambda *_args, **_kwargs: {
        "status": "NOT_IN_CONFIGURED_SCOPE", "findings": [],
    })

    result = native_payroll.inspect_native_payroll_readiness(
        "TCL", date(2026, 9, 1), date(2026, 9, 30)
    )

    assert result["status"] == "READY"
    assert result["outcomes"][0]["status"] == "READY"


def test_native_readiness_blocks_stale_attendance(monkeypatch):
    employees = [{
        "name": "EMP-DAILY",
        "employee_name": "Daily",
        "company": "TCL",
        "status": "Active",
        "date_of_joining": date(2026, 1, 1),
        "relieving_date": None,
    }]
    monkeypatch.setattr(native_payroll, "_employees_for_period", lambda *_args: employees)
    monkeypatch.setattr(native_payroll, "resolve_pay_basis", lambda *_args: {"status": "Daily Wage"})
    monkeypatch.setattr(native_payroll, "_period_attendance_gate", lambda *_args: [{
        "employee": "EMP-DAILY", "code": "BLOCKED_ATTENDANCE_STALE", "reason": "stale"
    }])
    monkeypatch.setattr(native_payroll, "_unapproved_overtime", lambda *_args: [])
    monkeypatch.setattr(native_payroll, "prepare_wage_floor_context", lambda *_args: {})
    monkeypatch.setattr(native_payroll, "inspect_wage_floor_for_employee", lambda *_args, **_kwargs: {
        "status": "NOT_IN_CONFIGURED_SCOPE", "findings": [],
    })
    monkeypatch.setattr(native_payroll, "inspect_daily_wage_structure", lambda *_args: {"status": "READY"})
    monkeypatch.setattr(native_payroll, "calculate_daily_wage_input", lambda *_args: pytest.fail("stale input must stop first"))

    result = native_payroll.inspect_native_payroll_readiness(
        "TCL", date(2026, 9, 1), date(2026, 9, 30)
    )

    assert result["status"] == "BLOCKED"
    assert result["outcomes"][0]["status"] == "BLOCKED_ATTENDANCE_STALE"


def test_native_readiness_blocks_only_employee_below_wage_floor(monkeypatch):
    employees = [
        {"name": "EMP-READY", "employee_name": "Ready", "company": "TCL", "branch": "TCL Factory", "status": "Active"},
        {"name": "EMP-BELOW", "employee_name": "Below", "company": "TCL", "branch": "TCL Factory", "status": "Active"},
    ]
    monkeypatch.setattr(native_payroll, "_employees_for_period", lambda *_args: employees)
    monkeypatch.setattr(native_payroll, "_validate_supported_scope", lambda *_args: None)
    monkeypatch.setattr(native_payroll, "resolve_pay_basis", lambda employee, *_args: {"status": "Monthly Salary", "employee": employee})
    monkeypatch.setattr(native_payroll, "_attendance_required_for_payroll", lambda: False)
    monkeypatch.setattr(native_payroll, "_period_attendance_gate", lambda *_args: [])
    monkeypatch.setattr(native_payroll, "_unapproved_overtime", lambda *_args: [])
    monkeypatch.setattr(native_payroll, "prepare_wage_floor_context", lambda *_args: {"shared": True})
    monkeypatch.setattr(native_payroll, "inspect_wage_floor_for_employee", lambda employee, *_args, **_kwargs: {
        "status": "READY" if employee == "EMP-READY" else "WAGE_FLOOR_BELOW_MINIMUM",
        "findings": [] if employee == "EMP-READY" else [{"code": "WAGE_COMPONENT_BELOW_MINIMUM", "message": "Basic is below floor.", "severity": "blocker"}],
    })

    result = native_payroll.inspect_native_payroll_readiness("TCL", date(2026, 9, 1), date(2026, 9, 30))

    outcomes = {row["employee"]: row for row in result["outcomes"]}
    assert outcomes["EMP-READY"]["status"] == "READY"
    assert outcomes["EMP-READY"]["wage_floor"]["status"] == "READY"
    assert outcomes["EMP-BELOW"]["status"] == "WAGE_FLOOR_BELOW_MINIMUM"


def test_prepare_reuses_existing_native_payroll_entry(monkeypatch):
    existing = [{"name": "PAY-1", "custom_tradex_run_key": "KEY"}]
    doc = frappe._dict({
        "name": "PAY-1", "company": "TCL", "start_date": date(2026, 9, 1),
        "end_date": date(2026, 9, 30), "payroll_frequency": "Monthly",
        "custom_tradex_run_key": "KEY", "custom_tradex_population_hash": "FINGERPRINT",
        "custom_tradex_attendance_revision": "", "employees": [],
        "branch": None, "department": None, "designation": None, "status": "Draft",
    })
    monkeypatch.setattr(native_payroll, "_assert_preparation_authorized", lambda *_args: None)
    monkeypatch.setattr(native_payroll, "_managed_run_key", lambda *_args: "KEY")
    monkeypatch.setattr(native_payroll, "_daily_inputs_for_readiness", lambda *_args: ([], []))
    monkeypatch.setattr(native_payroll, "_population_fingerprint", lambda *_args: "FINGERPRINT")
    monkeypatch.setattr(native_payroll, "_attendance_revision", lambda *_args: "")
    monkeypatch.setattr(native_payroll.frappe, "get_doc", lambda *_args: doc)
    monkeypatch.setattr(native_payroll, "inspect_native_payroll_readiness", lambda *_args, **_kwargs: {
        "status": "READY", "outcomes": [], "employee_count": 0, "ready_count": 0, "blocked_count": 0,
    })
    monkeypatch.setattr(native_payroll, "_existing_payroll_entry", lambda *_args: existing)

    result = native_payroll.prepare_native_payroll("TCL", date(2026, 9, 1), date(2026, 9, 30))

    assert result["status"] == "PREPARED"
    assert result["payroll_entry"] == "PAY-1"


def test_prepare_blocks_missing_payroll_account_before_daily_input(monkeypatch):
    readiness = {
        "status": "READY",
        "outcomes": [{"employee": "EMP-DAILY", "employee_data": {}, "pay_basis": {"status": "Daily Wage"}}],
        "employee_count": 1,
        "ready_count": 1,
        "blocked_count": 0,
    }
    monkeypatch.setattr(native_payroll, "inspect_native_payroll_readiness", lambda *_args, **_kwargs: readiness)
    monkeypatch.setattr(native_payroll, "_existing_payroll_entry", lambda *_args: [])
    monkeypatch.setattr(native_payroll, "_assert_preparation_authorized", lambda *_args: None)
    monkeypatch.setattr(native_payroll, "_daily_inputs_for_readiness", lambda *_args: ([{"employee": "EMP-DAILY", "period": "PERIOD", "amount": 100}], []))
    monkeypatch.setattr(native_payroll.frappe, "get_cached_value", lambda *_args: (None, None, None))
    monkeypatch.setattr(
        native_payroll,
        "create_daily_wage_input",
        lambda *_args: pytest.fail("payroll inputs must not be written without a payable account"),
    )

    result = native_payroll.prepare_native_payroll("TCL", date(2026, 9, 1), date(2026, 9, 30))

    assert result["status"] == "BLOCKED_PAYROLL_ACCOUNT"


def test_prepare_checks_payroll_entry_permission_before_insert(monkeypatch):
    readiness = {
        "status": "READY",
        "outcomes": [{"employee": "EMP-MONTHLY", "employee_data": {}, "pay_basis": {"status": "Monthly Salary"}}],
        "employee_count": 1,
        "ready_count": 1,
        "blocked_count": 0,
    }
    monkeypatch.setattr(native_payroll, "inspect_native_payroll_readiness", lambda *_args, **_kwargs: readiness)
    monkeypatch.setattr(native_payroll, "_existing_payroll_entry", lambda *_args: [])
    monkeypatch.setattr(native_payroll.frappe, "get_cached_value", lambda *_args: ("BDT", "ACC-PAYABLE", "CC-TCL"))
    monkeypatch.setattr(
        native_payroll.frappe,
        "has_permission",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(frappe.PermissionError("denied")),
    )
    monkeypatch.setattr(
        native_payroll.frappe,
        "get_doc",
        lambda *_args: pytest.fail("Payroll Entry must not be inserted without permission"),
    )

    with pytest.raises(frappe.PermissionError, match="denied"):
        native_payroll.prepare_native_payroll("TCL", date(2026, 9, 1), date(2026, 9, 30))


def test_native_payroll_creates_draft_entry_and_slip_from_finalized_daily_attendance(monkeypatch):
    employee = frappe.db.get_value(
        "Employee",
        {"name": "HR-EMP-00225", "company": "Tradexcel Ceramics Ltd.", "status": "Active"},
        ["name", "employee_name", "company"],
        as_dict=True,
    )
    if not employee:
        pytest.skip("No active TCL staging employee")

    created = {
        "attendance": [],
        "period": None,
        "assignment": None,
        "structure": None,
        "additional_salary": [],
        "payroll_entry": None,
        "salary_slips": [],
        "users": [],
        "user_permissions": [],
    }

    def cleanup():
        frappe.set_user("Administrator")
        frappe.enqueue = lambda *_args, **_kwargs: None
        if created["payroll_entry"]:
            _delete_test_doc("Payroll Entry", created["payroll_entry"])
        for name in created["salary_slips"]:
            _delete_test_doc("Salary Slip", name)
        for name in created["additional_salary"]:
            _delete_test_doc("Additional Salary", name)
        if created["assignment"]:
            _delete_test_doc("Salary Structure Assignment", created["assignment"])
        if created["structure"]:
            _delete_test_doc("Salary Structure", created["structure"])
        if created["period"]:
            _delete_test_doc("Tradexcel Attendance Period", created["period"])
        for permission_name in created["user_permissions"]:
            if frappe.db.exists("User Permission", permission_name):
                frappe.delete_doc("User Permission", permission_name, ignore_permissions=True, force=True)
        for user_name in created["users"]:
            if frappe.db.exists("User", user_name):
                frappe.delete_doc("User", user_name, ignore_permissions=True, force=True)
        frappe.clear_cache()
        frappe.set_user("Administrator")
        for name in created["attendance"]:
            _delete_test_doc("Attendance", name)
        frappe.db.commit()

    try:
        structure = frappe.get_doc({
            "doctype": "Salary Structure",
            "name": f"TEST Native Daily {frappe.generate_hash(6)}",
            "company": employee.company,
            "currency": "BDT",
            "payroll_frequency": "Monthly",
            "is_active": "Yes",
            "custom_tradex_pay_basis": "Daily Wage",
            "earnings": [{"salary_component": "Daily Wage", "amount": 0, "depends_on_payment_days": 0}],
        })
        structure.insert(ignore_permissions=True)
        created["structure"] = structure.name
        structure.submit()
        assignment = frappe.get_doc({
            "doctype": "Salary Structure Assignment",
            "employee": employee.name,
            "company": employee.company,
            "currency": "BDT",
            "salary_structure": structure.name,
            "from_date": "2027-01-01",
            "base": 350,
            "payroll_payable_account": frappe.db.get_value("Company", employee.company, "default_payroll_payable_account"),
        })
        assignment.insert(ignore_permissions=True)
        created["assignment"] = assignment.name
        assignment.submit()

        start, end = date(2027, 1, 1), date(2027, 1, 31)
        probe = SalarySlip({"doctype": "Salary Slip"})
        probe.employee = employee.name
        probe.start_date = start
        probe.end_date = end
        holidays = set(probe.get_holidays_for_employee(start, end))
        for offset in range((end - start).days + 1):
            day = start + timedelta(days=offset)
            if day in holidays:
                continue
            attendance = frappe.get_doc({
                "doctype": "Attendance",
                "employee": employee.name,
                "attendance_date": day,
                "status": "Present" if offset < 10 else "Absent",
                "company": employee.company,
            })
            attendance.insert(ignore_permissions=True)
            created["attendance"].append(attendance.name)
            attendance.submit()

        period = frappe.get_doc({
            "doctype": "Tradexcel Attendance Period",
            "company": employee.company,
            "from_date": start,
            "to_date": end,
            "status": "Finalized",
            "revision": 1,
            "attendance_hash": native_payroll.current_attendance_period_hash(employee.company, start, end),
        })
        period._finalize_context = True
        period.insert(ignore_permissions=True)
        created["period"] = period.name
        monkeypatch.setattr(daily_wage_input, "require_finalized_attendance", lambda *_args: period)
        monkeypatch.setattr(
            native_payroll,
            "_employees_for_period",
            lambda _company, _start, _end, _employee_ids=None: [{**dict(employee), "status": "Active", "date_of_joining": date(2020, 1, 1), "relieving_date": None}],
        )
        original_get_cached_value = frappe.get_cached_value
        monkeypatch.setattr(
            frappe,
            "get_cached_value",
            lambda doctype, name, fields, *args, **kwargs: (
                ("BDT", "Creditors - TCL", frappe.db.get_value("Company", employee.company, "cost_center"))
                if doctype == "Company" and name == employee.company
                else original_get_cached_value(doctype, name, fields, *args, **kwargs)
            ),
        )

        original_enqueue = frappe.enqueue
        frappe.enqueue = lambda *_args, **_kwargs: None
        workflow_users = {}
        for role, name in (
            ("Tradexcel Payroll Manager", "Payroll Manager"),
            ("Tradexcel Payroll Approver", "Payroll Approver"),
            ("Tradexcel Owner/Director", "Payroll Director"),
        ):
            user = frappe.get_doc({
                "doctype": "User",
                "email": f"codex-native-payroll-{frappe.generate_hash(8)}@example.test",
                "first_name": f"Synthetic {name}",
                "enabled": 1,
                "user_type": "System User",
                "send_welcome_email": 0,
                "roles": [{"role": role}],
            })
            user.insert(ignore_permissions=True)
            created["users"].append(user.name)
            workflow_users[role] = user.name
        frappe.clear_cache()
        frappe.set_user(workflow_users["Tradexcel Payroll Manager"])
        payroll_entries_before = frappe.db.count(
            "Payroll Entry",
            {"company": employee.company, "start_date": start, "end_date": end},
        )
        daily_inputs_before = frappe.db.count(
            "Additional Salary",
            {
                "employee": employee.name,
                "ref_doctype": "Tradexcel Attendance Period",
                "ref_docname": period.name,
            },
        )
        with pytest.raises(frappe.PermissionError, match="explicit Company User Permission"):
            payroll_readiness.execute({"company": employee.company, "payroll_month": start.isoformat()})
        with pytest.raises(frappe.PermissionError, match="explicit Company User Permission"):
            payroll_readiness.prepare_payroll(employee.company, start.isoformat())
        with pytest.raises(frappe.PermissionError, match="explicit Company User Permission"):
            payroll_readiness.get_daily_wage_migration_preview(employee.company, start.isoformat())
        assert frappe.db.count(
            "Payroll Entry",
            {"company": employee.company, "start_date": start, "end_date": end},
        ) == payroll_entries_before
        assert frappe.db.count(
            "Additional Salary",
            {
                "employee": employee.name,
                "ref_doctype": "Tradexcel Attendance Period",
                "ref_docname": period.name,
            },
        ) == daily_inputs_before

        for user_name in workflow_users.values():
            user_permission = frappe.get_doc({
                "doctype": "User Permission",
                "user": user_name,
                "allow": "Company",
                "for_value": employee.company,
                "apply_to_all_doctypes": 1,
            })
            user_permission.insert(ignore_permissions=True)
            created["user_permissions"].append(user_permission.name)
        frappe.clear_cache()
        frappe.enqueue = original_enqueue
        frappe.set_user(workflow_users["Tradexcel Payroll Manager"])
        assert not frappe.has_permission("Additional Salary", "submit")
        result = payroll_readiness.prepare_payroll(employee.company, start.isoformat())
        retry_result = payroll_readiness.prepare_payroll(employee.company, start.isoformat())
        frappe.set_user("Administrator")

        assert result["status"] == "PREPARED", result
        assert retry_result["status"] == "PREPARED"
        assert retry_result["payroll_entry"] == result["payroll_entry"]
        created["payroll_entry"] = result["payroll_entry"]
        frappe.db.commit()  # Simulate the prepare request boundary; native jobs commit independently.
        created["additional_salary"] = frappe.get_all(
            "Additional Salary",
            filters={"ref_doctype": "Tradexcel Attendance Period", "ref_docname": period.name},
            pluck="name",
        )
        entry = frappe.get_doc("Payroll Entry", result["payroll_entry"])
        assert entry.docstatus == 0
        assert frappe.db.count("Salary Slip", {"payroll_entry": entry.name}) == 0

        queued_jobs = []
        monkeypatch.setattr(frappe, "enqueue", lambda method, *args, **kwargs: queued_jobs.append((method, args, kwargs)))
        frappe.flags.enqueue_payroll_entry = True
        try:
            frappe.set_user(workflow_users["Tradexcel Payroll Manager"])
            apply_workflow({"doctype": "Payroll Entry", "name": entry.name}, "Submit for Review")
        finally:
            frappe.flags.enqueue_payroll_entry = False
            frappe.set_user("Administrator")
        entry.reload()
        assert entry.docstatus == 1
        assert entry.workflow_state == "Tradexcel Payroll Pending Review"
        assert entry.status == "Queued"
        assert entry.salary_slips_created == 0
        actions = {item.action for item in get_transitions(entry)}
        assert "Review Complete" not in actions
        assert "Reject" not in actions
        assert len(queued_jobs) == 1
        frappe.db.commit()  # Persist submitted entry before simulating the native worker request.

        method, _args, job_kwargs = queued_jobs[0]
        frappe.message_log.clear()  # A background worker starts with a fresh request message log.
        def fail_slip_insert(*_args, **_kwargs):
            raise RuntimeError("synthetic native salary-slip failure")
        with monkeypatch.context() as failing_job:
            failing_job.setattr(SalarySlip, "insert", fail_slip_insert)
            method(
                employees=job_kwargs["employees"],
                args=job_kwargs["args"],
                publish_progress=job_kwargs["publish_progress"],
            )
        entry.reload()
        assert entry.status == "Failed"
        assert "synthetic native salary-slip failure" in entry.error_message
        actions = {item.action for item in get_transitions(entry)}
        assert "Review Complete" not in actions
        assert "Reject" in actions

        # HRMS's native retry action calls create_salary_slips() on the same entry.
        entry.create_salary_slips()
        entry.reload()
        assert entry.docstatus == 1
        assert entry.status == "Submitted"
        assert entry.salary_slips_created == 1
        slips = frappe.get_all("Salary Slip", filters={"payroll_entry": entry.name, "docstatus": 0}, fields=["name"])
        assert len(slips) == 1
        created["salary_slips"] = [row.name for row in slips]
        slip = frappe.get_doc("Salary Slip", slips[0].name)
        wage_rows = [row for row in slip.earnings if row.salary_component == "Daily Wage"]
        assert sum(row.amount for row in wage_rows) == 3500
        with pytest.raises(frappe.ValidationError, match="Submit managed Salary Slips from the approved Payroll Entry"):
            slip.submit()
        slip.reload()

        financial = financial_readiness.inspect_payroll_financial_readiness(entry)
        assert "COMPONENT_ACCOUNT_MISSING" in {row["code"] for row in financial["blockers"]}
        original_inspector = financial_readiness.inspect_payroll_financial_readiness
        frappe.set_user(workflow_users["Tradexcel Payroll Approver"])
        with pytest.raises(frappe.ValidationError, match="Payroll financial readiness is blocked"):
            apply_workflow({"doctype": "Payroll Entry", "name": entry.name}, "Review Complete")
        entry.reload()
        assert entry.workflow_state == "Tradexcel Payroll Pending Review"

        # Prove both native workflow transitions enforce the server boundary.
        # Use a READY result only to reach the second transition; do not mutate
        # company Salary Component account configuration for this fixture.
        monkeypatch.setattr(financial_readiness, "inspect_payroll_financial_readiness", lambda *_: {"status": "READY", "blockers": []})
        apply_workflow({"doctype": "Payroll Entry", "name": entry.name}, "Review Complete")
        entry.reload()
        assert entry.workflow_state == "Tradexcel Payroll Pending Director Approval"
        monkeypatch.setattr(financial_readiness, "inspect_payroll_financial_readiness", original_inspector)
        frappe.local.tradex_financial_readiness = {}

        frappe.set_user(workflow_users["Tradexcel Owner/Director"])
        with pytest.raises(frappe.ValidationError, match="Payroll financial readiness is blocked"):
            apply_workflow({"doctype": "Payroll Entry", "name": entry.name}, "Approve")
        entry.reload()
        assert entry.workflow_state == "Tradexcel Payroll Pending Director Approval"

        # Financial READY behavior is exercised by dedicated service tests.
        monkeypatch.setattr(financial_readiness, "inspect_payroll_financial_readiness", lambda *_: {"status": "READY", "blockers": []})
        frappe.local.tradex_financial_readiness = {}
        apply_workflow({"doctype": "Payroll Entry", "name": entry.name}, "Approve")
        frappe.set_user("Administrator")
        entry.reload()
        assert entry.workflow_state == "Tradexcel Payroll Approved"
        with pytest.raises(frappe.ValidationError, match="Submit managed Salary Slips from the approved Payroll Entry"):
            native_payroll.validate_salary_slip_before_submit(slip)

        retry = native_payroll.prepare_native_payroll(employee.company, start, end)
        assert retry["status"] == "PREPARED"
        assert retry["payroll_entry"] == entry.name

        # Cleanup exercises native Payroll Entry cancellation of linked draft slips.
        frappe.set_user(workflow_users["Tradexcel Owner/Director"])
        with pytest.raises(frappe.PermissionError):
            slip.delete()
        apply_workflow({"doctype": "Payroll Entry", "name": entry.name}, "Cancel")
        frappe.set_user("Administrator")
        entry.reload()
        assert entry.docstatus == 2
        assert entry.workflow_state == "Tradexcel Payroll Cancelled"
        assert not frappe.db.exists("Salary Slip", slip.name)
    finally:
        cleanup()


def _delete_test_doc(doctype, name):
    if not name or not frappe.db.exists(doctype, name):
        return
    doc = frappe.get_doc(doctype, name)
    if doc.docstatus == 1:
        doc.cancel()
    frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)


def test_unauthorized_prepare_is_denied_before_readiness_query(monkeypatch):
    import pytest
    import frappe
    from tradex_hr.tradexcel_hr import native_payroll

    def deny(*_args, **_kwargs):
        raise frappe.PermissionError("no company scope")

    monkeypatch.setattr(native_payroll, "_assert_preparation_authorized", deny)
    monkeypatch.setattr(
        native_payroll,
        "inspect_native_payroll_readiness",
        lambda *_args, **_kwargs: pytest.fail("readiness data was queried before authorization"),
    )

    with pytest.raises(frappe.PermissionError, match="no company scope"):
        native_payroll.prepare_native_payroll(
            "Tradexcel Ceramics Ltd.", "2026-09-01", "2026-09-30"
        )
