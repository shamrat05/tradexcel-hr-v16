from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2]
NAVIGATION = (APP_ROOT / "tradex_hr/public/js/tradex_hr.bundle.js").read_text()


def test_persistent_hr_navigation_has_requested_groups():
    for group in (
        "Home",
        "People",
        "Time & Attendance",
        "Leave",
        "Payroll",
        "Operations",
        "Devices",
        "Analytics",
        "Administration",
    ):
        assert f'label: __("{group}")' in NAVIGATION


def test_navigation_uses_native_and_app_owned_routes():
    for route in (
        "workspace/tradexcel-hr",
        "List/Employee",
        "List/Attendance",
        "List/Employee Checkin",
        "List/Leave Application",
        "leave-application/view/calendar",
        "List/Payroll Entry",
        "List/Tradexcel Biometric Device",
        "query-report/Daily Attendance Summary",
    ):
        assert f'route: "{route}"' in NAVIGATION


def test_navigation_has_collapsed_and_expanded_modes():
    assert "tradex-hr-rail-expanded" in NAVIGATION or "tradex-hr-rail-expanded" in (
        APP_ROOT / "tradex_hr/public/css/tradex_hr.bundle.css"
    ).read_text()
    assert "tradex-hr-rail-collapsed" in (
        APP_ROOT / "tradex_hr/public/css/tradex_hr.bundle.css"
    ).read_text()


def test_navigation_repairs_after_frappe_route_shell_replacement():
    javascript = NAVIGATION
    assert "function ensureRail()" in javascript
    assert '$(document).on("page-change"' in javascript
    assert "MutationObserver" in javascript
    assert "observe(document.documentElement" in javascript
    assert "__tradex_hr_rail_repair_timer" in javascript
