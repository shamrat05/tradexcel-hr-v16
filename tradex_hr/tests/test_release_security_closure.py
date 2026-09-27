"""Integrated security contract; no dependency on historical commit SHAs."""
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
import json
import frappe
import pytest
from frappe.utils import now_datetime
from tradex_hr.tests.persona_uat import SyntheticPersonaHarness, PERSONA_ROLES
from tradex_hr.tests.test_bulk_attendance_corrections_integration import site, _active_day, _masters, _remove_synthetic
from tradex_hr.tradexcel_hr import field_attendance_service as mobile, attendance_corrections as corrections


def test_owner_cannot_approve_after_maker_role_removed():
    h = SyntheticPersonaHarness('RELCLOSE' + frappe.generate_hash(8).upper())
    tracked = {dt: [] for dt in ('Attendance Request', 'Attendance', 'Employee Checkin')}
    try:
        company = 'Tradexcel Ceramics Ltd.'
        bs, ds = _masters(company)
        maker = h.create_user('maker', [PERSONA_ROLES['attendance_officer']], company=company, branch=bs[0])
        approver = h.create_user('checker', [PERSONA_ROLES['attendance_correction_approver']], company=company, branch=bs[0])
        outside = h.create_user('outside', [PERSONA_ROLES['attendance_correction_approver']], company=company, branch=bs[1])
        emp = h.create_employee('owner', company, bs[0], ds[0])
        day = _active_day(emp)
        frappe.set_user(maker)
        doc = frappe.get_doc(dict(doctype='Attendance Request', employee=emp, from_date=day,
            to_date=day, reason='On Duty', explanation='Synthetic independent review')).insert()
        tracked['Attendance Request'].append(doc.name)
        frappe.set_user('Administrator')
        user = frappe.get_doc('User', maker)
        user.set('roles', [{'role': PERSONA_ROLES['attendance_correction_approver']}])
        user.save(ignore_permissions=True)
        frappe.clear_cache(user=maker)
        frappe.set_user(maker)
        with pytest.raises(frappe.PermissionError, match='different'):
            frappe.get_doc('Attendance Request', doc.name).submit()
        frappe.set_user(outside)
        with pytest.raises(frappe.PermissionError):
            frappe.get_doc('Attendance Request', doc.name).submit()
        frappe.set_user(approver)
        frappe.get_doc('Attendance Request', doc.name).submit()
        assert frappe.db.get_value('Attendance Request', doc.name, 'docstatus') == 1
    finally:
        frappe.set_user('Administrator')
        if h.employees:
            tracked['Attendance'] = frappe.get_all('Attendance', filters={'employee': ['in', h.employees]}, pluck='name')
        _remove_synthetic(tracked, h)


