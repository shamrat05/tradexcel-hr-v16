"""Static checks for file-backed report filters and default UX."""

from __future__ import annotations

import pathlib
import re

APP = pathlib.Path(__file__).resolve().parents[2]
INSTALL = APP / "tradex_hr" / "install.py"
REPORT_DIR = APP / "tradex_hr" / "tradexcel_hr" / "report"

SCRIPT_REPORTS = {
    "Tradexcel Payroll Register": {"company", "from_date", "to_date"},
    "Tradexcel Leave Balance Board": {"company", "as_of_date"},
    "Tradexcel Daily Attendance Board": {"company", "attendance_date"},
    "Tradexcel Shift Coverage": {"company", "as_of_date", "branch", "department", "coverage"},
    "Tradexcel Joiners and Leavers": {"company", "from_date", "to_date", "branch", "department"},
    "Tradexcel Pay Component Register": {
        "company", "from_date", "to_date", "branch", "department", "component_type", "component"
    },
    "Tradexcel Payroll Variance": {"company", "from_date", "to_date", "branch", "department"},
}


def _slug(name: str) -> str:
    return name.lower().replace(" ", "_")


def _script(name: str, suffix: str) -> str:
    path = REPORT_DIR / _slug(name) / f"{_slug(name)}.{suffix}"
    assert path.exists(), f"Script Report file missing for {name}: {path}"
    return path.read_text(encoding="utf-8")


def _declared_filters(js: str) -> set[str]:
    return set(re.findall(r'fieldname:\s*"(\w+)"', js))


def test_script_reports_declare_and_default_their_filters():
    for name, expected in SCRIPT_REPORTS.items():
        py = _script(name, "py")
        js = _script(name, "js")
        assert any(token in py for token in ("normalize_filters", "normalise_filters", "_normalise", "normalize("))
        assert expected <= _declared_filters(js), f"{name} is missing UI filters"
        for field in expected:
            assert re.search(r'fieldname:\s*"%s"[^}]*default:' % re.escape(field), js), (
                f"{name}: {field} has no safe UI default"
            )


def test_salary_reports_keep_user_filters_out_of_raw_sql():
    for name in ("Tradexcel Pay Component Register", "Tradexcel Payroll Variance"):
        py = _script(name, "py")
        assert "permitted_employee_names" in py
        assert "permitted_salary_slips" in py
        assert "ignore_permissions" not in py
    scope = (APP / "tradex_hr" / "tradexcel_hr" / "report_scope.py").read_text(encoding="utf-8")
    assert 'frappe.get_list(\n            "Salary Slip"' in scope
    component = _script("Tradexcel Pay Component Register", "py")
    assert "s.name IN %(slip_names)s" in component


def test_global_query_report_override_has_no_app_dependency():
    hooks = (APP / "tradex_hr" / "hooks.py").read_text(encoding="utf-8")
    install = INSTALL.read_text(encoding="utf-8")
    assert "override_whitelisted_methods" not in hooks
    assert "tradex_hr.report_filters" not in hooks + install
    assert "GLOBAL_REPORT_ROLES" not in install
    assert not (APP / "tradex_hr" / "report_filters.py").exists()
    assert '"report_type": "Query Report"' not in install


def test_navigation_sequence_reports_declare_only_their_own_filters():
    foreign = {
        "Tradexcel Payroll Register": {"as_of_date", "attendance_date"},
        "Tradexcel Leave Balance Board": {"from_date", "to_date", "attendance_date"},
        "Tradexcel Daily Attendance Board": {"from_date", "to_date", "as_of_date"},
        "Tradexcel Payroll Variance": {"attendance_date", "as_of_date", "component"},
        "Tradexcel Pay Component Register": {"attendance_date", "as_of_date"},
    }
    for name, forbidden in foreign.items():
        declared = _declared_filters(_script(name, "js"))
        assert not (declared & forbidden), f"{name} declares foreign filters: {declared & forbidden}"


def test_legacy_reports_do_not_restore_stale_stored_javascript():
    import inspect
    from tradex_hr import install

    source = inspect.getsource(install)
    assert 'DAILY_ATTENDANCE_JAVASCRIPT' not in source
    assert 'WORKFORCE_ANOMALY_RADAR_JAVASCRIPT' not in source
    assert 'ensure_daily_attendance_report' not in source
    assert 'javascript' not in install.REPORTS['Workforce Anomaly Radar']
    assert 'Not Marked' in _script('Daily Attendance Summary', 'js')
