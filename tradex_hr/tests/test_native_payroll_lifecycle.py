from datetime import date
import os

import frappe
import pytest

from tradex_hr import approval_setup
from tradex_hr.tradexcel_hr import financial_readiness, native_payroll


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


def test_payroll_workflow_submits_for_review_and_cancels_rejection():
    workflow = approval_setup.WORKFLOWS["Tradexcel Payroll Approval"]
    states = {name: docstatus for name, docstatus, _role in workflow["states"]}
    assert states["Tradexcel Payroll Draft"] == "0"
    assert states["Tradexcel Payroll Pending Review"] == "1"
    assert states["Tradexcel Payroll Pending Director Approval"] == "1"
    assert states["Tradexcel Payroll Approved"] == "1"
    assert states["Tradexcel Payroll Rejected"] == "2"


def test_managed_payroll_supports_only_complete_calendar_months(monkeypatch):
    native_payroll._validate_supported_scope(
        "Company A", date(2026, 9, 1), date(2026, 9, 30), employee_ids=None
    )
    with pytest.raises(Exception, match="Managed payroll supports one complete calendar month"):
        native_payroll._validate_supported_scope(
            "Company A", date(2026, 9, 2), date(2026, 9, 30), employee_ids=None
        )
    monkeypatch.setattr(frappe.session, "user", "payroll.operator@example.com", raising=False)
    with pytest.raises(Exception, match="Partial employee"):
        native_payroll._validate_supported_scope(
            "Company A", date(2026, 9, 1), date(2026, 9, 30), employee_ids=["EMP-1"]
        )


def test_managed_run_key_is_deterministic_for_company_and_month():
    start, end = date(2026, 9, 1), date(2026, 9, 30)
    key = native_payroll._managed_run_key("Company A", start, end)
    assert key == native_payroll._managed_run_key("Company A", start, end)
    assert key != native_payroll._managed_run_key("Company B", start, end)
    assert key != native_payroll._managed_run_key("Company A", date(2026, 10, 1), date(2026, 10, 31))


def test_prepare_rejects_unmanaged_same_month_entry_before_writes(monkeypatch):
    readiness = {"status": "READY", "outcomes": [], "employee_count": 0, "ready_count": 0, "blocked_count": 0}
    monkeypatch.setattr(native_payroll, "inspect_native_payroll_readiness", lambda *_args, **_kwargs: readiness)
    monkeypatch.setattr(native_payroll, "_assert_preparation_authorized", lambda *_args: None)
    monkeypatch.setattr(native_payroll, "_existing_payroll_entry", lambda *_args: [{"name": "MANUAL-ENTRY", "custom_tradex_run_key": None}])
    monkeypatch.setattr(native_payroll, "_daily_inputs_for_readiness", lambda *_args: pytest.fail("must stop before materializing inputs"))
    result = native_payroll.prepare_native_payroll("TCL", date(2026, 9, 1), date(2026, 9, 30))
    assert result["status"] == "BLOCKED_EXISTING_PAYROLL_MISMATCH"
    assert result["blockers"][0]["payroll_entry"] == "MANUAL-ENTRY"


def test_known_daily_input_blocker_materializes_no_batch_inputs(monkeypatch):
    from tradex_hr.tradexcel_hr import native_payroll as service

    readiness = {
        "status": "READY",
        "outcomes": [
            {"employee": "EMP-1", "employee_data": {"company": "TCL"}, "pay_basis": {"status": "Daily Wage"}},
            {"employee": "EMP-2", "employee_data": {"company": "TCL"}, "pay_basis": {"status": "Daily Wage"}},
        ],
        "employee_count": 2, "ready_count": 2, "blocked_count": 0,
    }
    before_additional = frappe.db.count("Additional Salary")
    before_entries = frappe.db.count("Payroll Entry")
    monkeypatch.setattr(service, "inspect_native_payroll_readiness", lambda *_args, **_kwargs: readiness)
    monkeypatch.setattr(service, "_assert_preparation_authorized", lambda *_args: None)
    monkeypatch.setattr(service, "_existing_payroll_entry", lambda *_args: [])
    monkeypatch.setattr(service, "_daily_inputs_for_readiness", lambda *_args: (
        [{"employee": "EMP-1", "amount": 100, "period": "PERIOD"}],
        [{"employee": "EMP-2", "code": "BLOCKED_DAILY_WAGE_INPUT_MISMATCH", "reason": "bad input"}],
    ))
    monkeypatch.setattr(service, "create_daily_wage_input", lambda *_args: pytest.fail("known blockers must write nothing"))
    result = service.prepare_native_payroll("TCL", date(2026, 9, 1), date(2026, 9, 30))
    assert result["status"] == "BLOCKED_DAILY_WAGE_INPUT"
    assert frappe.db.count("Additional Salary") == before_additional
    assert frappe.db.count("Payroll Entry") == before_entries


