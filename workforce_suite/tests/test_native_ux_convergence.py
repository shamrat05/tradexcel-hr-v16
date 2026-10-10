"""Native navigation and administration contracts; synthetic disposable site only."""
import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import frappe
import pytest

from workforce_suite import install
from workforce_suite.tests.persona_uat import SyntheticPersonaHarness


@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(site=os.environ["FRAPPE_TEST_SITE"], sites_path=os.environ["FRAPPE_TEST_SITES_PATH"], force=True)
    frappe.connect()
    assert frappe.conf.workforce_rehearsal, "Disposable rehearsal site required"
    frappe.set_user("Administrator")
    yield
    frappe.set_user("Administrator")
    frappe.destroy()


def test_all_catalog_routes_have_one_discoverable_home_and_exist():
    shortcuts = list(install.WORKSPACE_SHORTCUTS) + list(install.BULK_WORKSPACE_SHORTCUTS)
    labels = [label for _, _, section in install.WORKSPACE_SECTIONS for label in section]
    assert len(labels) == len(set(labels))
    assert set(labels) == {row[0] for row in shortcuts}
    for label, target, kind in shortcuts:
        assert frappe.db.exists(kind, target), (label, target)
    sections = dict((title, set(labels)) for title, _, labels in install.WORKSPACE_SECTIONS)
    assert "Today's Attendance" in sections["Attendance"]
    assert "Shift Assignments" in sections["Shift Planning"]
    assert "Payroll Register" in sections["Payroll"]
    assert "Salary Components" in sections["Payroll Setup"]
    assert "Site Announcements" in sections["Administration"]
    assert len(install.COMMON_ACTION_SHORTCUTS) == 8
    actual = frappe.get_doc("Workspace Sidebar", "Workforce Suite")
    assert [i.label for i in actual.items if i.type == "Section Break"] == list(sections)


def test_native_multiple_roles_scope_and_no_self_escalation():
    h = SyntheticPersonaHarness("UX78" + frappe.generate_hash(8).upper())
    try:
        manager = h.create_user("system", ["System Manager"])
        operator = h.create_user("operator", ["Workforce Suite/Attendance Officer"], company="Example Company A")
        frappe.set_user(manager)
        doc = frappe.get_doc("User", operator)
        doc.append_roles("Workforce Payroll Manager")
        with patch.object(frappe, "in_test", True):
            doc.save()  # Native permission check; no ignore_permissions.
        frappe.set_user(operator)
        assert {"Workforce Suite/Attendance Officer", "Workforce Payroll Manager"} <= set(frappe.get_roles())
        assert frappe.has_permission("Attendance", "read")
        assert frappe.has_permission("Salary Slip", "read")
        assert not frappe.has_permission("Navbar Settings", "write")
        from workforce_suite.workforce_suite.company_context import assert_company_access
        assert_company_access("Example Company A", require_explicit_scope=True)
        with pytest.raises(frappe.PermissionError):
            assert_company_access("Example Company B", require_explicit_scope=True)
        # An operator cannot edit someone else's roles or gain System Manager.
        other = frappe.get_doc("User", manager)
        other.append_roles("Workforce Owner/Director")
        with pytest.raises(frappe.PermissionError):
            other.save()
        own = frappe.get_doc("User", operator)
        own.append_roles("System Manager")
        try:
            with patch.object(frappe, "in_test", True):
                own.save()
        except frappe.PermissionError:
            pass  # Native write denial is also a valid protection.
        frappe.clear_cache(user=operator)
        assert "System Manager" not in frappe.get_roles(operator)
        assert "Workforce Owner/Director" not in frappe.get_roles(manager)
    finally:
        frappe.set_user("Administrator")
        with patch.object(frappe, "in_test", True):
            h.cleanup()


def test_native_announcement_publish_update_remove_and_restricted_write():
    h = SyntheticPersonaHarness("UX78NOTICE" + frappe.generate_hash(8).upper())
    original = frappe.db.get_single_value("Navbar Settings", "announcement_widget")
    try:
        manager = h.create_user("system", ["System Manager"])
        operator = h.create_user("hr", ["Workforce Suite Manager"])
        frappe.set_user(manager)
        for content in ("<p>TEST UX78 notice one</p>", "<p>TEST UX78 notice two</p>", ""):
            doc = frappe.get_doc("Navbar Settings")
            doc.announcement_widget = content
            doc.save()
            assert frappe.get_doc("Navbar Settings").announcement_widget == content
        frappe.set_user(operator)
        doc.announcement_widget = "Not permitted"
        with pytest.raises(frappe.PermissionError):
            doc.save()
        assert frappe.db.get_single_value("Navbar Settings", "announcement_widget") != "Not permitted"
        assert "across all companies" in install.ANNOUNCEMENT_GUIDANCE
        assert "not a read receipt" in install.ANNOUNCEMENT_GUIDANCE
    finally:
        frappe.set_user("Administrator")
        doc = frappe.get_doc("Navbar Settings")
        doc.announcement_widget = original
        doc.save()
        with patch.object(frappe, "in_test", True):
            h.cleanup()


