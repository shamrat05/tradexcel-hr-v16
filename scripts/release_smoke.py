"""Read-only installed-source smoke: run from bench with its Python.

Usage: env/bin/python apps/tradex_hr/scripts/release_smoke.py SITE [--neutral]
Never exports identities, configuration secrets or financial amounts.
"""
from pathlib import Path
import argparse
import json
import os
import frappe

parser = argparse.ArgumentParser()
parser.add_argument('site')
parser.add_argument('--neutral', action='store_true')
args = parser.parse_args()
os.chdir(Path.cwd() / 'sites')
frappe.init(site=args.site, force=True)
frappe.connect()
try:
    assert int(frappe.conf.db_port) == 3307, 'This rehearsal requires isolated MariaDB 3307'
    assert set(('frappe', 'erpnext', 'hrms', 'tradex_hr')) <= set(frappe.get_installed_apps())
    frappe.set_user('Administrator')
    from frappe.model.base_document import get_controller
    for dt, extension in (
        ('Shift Assignment Tool', 'tradex_hr.tradexcel_hr.shift_assignment_tool'),
        ('Bulk Salary Structure Assignment', 'tradex_hr.tradexcel_hr.bulk_salary_structure_assignment'),
        ('Leave Control Panel', 'tradex_hr.tradexcel_hr.leave_control_panel'),
    ):
        assert any(c.__module__ == extension for c in get_controller(dt).__mro__), dt
    assert not frappe.get_hooks('override_whitelisted_methods').get('frappe.desk.query_report.run')
    reports = frappe.get_all('Report', filters={'module': 'Tradexcel HR'}, fields=['name', 'report_type', 'is_standard', 'query'])
    assert reports and all(r.report_type == 'Script Report' and r.is_standard == 'Yes' and not r.query for r in reports)
    assert frappe.db.exists('Workspace', 'tradexcel-hr')
    assert frappe.get_meta('Salary Structure').has_field('custom_tradex_pay_basis')
    assert frappe.get_meta('Tradexcel Attendance Policy').has_field('offline_trust_window_minutes')
    for field in ('custom_tradex_review_status', 'custom_tradex_reviewed_by',
                  'custom_tradex_reviewed_at', 'custom_tradex_review_reason', 'custom_tradex_time_reason'):
        assert frappe.get_meta('Employee Checkin').has_field(field), field
    assert 'employee_checkin_review.js' in str(frappe.get_hooks('doctype_js').get('Employee Checkin'))
    from tradex_hr.tradexcel_hr import field_attendance_service as mobile
    for action in (mobile.approve_mobile_checkin, mobile.reject_mobile_checkin):
        assert action in frappe.whitelisted
        assert frappe.allowed_http_methods_for_whitelisted_func[action] == ['POST']
    if args.neutral:
        empty = ('Company', 'Employee', 'Branch', 'Salary Structure', 'Salary Structure Assignment',
                 'Salary Slip', 'Payroll Entry', 'Leave Allocation', 'Leave Policy',
                 'Tradexcel Wage Floor Rule Set', 'Tradexcel Statutory Benefit Rule Set',
                 'Tradexcel Working Time Rule Set', 'Tradexcel Maternity Rule Set',
                 'Tradexcel Flexible Work Policy')
        for dt in empty:
            assert frappe.db.count(dt) == 0, f'Neutral install manufactured {dt}'
    print(json.dumps({'site': args.site, 'neutral': args.neutral, 'standard_reports': len(reports), 'extension_contract': 'PASS', 'db_port': 3307}))
finally:
    frappe.db.rollback()
    frappe.destroy()