def test_real_payroll_manager_permissions_are_narrow_and_company_scoped(monkeypatch):
    company = "Tradexcel Ceramics Ltd."
    email = f"codex-payroll-{frappe.generate_hash(8)}@example.test"
    monkeypatch.setattr(frappe, "enqueue", lambda *_args, **_kwargs: None)
    user = frappe.get_doc({
        "doctype": "User",
        "email": email,
        "first_name": "Synthetic Payroll Manager",
        "enabled": 1,
        "user_type": "System User",
        "send_welcome_email": 0,
        "roles": [{"role": "Tradexcel Payroll Manager"}],
    })
    user.insert(ignore_permissions=True)
    permission = frappe.get_doc({
        "doctype": "User Permission",
        "user": email,
        "allow": "Company",
        "for_value": company,
        "apply_to_all_doctypes": 1,
    })
    permission.insert(ignore_permissions=True)
    frappe.clear_cache()
    old_user = frappe.session.user
    employees = frappe.get_all("Employee", filters={"company": company, "status": "Active"}, pluck="name", limit=1)
    other_employees = frappe.get_all("Employee", filters={"company": ["!=", company], "status": "Active"}, pluck="name", limit=1)
    try:
        frappe.set_user(email)
        from tradex_hr.tradexcel_hr.report.tradexcel_payroll_readiness import tradexcel_payroll_readiness as readiness_report
        readiness_report._require_payroll_manager(company)
        with pytest.raises(frappe.PermissionError):
            readiness_report._require_payroll_manager("Elegance Footwear Ltd.")
        assert frappe.has_permission("Payroll Entry", "create")
        assert frappe.has_permission("Payroll Entry", "submit")
        assert frappe.has_permission("Additional Salary", "create")
        assert not frappe.has_permission("Additional Salary", "submit")
        assert not frappe.has_permission("Salary Slip", "submit")
        if employees:
            assert frappe.has_permission("Employee", "read", employees[0])
        if other_employees:
            assert not frappe.has_permission("Employee", "read", other_employees[0])
    finally:
        frappe.set_user("Administrator")
        frappe.delete_doc("User Permission", permission.name, ignore_permissions=True, force=True)
        frappe.delete_doc("User", email, ignore_permissions=True, force=True)
        frappe.clear_cache()
        frappe.set_user(old_user)


def test_direct_native_payroll_entry_submit_without_preparation_is_blocked(monkeypatch):
    monkeypatch.setattr(frappe, "enqueue", lambda *_args, **_kwargs: None)
    entry = frappe.get_doc({
        "doctype": "Payroll Entry",
        "company": "Tradexcel Ceramics Ltd.",
        "posting_date": "2027-03-31",
        "start_date": "2027-03-01",
        "end_date": "2027-03-31",
        "payroll_frequency": "Monthly",
        "currency": "BDT",
        "exchange_rate": 1,
        "payroll_payable_account": "Creditors - TCL",
        "salary_slip_based_on_timesheet": 0,
        "validate_attendance": 0,
        "employees": [],
    })
    entry.insert(ignore_permissions=True)
    try:
        with pytest.raises(frappe.ValidationError, match="Payroll is not prepared"):
            entry.submit()
        entry.reload()
        assert entry.docstatus == 0
    finally:
        if frappe.db.exists("Payroll Entry", entry.name):
            frappe.delete_doc("Payroll Entry", entry.name, ignore_permissions=True, force=True)


