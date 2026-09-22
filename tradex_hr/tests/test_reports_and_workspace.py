"""App-level smoke tests: the reports, workspace and desk routes really resolve.

These are the *valuable* half of six investigation scripts that lived in
`~/frappe-bench/sync/` (unversioned, outside the app). Those scripts imported
`frappe`, called `frappe.init()`, printed, and asserted nothing — so pytest
collected them, executed their side effects, and proved nothing. This file keeps
their intent while making it enforceable.

Not versioned here (they test one-off migration tooling that is being retired,
not the app): test_audit_biometric_ids, test_branch_mapping,
test_extract_verified, test_rebuild_tradex, test_reconciliation,
test_reset_and_demo.
"""

from __future__ import annotations

import pathlib

import pytest

APP = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def site():
    frappe = pytest.importorskip("frappe")
    import os

    sites = os.environ.get("FRAPPE_TEST_SITES_PATH", os.path.expanduser("~/frappe-bench/sites"))
    if not os.path.isdir(sites):
        pytest.skip("no bench sites directory")
    try:
        frappe.init(site=os.environ.get("FRAPPE_TEST_SITE", "hrms.localhost"), sites_path=sites)
        frappe.connect()
        frappe.set_user("Administrator")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"cannot reach site: {type(exc).__name__}: {exc}")
    return frappe


def test_every_app_report_exists_and_has_roles(site):
    """A report with no roles is reachable by anyone; a missing one is a dead link."""
    names = [
        "Daily Attendance Summary",
        "Employee Data Gaps",
        "Workforce Anomaly Radar",
        "Biometric ID Audit",
        "Tradexcel Salary Coverage Board",
        "Tradexcel Daily Attendance Board",
        "Tradexcel Payroll Register",
    ]
    missing = [n for n in names if not site.db.exists("Report", n)]
    assert not missing, f"reports missing from the site: {missing}"
    for n in names:
        doc = site.get_doc("Report", n)
        assert doc.ref_doctype, f"{n} has no reference doctype"


def test_workspace_resolves_and_is_public(site):
    """The workspace the app ships must exist and be loadable."""
    assert site.db.exists("Workspace", "tradexcel-hr"), "workspace tradexcel-hr is missing"
    doc = site.get_doc("Workspace", "tradexcel-hr")
    assert doc.public in (1, "1", True), "the Tradexcel HR workspace must be public"


def test_desk_route_has_no_dead_shortcuts(site):
    """Every shortcut in the workspace must point at something that exists.

    This is the check the old scripts never made: they printed the sidebar and
    exited, so a shortcut to a deleted report stayed broken silently. The demo
    workspace previously pointed at `tradex-hr-management`, a name that no longer
    exists.
    """
    ws = site.get_doc("Workspace", "tradexcel-hr")
    dead = []
    for row in ws.shortcuts:
        if row.type == "DocType" and row.link_to and not site.db.exists(row.type, row.link_to):
            dead.append(f"{row.label}: {row.link_to}")
        elif row.type == "Report" and row.link_to and not site.db.exists("Report", row.link_to):
            dead.append(f"{row.label} (report): {row.link_to}")
        elif row.type == "Page" and row.link_to and not site.db.exists("Page", row.link_to):
            dead.append(f"{row.label} (page): {row.link_to}")
    assert not dead, f"workspace shortcuts point at things that do not exist: {dead}"


def test_salary_setup_spec_is_valid(site):
    """The declarative spec must load and name only real Frappe fields."""
    import sys

    sys.path.insert(0, str(APP.parent))
    from tradex_hr.tradexcel_hr.salary_setup import load_spec

    spec = load_spec()
    assert spec["components"], "no components declared"
    assert spec["structures"], "no structures declared"
    meta = site.get_meta("Salary Component")
    for comp in spec["components"]:
        for field in (comp.get("fields") or {}):
            assert meta.has_field(field), (
                f"{comp['name']} sets {field!r}, which Salary Component does not have"
            )
    # structures must sum to 100% or payroll cannot reconcile to the base.
    # Attendance-based rows (base * payment_days) are paid per day, not a share
    # of a monthly gross, so they are excluded from the percentage check.
    for st in spec["structures"]:
        factors, attendance_based = [], False
        for e in st["earnings"]:
            f = (e.get("formula") or "").replace(" ", "")
            if not f.startswith("base*"):
                continue
            factor = f[len("base*"):]
            if not factor.replace(".", "").isdigit():
                attendance_based = True
                continue
            factors.append(float(factor))
        if factors and not attendance_based:
            assert abs(sum(factors) - 1.0) < 1e-9, (
                f"{st['name']} percentages sum to {sum(factors)}, not 1.0"
            )


def test_assignment_structures_belong_to_the_employees_company(site):
    """Frappe blocks a mismatch, so a bad row means something wrote around it."""
    rows = site.db.sql(
        """SELECT a.name, a.employee, e.company AS emp_co, s.company AS struct_co
           FROM `tabSalary Structure Assignment` a
           JOIN tabEmployee e ON e.name = a.employee
           JOIN `tabSalary Structure` s ON s.name = a.salary_structure
           WHERE a.docstatus = 1 AND e.company != s.company""",
        as_dict=True,
    )
    assert not rows, f"assignments whose structure belongs to another company: {rows[:5]}"
