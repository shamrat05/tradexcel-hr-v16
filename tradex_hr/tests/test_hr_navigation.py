"""Navigation belongs to native Workspace metadata; retain unrelated Desk aids."""
from pathlib import Path
from tradex_hr.install import WORKSPACE_SECTIONS, WORKSPACE_SHORTCUTS, BULK_WORKSPACE_SHORTCUTS, workspace_sidebar_items

APP_ROOT = Path(__file__).resolve().parents[2]
NAVIGATION = (APP_ROOT / 'tradex_hr/public/js/tradex_hr.bundle.js').read_text()
CSS = (APP_ROOT / 'tradex_hr/public/css/tradex_hr.bundle.css').read_text()


def test_native_hr_navigation_has_job_groups():
    assert [row[0] for row in WORKSPACE_SECTIONS] == [
        'Employees', 'Attendance & Shifts', 'Leave & Holidays', 'Expenses & Travel',
        'Payroll', 'Recruitment', 'Development & Relations', 'Separation',
        'Compliance', 'Reports', 'Setup', 'Devices',
    ]


def test_navigation_uses_native_and_app_owned_targets():
    items = workspace_sidebar_items(WORKSPACE_SHORTCUTS + BULK_WORKSPACE_SHORTCUTS)
    assert items[0]['link_to'] == 'tradexcel-hr'
    targets = {row.get('link_to') for row in items}
    assert {'Employee', 'Attendance', 'Employee Checkin', 'Leave Application', 'Payroll Entry',
            'Tradexcel Biometric Device', 'Daily Attendance Summary', 'Shift Assignment',
            'Shift Assignment Tool', 'Bulk Salary Structure Assignment', 'Attendance Request'} <= targets
    assert len([row['label'] for row in items]) == len({row['label'] for row in items})


def test_native_sidebar_is_not_hidden_or_replaced_by_custom_rail():
    for source in (NAVIGATION, CSS):
        assert 'tradex-hr-rail' not in source
        assert 'body-sidebar-container' not in source
    assert 'function ensureRail()' not in NAVIGATION
    assert 'resolvedRoute' not in NAVIGATION


def test_theme_selection_belongs_to_native_desk():
    assert 'tradex-theme-toggle' not in NAVIGATION
    assert 'switch_theme' not in NAVIGATION
    assert 'setTimeout' not in NAVIGATION
    assert 'navbar-brand {' not in CSS


def test_report_defaults_do_not_depend_on_removed_rail():
    root = APP_ROOT / 'tradex_hr/tradexcel_hr/report'
    for name in ('tradexcel_daily_attendance_board', 'tradexcel_salary_coverage_board', 'tradexcel_shift_coverage'):
        source = (root / name / (name + '.js')).read_text()
        assert 'get_user_default("Company")' in source
        assert 'frappe.datetime.get_today()' in source
    assert 'frappe.route_options' not in NAVIGATION


def test_tradexcel_desktop_tile_uses_native_metadata():
    from tradex_hr import hooks
    assert hooks.add_to_apps_screen[0]['route'] == '/app/tradexcel-hr'
    import json
    icon = json.loads((APP_ROOT / 'tradex_hr/desktop_icon/tradexcel_hr.json').read_text())
    assert icon['link_type'] == 'Workspace Sidebar'
    assert icon['logo_url'] == hooks.add_to_apps_screen[0]['logo']
    assert 'removeAttribute' not in NAVIGATION
    assert 'querySelectorAll' not in NAVIGATION
