"""Native global-completion reproduction and completion-independent form help."""
from unittest.mock import patch

import frappe
import pytest

from workforce_suite import install
from workforce_suite.tests.persona_uat import SyntheticPersonaHarness


@pytest.fixture(scope='module', autouse=True)
def site():
    frappe.init(site='hrms-v16.localhost', sites_path='/home/sanchita/frappe-bench-v16/sites', force=True)
    frappe.connect()
    frappe.set_user('Administrator')
    yield
    frappe.set_user('Administrator')
    frappe.destroy()


def test_native_shared_completion_hides_the_guide_from_second_operator():
    from frappe.desk.desktop import get_onboarding_data, update_onboarding_step
    h = SyntheticPersonaHarness('TXUX005P01' + frappe.generate_hash(8).upper())
    name = 'TEST ' + h.token
    try:
        for key in ('first', 'second'):
            h.create_user(key, ['Workforce Suite Manager'])
        step = frappe.get_doc({'doctype': 'Onboarding Step', 'name': name, 'title': 'Synthetic navigation',
            'action': 'Go to Page', 'path': 'List/Attendance Request/List'}).insert(ignore_permissions=True)
        # Prevent developer-mode export of these strictly synthetic native fixtures.
        with patch('frappe.desk.doctype.module_onboarding.module_onboarding.export_to_files'):
            frappe.get_doc({'doctype': 'Module Onboarding', 'name': name, 'module': 'Workforce Suite',
                'title': 'Synthetic shared-completion proof', 'allow_roles': [{'role': 'Workforce Suite Manager'}],
                'steps': [{'step': step.name}]}).insert(ignore_permissions=True)
        settings = frappe.get_system_settings
        with patch.object(frappe, 'get_system_settings', side_effect=lambda key: 1 if key == 'enable_onboarding' else settings(key)), patch('frappe.utils.telemetry.capture'):
            frappe.set_user(h.users['first'])
            assert get_onboarding_data(name)
            update_onboarding_step(step.name, 'is_complete', 1)
            frappe.set_user(h.users['second'])
            assert frappe.db.get_value('Onboarding Step', step.name, 'is_complete') == 1
            assert get_onboarding_data(name) == []
            # Our replacement does not consult native onboarding progress/settings.
            with patch.object(frappe.db, 'exists', return_value=False), \
                 patch('frappe.custom.doctype.property_setter.property_setter.make_property_setter') as make:
                install.ensure_operator_guidance()
                assert make.call_args.args[3] == install.ATTENDANCE_REQUEST_GUIDANCE
    finally:
        frappe.set_user('Administrator')
        with patch.object(frappe, 'enqueue'), patch.object(frappe, 'in_test', True):
            for dt in ('Module Onboarding', 'Onboarding Step'):
                if frappe.db.exists(dt, name):
                    frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
            h.cleanup()
        assert not frappe.db.exists('Onboarding Step', name)
        assert not frappe.db.exists('Module Onboarding', name)


def test_persistent_help_has_no_completion_state_and_preserves_admin_override():
    with patch.object(frappe.db, 'exists', return_value=False), \
         patch('frappe.custom.doctype.property_setter.property_setter.make_property_setter') as make:
        install.ensure_operator_guidance()
        make.assert_called_once_with('Attendance Request', 'explanation', 'description',
                                    install.ATTENDANCE_REQUEST_GUIDANCE, 'Small Text')
    with patch.object(frappe.db, 'exists', return_value=True), \
         patch('frappe.custom.doctype.property_setter.property_setter.make_property_setter') as make:
        install.ensure_operator_guidance()
        make.assert_not_called()
    assert 'draft' in install.ATTENDANCE_REQUEST_GUIDANCE
    assert 'independent reviewer' in install.ATTENDANCE_REQUEST_GUIDANCE
    assert 'does not create approved Attendance' in install.ATTENDANCE_REQUEST_GUIDANCE


def test_help_destination_uses_existing_native_access_without_management_navigation():
    h = SyntheticPersonaHarness('TXUX005P01' + frappe.generate_hash(8).upper())
    try:
        for key, role in [('hr', 'Workforce Suite Manager'), ('officer', 'Workforce Suite/Attendance Officer'),
                          ('system', 'System Manager'), ('worker', 'Workforce Employee/Worker')]:
            user = h.create_user(key, [role])
            frappe.set_user(user)
            if key == 'worker':
                assert not frappe.has_permission('Attendance Request', 'read')
                frappe.set_user('Administrator')
                continue
            assert frappe.has_permission('Attendance Request', 'read'), role
            assert frappe.has_permission('Attendance Request', 'create'), role
            # Help is generic request guidance, not management onboarding/navigation.
            meta = frappe.get_meta('Attendance Request')
            assert meta.get_field('explanation').fieldtype == 'Small Text'
            assert not meta.get_field('explanation').show_description_on_click
            frappe.set_user('Administrator')
    finally:
        frappe.set_user('Administrator')
        with patch.object(frappe, 'enqueue'), patch.object(frappe, 'in_test', True):
            h.cleanup()


def test_source_does_not_install_shared_onboarding_or_change_sidebar_owner():
    import inspect
    guidance = inspect.getsource(install.ensure_operator_guidance)
    sidebar = inspect.getsource(install.ensure_workspace_sidebar)
    assert 'Onboarding Step' not in guidance and 'Module Onboarding' not in guidance
    assert 'module_onboarding' not in sidebar
    assert 'standard = 0' in sidebar
