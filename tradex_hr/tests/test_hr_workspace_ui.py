"""Tests for native-first HR workspace layout, progressive disclosure, sidebar curation, and Tradexcel-only persona permissions."""
import json
from pathlib import Path

import frappe
import pytest

from tradex_hr.install import (
    COMMON_ACTION_SHORTCUTS,
    HOME_NUMBER_CARDS,
    HOME_QUICK_LISTS,
    WORKSPACE_SECTIONS,
    WORKSPACE_SHORTCUTS,
    BULK_WORKSPACE_SHORTCUTS,
    workspace_blocks,
    workspace_sidebar_items,
)
from tradex_hr.tests.persona_uat import PERSONA_ROLES, SyntheticPersonaHarness, assert_only_tradexcel_roles


@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(site="hrms-v16.localhost", sites_path="/home/sanchita/frappe-bench-v16/sites", force=True)
    frappe.connect()
    frappe.set_user("Administrator")
    yield
    frappe.set_user("Administrator")
    frappe.destroy()


def test_workspace_layout_and_progressive_disclosure():
    workspace = frappe.get_doc("Workspace", "tradexcel-hr")
    assert not workspace.charts, "Workspace must have 0 charts"
    assert len(workspace.number_cards) == 4, "Operational Snapshot must have exactly 4 Number Cards"

    expected_cards = [
        "Number of Employees on Leave (Today)",
        "Number of Employees on Leave (This Month)",
        "Holidays in this month",
        "Expense Claims (This Month)",
    ]
    actual_cards = [row.number_card_name for row in workspace.number_cards]
    assert actual_cards == expected_cards

    for card_name in expected_cards:
        assert frappe.db.exists("Number Card", card_name), f"Number Card {card_name} must exist in DB"

    assert len(workspace.quick_lists) == 4, "Pending Work must have exactly 4 Quick Lists"
    quick_lists_by_doctype = {row.document_type: json.loads(row.quick_list_filter) for row in workspace.quick_lists}
    assert quick_lists_by_doctype.get("Leave Application") == {"status": "Open"}
    assert quick_lists_by_doctype.get("Attendance Request") == {"docstatus": 0}
    assert quick_lists_by_doctype.get("Expense Claim") == {"docstatus": 0, "approval_status": "Draft"}
    assert quick_lists_by_doctype.get("Shift Request") == {"status": "Draft"}

    blocks = json.loads(workspace.content)
    block_types = [b["type"] for b in blocks]
    assert "chart" not in block_types, "No chart blocks allowed on home"

    shortcut_blocks = [b for b in blocks if b["type"] == "shortcut"]
    assert len(shortcut_blocks) <= 16, f"Expected <= 16 home shortcuts, got {len(shortcut_blocks)}"
    assert len(shortcut_blocks) == 12, f"Expected 12 common action shortcuts, got {len(shortcut_blocks)}"
    rendered_shortcut_names = [b["data"]["shortcut_name"] for b in shortcut_blocks]
    assert rendered_shortcut_names == COMMON_ACTION_SHORTCUTS

    custom_blocks = [b for b in blocks if b["type"] == "custom_block"]
    assert len(custom_blocks) == 1
    assert custom_blocks[0]["data"]["custom_block_name"] == "Tradexcel Work Needing Attention"


def test_curated_sidebar_sections_and_targets_exist():
    sidebar = frappe.get_doc("Workspace Sidebar", "Tradexcel HR")
    section_breaks = [item.label for item in sidebar.items if item.type == "Section Break"]
    expected_sections = [
        "Employees",
        "Attendance & Shifts",
        "Leave & Holidays",
        "Expenses & Travel",
        "Payroll",
        "Recruitment",
        "Development & Relations",
        "Separation",
        "Compliance",
        "Reports",
        "Setup",
        "Devices",
    ]
    assert section_breaks == expected_sections

    links = [item for item in sidebar.items if item.type == "Link"]
    for link in links:
        assert frappe.db.exists(link.link_type, link.link_to), f"Dead link in sidebar: {link.link_type} -> {link.link_to}"

    link_targets = {link.link_to for link in links}

    new_features = [
        "Expense Claim", "Employee Advance", "Travel Request",
        "Employee Advance Summary", "Unpaid Expense Claim", "Expense Claim Type", "Purpose of Travel",
        "Shift Request", "Shift Schedule Assignment", "Shift Location", "Overtime Type",
        "Monthly Attendance Sheet", "Shift Attendance", "Employees working on a holiday",
        "Compensatory Leave Request", "Leave Encashment", "Holiday List Assignment", "Leave Type", "Leave Block List",
        "Employee Incentive", "Retention Bonus", "Salary Withholding",
        "Staffing Plan", "Job Requisition", "Interview", "Interview Feedback",
        "Employee Referral", "Appointment Letter", "Interview Type", "Appointment Letter Template", "Recruitment Analytics",
        "Employee Grievance", "Training Program", "Training Event", "Appraisal", "Goal",
        "Employee Skill Map", "Training Feedback", "Training Result", "Appraisal Cycle", "Grievance Type", "Appraisal Template",
        "Employee Grade", "Employee Group", "HR Settings", "Payroll Settings",
    ]
    for feat in new_features:
        assert feat in link_targets, f"Feature {feat} missing from curated sidebar links"


