"""Actual native personas, source adapters and Workspace block scope."""
from unittest.mock import patch

import frappe
import pytest

from tradex_hr.tests.persona_uat import PERSONA_ROLES, SyntheticPersonaHarness


@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(site="hrms-v16.localhost", sites_path="/home/sanchita/frappe-bench-v16/sites", force=True)
    frappe.connect()
    frappe.set_user("Administrator")
    yield
    frappe.set_user("Administrator")
    frappe.destroy()


def test_action_board_native_scope_roles_and_read_only_sources():
    from tradex_hr.tradexcel_hr import action_board as board

    company, other = "Tradexcel Ceramics Ltd.", "Elegance Footwear Ltd."
    branches = frappe.get_all("Branch", filters={"company": company}, pluck="name", order_by="name")
    departments = frappe.get_all("Department", filters={"company": company}, pluck="name", order_by="name")
    h = SyntheticPersonaHarness("SOLBOARD" + frappe.generate_hash(8).upper())
    requests = []
    try:
        for key, role in PERSONA_ROLES.items():
            h.create_user(key, [role], company=company, branch=branches[0], department=departments[0])
        own = h.create_employee("in", company, branches[0], departments[0])
        outside = h.create_employee("out", company, branches[1], departments[0])
        other_department = h.create_employee("department", company, branches[0], departments[1])
        other_company = h.create_employee("company", other,
            frappe.db.get_value("Branch", {"company": other}, "name"),
            frappe.db.get_value("Department", {"company": other}, "name"))
        for employee in (own, outside, other_department, other_company):
            doc = frappe.get_doc({"doctype": "Attendance Request", "employee": employee,
                "company": frappe.db.get_value("Employee", employee, "company"), "from_date": "2026-09-01", "to_date": "2026-09-01",
                "reason": "On Duty", "include_holidays": 1,
                "explanation": "Synthetic action board scope"}).insert(ignore_permissions=True)
            requests.append(doc.name)
        frappe.db.commit()
        for key, user in h.users.items():
            frappe.set_user(user)
            if key in {"worker", "import_reviewer"}:
                with pytest.raises(frappe.PermissionError):
                    board.get_board_context()
                with pytest.raises(frappe.PermissionError):
                    board.get_action_board(company)
                continue
            context = board.get_board_context()
            assert company in context["companies"]
            assert other not in context["companies"]
            with pytest.raises(frappe.PermissionError):
                board.get_action_board(other)
            visible = board._employee_names(company)
            assert own in visible and not {outside, other_department, other_company}.intersection(visible)
            with patch.object(board, "_report_items", return_value=[]) as reports, \
                 patch.object(board, "_attendance_items", return_value=[]), \
                 patch.object(board, "_people_items", return_value=[]), \
                 patch.object(board, "_payment_items", return_value=[]):
                result = board.get_action_board(company, "2026-09-01")
            if key in {"attendance_officer", "factory_supervisor", "branch_manager", "department_manager", "device_admin", "attendance_correction_approver", "leave_approver"}:
                assert not any(call.args[3] == "Payroll" for call in reports.call_args_list)
                assert not any(item["category"] in {"Payroll", "Finance"} for item in result["items"])
            if key != "device_admin":
                assert not any(item["category"] == "Devices" for item in result["items"])
        frappe.set_user(h.users["attendance_correction_approver"])
        queue = board._queue(company, (own,), "Attendance Request", "Attendance", "Review")
        assert queue[0]["count"] == 1
        assert queue[0]["filters"]["name"] == ["in", [requests[0]]]
        assert not board._queue(company, (outside, other_department, other_company), "Attendance Request", "Attendance", "Review")
        assert board._queue(company, (), "Attendance Request", "Attendance", "Review") == []
        # Real source execution, not just mocked persona routing. The source
        # reports and native integrity engine remain responsible for findings.
        for key in ("hr_manager", "branch_manager", "payroll_manager", "device_admin"):
            frappe.set_user(h.users[key])
            result = board.get_action_board(company, "2026-09-01")
            assert result["company"] == company
            assert all(item["company"] == company for item in result["items"])
            assert outside not in {item.get("employee") for item in result["items"]}
            assert all(not {"base", "net_pay", "bank_ac_no"} & set(item) for item in result["items"])
        frappe.set_user("Administrator")
        frappe.set_user(h.users["hr_manager"])
        with patch("tradex_hr.tradexcel_hr.joiner_readiness.inspect_joiner_readiness", new=lambda _employee: {"findings": ["synthetic"]}):
            people = board._people_items(company, "2020-01-31", (own, outside))
        assert [item["employee"] for item in people] == [own]
        assert people[0]["context"] == f"{h.employee_marker} in · {own}"
        assert people[0]["route"] == ["Form", "Employee", own]
        frappe.set_user("Administrator")
        with patch.object(frappe, "in_test", True):
            disabled = frappe.get_doc("User", h.users["hr_manager"])
            disabled.enabled = 0
            disabled.save(ignore_permissions=True)
        frappe.set_user(disabled.name)
        with pytest.raises(frappe.PermissionError):
            board.get_action_board(company)
        frappe.set_user("Administrator")
        assert all(frappe.db.get_value("Attendance Request", name, "docstatus") == 0 for name in requests)
        for doctype in ("Attendance", "Salary Structure Assignment", "Salary Slip", "Additional Salary"):
            assert not frappe.get_all(doctype, filters={"employee": ["in", h.employees]}, pluck="name")
    finally:
        frappe.set_user("Administrator")
        with patch.object(frappe, "in_test", True):
            for name in reversed(requests):
                if frappe.db.exists("Attendance Request", name):
                    frappe.delete_doc("Attendance Request", name, force=True, ignore_permissions=True)
            h.cleanup()
        assert not any(frappe.db.exists("Attendance Request", name) for name in requests)


