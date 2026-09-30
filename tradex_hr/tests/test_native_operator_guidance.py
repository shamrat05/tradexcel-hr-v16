"""Source projection, native visibility and destination permission proof."""
from unittest.mock import Mock, patch

import frappe
import pytest

from tradex_hr import install


@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(site='hrms-v16.localhost', sites_path='/home/sanchita/frappe-bench-v16/sites', force=True)
    frappe.connect()
    frappe.set_user('Administrator')
    yield
    frappe.set_user('Administrator')
    frappe.destroy()


def test_guidance_is_native_navigation_and_preserves_existing_progress():
    saved = []
    def doc(values):
        result = Mock()
        result.insert.side_effect = lambda **kwargs: saved.append(values)
        return result
    with patch.object(frappe.db, "exists", return_value=False), patch.object(frappe, "get_doc", side_effect=doc):
        install.ensure_operator_guidance()
    assert len(saved) == 3
    assert {r['doctype'] for r in saved} == {'Onboarding Step', 'Module Onboarding'}
    assert all(r['action'] == 'Go to Page' for r in saved[:2])
    assert all('Attendance Request' in r['path'] for r in saved[:2])
    assert all('is_complete' not in r and 'is_skipped' not in r for r in saved)
    with patch.object(frappe.db, "exists", return_value=True), patch.object(frappe, "get_doc") as get:
        install.ensure_operator_guidance()
        get.assert_not_called()  # Never reset dismissal, completion or admin edits.


def test_guidance_uses_installed_native_enablement_and_role_filtering():
    from frappe.desk.desktop import get_onboarding_data
    from frappe.desk.doctype.module_onboarding.module_onboarding import ModuleOnboarding
    module = ModuleOnboarding({"doctype": "Module Onboarding", "name": install.ATTENDANCE_GUIDE,
        "title": "Learn attendance", "allow_roles": [{"role": r} for r in install.ATTENDANCE_GUIDE_ROLES]})
    with patch.object(frappe, "get_system_settings", return_value=0), patch.object(frappe, "get_doc") as get:
        assert get_onboarding_data(install.ATTENDANCE_GUIDE) == []
        get.assert_not_called()
    for role, allowed in [(r, True) for r in install.ATTENDANCE_GUIDE_ROLES] + [
        ('System Manager', True), ('Tradexcel Employee/Worker', False), ('Tradexcel Payroll Manager', False),
        ('Tradexcel Finance/Accounts Officer', False), ('Tradexcel Branch Manager', False)]:
        with patch.object(frappe, "get_system_settings", return_value=1), \
             patch.object(frappe, "get_doc", return_value=module), patch.object(frappe, "get_roles", return_value=[role]), \
             patch('frappe.desk.desktop.get_onboarding_step_maps', return_value=[s['name'] for s in install.ATTENDANCE_GUIDE_STEPS]), \
             patch.object(frappe, "get_all", side_effect=lambda *a, **kw: [frappe._dict(next(s for s in install.ATTENDANCE_GUIDE_STEPS if s['name'] == kw['filters']['name']))]):
            result = get_onboarding_data(install.ATTENDANCE_GUIDE)
            assert bool(result) == allowed
    module.is_complete = 1
    with patch.object(frappe, "get_system_settings", return_value=1), patch.object(frappe, "get_doc", return_value=module):
        assert get_onboarding_data(install.ATTENDANCE_GUIDE) == []


def test_guidance_destination_permissions_and_worker_exclusion():
    from tradex_hr.tests.persona_uat import SyntheticPersonaHarness
    frappe.set_user('Administrator')
    h = SyntheticPersonaHarness('TXUX005' + frappe.generate_hash(8).upper())
    try:
        company = 'Tradexcel Ceramics Ltd.'
        branch = frappe.db.get_value('Branch', {'company': company}, 'name')
        department = frappe.db.get_value('Department', {'company': company}, 'name')
        for i, role in enumerate((*install.ATTENDANCE_GUIDE_ROLES, 'System Manager', 'Tradexcel Employee/Worker')):
            user = h.create_user(str(i), [role], company=company, branch=branch, department=department)
            frappe.set_user(user)
            if role != 'Tradexcel Employee/Worker':
                assert frappe.has_permission('Attendance Request', 'read')
                assert frappe.has_permission('Attendance Request', 'create')
            else:
                assert role not in install.ATTENDANCE_GUIDE_ROLES
            frappe.set_user('Administrator')
        assert not frappe.db.exists('Module Onboarding', install.ATTENDANCE_GUIDE)
    finally:
        frappe.set_user('Administrator')
        with patch.object(frappe, 'in_test', True), patch.object(frappe, 'enqueue'):
            h.cleanup()


def test_installed_metadata_supports_source_projection_without_custom_frontend():
    assert frappe.get_meta('Workspace Sidebar').has_field('module_onboarding')
    for values in install.ATTENDANCE_GUIDE_STEPS:
        doc = frappe.get_doc({'doctype': 'Onboarding Step', **values})
        assert doc.action in doc.meta.get_field('action').options.split('\n')
        assert all(doc.meta.has_field(field) for field in values if field != 'name')
        assert doc.path.startswith(('List/Attendance Request/', 'Form/Attendance Request/'))
    assert 'module_onboarding = ATTENDANCE_GUIDE' in __import__('inspect').getsource(install.ensure_workspace_sidebar)
    assert 'standard = 0' in __import__('inspect').getsource(install.ensure_workspace_sidebar)