def test_curated_navigation_does_not_promote_excluded_features():
    sidebar = frappe.get_doc("Workspace Sidebar", "Tradexcel HR")
    sidebar_targets = {item.link_to for item in sidebar.items if item.type == "Link"}

    workspace = frappe.get_doc("Workspace", "tradexcel-hr")
    workspace_targets = {s.link_to for s in workspace.shortcuts}

    excluded_items = {
        "Employee Attendance Tool",
        "Gratuity",
        "Employee Benefit Application",
        "Employee Benefit Claim",
        "Timesheet",
        "Sales Invoice",
    }
    for item in excluded_items:
        assert item not in sidebar_targets, f"Excluded item {item} must not be in sidebar"
        assert item not in workspace_targets, f"Excluded item {item} must not be in workspace shortcuts"


def test_tradexcel_only_personas_and_permission_enforcement():
    from frappe.desk.desktop import get_workspaces

    h = SyntheticPersonaHarness("UIUAT" + frappe.generate_hash(8).upper())
    try:
        # 1. Tradexcel HR Manager (strictly NO native HR Manager role)
        frappe.set_user("Administrator")
        hr_user = h.create_user("hr_manager", [PERSONA_ROLES["hr_manager"]], company="Tradexcel Ceramics Ltd.")
        assert_only_tradexcel_roles(hr_user)
        frappe.set_user(hr_user)

        # Approved administrative permissions
        assert frappe.has_permission("Expense Claim", "read")
        assert frappe.has_permission("Expense Claim", "create")
        assert frappe.has_permission("Expense Claim", "write")
        assert not frappe.has_permission("Expense Claim", "submit"), "Expense Claim submit must not be granted without Expense Approver"

        assert frappe.has_permission("Compensatory Leave Request", "read")
        assert frappe.has_permission("Compensatory Leave Request", "submit")
        assert frappe.has_permission("Holiday List Assignment", "read")
        assert frappe.has_permission("Holiday List Assignment", "submit")

        assert frappe.has_permission("Employee Grievance", "read")
        assert frappe.has_permission("Employee Grievance", "submit")
        assert frappe.has_permission("Training Program", "read")
        assert frappe.has_permission("Training Event", "read")
        assert frappe.has_permission("Training Event", "submit")
        assert frappe.has_permission("Training Feedback", "read")
        assert frappe.has_permission("Training Result", "read")
        assert frappe.has_permission("Training Result", "submit")

        assert frappe.has_permission("Appraisal", "read")
        assert frappe.has_permission("Appraisal", "submit")
        assert frappe.has_permission("Appraisal Cycle", "read")
        assert frappe.has_permission("Goal", "read")
        assert frappe.has_permission("Employee Skill Map", "read")

        assert frappe.has_permission("Job Requisition", "read")
        assert frappe.has_permission("Employee Referral", "read")
        assert frappe.has_permission("Employee Referral", "submit")
        assert frappe.has_permission("Appointment Letter", "read")

        # Explicitly DECISION_REQUIRED / UNGRANTED features
        assert not frappe.has_permission("Employee Advance", "read"), "Employee Advance must remain ungranted (DECISION_REQUIRED)"
        assert not frappe.has_permission("Travel Request", "read"), "Travel Request must remain ungranted (DECISION_REQUIRED)"

        # Explicitly PRESERVE_EXISTING_DENIAL features
        assert not frappe.has_permission("Shift Request", "read"), "Shift Request must remain denied (PRESERVE_EXISTING_DENIAL)"
        assert not frappe.has_permission("Shift Schedule Assignment", "read"), "Shift Schedule Assignment must remain denied"

        # Explicitly payroll-affecting extras (no submit authority)
        assert not frappe.has_permission("Employee Incentive", "submit"), "Employee Incentive submit must not bypass maker/checker"
        assert not frappe.has_permission("Retention Bonus", "submit"), "Retention Bonus submit must not bypass maker/checker"
        assert not frappe.has_permission("Salary Withholding", "submit"), "Salary Withholding submit must not bypass maker/checker"

        # 2. Branch Manager cannot read sensitive payroll
        frappe.set_user("Administrator")
        bm_user = h.create_user("branch_manager", [PERSONA_ROLES["branch_manager"]], company="Tradexcel Ceramics Ltd.")
        assert_only_tradexcel_roles(bm_user)
        frappe.set_user(bm_user)
        assert not frappe.has_permission("Salary Slip", "read")
        assert not frappe.has_permission("Salary Structure Assignment", "read")
        assert not frappe.has_permission("Payroll Entry", "read")

        # 3. Worker cannot see administrative Tradexcel HR workspace
        frappe.set_user("Administrator")
        worker_user = h.create_user("worker", [PERSONA_ROLES["worker"]], company="Tradexcel Ceramics Ltd.")
        assert_only_tradexcel_roles(worker_user)
        frappe.set_user(worker_user)
        visible_workspaces = [p.name for p in get_workspaces()["pages"]]
        assert "tradexcel-hr" not in visible_workspaces, "Worker must not have access to tradexcel-hr workspace"

        # 4. Attendance Officer has attendance & shift tool access but no payroll access
        frappe.set_user("Administrator")
        att_user = h.create_user("attendance_officer", [PERSONA_ROLES["attendance_officer"]], company="Tradexcel Ceramics Ltd.")
        assert_only_tradexcel_roles(att_user)
        frappe.set_user(att_user)
        assert frappe.has_permission("Attendance Request", "read")
        assert frappe.has_permission("Attendance", "read")
        assert not frappe.has_permission("Salary Slip", "read")
        assert not frappe.has_permission("Payroll Entry", "read")
        assert not frappe.has_permission("Expense Claim", "read")
        assert not frappe.has_permission("Shift Request", "read")
    finally:
        frappe.set_user("Administrator")
        h.cleanup()


