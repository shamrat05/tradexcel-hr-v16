"""Precise native skip classification; no records written or queue mocking."""
import os
import pytest
import frappe
from frappe.utils import getdate
from hrms.hr.doctype.attendance_request.attendance_request import AttendanceRequest
from workforce_suite.workforce_suite import attendance_corrections as service

@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(site=os.environ.get("FRAPPE_TEST_SITE", "hrms-v16.localhost"), sites_path="/home/sanchita/frappe-bench-v16/sites")
    frappe.connect()
    yield
    frappe.db.rollback()
    frappe.destroy()

@pytest.fixture
def preview(monkeypatch):
    old = getattr(frappe.local, "message_log", [])
    frappe.local.message_log = []
    employee = frappe._dict(name="TXUX-SYNTHETIC", employee_name="Synthetic", branch=None, department=None)
    request = frappe.get_doc({"doctype":"Attendance Request", "employee":employee.name,
        "from_date":getdate(), "to_date":getdate()})
    monkeypatch.setattr(service, "_candidate", lambda *a: request)
    monkeypatch.setattr(service, "_day_context", lambda *a: dict(attendance=None,
        attendance_state="Not Marked", attendance_status="Not Marked", attendance_docstatus=None,
        checkin_count=0, in_time=None, out_time=None, mobile_review_pending=False))
    for name in ("_payroll_consumed", "_pending_mobile_event", "_existing_request"):
        monkeypatch.setattr(service, name, lambda *a: False)
    monkeypatch.setattr(AttendanceRequest, "get_attendance_warnings", lambda self:
        [{"date":getdate(), "reason":"Holiday", "action":"Skip"}])
    def run(): return service._preview_one(employee, "Synthetic", getdate(), "Present", "Synthetic preview", [])
    yield run
    frappe.local.message_log = old

@pytest.mark.parametrize("prior,extra", [(False,False),(True,False),(False,True),(True,True)])
def test_actual_native_skip_preserves_other_messages(preview,monkeypatch,prior,extra):
    if prior: frappe.msgprint("Existing notice")
    def validate(self):
        if extra: frappe.msgprint("New unrelated notice")
        self.validate_no_attendance_to_create() # actual installed native method
    monkeypatch.setattr(AttendanceRequest,"validate",validate)
    assert preview()["outcome"] == "Skipped"
    assert [m.message for m in frappe.local.message_log] == (
        (["Existing notice"] if prior else []) + (["New unrelated notice"] if extra else []))

@pytest.mark.parametrize("spoof_title", [False,True])
def test_unrelated_validation_with_skip_warnings_is_blocked(preview,monkeypatch,spoof_title):
    def validate(self):
        frappe.throw("Unrelated validation failure", title=(
            "No attendance records to create due to following reasons" if spoof_title else "Other failure"))
    monkeypatch.setattr(AttendanceRequest,"validate",validate)
    assert preview()["outcome"] == "Blocked"
    assert len(frappe.local.message_log)==1
    assert frappe.local.message_log[0].message=="Unrelated validation failure"

def test_unexpected_exception_propagates_without_clearing(preview,monkeypatch):
    frappe.msgprint("Existing notice")
    def validate(self): raise RuntimeError("Unexpected failure")
    monkeypatch.setattr(AttendanceRequest,"validate",validate)
    with pytest.raises(RuntimeError,match="Unexpected failure"): preview()
    assert frappe.local.message_log[0].message=="Existing notice"