def test_unauthorized_payroll_caller_writes_no_financial_records(monkeypatch):
    monkeypatch.setattr(frappe, "enqueue", lambda *_args, **_kwargs: None)
    email = f"codex-unauthorized-payroll-{frappe.generate_hash(8)}@example.test"
    user = frappe.get_doc({
        "doctype": "User",
        "email": email,
        "first_name": "Synthetic HR Manager",
        "enabled": 1,
        "user_type": "System User",
        "send_welcome_email": 0,
        "roles": [{"role": "Tradexcel HR Manager"}],
    })
    user.insert(ignore_permissions=True)
    before_additional = frappe.db.count("Additional Salary")
    before_entries = frappe.db.count("Payroll Entry")
    readiness = {
        "status": "READY",
        "outcomes": [{
            "employee": "SYNTHETIC-EMP",
            "employee_data": {"company": "Tradexcel Ceramics Ltd."},
            "pay_basis": {"status": "Daily Wage"},
        }],
        "employee_count": 1,
        "ready_count": 1,
        "blocked_count": 0,
    }
    monkeypatch.setattr(native_payroll, "inspect_native_payroll_readiness", lambda *_args, **_kwargs: readiness)
    monkeypatch.setattr(native_payroll, "create_daily_wage_input", lambda *_args: pytest.fail("unauthorized caller wrote money"))
    old_user = frappe.session.user
    try:
        frappe.set_user(email)
        with pytest.raises(frappe.PermissionError, match="Payroll Manager role is required"):
            native_payroll.prepare_native_payroll(
                "Tradexcel Ceramics Ltd.", date(2026, 9, 1), date(2026, 9, 30)
            )
        assert frappe.db.count("Additional Salary") == before_additional
        assert frappe.db.count("Payroll Entry") == before_entries
    finally:
        frappe.set_user("Administrator")
        frappe.delete_doc("User", email, ignore_permissions=True, force=True)
        frappe.clear_cache()
        frappe.set_user(old_user)


def test_approved_managed_payroll_allows_salary_slip_submission_eligibility(monkeypatch):
    approved = frappe._dict({
        "docstatus": 1,
        "workflow_state": "Tradexcel Payroll Approved",
        "salary_slips_created": 1,
        "status": "Submitted",
    })
    monkeypatch.setattr(native_payroll.frappe.db, "get_value", lambda *_args, **_kwargs: "MANAGED-KEY")
    monkeypatch.setattr(native_payroll.frappe, "get_doc", lambda *_args, **_kwargs: approved)
    monkeypatch.setattr(financial_readiness, "inspect_payroll_financial_readiness", lambda *_: {"status": "READY", "blockers": []})
    slip = frappe._dict({"payroll_entry": "PAY-APPROVED"})
    assert native_payroll.validate_salary_slip_before_submit(slip) is None