def test_quick_list_native_permission_filtering():
    from frappe.desk.desktop import get_desktop_page, get_workspaces

    h = SyntheticPersonaHarness("QLTEST" + frappe.generate_hash(8).upper())
    try:
        # Attendance Officer should only see Leave and Attendance quick lists, NOT Expense or Shift quick lists
        frappe.set_user("Administrator")
        att_user = h.create_user("attendance_officer", [PERSONA_ROLES["attendance_officer"]], company="Tradexcel Ceramics Ltd.")
        assert_only_tradexcel_roles(att_user)
        frappe.set_user(att_user)

        page = next(p for p in get_workspaces()["pages"] if p["name"] == "tradexcel-hr")
        desktop_page = get_desktop_page(json.dumps(page))
        ql_labels = [q.label for q in desktop_page.get("quick_lists", {}).get("items", [])]
        assert "Open Leave Requests" in ql_labels
        assert "Attendance Requests to Review" in ql_labels
        assert "Expense Claims to Review" not in ql_labels, "Attendance Officer must not see Expense Claims Quick List"
        assert "Shift Requests to Review" not in ql_labels, "Attendance Officer must not see Shift Requests Quick List"

        # HR Manager sees Leave, Attendance, and Expense quick lists, but NOT Shift quick list (denied)
        frappe.set_user("Administrator")
        hr_user = h.create_user("hr_manager", [PERSONA_ROLES["hr_manager"]], company="Tradexcel Ceramics Ltd.")
        assert_only_tradexcel_roles(hr_user)
        frappe.set_user(hr_user)

        desktop_page = get_desktop_page(json.dumps(page))
        hr_ql_labels = [q.label for q in desktop_page.get("quick_lists", {}).get("items", [])]
        assert "Open Leave Requests" in hr_ql_labels
        assert "Attendance Requests to Review" in hr_ql_labels
        assert "Expense Claims to Review" in hr_ql_labels
        assert "Shift Requests to Review" not in hr_ql_labels, "HR Manager must not see Shift Requests Quick List (denied)"
    finally:
        frappe.set_user("Administrator")
        h.cleanup()


def test_record_scope_user_permission_isolation():
    from tradex_hr.tests.persona_uat import SyntheticPersonaHarness, PERSONA_ROLES, assert_only_tradexcel_roles

    h = SyntheticPersonaHarness("SCOPETEST" + frappe.generate_hash(8).upper())
    try:
        frappe.set_user("Administrator")
        # Create scoped HR Manager for Branch A
        hr_user_a = h.create_user(
            "hr_manager",
            [PERSONA_ROLES["hr_manager"]],
            company="Tradexcel Ceramics Ltd.",
            branch="Tradexcel Headquarters",
        )
        assert_only_tradexcel_roles(hr_user_a)

        # Scoped user list query on Employee must only return employees within scope
        frappe.set_user(hr_user_a)
        scoped_employees = frappe.get_list("Employee", fields=["name", "company", "branch"], limit=10)
        for emp in scoped_employees:
            assert emp["company"] == "Tradexcel Ceramics Ltd."
            if emp.get("branch"):
                assert emp["branch"] == "Tradexcel Headquarters"

        # Cross-company attempt: user should not be able to read records from unpermitted company
        unauthorized = frappe.get_list("Employee", filters={"company": ["!=", "Tradexcel Ceramics Ltd."]}, limit=5)
        assert len(unauthorized) == 0, "Scoped user must not see cross-company records"
    finally:
        frappe.set_user("Administrator")
        h.cleanup()
