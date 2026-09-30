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


@pytest.fixture(autouse=True)
def fixture_enqueue(monkeypatch):
    """Intercept frappe.enqueue background jobs so teardown doesn't fail on full queues."""
    real_enqueue = frappe.enqueue

    def safe_enqueue(method, *args, **kwargs):
        if method in (
            "frappe.model.delete_doc.delete_dynamic_links",
            "frappe.desk.doctype.workspace.workspace.rebuild_for_doctype",
        ):
            return None
        try:
            return real_enqueue(method, *args, **kwargs)
        except frappe.exceptions.QueueOverloaded:
            return None

    monkeypatch.setattr(frappe, "enqueue", safe_enqueue)



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
    # No automatic Shift Type selection is passed to the native tool.
    assert "shift_type" not in source.split("const openTool")[1].split("const openAssignments")[0]


def test_shift_assignment_route_uses_only_confirmed_native_fields():
    """P02: docstatus, start_date and end_date are verified; from_date/to_date are not."""
    meta = frappe.get_meta("Shift Assignment")
    assert meta.has_field("start_date") and meta.has_field("end_date")
    assert not meta.has_field("from_date") and not meta.has_field("to_date")
    assert meta.is_submittable == 1

    source = (COVERAGE_DIR / "tradexcel_shift_coverage.js").read_text()
    assert "docstatus: 1" in source
    assert 'start_date: ["<=", report.get_filter_value("as_of_date")]' in source
    assert "from_date" not in source and "to_date" not in source
    # Route options cannot express "End Date blank OR End Date >= day", so no
    # end_date filter may be implied; the operator gets an explicit instruction.
    assert "end_date: [" not in source
    assert "End Date" in source and "blank" in source and "previously ended" in source
    assert "submitted" in source and "docstatus 1" in source
    assert "historical validity" in source and "cached" in source
    assert "existing native Shift Assignments for this date" not in source



def test_native_list_route_options_cannot_express_open_ended_or_condition():
    """The installed List View route parser is AND-only; OR lives server-side."""
    list_view = Path(frappe.get_app_path("frappe", "public/js/frappe/list/list_view.js")).read_text()
    parser = list_view.split("parse_filters_from_route_options()")[1].split("get_list_view")[0]
    assert "or_filters" not in parser
    # The server-side query builder does support the exact condition, which is
    # why the fallback instruction (not a fake filter) is the safe choice.
    db_query = Path(frappe.get_app_path("frappe", "model/db_query.py")).read_text()
    assert "or_filters" in db_query


def test_shift_assignment_route_filter_semantics_on_installed_schema():
    from tradex_hr.tests.persona_uat import SyntheticPersonaHarness

    company = "Tradexcel Ceramics Ltd."
    branch = frappe.db.get_value("Branch", {"company": company}, "name")
    department = frappe.db.get_value("Department", {"company": company}, "name")
    shift_type = "General Shift" if frappe.db.exists("Shift Type", "General Shift") else frappe.get_all(
        "Shift Type", limit=1, pluck="name"
    )[0]
    day = frappe.utils.getdate("2026-09-15")
    harness = SyntheticPersonaHarness("TXUX006P02" + frappe.generate_hash(6).upper())
    tracked = []
    try:
        employee = harness.create_employee("route", company, branch, department)
        other = harness.create_employee("other", company, branch, department)

        def assignment(target, start, end, docstatus=1):
            doc = frappe.get_doc({
                "doctype": "Shift Assignment", "employee": target, "shift_type": shift_type,
                "company": company, "start_date": start, "end_date": end, "status": "Active",
                "docstatus": docstatus,
            })
            doc.db_insert()
            tracked.append(doc.name)
            return doc.name

        # Synthetic records: direct insert avoids native same-date overlap
        # validation (allow_multiple_shift_assignments is 0 site-wide).
        overlap = assignment(employee, frappe.utils.add_days(day, -5), frappe.utils.add_days(day, 5), docstatus=1)
        open_ended = assignment(employee, frappe.utils.add_days(day, -10), None, docstatus=1)
        ended = assignment(employee, frappe.utils.add_days(day, -20), frappe.utils.add_days(day, -1), docstatus=1)
        draft = assignment(employee, frappe.utils.add_days(day, -5), frappe.utils.add_days(day, 5), docstatus=0)
        cancelled = assignment(employee, frappe.utils.add_days(day, -5), frappe.utils.add_days(day, 5), docstatus=2)
        foreign = assignment(other, frappe.utils.add_days(day, -5), frappe.utils.add_days(day, 5), docstatus=1)

        # The route's actual AND-only filter: submitted status (docstatus 1),
        # selected Employees, start on or before the day.
        # It includes ended rows, but strictly excludes draft, cancelled, and foreign rows.
        route_rows = set(frappe.get_list(
            "Shift Assignment",
            filters={"docstatus": 1, "employee": ["in", [employee]], "start_date": ["<=", day]},
            pluck="name",
        ))
        assert route_rows == {overlap, open_ended, ended}
        assert draft not in route_rows, "draft assignments (docstatus 0) must be excluded"
        assert cancelled not in route_rows, "cancelled assignments (docstatus 2) must be excluded"
        assert foreign not in route_rows, "selected Employee scoping must hold"

        # The exact active-on-day definition (submitted + blank End Date OR End Date >= day)
        # is available only server-side, not through List route options.
        active_rows = set(frappe.get_list(
            "Shift Assignment",
            filters={"docstatus": 1, "employee": ["in", [employee]], "start_date": ["<=", day]},
            or_filters=[["end_date", "is", "not set"], ["end_date", ">=", day]],
            pluck="name",
        ))
        assert active_rows == {overlap, open_ended}
        assert ended not in active_rows
        assert draft not in active_rows
        assert cancelled not in active_rows
    finally:
        frappe.set_user("Administrator")
        for name in tracked:
            if frappe.db.exists("Shift Assignment", name):
                # Synthetic rows were inserted directly; reset docstatus at DB level
                # so the test-owned record can be removed.
                frappe.db.sql("update `tabShift Assignment` set docstatus=0 where name=%s", (name,))
                frappe.delete_doc("Shift Assignment", name, force=True, ignore_permissions=True)
        harness.cleanup()
        assert not frappe.get_all(
            "Shift Assignment", filters={"employee": ["in", harness.employees]}, pluck="name"
        )



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