def test_native_administration_visibility_does_not_grant_roles():
    from frappe.boot import get_sidebar_items
    from frappe.desk.desktop import get_workspaces
    h = SyntheticPersonaHarness("UX78SCOPE" + frappe.generate_hash(8).upper())
    try:
        for key, roles in (("system", ["System Manager"]), ("hr", ["Workforce Suite Manager"]),
                           ("payroll", ["Workforce Payroll Manager"]), ("worker", ["Workforce Employee/Worker"])):
            user = h.create_user(key, roles, company="Example Company A")
            frappe.set_user(user)
            frappe.clear_cache(user=user)
            payload = get_sidebar_items(get_workspaces())
            items = payload.get("workforce suite", {}).get("items", [])
            # Native boot may represent the items as nested or flat; recursively collect targets.
            def targets(rows):
                result = set()
                for row in rows:
                    if row.get("link_to"): result.add(row["link_to"])
                    result.update(targets(row.get("nested_items", [])))
                return result
            shown = targets(items)
            from workforce_suite.navigation import extend_bootinfo
            boot = {"workspace_sidebar_item": payload}
            extend_bootinfo(boot)
            assert targets(boot["workspace_sidebar_item"].get("workforce suite", {}).get("items", [])) == shown
            if key == "system":
                assert "Navbar Settings" in shown
            else:
                assert "Navbar Settings" not in shown
                assert not frappe.has_permission("Navbar Settings", "write")
            frappe.set_user("Administrator")
    finally:
        frappe.set_user("Administrator")
        with patch.object(frappe, "in_test", True):
            h.cleanup()


def test_report_action_lifecycle_and_all_existing_action_contracts():
    root = Path(__file__).resolve().parents[2]
    node = shutil.which("node")
    assert node, "Node is required for the client regression checks"
    for script in ("check_native_action_layout.cjs", "check_report_action_lifecycle.cjs", "check_native_announcements.cjs"):
        subprocess.run([node, str(root / "scripts" / script)], check=True, capture_output=True, text=True)


def test_generated_slug_duplicate_omitted_without_record_or_permission_mutation():
    from workforce_suite.navigation import extend_bootinfo
    from frappe.boot import get_sidebar_items
    from frappe.desk.desktop import get_workspaces
    import copy
    frappe.set_user("Administrator")
    generated = frappe.get_doc("Workspace Sidebar", "workforce-suite")
    before = generated.as_dict()
    boot = {"workspace_sidebar_item": get_sidebar_items(get_workspaces())}
    managed = copy.deepcopy(boot["workspace_sidebar_item"]["workforce suite"])
    extend_bootinfo(boot)
    assert "workforce-suite" not in boot["workspace_sidebar_item"]
    assert boot["workspace_sidebar_item"]["workforce suite"] == managed
    assert frappe.get_doc("Workspace Sidebar", "workforce-suite").as_dict() == before
    # Unknown public customization is retained; no migration/overwrite shortcut.
    customized = frappe.get_doc(before)
    customized.append("items", {"type": "Link", "label": "Administrator choice", "link_type": "DocType", "link_to": "User"})
    original = {"workforce-suite": {"items": ["untouched"]}, "workforce suite": managed}
    boot = {"workspace_sidebar_item": copy.deepcopy(original)}
    with patch.object(frappe, "get_cached_doc", return_value=customized):
        extend_bootinfo(boot)
    assert boot["workspace_sidebar_item"] == original
    # Personal slug Sidebar wins; preserve its native session representation.
    exists = frappe.db.exists
    with patch.object(frappe.db, "exists", side_effect=lambda dt, name: True if name == "workforce-suite-Administrator" else exists(dt, name)):
        extend_bootinfo(boot)
    assert boot["workspace_sidebar_item"] == original
    # No curated/authorized Sidebar means no intervention.
    boot = {"workspace_sidebar_item": {"workforce-suite": {"items": []}}}
    extend_bootinfo(boot)
    assert "workforce-suite" in boot["workspace_sidebar_item"]
