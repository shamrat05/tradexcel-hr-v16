"""TXUX-260930-006-P03: attendance correction preview message leakage tests.

Verifies that expected row-level skips (e.g. Leave, Holiday, unchanged status)
return controlled row outcomes without leaking native HRMS validation messages into
frappe.local.message_log (which would render as unnecessary error modals in desk).
Also verifies that genuine validation failures or unexpected errors continue to be
preserved and reported.
"""
import os
from pathlib import Path

import frappe
from frappe.utils import getdate
import pytest

from tradex_hr.tradexcel_hr import attendance_corrections


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


def test_preview_skip_does_not_leak_server_message(monkeypatch):
    """When candidate.validate() raises validate_no_attendance_to_create due to an expected skip,
    the message must not leak into message_log, while row outcome is truthful ('Skipped').
    """
    frappe.local.message_log = []
    company = "Tradexcel Ceramics Ltd."
    emp = frappe.db.get_value("Employee", {"company": company, "status": "Active"}, "name")
    assert emp, "Active employee required"
    emp_doc = frappe.get_doc("Employee", emp)

    # Mock candidate warnings to return expected Skip
    skip_warnings = [{"date": getdate(), "reason": "On Leave", "action": "Skip"}]

    def mock_get_warnings(self):
        return skip_warnings

    def mock_validate(self):
        # Emulate native AttendanceRequest.validate_no_attendance_to_create
        frappe.msgprint(
            title="No attendance records to create due to following reasons",
            msg=[["Date", "Reason", "Action"], [str(getdate()), "On Leave", "Skip"]],
            as_table=True,
            raise_exception=True,
        )

    monkeypatch.setattr("hrms.hr.doctype.attendance_request.attendance_request.AttendanceRequest.get_attendance_warnings", mock_get_warnings)
    monkeypatch.setattr("hrms.hr.doctype.attendance_request.attendance_request.AttendanceRequest.validate", mock_validate)

    # Set prior message in message_log to verify it is NOT globally cleared
    frappe.local.message_log = [{"message": "Existing unrelated message", "title": "Info"}]
    initial_log_len = len(frappe.local.message_log)

    row = attendance_corrections._preview_one(
        emp_doc, company, getdate(), "Present", "Verified missed attendance", ambiguous=[]
    )

    assert row["outcome"] == "Skipped"
    assert "On Leave" in row["message"] or "leave" in row["message"].lower()

    # Verify that prior message is intact and no new message was leaked
    assert len(frappe.local.message_log) == initial_log_len
    assert frappe.local.message_log[0]["message"] == "Existing unrelated message"


def test_genuine_validation_error_is_preserved(monkeypatch):
    """When candidate.validate() raises a non-skip validation error, the message must be preserved."""
    frappe.local.message_log = []
    company = "Tradexcel Ceramics Ltd."
    emp = frappe.db.get_value("Employee", {"company": company, "status": "Active"}, "name")
    assert emp, "Active employee required"
    emp_doc = frappe.get_doc("Employee", emp)

    def mock_validate(self):
        frappe.msgprint(
            title="Genuine Error",
            msg="Employee is not eligible for attendance request",
            raise_exception=True,
        )

    monkeypatch.setattr("hrms.hr.doctype.attendance_request.attendance_request.AttendanceRequest.get_attendance_warnings", lambda self: [])
    monkeypatch.setattr("hrms.hr.doctype.attendance_request.attendance_request.AttendanceRequest.validate", mock_validate)

    row = attendance_corrections._preview_one(
        emp_doc, company, getdate(), "Present", "Verified missed attendance", ambiguous=[]
    )

    assert row["outcome"] == "Blocked"
    assert "need review" in row["message"].lower()

    # The genuine error message should be preserved in message_log
    assert len(frappe.local.message_log) == 1
    assert frappe.local.message_log[0]["title"] == "Genuine Error"
