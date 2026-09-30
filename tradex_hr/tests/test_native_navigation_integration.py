"""Installed native sidebar filtering, not a client-side role imitation."""
import json
from pathlib import Path

import frappe
import pytest

from tradex_hr.tests.persona_uat import PERSONA_ROLES, SyntheticPersonaHarness


@pytest.fixture(scope='module', autouse=True)
def site():
    frappe.init(site='hrms-v16.localhost', sites_path='/home/sanchita/frappe-bench-v16/sites', force=True)
    frappe.connect()
    frappe.set_user('Administrator')
    yield
    frappe.set_user('Administrator')
    frappe.destroy()


def test_installed_sidebar_and_source_workspace_targets_exist():
    from tradex_hr.install import WORKSPACE_SHORTCUTS, BULK_WORKSPACE_SHORTCUTS, workspace_sidebar_items, workspace_blocks
    expected = workspace_sidebar_items(WORKSPACE_SHORTCUTS + BULK_WORKSPACE_SHORTCUTS)
    doc = frappe.get_doc('Workspace Sidebar', 'Tradexcel HR')
    assert doc.app == 'tradex_hr' and doc.module == 'Tradexcel HR' and not doc.for_user
    assert len(doc.items) == len(expected)
    for row, values in zip(doc.items, expected, strict=True):
        for key, value in values.items():
            assert row.get(key) == value, (row.label, key)
        if row.type == 'Link':
            assert frappe.db.exists(row.link_type, row.link_to), row.link_to
    assert next(row.link_to for row in doc.items if row.label == 'Shift Assignments') == 'Shift Assignment'
    workspace = frappe.get_doc('Workspace', 'tradexcel-hr')
    # Staging metadata is not overwritten by this unmerged UI branch.
    # Compare the source layout below, and retain native installed target checks.
    # Installed Workspace Block.make matches the layout key to row.label.
    for block in json.loads(workspace.content):
        if block['type'] == 'custom_block':
            assert block['data']['custom_block_name'] in {row.label for row in workspace.custom_blocks}
    bundled = json.loads((Path(__file__).resolve().parents[1] / 'tradexcel_hr/workspace/tradexcel_hr/tradexcel_hr.json').read_text())
    assert json.loads(bundled['content']) == workspace_blocks()
    assert not bundled['number_cards']
    assert [row['document_type'] for row in bundled['quick_lists']] == ['Expense Claim']
    assert {row['label'] for row in bundled['shortcuts']} == {row.label for row in workspace.shortcuts}


def test_native_boot_sidebar_filters_every_persona_without_dead_links():
    from frappe.boot import get_sidebar_items
    from frappe.desk.desktop import get_workspaces, get_desktop_page
    from frappe.desk.query_report import get_report_doc

    h = SyntheticPersonaHarness('SOLNAV' + frappe.generate_hash(8).upper())
    matrix = {}
    denied_reports = []
    try:
        for key, role in PERSONA_ROLES.items():
            frappe.set_user('Administrator')
            user = h.create_user(key, [role], company='Tradexcel Ceramics Ltd.')
            frappe.set_user(user)
            pages = get_workspaces()['pages']
            workspaces = [row.name for row in pages]
            sidebars = get_sidebar_items(workspaces)
            sidebar = sidebars.get('tradexcel hr', {})
            links = [row for row in sidebar.get('items', []) if row['type'] == 'Link']
            targets = {row['link_to'] for row in links}
            matrix[key] = {'links': len(links), 'home': 'tradexcel-hr' in targets}
            for row in links:
                if row['link_type'] == 'DocType':
                    assert frappe.has_permission(row['link_to'], 'read'), (key, row)
                elif row['link_type'] == 'Report':
                    try:
                        get_report_doc(row['link_to'])
                    except frappe.PermissionError:
                        denied_reports.append((key, row["link_to"]))
                elif row['link_type'] == 'Workspace':
                    assert row['link_to'] in workspaces
            if key in {'attendance_officer', 'factory_supervisor', 'branch_manager', 'department_manager', 'worker', 'device_admin'}:
                assert not targets.intersection({'Salary Slip', 'Salary Structure Assignment', 'Payroll Entry', 'Tradexcel Pay Component Register', 'Tradexcel Payroll Variance'}), (key, targets)
            if key in {'hr_manager', 'attendance_officer'}:
                assert 'Shift Assignment Tool' in targets
            if key in {'hr_manager', 'payroll_manager'}:
                assert 'Bulk Salary Structure Assignment' in targets
            if key in {'factory_supervisor', 'branch_manager', 'department_manager', 'worker', 'device_admin'}:
                assert not {'Shift Assignment Tool', 'Bulk Salary Structure Assignment', 'Leave Control Panel'} & targets
            if key in {'worker', 'import_reviewer'}:
                assert 'tradexcel-hr' not in targets
            else:
                assert 'tradexcel-hr' in targets, key
                page = next(row for row in pages if row.name == 'tradexcel-hr')
                payload = get_desktop_page(json.dumps(page))
                assert payload['custom_blocks']['items'], key
            if key == 'device_admin':
                assert 'Tradexcel Biometric Device' in targets
        print('Native sidebar persona matrix: ' + json.dumps(matrix, sort_keys=True))
        assert not denied_reports, denied_reports
    finally:
        frappe.set_user('Administrator')
        h.cleanup()
