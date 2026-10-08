"""TXUX-260930-008: Employee, lifecycle, calendar, and separation recovery UI tests.

Verifies:
1. Static and projection contracts for employee_calendar.js:
   - Month navigation race condition prevention (request ID tracking).
   - Error handling via .catch() for failed requests.
   - Comprehensive XSS escaping of all server-provided data.
   - Responsive scrolling container avoiding document-level overflow at 375px.
   - Separation of Approved Attendance, Raw Checkin Evidence, Leave, and Scheduled Off.
   - Strict role checks for "Finalize Exit Access" and preservation of independent settlement.
   - Distinct inspections for Joiner Readiness, Operational Exit Readiness, and Full & Final Settlement.
2. Static and projection contracts for employee_separation.js:
   - Owner/Director role check and separation-maker self-review guard.
   - Dynamic field requirement toggling based on review decision.
   - Scoped Rule Set query.
3. Static and projection contracts for employee_data_gaps.js and workforce_joiners_and_leavers.js:
   - Filter scoping and link queries.
   - Formatter pills for priorities and movements.
   - Native navigation routes.
4. Server endpoint contracts and negative permission enforcement:
   - get_employee_calendar permission checks.
   - finalize_employee_exit_access authorization guards.
   - inspect_joiner_readiness hire-source distinction without fake recruitment records.
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest

import frappe

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(
        site=os.environ.get("FRAPPE_TEST_SITE", "hrms-v16.localhost"),
        sites_path=os.environ.get("FRAPPE_TEST_SITES_PATH", "/home/sanchita/frappe-bench-v16/sites"),
        force=True,
    )
    frappe.connect()
    frappe.set_user("Administrator")
    yield
    frappe.set_user("Administrator")
    frappe.destroy()


def test_calendar_js_prevents_navigation_race_and_escapes_html():
    """Verify employee_calendar.js tracks request ID and escapes server-provided text."""
    js_path = ROOT / "public/js/employee_calendar.js"
    assert js_path.exists(), "employee_calendar.js must exist"
    code = js_path.read_text()

    # Race condition protection: request id counter and comparison
    assert "current_request_id" in code
    assert "req_id !== current_request_id" in code
    assert ".catch(" in code, "Failed requests must have catch error handler"

    # XSS prevention: escaping
    assert "frappe.utils.escape_html" in code
    assert "escape_html(safe_month_label)" in code or "escape_html(month_label)" in code
    assert "escape_html(data.holiday_list" in code
    assert "escape_html(data.weekly_off" in code
    assert "escape_html(__(name))" in code

    # Responsive wrapper preventing 375px document overflow
    assert "overflow-x:auto" in code or "overflow-x: auto" in code
    assert "min-width:540px" in code or "min-width: 540px" in code or "min-width:" in code

    # Clear distinction of unapproved punches and scheduled off
    assert "Punched Only (Raw)" in code or "Punched Only" in code
    assert "Holiday" in code
    assert "Weekly Off" in code

    # No client-side settlement or money calculations
    for forbidden in ("parseFloat", "parseInt", "toFixed(", "net_pay", "calculate_settlement"):
        assert forbidden not in code, f"Forbidden client calculation found: {forbidden}"


def test_calendar_js_separates_readiness_modalities():
    """Verify calendar JS provides distinct UX for Joiner, Exit, and Full & Final readiness."""
    js_path = ROOT / "public/js/employee_calendar.js"
    code = js_path.read_text()

    assert "show_joiner_readiness" in code
    assert "show_exit_readiness" in code
    assert "show_full_and_final_readiness" in code

    # Canonical destinations
    assert "/app/salary-structure-assignment" in code
    assert "/app/shift-assignment-tool" in code
    assert "/app/holiday-list" in code

    # Finalize Exit Access button role guard
    assert "has_manager_role" in code
    assert "frm.doc.relieving_date" in code


def test_separation_js_role_and_validation_guards():
    """Verify employee_separation.js checks Owner/Director role, prevents maker self-review, and sets requirements."""
    js_path = ROOT / "public/js/employee_separation.js"
    assert js_path.exists(), "employee_separation.js must exist"
    code = js_path.read_text()

    assert "Workforce Owner/Director" in code
    assert "frm.doc.owner !== frappe.session.user" in code
    assert "review_separation_statutory_status" in code

    # Dynamic requirement toggling
    assert "dialog.set_df_property(\"rule_set\", \"reqd\"" in code
    assert "dialog.set_df_property(\"classification\", \"reqd\"" in code

    # Invalid "Review Required" option excluded
    assert "Review Required" not in code


def test_data_gaps_and_joiners_leavers_ui_contracts():
    """Verify employee_data_gaps.js and workforce_joiners_and_leavers.js have proper filters, formatters, and native routes."""
    gaps_js = (ROOT / "workforce_suite/report/employee_data_gaps/employee_data_gaps.js").read_text()
    assert "departments_used_by_branch" in gaps_js
    assert "indicator-pill red" in gaps_js
    assert "Shift Assignment Tool" in gaps_js
    assert "Employee Onboarding" in gaps_js

    joiners_js = (ROOT / "workforce_suite/report/workforce_joiners_and_leavers/workforce_joiners_and_leavers.js").read_text()
    assert "indicator-pill green" in joiners_js
    assert "Employee Onboarding" in joiners_js
    assert "Employee Separation" in joiners_js


def test_get_employee_calendar_permission_negative():
    """Test get_employee_calendar enforces Employee read permissions."""
    from workforce_suite.workforce_suite.employee_calendar import get_employee_calendar

    emp = frappe.db.get_value("Employee", filters={"status": "Active"}, fieldname="name")
    assert emp, "An active employee must exist for permission testing"

    frappe.set_user("Guest")
    try:
        with pytest.raises(frappe.PermissionError):
            get_employee_calendar(emp)
    finally:
        frappe.set_user("Administrator")


def test_finalize_employee_exit_access_negative_authorization(monkeypatch):
    """Verify unauthorized users cannot call finalize_employee_exit_access."""
    from workforce_suite.workforce_suite.employee_separation import finalize_employee_exit_access

    emp = frappe.db.get_value("Employee", filters={"status": "Active"}, fieldname="name")
    assert emp, "An active employee must exist for exit access authorization testing"

    # Simulate a non-manager employee user
    monkeypatch.setattr(frappe, "get_roles", lambda *args, **kwargs: ["Employee"])
    monkeypatch.setattr(frappe.session, "user", "unauthorized_worker@example.test", raising=False)

    with pytest.raises(frappe.PermissionError):
        finalize_employee_exit_access(emp)


def test_calendar_only_submitted_attendance(monkeypatch):
    from workforce_suite.workforce_suite import employee_calendar as calendar
    from datetime import date
    monkeypatch.setattr(frappe, "has_permission", lambda *a, **k: True)
    monkeypatch.setattr(frappe.db, "get_value", lambda *a, **k: None)
    monkeypatch.setattr(frappe.db, "sql", lambda *a, **k: [])
    rows=[frappe._dict(attendance_date=date(2026,9,1),status="Absent",docstatus=0,late_entry=0,early_exit=0),
          frappe._dict(attendance_date=date(2026,9,2),status="Present",docstatus=1,late_entry=0,early_exit=0)]
    def get_all(dt,filters=None,**kw):
        if dt!="Attendance":return []
        assert filters["docstatus"]==1
        return [r for r in rows if r.docstatus==filters["docstatus"]]
    monkeypatch.setattr(frappe,"get_all",get_all)
    result=calendar.get_employee_calendar("TXUX-SYNTHETIC","2026-09")
    assert result["days"][0]["category"]=="No Record"
    assert result["days"][1]["category"]=="Present"


@pytest.mark.parametrize("role,user,passes",[
    ("Workforce Suite Manager","synthetic@test",True),
    ("Workforce Owner/Director","synthetic@test",True),
    ("System Manager","synthetic@test",False),
    ("Employee","synthetic@test",False),
    ("System Manager","Administrator",True),
])
def test_exact_exit_role_boundary_without_writes(monkeypatch,role,user,passes):
    from workforce_suite.workforce_suite import employee_separation as service
    monkeypatch.setattr(service,"_authorized_employee",lambda name:frappe._dict(name=name))
    monkeypatch.setattr(frappe,"get_roles",lambda:[role])
    monkeypatch.setattr(frappe.session,"user",user)
    monkeypatch.setattr(service,"inspect_employee_exit_readiness",lambda name:{"ready_for_access_finalization":False})
    with pytest.raises(frappe.ValidationError if passes else frappe.PermissionError) as error:
        service.finalize_employee_exit_access("TXUX-SYNTHETIC")
    assert ("operational exit blockers" in str(error.value))==passes


def test_early_fnf_blocker_is_authoritative(monkeypatch):
    from workforce_suite.workforce_suite import employee_separation as service
    monkeypatch.setattr(service,"_authorized_employee",lambda name:frappe._dict(name=name,relieving_date=None))
    result=service.inspect_full_and_final_readiness("TXUX-SYNTHETIC")
    assert result=={"status":"BLOCKED","employee":"TXUX-SYNTHETIC","findings":[{"code":"RELIEVING_DATE_MISSING"}]}


@pytest.mark.parametrize("decision,classification,rule_name,allowed",[
    ("Not Applicable","Outside worker scope",None,True),
    ("Not Applicable","Worker under selected regime",None,False),
    ("Not Applicable","Outside worker scope","Synthetic rule",False),
    ("Approved","Worker under selected regime","Synthetic rule",True),
    ("Approved","Worker under selected regime",None,False),
    ("Approved",None,"Synthetic rule",False),
])
def test_actual_legal_review_decisions(monkeypatch,decision,classification,rule_name,allowed):
    from workforce_suite.workforce_suite import statutory_exit as service
    from datetime import date
    class Synthetic(frappe._dict):
        def db_set(self,values):self.update(values)
    doc=Synthetic(name="TXUX-SYNTHETIC",employee="TXUX-SYNTHETIC",company="Synthetic",owner="maker@test",docstatus=1)
    doc[service.SEPARATION_TYPE]="Resignation"
    rule=frappe._dict(docstatus=1,company="Synthetic",branch=None,
        applicability_date_basis="Employee Relieving Date (Legal Review)",
        effective_from="2026-01-01",effective_to=None,
        entitlements=[frappe._dict(separation_type="Resignation",classification="Worker under selected regime")])
    monkeypatch.setattr(service,"_separation",lambda name:doc)
    monkeypatch.setattr(frappe,"get_doc",lambda *a:rule)
    monkeypatch.setattr(frappe.db,"get_value",lambda dt,name,field: "2026-09-01" if field=="relieving_date" else None)
    monkeypatch.setattr(frappe,"get_roles",lambda:["Workforce Owner/Director"])
    monkeypatch.setattr(frappe.session,"user","reviewer@test")
    if not allowed:
        with pytest.raises(frappe.ValidationError):service.review_separation_statutory_status(doc.name,decision,"Synthetic notes",rule_name,classification)
        assert not doc.get(service.STATUS_FIELD)
    else:
        result=service.review_separation_statutory_status(doc.name,decision,"Synthetic notes",rule_name,classification)
        assert result["status"]==decision
        assert doc[service.CLASSIFICATION_FIELD]==classification
        assert result["rule_set"]==(rule_name if decision=="Approved" else None)
    # Durable maker evidence still prevents self-review.
    monkeypatch.setattr(frappe.session,"user","maker@test")
    with pytest.raises(frappe.PermissionError):service.review_separation_statutory_status(doc.name,decision,"Synthetic notes",rule_name,classification)
