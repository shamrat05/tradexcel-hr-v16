from types import SimpleNamespace
import os

import frappe
import pytest

from workforce_suite.workforce_suite import attendance_corrections as corrections


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


@pytest.mark.parametrize(
    ("action", "reason", "half_day"),
    [
        ("Present", "On Duty", 0),
        ("Half Day", "On Duty", 1),
        ("Work From Home", "Work From Home", 0),
    ],
)
def test_supported_attendance_actions_map_to_native_request_fields(action, reason, half_day):
    assert corrections.ACTION_FIELDS[action] == {"reason": reason, "half_day": half_day}


def test_unsupported_absent_action_is_not_exposed():
    assert "Absent" not in corrections.ACTION_FIELDS


def test_request_submission_requires_different_approver_for_maker(monkeypatch):
    doc = SimpleNamespace(employee="EMP-1", company="Company A", owner="maker@example.test", from_date="2026-09-24", to_date="2026-09-24")
    monkeypatch.setattr(corrections.frappe, "get_roles", lambda: ["Workforce Suite Manager", corrections.APPROVER_ROLE])
    monkeypatch.setattr(corrections.frappe.session, "user", "maker@example.test", raising=False)
    monkeypatch.setattr(corrections, "_request_employee_scope", lambda _doc: None)
    monkeypatch.setattr(corrections, "_assert_payroll_not_consumed", lambda _doc: None)

    with pytest.raises(corrections.frappe.PermissionError, match="different Attendance Correction Approver"):
        corrections.validate_attendance_request_before_submit(doc)


def test_request_submission_allows_independent_approver(monkeypatch):
    doc = SimpleNamespace(employee="EMP-1", company="Company A", owner="maker@example.test", from_date="2026-09-24", to_date="2026-09-24")
    monkeypatch.setattr(corrections.frappe, "get_roles", lambda: [corrections.APPROVER_ROLE])
    monkeypatch.setattr(corrections.frappe.session, "user", "approver@example.test", raising=False)
    monkeypatch.setattr(corrections, "_request_employee_scope", lambda _doc: None)
    monkeypatch.setattr(corrections, "_validate_existing_attendance_overwrites", lambda _doc: None)
    monkeypatch.setattr(corrections, "_assert_payroll_not_consumed", lambda _doc: None)
    corrections.validate_attendance_request_before_submit(doc)


def test_submitted_salary_slip_blocks_attendance_history_rewrite(monkeypatch):
    doc = SimpleNamespace(employee="EMP-1", company="Company A", from_date="2026-09-24", to_date="2026-09-24")
    monkeypatch.setattr(corrections.frappe, "get_all", lambda doctype, **_kwargs: [{"name": "SYNTHETIC-SLIP"}] if doctype == "Salary Slip" else [])
    with pytest.raises(corrections.frappe.ValidationError, match="consumed by submitted payroll"):
        corrections._assert_payroll_not_consumed(doc)
