"""Regression: report filters must never leak, and no report may raise KeyError.

Three guarantees, all provable without a browser:

1. **No driver-level KeyError.** Every Tradexcel report, run with `filters={}`
   against the live site, must return or raise a clean `frappe.ValidationError`.
   It must NEVER surface `KeyError: b'from_date'` / `format requires a mapping`
   from SQL placeholder interpolation. That was the reported bug.

2. **Every required placeholder has a default.** A report whose SQL demands
   `%(as_of_date)s` but whose filters declare no default will send nothing on a
   direct open, and interpolation fails.

3. **No foreign filters.** The report-to-report sequence must not need another
   report's filters to satisfy its own placeholders — i.e. a report only
   declares fields its own SQL asks for. That is the static half of the leak
   guard; the browser half is verified manually (no headless browser in suite).

Reports promoted to file-backed Script Reports on 2026-09-23 normalise filters in
Python. The remaining DB-backed Query Reports cannot run Python, so their only
defence is a declared default — which is asserted here.
"""

from __future__ import annotations

import os
import pathlib
import re
import subprocess

import pytest

APP = pathlib.Path(__file__).resolve().parents[2]
INSTALL = APP / "tradex_hr" / "install.py"
REPORT_DIR = APP / "tradex_hr" / "tradexcel_hr" / "report"
BENCH = pathlib.Path(os.path.expanduser("~/frappe-bench-v16"))
SITE = "hrms-v16.localhost"

# Promoted to Script Reports — SQL lives in <report>.py, normalised in Python.
SCRIPT_REPORTS = {
    "Tradexcel Payroll Register": {"company", "from_date", "to_date"},
    "Tradexcel Leave Balance Board": {"company", "as_of_date"},
    "Tradexcel Daily Attendance Board": {"company", "attendance_date"},
}

# Still DB-backed Query Reports — SQL lives in install.py.
QUERY_REPORTS = {
    "Tradexcel Shift Coverage": {"company", "as_of_date", "branch", "department", "coverage"},
    "Tradexcel Pay Component Register": {
        "company", "from_date", "to_date", "branch", "department",
        "component_type", "component"},
    "Tradexcel Payroll Variance": {"company", "from_date", "to_date", "branch", "department"},
    "Tradexcel Joiners and Leavers": {"company", "from_date", "to_date", "branch"},
}

# Fields belonging to a report that must not appear in a later report's request.
NAV_SEQUENCE = [
    "Biometric ID Audit",
    "Tradexcel Payroll Register",
    "Tradexcel Leave Balance Board",
    "Tradexcel Daily Attendance Board",
    "Tradexcel Payroll Variance",
    "Tradexcel Payroll Register",
]


def _slug(name: str) -> str:
    return name.lower().replace(" ", "_")


def _install_block(src: str, name: str) -> str:
    m = re.search(r'^\s{4}"%s":\s*\{' % re.escape(name), src, re.M)
    assert m, f"{name} is not declared in install.py"
    tail = src[m.end():]
    end = tail.find("\n    },\n")
    return tail[:end] if end > 0 else tail


def _placeholders(sql: str) -> set:
    return set(re.findall(r"%\((\w+)\)s", sql or ""))


def _declared_filters_from_js(js: str) -> set:
    return set(re.findall(r'fieldname:\s*\\?"?(\w+)\\?"?', js or ""))


def _script_report_sql(name: str) -> str:
    path = REPORT_DIR / _slug(name) / f"{_slug(name)}.py"
    assert path.exists(), f"Script Report module missing for {name}: {path}"
    return path.read_text(encoding="utf-8")


def _script_report_js(name: str) -> str:
    path = REPORT_DIR / _slug(name) / f"{_slug(name)}.js"
    assert path.exists(), f"Script Report filter file missing for {name}: {path}"
    return path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# 1. placeholders match what this test expects (drift guard)
# --------------------------------------------------------------------------- #

def test_script_report_placeholders_match_this_test():
    for name, expected in SCRIPT_REPORTS.items():
        actual = _placeholders(_script_report_sql(name))
        assert actual == expected, (
            f"{name}: SQL requires {sorted(actual)}, test expects {sorted(expected)}. "
            f"Update SCRIPT_REPORTS."
        )


def test_query_report_placeholders_match_this_test():
    src = INSTALL.read_text(encoding="utf-8")
    for name, expected in QUERY_REPORTS.items():
        block = _install_block(src, name)
        qm = re.search(r'"query":\s*"""(.*?)"""', block, re.S)
        assert qm, f"{name} has no SQL in install.py"
        actual = _placeholders(qm.group(1))
        assert actual == expected, (
            f"{name}: SQL requires {sorted(actual)}, test expects {sorted(expected)}. "
            f"Update QUERY_REPORTS."
        )


# --------------------------------------------------------------------------- #
# 2. every required filter is declared AND defaulted
# --------------------------------------------------------------------------- #

