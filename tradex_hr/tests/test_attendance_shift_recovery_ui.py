"""TXUX-260930-006: attendance/shift recovery UI contracts.

Offline Node projection of the candidate client scripts plus read-only source
projection checks. No business mutation, no new approval state.
"""
import os
import shutil
from pathlib import Path

import frappe
import pytest

ROOT = Path(__file__).resolve().parents[1]
DAILY_DIR = ROOT / "tradexcel_hr/report/tradexcel_daily_attendance_board"
COVERAGE_DIR = ROOT / "tradexcel_hr/report/tradexcel_shift_coverage"


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


def test_offline_recovery_ui_contracts():
    node = shutil.which("node") or "/home/sanchita/.nvm/versions/node/v24.15.0/bin/node"
    import subprocess

    subprocess.run([node, str(ROOT / "tests/js/attendance_shift_recovery.cjs")], check=True, capture_output=True, text=True)


def test_daily_board_bundled_script_is_the_active_projection():
    from frappe.desk.query_report import get_script

    script = get_script("Tradexcel Daily Attendance Board")["script"]
    bundled = (DAILY_DIR / "tradexcel_daily_attendance_board.js").read_text()
    assert "Prepare Attendance Corrections" in script
    assert "Problem / Result" in script
    assert "Draft Attendance Requests created" in script
    assert bundled.splitlines()[0] in script


def test_daily_board_keeps_preview_confirm_and_native_mutation_contract():
    source = (DAILY_DIR / "tradexcel_daily_attendance_board.js").read_text()
    assert "preview_attendance_corrections" in source
    assert "prepare_attendance_corrections" in source
    # No client-side Attendance write, submit or approval endpoint.
    for forbidden in ("submit_attendance", "frappe.db.", ".insert(", ".submit(", "frm.save"):
        assert forbidden not in source, f"unexpected client mutation surface: {forbidden}"
    assert "Draft requests are not approved Attendance" in source
    assert "an independent Attendance Correction Approver must submit each request" in source


def test_shift_coverage_routes_to_native_tool_without_employee_ids():
    source = (COVERAGE_DIR / "tradexcel_shift_coverage.js").read_text()
    assert "Shift Assignment Tool" in source
    assert "set_route(\"Form\", \"Shift Assignment Tool\")" in source
    assert "employee_names" not in source
    assert 'route_options = { action: "Assign Shift", start_date: report.get_filter_value("as_of_date") }' in source
    # Conflicting assignments never auto-select a winner.
    assert "The app never chooses between assignments" in source


def test_checkin_review_has_no_client_state_and_uses_server_endpoints():
    source = (ROOT / "public/js/employee_checkin_review.js").read_text()
    assert "approve_mobile_checkin" in source
    assert "reject_mobile_checkin" in source
    assert "custom_tradex_review_status" in source  # read-only projection
    assert "frm.set_value" not in source
    assert "save(" not in source
    # Client only calls the two controlled review endpoints with a POST.
    assert source.count("frappe.call") == 1
    assert 'type: "POST"' in source


def test_attendance_period_status_only_changes_through_server_actions():
    source = (ROOT / "public/js/tradexcel_attendance_period.js").read_text()
    assert "finalize_attendance_period" in source
    assert "reopen_attendance_period" in source
    assert "frappe.confirm" in source
    assert "frm.set_value" not in source
    assert "never silently rewritten" in source
