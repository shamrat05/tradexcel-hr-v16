"""Let native Desk resolve Home to its curated, permission-filtered Sidebar.

Frappe auto-generates a second, flat Sidebar named after our slug Workspace.
Its exact-route precedence otherwise hides the curated Sidebar on direct Home
navigation. Omit only that recognized generated duplicate from this session's
boot payload. Never write/delete Sidebar records or replace Frappe routing.
"""
import frappe


def extend_bootinfo(bootinfo):
    sidebars = bootinfo.get("workspace_sidebar_item", {})
    if "workforce suite" not in sidebars or "workforce-suite" not in sidebars:
        return
    # A personal slug Sidebar is an intentional user choice, not our duplicate.
    if frappe.db.exists("Workspace Sidebar", f"workforce-suite-{frappe.session.user}"):
        return
    if not frappe.db.exists("Workspace Sidebar", "workforce-suite"):
        return
    generated = frappe.get_cached_doc("Workspace Sidebar", "workforce-suite")
    if generated.for_user or generated.app or generated.standard or generated.module_onboarding:
        return
    from workforce_suite.install import WORKSPACE_SHORTCUTS, BULK_WORKSPACE_SHORTCUTS

    shortcuts = list(WORKSPACE_SHORTCUTS) + [
        row for row in BULK_WORKSPACE_SHORTCUTS if frappe.db.exists("DocType", row[1])
    ]
    # Recognize the pre-administration catalog as well as the current catalog.
    # Unknown public edits, reordered items, filters and personal records survive.
    admin_labels = {"Users & Roles", "Role Profiles", "User Permissions", "Site Announcements"}
    expected = [("Home", "workforce-suite", "Workspace")] + shortcuts
    previous = [row for row in expected if row[0] not in admin_labels]
    actual = [(row.label, row.link_to, row.link_type) for row in generated.items]
    if actual not in (expected, previous):
        return
    if any(row.type != "Link" or row.child or row.filters or row.route_options or row.url
           for row in generated.items):
        return
    # All data left in boot was already filtered by Frappe for this user. We do
    # not inject links or copy administrator permissions into another session.
    sidebars.pop("workforce-suite")