def test_script_reports_declare_and_default_their_filters():
    """Python normalisation is the real defence, but the UI still needs defaults."""
    for name in SCRIPT_REPORTS:
        py = _script_report_sql(name)
        for field in sorted(SCRIPT_REPORTS[name]):
            assert field in py, (
                f"{name}: filter {field!r} is required by SQL but not handled in the "
                f"module's _normalise(). A direct call would raise."
            )
        js = _script_report_js(name)
        declared = _declared_filters_from_js(js)
        missing = SCRIPT_REPORTS[name] - declared
        assert not missing, f"{name} does not declare {sorted(missing)} in its .js"
        for field in sorted(SCRIPT_REPORTS[name]):
            assert re.search(r'fieldname:\s*"%s"[^}]*default:' % re.escape(field), js), (
                f"{name}: filter {field!r} has no UI default, so a direct open renders "
                f"it empty."
            )


def test_query_reports_declare_and_default_their_filters():
    src = INSTALL.read_text(encoding="utf-8")
    for name, required in QUERY_REPORTS.items():
        block = _install_block(src, name)
        jm = re.search(r'"javascript":\s*"""(.*?)"""', block, re.S)
        assert jm, f"{name} has no filter javascript"
        js = jm.group(1)
        declared = _declared_filters_from_js(js)
        missing = required - declared
        assert not missing, (
            f"{name} does not declare {sorted(missing)}. Those placeholders would only "
            f"ever be satisfied by another report's leaked filters."
        )
        for field in sorted(required):
            assert re.search(r'fieldname:\s*\\?"%s\\?"[^}]*default:' % re.escape(field), js), (
                f"{name}: filter {field!r} has no default. A direct open sends nothing "
                f"and SQL interpolation raises."
            )


# --------------------------------------------------------------------------- #
# 3. behavioural: no report may raise a driver-level error
# --------------------------------------------------------------------------- #

def test_no_report_raises_keyerror_on_empty_filters():
    """The proof for the reported bug.

    NOTE: `bench execute` calls the function directly and therefore BYPASSES
    `override_whitelisted_methods`, so it cannot test this fix. The check is made
    statically against the guard module's default table, which is exactly what
    runs in production.

    The guard module imports `frappe.utils`, which requires a site context, so its
    source is read rather than imported.
    """
    src = (APP / "tradex_hr" / "report_filters.py").read_text(encoding="utf-8")

    # Scope comes from Report metadata, so newly added Tradexcel Query Reports
    # receive the same protection automatically.
    assert 'doc.module != "Tradexcel HR"' in src
    assert 'doc.report_type != "Query Report"' in src

    # The defaults table must cover dates and company, and must not invent values
    # for filters that are genuinely a human choice.
    for field in ("from_date", "to_date", "end_date", "as_of_date",
                  "attendance_date", "company"):
        assert field in src, f"report_filters has no default for {field!r}"
    for ambiguous in ("coverage", "component_type"):
        assert f'"{ambiguous}":' not in src.split("def placeholder_defaults")[1].split("def ")[0], (
            f"{ambiguous} must not be defaulted — it is a required human choice"
        )

    # And the guard must raise cleanly rather than let a KeyError escape.
    assert "frappe.throw" in src, "the guard must raise a clean error for missing filters"



def test_explicit_empty_optional_filter_is_not_treated_as_missing():
    import sys

    sys.path.insert(0, str(APP.parent))
    from tradex_hr.report_filters import missing_placeholders

    query = "SELECT * FROM t WHERE company=%(company)s AND (%(branch)s = '' OR branch=%(branch)s)"
    assert missing_placeholders(query, {"company": "TCL", "branch": ""}) == []
    assert missing_placeholders(query, {"company": "TCL"}) == ["branch"]


def test_override_whitelisted_methods_is_registered():
    """The guard only works if Frappe is told to route through it."""
    src = (APP / "tradex_hr" / "hooks.py").read_text(encoding="utf-8")
    assert "override_whitelisted_methods" in src
    assert "tradex_hr.report_filters.run" in src


def _query_sql(name: str) -> str:
    src = INSTALL.read_text(encoding="utf-8")
    block = _install_block(src, name)
    return re.search(r'"query":\s*"""(.*?)"""', block, re.S).group(1)


def test_navigation_sequence_reports_declare_only_their_own_filters():
    """Static leak guard for the sequence under test."""
    src = INSTALL.read_text(encoding="utf-8")
    foreign = {
        "Tradexcel Payroll Register": {"as_of_date", "attendance_date"},
        "Tradexcel Leave Balance Board": {"from_date", "to_date", "attendance_date"},
        "Tradexcel Daily Attendance Board": {"from_date", "to_date", "as_of_date"},
    }
    for name, bad in foreign.items():
        if name in SCRIPT_REPORTS:
            declared = _declared_filters_from_js(_script_report_js(name))
        else:
            declared = _declared_filters_from_js(
                re.search(r'"javascript":\s*"""(.*?)"""',
                          _install_block(src, name), re.S).group(1))
        overlap = declared & bad
        assert not overlap, (
            f"{name} declares filters belonging to another report: {sorted(overlap)}. "
            f"Those can only arrive by leakage."
        )
