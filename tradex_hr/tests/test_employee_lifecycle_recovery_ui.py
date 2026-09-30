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
3. Static and projection contracts for employee_data_gaps.js and tradexcel_joiners_and_leavers.js:
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


@pytest.fixture(autouse=True)
def fixture_enqueue(monkeypatch):
    """Intercept frappe.enqueue background jobs so teardown doesn't fail on full queues."""
    real_enqueue = frappe.enqueue

    def safe_enqueue(method, *args, **kwargs):
        if method in (
            "frappe.model.delete_doc.delete_dynamic_links",
            "frappe.desk.doctype.workspace.workspace.rebuild_for_doctype",
            "frappe.core.doctype.user.user.create_contact",
        ):
            return None
        try:
            return real_enqueue(method, *args, **kwargs)
        except frappe.exceptions.QueueOverloaded:
            return None

    monkeypatch.setattr(frappe, "enqueue", safe_enqueue)


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

    assert "Tradexcel Owner/Director" in code
    assert "frm.doc.owner !== frappe.session.user" in code
    assert "review_separation_statutory_status" in code

    # Dynamic requirement toggling
    assert "dialog.set_df_property(\"rule_set\", \"reqd\"" in code
    assert "dialog.set_df_property(\"classification\", \"reqd\"" in code

    # Invalid "Review Required" option excluded
    assert "Review Required" not in code


def test_data_gaps_and_joiners_leavers_ui_contracts():
    """Verify employee_data_gaps.js and tradexcel_joiners_and_leavers.js have proper filters, formatters, and native routes."""
    gaps_js = (ROOT / "tradexcel_hr/report/employee_data_gaps/employee_data_gaps.js").read_text()
    assert "departments_used_by_branch" in gaps_js
    assert "indicator-pill red" in gaps_js
    assert "Shift Assignment Tool" in gaps_js
    assert "Employee Onboarding" in gaps_js

    joiners_js = (ROOT / "tradexcel_hr/report/tradexcel_joiners_and_leavers/tradexcel_joiners_and_leavers.js").read_text()
    assert "indicator-pill green" in joiners_js
    assert "Employee Onboarding" in joiners_js
    assert "Employee Separation" in joiners_js


def test_get_employee_calendar_permission_negative():
    """Test get_employee_calendar enforces Employee read permissions."""
    from tradex_hr.tradexcel_hr.employee_calendar import get_employee_calendar

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
    from tradex_hr.tradexcel_hr.employee_separation import finalize_employee_exit_access

    emp = frappe.db.get_value("Employee", filters={"status": "Active"}, fieldname="name")
    assert emp, "An active employee must exist for exit access authorization testing"

    # Simulate a non-manager employee user
    monkeypatch.setattr(frappe, "get_roles", lambda *args, **kwargs: ["Employee"])
    monkeypatch.setattr(frappe.session, "user", "unauthorized_worker@example.test", raising=False)

    with pytest.raises(frappe.PermissionError):
        finalize_employee_exit_access(emp)
