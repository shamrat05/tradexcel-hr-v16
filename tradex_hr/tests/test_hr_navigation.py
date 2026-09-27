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


def test_theme_toggle_remains_supported_and_accessible():
    assert 'frappe.ui.set_theme(next)' in NAVIGATION
    assert 'frappe.core.doctype.user.user.switch_theme' in NAVIGATION
    assert 'toolbar_setup page-change' in NAVIGATION
    assert 'aria-label="${__("Toggle Theme")}"' in NAVIGATION


def test_report_defaults_do_not_depend_on_removed_rail():
    root = APP_ROOT / 'tradex_hr/tradexcel_hr/report'
    for name in ('tradexcel_daily_attendance_board', 'tradexcel_salary_coverage_board', 'tradexcel_shift_coverage'):
        source = (root / name / (name + '.js')).read_text()
        assert 'get_user_default("Company")' in source
        assert 'frappe.datetime.get_today()' in source
    assert 'frappe.route_options' not in NAVIGATION


def test_tradexcel_desktop_tile_stays_in_same_tab():
    assert 'getAttribute("data-id") === "Tradexcel HR"' in NAVIGATION
    assert 'desk/tradexcel-hr' in NAVIGATION
    assert 'removeAttribute("target")' in NAVIGATION