def test_mobile_quarantine_review_scope_and_attendance_boundary():
    frappe.set_user('Administrator')
    h = SyntheticPersonaHarness('RELMOBILE' + frappe.generate_hash(8).upper())
    tracked = {dt: [] for dt in ('Attendance Request', 'Attendance', 'Employee Checkin')}
    policies = []
    try:
        company = 'Tradexcel Ceramics Ltd.'
        bs, ds = _masters(company)
        reviewer = h.create_user('review', [PERSONA_ROLES['attendance_correction_approver']], company=company, branch=bs[0])
        outsider = h.create_user('outside', [PERSONA_ROLES['attendance_correction_approver']], company=company, branch=bs[1])
        wrong = h.create_user('wrong', [PERSONA_ROLES['payroll_manager']], company=company)
        emp = h.create_employee('evidence', company, bs[0], ds[0])
        policy = frappe.get_doc(dict(doctype='Tradexcel Attendance Policy', policy_name=h.token,
            company=company, effective_from='2020-01-01', attendance_mode='Hybrid',
            outside_action='Accept', allowance_mode='None', offline_time_action='Flag',
            offline_max_age_hours=72, offline_trust_window_minutes=5, retention_days=90)).insert(ignore_permissions=True)
        policies.append(policy.name)
        policy.submit()
        receipt = now_datetime()
        # Only policy selection and shift availability are fixture-controlled;
        # native Checkin insertion, hooks, scope and review endpoints execute.
        with patch.object(mobile, '_policy', return_value=policy), patch.object(mobile, 'now_datetime', return_value=receipt), patch.object(mobile, 'get_actual_start_end_datetime_of_shift', return_value=None):
            for offset in (6, 7):
                captured = receipt - timedelta(hours=offset)
                doc = frappe.get_doc(dict(doctype='Employee Checkin', employee=emp, log_type='IN',
                    time=captured, custom_tradex_source='Mobile', custom_tradex_device_time=captured)).insert(ignore_permissions=True)
                tracked['Employee Checkin'].append(doc.name)
                assert doc.skip_auto_attendance == 1
                assert doc.custom_tradex_review_status == 'Pending'
                assert doc.custom_tradex_time_reason
                assert corrections._day_context(frappe._dict(name=emp), captured.date())['mobile_review_pending']
            name, rejected = tracked['Employee Checkin']
            # Source relabelling cannot bypass quarantine even for a writer.
            forged = frappe.get_doc('Employee Checkin', name)
            forged.custom_tradex_source = 'Manual'
            forged.skip_auto_attendance = 0
            with pytest.raises(frappe.PermissionError):
                forged.save()
            for user in (outsider, wrong):
                frappe.set_user(user)
                with pytest.raises(frappe.PermissionError):
                    mobile.approve_mobile_checkin(name, 'Synthetic reviewed evidence')
            frappe.set_user(reviewer)
            for operation in ('write', 'export', 'print'):
                assert not frappe.has_permission('Employee Checkin', operation, doc=name)
            result = mobile.approve_mobile_checkin(name, 'Synthetic reviewed evidence')
            assert result['skip_auto_attendance'] == 0
            assert result['custom_tradex_review_status'] == 'Approved'
            assert result['custom_tradex_policy'] == policy.name
            assert result['custom_tradex_time_reason']
            assert result['custom_tradex_reviewed_by'] == reviewer
            assert mobile.approve_mobile_checkin(name, 'Retry reviewed evidence')['name'] == name
            with pytest.raises(frappe.ValidationError):
                mobile.reject_mobile_checkin(name, 'Cannot reverse approval')
            result = mobile.reject_mobile_checkin(rejected, 'Synthetic rejected evidence')
            assert result['skip_auto_attendance'] == 1
            assert result['custom_tradex_review_status'] == 'Rejected'
            with pytest.raises(frappe.ValidationError):
                mobile.approve_mobile_checkin(rejected, 'Cannot reverse rejection')
            assert not frappe.db.exists('Attendance', {'employee': emp})
    finally:
        _remove_synthetic(tracked, h)
        for name in policies:
            doc = frappe.get_doc('Tradexcel Attendance Policy', name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc('Tradexcel Attendance Policy', name, force=True, ignore_permissions=True)
        frappe.db.commit()
        assert not any(frappe.db.exists('Tradexcel Attendance Policy', n) for n in policies)


def test_source_install_mobile_security_contract():
    from tradex_hr.field_attendance_setup import _fields
    root = Path(__file__).parents[1]
    policy = json.loads((root / 'tradexcel_hr/doctype/tradexcel_attendance_policy/tradexcel_attendance_policy.json').read_text())
    fields = {f['fieldname']: f for f in policy['fields']}
    assert str(fields['offline_trust_window_minutes']['default']) == '5'
    assert 'offline_future_tolerance_minutes' not in fields
    checkin = {f['fieldname'] for f in _fields()['Employee Checkin']}
    assert {'custom_tradex_reviewed_by', 'custom_tradex_reviewed_at', 'custom_tradex_review_reason', 'custom_tradex_time_reason'} <= checkin
    assert 'employee_checkin_review.js' in str(frappe.get_hooks('doctype_js')['Employee Checkin'])
    for endpoint in (mobile.approve_mobile_checkin, mobile.reject_mobile_checkin):
        assert frappe.allowed_http_methods_for_whitelisted_func[endpoint] == ['POST']


def test_flagged_out_api_defers_allowance_until_scoped_approval():
    from zoneinfo import ZoneInfo
    from frappe.utils import get_system_timezone
    frappe.set_user('Administrator')
    h = SyntheticPersonaHarness('RELMOBILEOUT' + frappe.generate_hash(6).upper())
    created = []
    try:
        company = 'Tradexcel Ceramics Ltd.'
        bs, ds = _masters(company)
        reviewer = h.create_user('review', [PERSONA_ROLES['attendance_correction_approver']], company=company, branch=bs[0])
        emp = h.create_employee('field', company, bs[0], ds[0])
        receipt = now_datetime()
        captured = receipt - timedelta(hours=6)
        policy = frappe.get_doc(dict(doctype='Tradexcel Attendance Policy', policy_name=h.token,
            company=company, effective_from='2020-01-01', attendance_mode='Hybrid',
            outside_action='Accept', allowance_mode='None', offline_time_action='Flag',
            offline_max_age_hours=72, offline_trust_window_minutes=5, retention_days=90)).insert(ignore_permissions=True)
        created.append((policy.doctype, policy.name))
        policy.submit()
        duty = frappe.get_doc(dict(doctype='Tradexcel Field Duty', duty_id=h.token, employee=emp,
            company=company, duty_date=captured.date(), duty_type='Field Work',
            purpose='Synthetic security review', allowance_mode='None')).insert(ignore_permissions=True)
        created.append((duty.doctype, duty.name))
        duty.submit()
        with patch.object(mobile, '_policy', return_value=policy), patch.object(mobile, 'now_datetime', return_value=receipt), patch.object(frappe, 'enqueue') as enqueue:
            result = mobile.mobile_checkin(emp, 'OUT', time=captured.replace(tzinfo=ZoneInfo(get_system_timezone())).isoformat(), field_duty=duty.name, sync_id=h.token)
            created.extend([('Tradex Mobile Event', h.token), ('Employee Checkin', result['name'])])
            assert result['skip_auto_attendance'] == 1
            enqueue.assert_not_called()
            assert mobile.settle_field_duty_allowance(duty.name)['status'] == 'Awaiting attendance review'
            frappe.set_user(reviewer)
            mobile.approve_mobile_checkin(result['name'], 'Reviewed synthetic delayed field evidence')
            enqueue.assert_called_once()
            assert enqueue.call_args.args == ('tradex_hr.tradexcel_hr.field_attendance_service.settle_field_duty_allowance',)
            assert enqueue.call_args.kwargs['enqueue_after_commit'] is True
            assert enqueue.call_args.kwargs['duty_name'] == duty.name
            assert mobile.settle_field_duty_allowance(duty.name)['status'] == 'No automatic allowance'
            for dt in ('Attendance', 'Additional Salary', 'Salary Slip'):
                assert not frappe.db.exists(dt, {'employee': emp})
    finally:
        frappe.set_user('Administrator')
        for dt, name in reversed(created):
            if frappe.db.exists(dt, name):
                doc = frappe.get_doc(dt, name)
                if doc.docstatus == 1:
                    doc.cancel()
                frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
        h.cleanup()
        frappe.db.commit()
        assert not any(frappe.db.exists(dt, name) for dt, name in created)
