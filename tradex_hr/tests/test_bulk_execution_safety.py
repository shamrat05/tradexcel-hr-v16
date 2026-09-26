"""Installed publisher/commit and native worker retry compatibility contract."""
from unittest.mock import patch
import frappe
import pytest
from tradex_hr.tests.persona_uat import SyntheticPersonaHarness, PERSONA_ROLES
SITE = 'hrms-v16.localhost'
SITES = '/home/sanchita/frappe-bench-v16/sites'


def connect():
    frappe.init(site=SITE, sites_path=SITES, force=True)
    frappe.connect()
    frappe.set_user('Administrator')


@pytest.fixture(autouse=True)
def site():
    connect()
    yield
    connect()
    frappe.db.rollback()
    frappe.destroy()


def test_native_bulk_completion_uses_operator_room_at_real_commit():
    from tradex_hr.tradexcel_hr.bulk_execution_safety import private_bulk_results, BULK_RESULT_EVENTS
    h = SyntheticPersonaHarness('SOLJOB' + frappe.generate_hash(8).upper())
    try:
        user = h.create_user('maker', [PERSONA_ROLES['hr_manager']], company='Tradexcel Ceramics Ltd.')
        frappe.db.commit()
        frappe.set_user(user)
        with private_bulk_results():
            for event in BULK_RESULT_EVENTS:
                frappe.publish_realtime(event, {'success': [], 'failure': ['SYNTHETIC']},
                                        doctype='Shift Assignment Tool', after_commit=True)
            assert all(row[2] == 'all' for row in frappe.local._realtime_log)
        with patch('frappe.realtime.emit_via_redis') as emit:
            frappe.db.commit()
        assert len(emit.call_args_list) == len(BULK_RESULT_EVENTS)
        assert all(call.args[2] == f'user:{user}' for call in emit.call_args_list)
        assert not getattr(frappe.local, '_realtime_log', None)
        with pytest.raises(frappe.PermissionError):
            with private_bulk_results():
                frappe.publish_realtime('completed_bulk_shift_assignment', {}, after_commit=True)
                frappe.set_user('Administrator')
        frappe.db.rollback()
    finally:
        frappe.set_user('Administrator')
        h.cleanup()


def test_native_retry_cannot_execute_as_administrator(monkeypatch):
    from frappe.utils.background_jobs import execute_job
    h = SyntheticPersonaHarness('SOLJOB' + frappe.generate_hash(8).upper())
    actors = []
    def harmless_job():
        actors.append(frappe.session.user)
        raise frappe.RetryBackgroundJobError
    try:
        user = h.create_user('maker', [PERSONA_ROLES['hr_manager']], company='Tradexcel Ceramics Ltd.')
        frappe.db.commit()
        monkeypatch.chdir(SITES)
        with patch('frappe.utils.background_jobs.time.sleep'):
            with pytest.raises(frappe.PermissionError, match='original user'):
                execute_job(SITE, harmless_job, None, 'synthetic-retry', {}, user=user)
        assert actors == [user]
    finally:
        connect()
        h.cleanup()


def test_disabled_and_missing_job_actor_fail_closed():
    from tradex_hr.tradexcel_hr.bulk_execution_safety import validate_job_actor
    h = SyntheticPersonaHarness('SOLJOB' + frappe.generate_hash(8).upper())
    try:
        user = h.create_user('disabled', [PERSONA_ROLES['hr_manager']])
        with patch.object(frappe, 'in_test', True):
            doc = frappe.get_doc('User', user)
            doc.enabled = 0
            doc.save(ignore_permissions=True)
        frappe.set_user(user)
        frappe.local.job = frappe._dict(user=user)
        with pytest.raises(frappe.PermissionError): validate_job_actor()
        frappe.set_user('Administrator')
        frappe.local.job = frappe._dict(user=None)
        with pytest.raises(frappe.PermissionError): validate_job_actor()
        frappe.local.job = frappe._dict(user='Administrator')
        validate_job_actor()
    finally:
        frappe.set_user('Administrator')
        h.cleanup()


def test_separate_native_calls_keep_separate_recipients_and_unknown_buffer_fails_closed():
    from tradex_hr.tradexcel_hr.bulk_execution_safety import private_bulk_results
    h = SyntheticPersonaHarness('SOLJOB' + frappe.generate_hash(8).upper())
    try:
        users = [h.create_user(key, [PERSONA_ROLES['hr_manager']]) for key in ('a', 'b')]
        frappe.db.commit()
        for user in users:
            frappe.set_user(user)
            with private_bulk_results():
                frappe.publish_realtime('completed_bulk_shift_assignment', {'synthetic': user}, after_commit=True)
        frappe.set_user('Administrator')
        with patch('frappe.realtime.emit_via_redis') as emit:
            frappe.db.commit()
        assert [call.args[2] for call in emit.call_args_list] == [f'user:{user}' for user in users]
        with pytest.raises(RuntimeError, match='native failure'):
            with private_bulk_results():
                frappe.publish_realtime('completed_bulk_shift_assignment', {'synthetic': True}, after_commit=True)
                raise RuntimeError('native failure')
        with patch('frappe.realtime.emit_via_redis') as emit:
            frappe.db.commit()
        emit.assert_not_called()
        with pytest.raises(frappe.ValidationError, match='compatibility review'):
            with private_bulk_results():
                frappe.local._realtime_log = {'unexpected': 'upstream shape'}
        del frappe.local._realtime_log
    finally:
        frappe.set_user('Administrator')
        h.cleanup()
