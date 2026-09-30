"""TXUX-260930-011: Native Sidebar source ownership and usability tests.

Verifies:
1. Frappe v16 lack of automatic app-level workspace_sidebar JSON sync in core migration,
   establishing why installer-owned metadata (standard=0) is the authoritative, safe mechanism.
2. Idempotency and correctness of ensure_workspace_sidebar across installs and upgrades.
3. Preservation of user-customized personal sidebars (for_user is not touched).
4. Desktop Icon native link_type = "Workspace Sidebar" matching label "Tradexcel HR".
5. Native SCSS origin of the collapsed sidebar scrollbar defect (recording selectors for TXUX-012).
"""
import json
import os
from pathlib import Path
import pytest

import frappe
from tradex_hr import install


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


def test_frappe_v16_workspace_sidebar_sync_architecture():
    """Verify that Frappe v16 does not automatically sync app-level workspace_sidebar/*.json during migrate.
    
    While WorkspaceSidebar has export_sidebar() in developer mode, Frappe's import_file and migrate
    modules do not have an automated discovery or sync handler for <app>/workspace_sidebar/*.json.
    Therefore, the source-owned installer mechanism (ensure_workspace_sidebar) with standard=0 is
    the only reliable, reproducible mechanism across fresh installs and upgrades without competing writers.
    """
    import frappe.modules.import_file as import_file_mod

    # Frappe standard module sync inspects doctypes in standard modules; workspace_sidebar is not one
    assert "Workspace Sidebar" not in import_file_mod.ignore_values
    app_root = Path(frappe.get_app_path("frappe"))
    migrate_py = (app_root / "migrate.py").read_text()
    assert "workspace_sidebar" not in migrate_py


def test_installer_sidebar_ownership_is_idempotent():
    """ensure_workspace_sidebar must run idempotently, establish correct app ownership, and maintain sections."""
    shortcuts = list(install.WORKSPACE_SHORTCUTS)

    # First run
    install.ensure_workspace_sidebar(shortcuts)
    sidebar = frappe.get_doc("Workspace Sidebar", "Tradexcel HR")
    assert sidebar.title == "Tradexcel HR"
    assert sidebar.app == "tradex_hr"
    assert sidebar.module == "Tradexcel HR"
    assert sidebar.standard == 0
    assert sidebar.for_user is None
    assert len(sidebar.items) > 0

    first_items = [(item.label, item.type, item.link_to) for item in sidebar.items]

    # Repeated synchronization (idempotency check)
    install.ensure_workspace_sidebar(shortcuts)
    sidebar_after = frappe.get_doc("Workspace Sidebar", "Tradexcel HR")
    second_items = [(item.label, item.type, item.link_to) for item in sidebar_after.items]

    assert first_items == second_items


def test_installer_sidebar_preserves_personal_user_sidebars():
    """Custom personal sidebars (with for_user set) must never be overwritten or deleted by installer."""
    # Use existing Administrator user for personal sidebar test
    user = "Administrator"
    personal_title = f"Tradexcel HR-{user}"
    
    # Simulate a user-edited personal sidebar
    if not frappe.db.exists("Workspace Sidebar", personal_title):
        personal_doc = frappe.get_doc({
            "doctype": "Workspace Sidebar",
            "title": personal_title,
            "for_user": user,
            "header_icon": "user",
            "items": [{"label": "My Personal Shortcut", "type": "Link", "link_type": "Workspace", "link_to": "tradexcel-hr"}],
        }).insert(ignore_permissions=True)
    else:
        personal_doc = frappe.get_doc("Workspace Sidebar", personal_title)

    try:
        shortcuts = list(install.WORKSPACE_SHORTCUTS)
        
        # Run installer synchronization
        install.ensure_workspace_sidebar(shortcuts)

        # Verify personal sidebar survived untouched
        reloaded = frappe.get_doc("Workspace Sidebar", personal_title)
        assert reloaded.for_user == user
        assert reloaded.items[0].label == "My Personal Shortcut"
    finally:
        frappe.delete_doc("Workspace Sidebar", personal_title, force=True, ignore_permissions=True)


def test_desktop_icon_routes_to_sidebar():
    """Tradexcel HR Desktop Icon must route to the native Workspace Sidebar."""
    app_root = Path(frappe.get_app_path("tradex_hr")).parent
    icon_path = app_root / "tradex_hr/desktop_icon/tradexcel_hr.json"
    assert icon_path.exists()
    
    with open(icon_path) as f:
        data = json.load(f)
    
    assert data.get("link_type") == "Workspace Sidebar"
    assert data.get("label") == "Tradexcel HR"
    assert data.get("standard") == 1


def test_collapsed_sidebar_defect_origin():
    """Audit the collapsed sidebar scrollbar obscuring defect:
    Frappe's native desk SCSS sets width: 50px on .body-sidebar when collapsed,
    and overflow-y: auto on .body-sidebar-top, generating a vertical scrollbar in 50px.
    """
    frappe_app_root = Path(frappe.get_app_path("frappe"))
    sidebar_scss = (frappe_app_root / "public/scss/desk/sidebar.scss").read_text()

    assert ".body-sidebar" in sidebar_scss
    assert "width: 50px;" in sidebar_scss
    assert "overflow-y: auto;" in sidebar_scss

    # Confirm that tradex_hr has no custom .body-sidebar CSS overriding this
    tradex_css_path = Path(frappe.get_app_path("tradex_hr")).parent / "tradex_hr/public/css/tradex_hr.bundle.css"
    tradex_css = tradex_css_path.read_text() if tradex_css_path.exists() else ""
    assert ".body-sidebar-top" not in tradex_css
