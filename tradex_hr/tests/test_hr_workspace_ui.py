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
    assert len(workspace.number_cards) == 3, "Operational Snapshot must have exactly 3 Number Cards"

    expected_cards = [
        "Number of Employees on Leave (Today)",
        "Number of Employees on Leave (This Month)",
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

        nc_labels = [c.label for c in desktop_page.get("number_cards", {}).get("items", [])]
        assert nc_labels == [
            "Number of Employees on Leave (Today)",
            "Number of Employees on Leave (This Month)",
        ]
        assert "Expense Claims (This Month)" not in nc_labels, "Attendance Officer must not see Expense Claims Number Card"
        assert "Holidays in this month" not in nc_labels, "Dead Holiday card removed from Home layout"

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

        hr_nc_labels = [c.label for c in desktop_page.get("number_cards", {}).get("items", [])]
        assert hr_nc_labels == [
            "Number of Employees on Leave (Today)",
            "Number of Employees on Leave (This Month)",
            "Expense Claims (This Month)",
        ]
        assert "Holidays in this month" not in hr_nc_labels, "Dead Holiday card removed from Home layout"
    finally:
        frappe.set_user("Administrator")
        h.cleanup()


PERSONA_WORKSPACE_TEST_CASES = [
    (
        "hr_manager",
        PERSONA_ROLES["hr_manager"],
        [
            "Number of Employees on Leave (Today)",
            "Number of Employees on Leave (This Month)",
            "Expense Claims (This Month)",
        ],
        [
            "Open Leave Requests",
            "Attendance Requests to Review",
            "Expense Claims to Review",
        ],
        [
            "Employee Directory",
            "Today's Attendance",
            "Attendance Summary",
            "Attendance Fix Requests",
            "Mobile Attendance",
            "Leave Requests",
            "Expense Claims",
            "Salary Setup Coverage",
            "Job Applicants",
            "Field Duties",
            "Final Settlements",
        ],
    ),
    (
        "attendance_officer",
        PERSONA_ROLES["attendance_officer"],
        [
            "Number of Employees on Leave (Today)",
            "Number of Employees on Leave (This Month)",
        ],
        [
            "Open Leave Requests",
            "Attendance Requests to Review",
        ],
        [
            "Employee Directory",
            "Today's Attendance",
            "Attendance Summary",
            "Attendance Fix Requests",
            "Mobile Attendance",
            "Leave Requests",
            "Field Duties",
        ],
    ),
    (
        "payroll_manager",
        PERSONA_ROLES["payroll_manager"],
        [],
        [],
        [
            "Employee Directory",
            "Run Monthly Payroll",
            "Salary Setup Coverage",
            "Final Settlements",
        ],
    ),
    (
        "finance",
        PERSONA_ROLES["finance"],
        [],
        [],
        [
            "Employee Directory",
            "Salary Setup Coverage",
            "Final Settlements",
        ],
    ),
    (
        "branch_manager",
        PERSONA_ROLES["branch_manager"],
        [
            "Number of Employees on Leave (Today)",
            "Number of Employees on Leave (This Month)",
        ],
        [
            "Open Leave Requests",
            "Attendance Requests to Review",
        ],
        [
            "Employee Directory",
            "Today's Attendance",
            "Attendance Fix Requests",
            "Mobile Attendance",
            "Leave Requests",
            "Field Duties",
        ],
    ),
]


@pytest.mark.parametrize(
    "persona_key,role_name,expected_cards,expected_quick_lists,expected_common_actions",
    PERSONA_WORKSPACE_TEST_CASES,
)
def test_tradexcel_persona_workspace_and_shortcut_authorization(
    persona_key, role_name, expected_cards, expected_quick_lists, expected_common_actions
):
    from frappe.desk.desktop import get_desktop_page, get_workspaces, DeskViews

    shortcut_map = {row[0]: (row[1], row[2]) for row in list(WORKSPACE_SHORTCUTS) + list(BULK_WORKSPACE_SHORTCUTS)}

    h = SyntheticPersonaHarness("PWSTEST" + frappe.generate_hash(8).upper())
    try:
        frappe.set_user("Administrator")
        user = h.create_user(persona_key, [role_name], company="Tradexcel Ceramics Ltd.")
        assert_only_tradexcel_roles(user)
        frappe.set_user(user)

        ws_list = [p for p in get_workspaces()["pages"] if p["name"] == "tradexcel-hr"]
        assert len(ws_list) == 1, f"Persona {role_name} must have access to tradexcel-hr workspace"
        page = ws_list[0]
        desktop_page = get_desktop_page(json.dumps(page))

        actual_cards = [c.label for c in desktop_page.get("number_cards", {}).get("items", [])]
        actual_quick_lists = [q.label for q in desktop_page.get("quick_lists", {}).get("items", [])]
        sc_allowed = {s.label for s in desktop_page.get("shortcuts", {}).get("items", [])}
        actual_common_actions = [ca for ca in COMMON_ACTION_SHORTCUTS if ca in sc_allowed]

        assert actual_cards == expected_cards, f"{role_name} Number Cards mismatch: {actual_cards} != {expected_cards}"
        assert actual_quick_lists == expected_quick_lists, f"{role_name} Quick Lists mismatch: {actual_quick_lists} != {expected_quick_lists}"
        assert actual_common_actions == expected_common_actions, f"{role_name} Common Actions mismatch: {actual_common_actions} != {expected_common_actions}"

        allowed_pages = DeskViews.get_allowed_pages()
        allowed_reports = DeskViews.get_allowed_reports()

        for label in actual_common_actions:
            target, link_type = shortcut_map[label]
            if link_type == "DocType":
                assert frappe.has_permission(target, "read"), f"{role_name} lacks read on DocType {target} for shortcut {label}"
            elif link_type == "Report":
                assert target in allowed_reports, f"{role_name} lacks access to Report {target} for shortcut {label}"
            elif link_type == "Page":
                assert target in allowed_pages, f"{role_name} lacks access to Page {target} for shortcut {label}"
    finally:
        frappe.set_user("Administrator")
        h.cleanup()


def test_expense_claim_maker_checker_boundary():
    from tradex_hr.role_setup import STANDARD_PERMISSION_MATRIX

    h = SyntheticPersonaHarness("EXPTEST" + frappe.generate_hash(8).upper())
    try:
        frappe.set_user("Administrator")
        hr_user = h.create_user("hr_manager", [PERSONA_ROLES["hr_manager"]], company="Tradexcel Ceramics Ltd.")
        assert_only_tradexcel_roles(hr_user)
        frappe.set_user(hr_user)

        # Maker rights: read, write, create
        assert frappe.has_permission("Expense Claim", "read")
        assert frappe.has_permission("Expense Claim", "write")
        assert frappe.has_permission("Expense Claim", "create")

        # Explicitly NO submit, cancel, or delete
        assert not frappe.has_permission("Expense Claim", "submit"), "HR Manager must not have submit on Expense Claim"
        assert not frappe.has_permission("Expense Claim", "cancel"), "HR Manager must not have cancel on Expense Claim"
        assert not frappe.has_permission("Expense Claim", "delete"), "HR Manager must not have delete on Expense Claim"

        # Checker rights unresolved: no Tradexcel role holds submit on Expense Claim
        ec_matrix = STANDARD_PERMISSION_MATRIX.get("Expense Claim", {})
        for role, perms in ec_matrix.items():
            assert "submit" not in perms, f"Role {role} must not have submit on Expense Claim"
            assert "cancel" not in perms, f"Role {role} must not have cancel on Expense Claim"
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


def test_new_native_features_scope_and_record_isolation():
    from tradex_hr.tests.persona_uat import SyntheticPersonaHarness, PERSONA_ROLES, assert_only_tradexcel_roles

    h = SyntheticPersonaHarness("FTSCOPE" + frappe.generate_hash(8).upper())
    ec_a = ec_b = app_a = app_b = g_a = g_b = clr_a = clr_b = None
    sect = ac_name = gt = None

    try:
        frappe.set_user("Administrator")
        comp_a = "Tradexcel Ceramics Ltd."
        comp_b = "Elegance Footwear Ltd."

        emp_a_data = frappe.db.get_value("Employee", {"company": comp_a, "status": "Active"}, ["name", "department"], as_dict=True)
        emp_b_data = frappe.db.get_value("Employee", {"company": comp_b, "status": "Active"}, ["name", "department"], as_dict=True)
        assert emp_a_data and emp_b_data, "Both active test employees must exist"
        emp_a = emp_a_data.name
        emp_b = emp_b_data.name
        dept_a = emp_a_data.department
        dept_b = emp_b_data.department

        # Setup synthetic types
        sect = f"SynthECT_{h.token}"
        frappe.get_doc({
            "doctype": "Expense Claim Type",
            "expense_type": sect,
            "accounts": [
                {"company": comp_a, "default_account": "Cash - TCL"},
                {"company": comp_b, "default_account": "Cash - EFL"},
            ],
        }).insert(ignore_permissions=True)

        ac_name = f"SynthAC_{h.token}"
        frappe.get_doc({
            "doctype": "Appraisal Cycle",
            "cycle_name": ac_name,
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
        }).insert(ignore_permissions=True)

        gt = f"SynthGT_{h.token}"
        frappe.get_doc({"doctype": "Grievance Type", "name": gt}).insert(ignore_permissions=True)

        # 1. Expense Claim
        ec_a = frappe.get_doc({
            "doctype": "Expense Claim",
            "employee": emp_a,
            "company": comp_a,
            "expenses": [{"expense_type": sect, "amount": 100, "expense_date": "2026-04-24"}],
        }).insert(ignore_permissions=True)
        ec_b = frappe.get_doc({
            "doctype": "Expense Claim",
            "employee": emp_b,
            "company": comp_b,
            "expenses": [{"expense_type": sect, "amount": 100, "expense_date": "2026-04-24"}],
        }).insert(ignore_permissions=True)

        # 2. Appraisal
        app_a = frappe.get_doc({
            "doctype": "Appraisal",
            "employee": emp_a,
            "company": comp_a,
            "appraisal_cycle": ac_name,
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
        }).insert(ignore_permissions=True)
        app_b = frappe.get_doc({
            "doctype": "Appraisal",
            "employee": emp_b,
            "company": comp_b,
            "appraisal_cycle": ac_name,
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
        }).insert(ignore_permissions=True)

        # 3. Employee Grievance
        g_a = frappe.get_doc({
            "doctype": "Employee Grievance",
            "subject": f"Grievance A {h.token}",
            "raised_by": emp_a,
            "date": frappe.utils.today(),
            "status": "Open",
            "grievance_against_party": "Employee",
            "grievance_against": emp_a,
            "grievance_type": gt,
            "description": "Desc A",
        }).insert(ignore_permissions=True)
        g_b = frappe.get_doc({
            "doctype": "Employee Grievance",
            "subject": f"Grievance B {h.token}",
            "raised_by": emp_b,
            "date": frappe.utils.today(),
            "status": "Open",
            "grievance_against_party": "Employee",
            "grievance_against": emp_b,
            "grievance_type": gt,
            "description": "Desc B",
        }).insert(ignore_permissions=True)

        # 4. Compensatory Leave Request
        clr_a = frappe.get_doc({
            "doctype": "Compensatory Leave Request",
            "employee": emp_a,
            "department": dept_a,
            "work_from_date": "2026-04-24",
            "work_end_date": "2026-04-24",
            "reason": "Reason A",
        })
        clr_a.flags.ignore_validate = True
        clr_a.insert(ignore_permissions=True)

        clr_b = frappe.get_doc({
            "doctype": "Compensatory Leave Request",
            "employee": emp_b,
            "department": dept_b,
            "work_from_date": "2026-04-24",
            "work_end_date": "2026-04-24",
            "reason": "Reason B",
        })
        clr_b.flags.ignore_validate = True
        clr_b.insert(ignore_permissions=True)

        # Persona 1: Company A scoped HR Manager
        hr_comp_a = h.create_user("hr_comp_a", [PERSONA_ROLES["hr_manager"]], company=comp_a)
        assert_only_tradexcel_roles(hr_comp_a)
        frappe.set_user(hr_comp_a)

        # Expense Claim: Company scope
        ecs = frappe.get_list("Expense Claim", pluck="name")
        assert ec_a.name in ecs, "ec_a must be in visible Expense Claims for Company A user"
        assert ec_b.name not in ecs, "ec_b must NOT be in visible Expense Claims for Company A user"
        assert frappe.has_permission("Expense Claim", doc=ec_a)
        assert not frappe.has_permission("Expense Claim", doc=ec_b)
        with pytest.raises(frappe.PermissionError):
            frappe.has_permission("Expense Claim", "read", doc=ec_b, throw=True)

        # Appraisal: Company scope
        apps = frappe.get_list("Appraisal", pluck="name")
        assert app_a.name in apps, "app_a must be in visible Appraisals for Company A user"
        assert app_b.name not in apps, "app_b must NOT be in visible Appraisals for Company A user"
        assert frappe.has_permission("Appraisal", doc=app_a)
        assert not frappe.has_permission("Appraisal", doc=app_b)
        with pytest.raises(frappe.PermissionError):
            frappe.has_permission("Appraisal", "read", doc=app_b, throw=True)

        # Persona 2: Department and Employee scoped HR Manager
        frappe.set_user("Administrator")
        hr_dept_emp = h.create_user("hr_dept_emp", [PERSONA_ROLES["hr_manager"]], company=comp_a)
        assert_only_tradexcel_roles(hr_dept_emp)
        frappe.get_doc({
            "doctype": "User Permission",
            "user": hr_dept_emp,
            "allow": "Department",
            "for_value": dept_a,
        }).insert(ignore_permissions=True)
        frappe.get_doc({
            "doctype": "User Permission",
            "user": hr_dept_emp,
            "allow": "Employee",
            "for_value": emp_a,
        }).insert(ignore_permissions=True)

        frappe.set_user(hr_dept_emp)

        # Employee Grievance: Employee scope (via raised_by/employee_responsible)
        grievs = frappe.get_list("Employee Grievance", pluck="name")
        assert g_a.name in grievs, "g_a must be visible to Employee A user"
        assert g_b.name not in grievs, "g_b must NOT be visible to Employee A user"
        assert frappe.has_permission("Employee Grievance", doc=g_a)
        assert not frappe.has_permission("Employee Grievance", doc=g_b)
        with pytest.raises(frappe.PermissionError):
            frappe.has_permission("Employee Grievance", "read", doc=g_b, throw=True)

        # Compensatory Leave Request: Department and Employee scope
        clrs = frappe.get_list("Compensatory Leave Request", pluck="name")
        assert clr_a.name in clrs, "clr_a must be visible to Dept A/Emp A user"
        assert clr_b.name not in clrs, "clr_b must NOT be visible to Dept A/Emp A user"
        assert frappe.has_permission("Compensatory Leave Request", doc=clr_a)
        assert not frappe.has_permission("Compensatory Leave Request", doc=clr_b)
        with pytest.raises(frappe.PermissionError):
            frappe.has_permission("Compensatory Leave Request", "read", doc=clr_b, throw=True)

    finally:
        frappe.set_user("Administrator")
        for dt, dn in [
            ("Expense Claim", ec_a.name if ec_a else None),
            ("Expense Claim", ec_b.name if ec_b else None),
            ("Appraisal", app_a.name if app_a else None),
            ("Appraisal", app_b.name if app_b else None),
            ("Employee Grievance", g_a.name if g_a else None),
            ("Employee Grievance", g_b.name if g_b else None),
            ("Compensatory Leave Request", clr_a.name if clr_a else None),
            ("Compensatory Leave Request", clr_b.name if clr_b else None),
            ("Expense Claim Type", sect),
            ("Appraisal Cycle", ac_name),
            ("Grievance Type", gt),
        ]:
            if dn and frappe.db.exists(dt, dn):
                frappe.delete_doc(dt, dn, force=True)
        frappe.db.commit()
        h.cleanup()