def test_action_board_uses_standard_report_module_without_prepared_report_writes():
    from tradex_hr.tradexcel_hr import action_board as board
    from unittest.mock import Mock
    report = Mock(is_standard="Yes", report_type="Script Report")
    report.execute_module.return_value = ([], [{"problem": True}, {"problem": False}])
    with patch("frappe.desk.query_report.get_report_doc", return_value=report):
        items = board._report_items("Synthetic", "2026-09-01", "Synthetic report", "People", "Review",
                                    lambda row: row["problem"], "Review the native finding")
    assert items[0]["count"] == 1
    report.execute_script_report.assert_not_called()
    report.execute_module.assert_called_once()


def test_native_workspace_filters_action_block_by_role_and_has_no_overview_cards():
    import json
    from frappe.desk.desktop import get_desktop_page, get_workspaces
    from tradex_hr.tradexcel_hr.action_board import BOARD_ROLES

    frappe.set_user("Administrator")
    workspace = frappe.get_doc("Workspace", "tradexcel-hr")
    block = frappe.get_doc("Custom HTML Block", "Tradexcel Work Needing Attention")
    from pathlib import Path
    source = Path(__file__).resolve().parents[1] / "public" / "action_board"
    assert block.script == (source / "home.js").read_text()
    assert block.html == (source / "home.html").read_text()
    assert block.style == (source / "home.css").read_text()
    assert {row.role for row in block.roles} == set(BOARD_ROLES)
    assert not workspace.charts and len(workspace.number_cards) == 3
    assert len(workspace.quick_lists) == 4
    assert [row.custom_block_name for row in workspace.custom_blocks] == [block.name]
    h = SyntheticPersonaHarness("SOLBOARDWS" + frappe.generate_hash(8).upper())
    try:
        for key in ("hr_manager", "branch_manager", "device_admin", "worker"):
            user = h.create_user(key, [PERSONA_ROLES[key]], company="Tradexcel Ceramics Ltd.")
            frappe.set_user(user)
            page = next((row for row in get_workspaces()["pages"] if row["name"] == "tradexcel-hr"), None)
            if page is None:
                assert key == "worker", f"Expected operational Workspace for {key}"
                frappe.set_user("Administrator")
                continue
            payload = get_desktop_page(json.dumps(page))
            visible = [row.custom_block_name for row in payload["custom_blocks"]["items"]]
            assert (block.name in visible) == (key != "worker")
            frappe.set_user("Administrator")
    finally:
        h.cleanup()