def test_rejecting_submitted_review_cancels_native_payroll_entry(monkeypatch):
    from frappe.model.workflow import apply_workflow

    monkeypatch.setattr(frappe, "enqueue", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(native_payroll, "validate_payroll_entry_before_submit", lambda *_args, **_kwargs: None)
    entry = frappe.get_doc({
        "doctype": "Payroll Entry",
        "company": "Tradexcel Ceramics Ltd.",
        "posting_date": "2027-04-30",
        "start_date": "2027-04-01",
        "end_date": "2027-04-30",
        "payroll_frequency": "Monthly",
        "currency": "BDT",
        "exchange_rate": 1,
        "payroll_payable_account": "Creditors - TCL",
        "salary_slip_based_on_timesheet": 0,
        "validate_attendance": 0,
        "workflow_state": "Tradexcel Payroll Draft",
        "employees": [],
    })
    entry.insert(ignore_permissions=True)
    try:
        apply_workflow({"doctype": "Payroll Entry", "name": entry.name}, "Submit for Review")
        entry.reload()
        assert entry.docstatus == 1
        assert entry.workflow_state == "Tradexcel Payroll Pending Review"
        entry.db_set({"salary_slips_created": 1, "status": "Submitted"})
        apply_workflow({"doctype": "Payroll Entry", "name": entry.name}, "Reject")
        entry.reload()
        assert entry.docstatus == 2
        assert entry.workflow_state == "Tradexcel Payroll Rejected"
        assert entry.status == "Cancelled"
    finally:
        frappe.set_user("Administrator")
        if frappe.db.exists("Payroll Entry", entry.name):
            frappe.delete_doc("Payroll Entry", entry.name, ignore_permissions=True, force=True)


def test_managed_entry_with_changed_population_is_not_reused(monkeypatch):
    readiness = {"status": "READY", "outcomes": [], "employee_count": 0, "ready_count": 0, "blocked_count": 0}
    row = {"name": "MANAGED-ENTRY", "custom_tradex_run_key": "RUN-KEY", "docstatus": 0}
    doc = frappe._dict({
        "name": "MANAGED-ENTRY",
        "company": "Company A",
        "start_date": date(2026, 9, 1),
        "end_date": date(2026, 9, 30),
        "payroll_frequency": "Monthly",
        "custom_tradex_run_key": "RUN-KEY",
        "custom_tradex_population_hash": "OLD-FINGERPRINT",
        "custom_tradex_attendance_revision": "",
        "employees": [],
        "branch": None,
        "department": None,
        "designation": None,
        "status": "Draft",
    })
    monkeypatch.setattr(native_payroll, "inspect_native_payroll_readiness", lambda *_args, **_kwargs: readiness)
    monkeypatch.setattr(native_payroll, "_assert_preparation_authorized", lambda *_args: None)
    monkeypatch.setattr(native_payroll, "_managed_run_key", lambda *_args: "RUN-KEY")
    monkeypatch.setattr(native_payroll, "_existing_payroll_entry", lambda *_args: [row])
    monkeypatch.setattr(native_payroll, "_daily_inputs_for_readiness", lambda *_args: ([], []))
    monkeypatch.setattr(native_payroll, "_population_fingerprint", lambda *_args: "CURRENT-FINGERPRINT")
    monkeypatch.setattr(native_payroll, "_attendance_revision", lambda *_args: "")
    monkeypatch.setattr(native_payroll.frappe, "get_doc", lambda *_args, **_kwargs: doc)
    result = native_payroll.prepare_native_payroll("Company A", date(2026, 9, 1), date(2026, 9, 30))
    assert result["status"] == "BLOCKED_EXISTING_PAYROLL_MISMATCH"
    assert "no longer matches current" in result["blockers"][0]["reason"]


def test_readiness_keeps_attendance_and_unsafe_structure_findings_visible(monkeypatch):
    employee = {"name": "EMP-1", "company": "Company A", "status": "Active"}
    monkeypatch.setattr(native_payroll, "_employees_for_period", lambda *_args: [employee])
    monkeypatch.setattr(native_payroll, "resolve_pay_basis", lambda *_args: {
        "status": native_payroll.DAILY,
        "employee": "EMP-1",
        "assignment": "SSA-1",
        "salary_structure": "Legacy Daily",
        "base": 350,
    })
    monkeypatch.setattr(native_payroll, "_attendance_required_for_payroll", lambda: False)
    monkeypatch.setattr(native_payroll, "_period_attendance_gate", lambda *_args: [{
        "employee": "EMP-1",
        "code": "ATTENDANCE_UNMARKED",
        "reason": "3 attendance days need review.",
    }])
    monkeypatch.setattr(native_payroll, "_unapproved_overtime", lambda *_args: [])
    monkeypatch.setattr(native_payroll, "inspect_daily_wage_structure", lambda *_args: {
        "status": "BLOCKED_UNSAFE_STRUCTURE",
        "reason": "The current structure prorates Daily Wage.",
    })

    result = native_payroll.inspect_native_payroll_readiness(
        "Company A", date(2026, 9, 1), date(2026, 9, 30)
    )

    outcome = result["outcomes"][0]
    assert {item["code"] for item in outcome["findings"]} == {
        "ATTENDANCE_UNMARKED", "BLOCKED_UNSAFE_STRUCTURE"
    }
    assert outcome["pay_basis"]["status"] == native_payroll.DAILY
    assert outcome["daily_wage_input"]["status"] == "BLOCKED_UNSAFE_STRUCTURE"


def test_period_gate_reports_attendance_findings_even_without_finalized_period(monkeypatch):
    monkeypatch.setattr(native_payroll.frappe, "get_all", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(native_payroll, "inspect_attendance_integrity", lambda *_args: {
        "blockers": [{
            "code": "ATTENDANCE_UNMARKED",
            "employee": "EMP-1",
            "reason": "Native Payroll Entry found 3 unmarked day(s).",
        }],
    })

    findings = native_payroll._period_attendance_gate(
        "Company A", date(2026, 9, 1), date(2026, 9, 30), ["EMP-1"]
    )

    assert findings[0]["code"] == "ATTENDANCE_UNMARKED"
    assert "3 unmarked" in findings[0]["reason"]
