"""TXUX-260930-013-P05: explicit retired-artifact cleanup contract tests.

Synthetic records only; real staging records are never deleted here.
Tests cover:
- Production allowlist enforcement and separation of test injection.
- Detection of additional functional references (Workspace Sidebar Item, Desktop Icon, custom Link fields).
- Fail-closed behavior on unresolvable custom Dynamic Link fields.
- Customization detection on presentation properties (background_color, show_percentage_stats, custom_options, show_values_over_chart).
- Verified backup preflight integrity checks against recorded evidence.
- Canonical allowlist coverage and zero source recreation paths.
"""
import ast
import gzip
import hashlib
import importlib
import inspect
import io
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKTREE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKTREE_ROOT))

import frappe
import pytest

from tradex_hr import install
importlib.reload(install)

TASK_TAG = "TXUX013P05"
PREFIX = f"{TASK_TAG}-SYNTH"

# Exact, unmistakable task-specific custom field and column identifiers
SYNTH_LINK_CF_DT = "Department"
SYNTH_LINK_CF_FIELDNAME = f"custom_{TASK_TAG.lower()}_card_ref"
SYNTH_LINK_CF_NAME = f"{SYNTH_LINK_CF_DT}-{SYNTH_LINK_CF_FIELDNAME}"

SYNTH_DYN_CF_DT = "Department"
SYNTH_DYN_CF_FIELDNAME = f"custom_{TASK_TAG.lower()}_dyn_link_ref"
SYNTH_DYN_CF_NAME = f"{SYNTH_DYN_CF_DT}-{SYNTH_DYN_CF_FIELDNAME}"

_TRACKED_DOCS: set[tuple[str, str]] = set()
_TRACKED_COLUMNS: set[tuple[str, str]] = set()


def _track_doc(doctype: str, name: str) -> str:
    _TRACKED_DOCS.add((doctype, name))
    return name


def _track_column(dt: str, fieldname: str) -> str:
    _TRACKED_COLUMNS.add((dt, fieldname))
    return fieldname


CANONICAL_CARDS = (
    "Tradexcel Active Employees",
    "Tradexcel Punches Logged",
    "Tradexcel Present Records",
    "Tradexcel Absent Records",
)
CANONICAL_CHARTS = (
    "Tradexcel Employees by Department",
    "Tradexcel Employees by Branch",
    "Tradexcel Headcount by Company",
    "Tradexcel Attendance Status",
    "Tradexcel Leave Allocated by Type",
    "Tradexcel Payroll by Month",
    "Tradexcel Checkins by Day",
)


@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(
        site=os.environ.get("FRAPPE_TEST_SITE", "hrms-v16.localhost"),
        sites_path=os.environ.get("FRAPPE_TEST_SITES_PATH", "/home/sanchita/frappe-bench-v16/sites"),
        force=True,
    )
    frappe.connect()
    frappe.set_user("Administrator")

    # Fixture-only housekeeping: synthetic rename/delete must not enqueue
    # search rebuilds or queue overloads in the shared staging environment.
    original_enqueue = frappe.enqueue

    def fixture_enqueue(method=None, *args, **kwargs):
        if method in (
            "frappe.model.delete_doc.delete_dynamic_links",
            "frappe.utils.global_search.rebuild_for_doctype",
        ):
            return None
        return original_enqueue(method, *args, **kwargs)

    with patch.object(frappe, "enqueue", new=fixture_enqueue):
        yield
    frappe.set_user("Administrator")
    frappe.destroy()


def _called_function_names(func) -> set[str]:
    tree = ast.parse(inspect.getsource(func))
    return {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def _synthetic_backup(
    tmp_path: Path,
    site_name: str = "hrms-v16.localhost",
    sql_content: bytes = b"CREATE TABLE synthetic (id int);\n",
    timestamp: str = "20260930_012059",
):
    site_tag = site_name.replace(".", "_")
    filename = f"{timestamp}-{site_tag}-database.sql.gz"
    backup_file = tmp_path / filename
    with gzip.open(backup_file, "wb") as gz:
        gz.write(sql_content)
    compressed_bytes = backup_file.read_bytes()
    checksum = hashlib.sha256(compressed_bytes).hexdigest()
    return filename, checksum, backup_file


def _synthetic_corrupt_backup(
    tmp_path: Path,
    site_name: str = "hrms-v16.localhost",
    timestamp: str = "20260930_012058",
):
    site_tag = site_name.replace(".", "_")
    filename = f"{timestamp}-{site_tag}-database.sql.gz"
    backup_file = tmp_path / filename
    # File containing arbitrary non-gzip bytes
    corrupt_bytes = b"CORRUPTED_NON_GZIP_CONTENT_BYTES"
    backup_file.write_bytes(corrupt_bytes)
    # Supplied checksum matches the actual bytes on disk
    checksum = hashlib.sha256(corrupt_bytes).hexdigest()
    return filename, checksum, backup_file


def _synthetic_truncated_backup(
    tmp_path: Path,
    site_name: str = "hrms-v16.localhost",
    timestamp: str = "20260930_012057",
):
    site_tag = site_name.replace(".", "_")
    filename = f"{timestamp}-{site_tag}-database.sql.gz"
    backup_file = tmp_path / filename
    # Create valid gzip bytes, then truncate before the 8-byte trailer
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        gz.write(b"CREATE TABLE synthetic (id int);\n" * 50)
    full_bytes = buf.getvalue()
    truncated_bytes = full_bytes[: len(full_bytes) - 10]
    backup_file.write_bytes(truncated_bytes)
    # Supplied checksum matches the actual truncated bytes on disk
    checksum = hashlib.sha256(truncated_bytes).hexdigest()
    return filename, checksum, backup_file


def _synthetic_file(
    tmp_path: Path,
    filename: str,
    content: bytes = b"SYNTHETIC_FILE_CONTENT\n",
):
    file_path = tmp_path / filename
    file_path.write_bytes(content)
    checksum = hashlib.sha256(content).hexdigest()
    return filename, checksum, file_path


def _synthetic_card(
    name,
    *,
    label=None,
    module="Tradexcel HR",
    color="Green",
    background_color=None,
    show_percentage_stats=1,
    dynamic_filters_json=None,
):
    fields = {
        "doctype": "Number Card",
        "label": label or name,
        "type": "Document Type",
        "document_type": "Employee",
        "function": "Count",
        "filters_json": "[]",
        "is_public": 1,
        "color": color,
        "show_percentage_stats": show_percentage_stats,
    }
    if background_color is not None:
        fields["background_color"] = background_color
    if dynamic_filters_json is not None:
        fields["dynamic_filters_json"] = dynamic_filters_json
    if module:
        fields["module"] = module
    doc = frappe.get_doc(fields)
    doc.insert(ignore_permissions=True)
    if doc.name != name:
        frappe.rename_doc("Number Card", doc.name, name, force=True)
    _track_doc("Number Card", name)
    return name


def _card_fingerprint(
    label,
    *,
    color="Green",
    background_color=None,
    show_percentage_stats=1,
    dynamic_filters_json=None,
):
    return {
        "label": label,
        "type": "Document Type",
        "document_type": "Employee",
        "function": "Count",
        "filters_json": "[]",
        "dynamic_filters_json": dynamic_filters_json,
        "filters_config": None,
        "aggregate_function_based_on": None,
        "parent_document_type": None,
        "report_name": None,
        "report_field": None,
        "method": None,
        "is_standard": 0,
        "is_public": 1,
        "color": color,
        "background_color": background_color,
        "show_percentage_stats": show_percentage_stats,
        "stats_time_interval": "Daily",
        "show_full_number": 0,
        "report_function": "Sum",
        "currency": "BDT",
    }


def _synthetic_chart(
    name,
    *,
    chart_name=None,
    module="Tradexcel HR",
    show_values_over_chart=0,
    custom_options=None,
):
    fields = {
        "doctype": "Dashboard Chart",
        "chart_name": chart_name or name,
        "chart_type": "Group By",
        "document_type": "Employee",
        "group_by_type": "Count",
        "group_by_based_on": "department",
        "type": "Bar",
        "filters_json": "[]",
        "is_public": 1,
        "show_values_over_chart": show_values_over_chart,
    }
    if custom_options is not None:
        fields["custom_options"] = custom_options
    if module:
        fields["module"] = module
    doc = frappe.get_doc(fields)
    doc.insert(ignore_permissions=True)
    if doc.name != name:
        frappe.rename_doc("Dashboard Chart", doc.name, name, force=True)
    _track_doc("Dashboard Chart", name)
    return name


def _chart_fingerprint(
    name,
    *,
    show_values_over_chart=0,
    custom_options=None,
):
    return {
        "chart_name": name,
        "chart_type": "Group By",
        "document_type": "Employee",
        "group_by_type": "Count",
        "group_by_based_on": "department",
        "type": "Bar",
        "filters_json": "[]",
        "is_standard": 0,
        "is_public": 1,
        "show_values_over_chart": show_values_over_chart,
        "custom_options": custom_options,
        "dynamic_filters_json": None,
        "color": None,
        "time_interval": "Yearly",
        "timespan": "Last Year",
        "timeseries": 0,
    }


def _synthetic_block(name, html="", script="", style=""):
    doc = frappe.get_doc({
        "doctype": "Custom HTML Block",
        "name": name,
        "html": html,
        "script": script,
        "style": style,
        "private": 1,
    }).insert(ignore_permissions=True)
    _track_doc("Custom HTML Block", doc.name)
    return doc.name


def _cleanup_synthetic():
    """Narrowly scoped cleanup for test-owned synthetic records.

    Eliminates broad wildcards (e.g. 'custom_cf_%') to avoid matching legitimate
    or unrelated custom fields. Tracks and cleans only records and columns created
    by this task's test suite, using supported Frappe deletion APIs.
    Verifies that each resource is actually gone before discarding tracking entries,
    and fails visibly if any tracked or task-owned resource remains.
    """
    failed_docs: list[str] = []
    failed_cols: list[str] = []

    # 1. Clean up explicitly tracked test documents
    for doctype, name in list(_TRACKED_DOCS):
        try:
            if doctype == "Workspace Sidebar Item":
                frappe.db.sql("DELETE FROM `tabWorkspace Sidebar Item` WHERE name=%s", (name,))
                frappe.db.commit()
            elif frappe.db.exists(doctype, name):
                frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
                frappe.db.commit()
        except Exception:
            pass

        # Verify removal before discarding from registry
        still_exists = False
        if doctype == "Workspace Sidebar Item":
            rows = frappe.db.sql("SELECT name FROM `tabWorkspace Sidebar Item` WHERE name=%s", (name,))
            still_exists = bool(rows)
        else:
            still_exists = bool(frappe.db.exists(doctype, name))

        if still_exists:
            failed_docs.append(f"{doctype}: {name}")
        else:
            _TRACKED_DOCS.discard((doctype, name))

    # 2. Clean up explicitly tracked test columns
    for dt, col in list(_TRACKED_COLUMNS):
        table = f"tab{dt}"
        try:
            cols = [c[0] for c in frappe.db.sql(f"DESCRIBE `{table}`")]
            if col in cols:
                frappe.db.commit()
                frappe.db.sql_ddl(f"ALTER TABLE `{table}` DROP COLUMN `{col}`")
                frappe.db.commit()
        except Exception:
            pass

        # Verify removal before discarding from registry
        cols_after = [c[0] for c in frappe.db.sql(f"DESCRIBE `{table}`")]
        if col in cols_after:
            failed_cols.append(f"{table}.{col}")
        else:
            _TRACKED_COLUMNS.discard((dt, col))

    # 3. Task-prefix scoped failsafe cleanup (e.g. for aborted test runs)
    for doctype in ("Number Card", "Dashboard Chart", "Custom HTML Block", "Desktop Icon"):
        for name in frappe.get_all(doctype, filters={"name": ["like", f"{PREFIX}%"]}, pluck="name"):
            try:
                frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
                frappe.db.commit()
            except Exception:
                pass
            if frappe.db.exists(doctype, name):
                failed_docs.append(f"{doctype}: {name}")

    # 4. Clean only exact task-owned custom fields and column
    for cf_name in (SYNTH_LINK_CF_NAME, SYNTH_DYN_CF_NAME):
        if frappe.db.exists("Custom Field", cf_name):
            try:
                frappe.delete_doc("Custom Field", cf_name, force=True, ignore_permissions=True)
                frappe.db.commit()
            except Exception:
                pass
    frappe.db.sql(
        "DELETE FROM `tabCustom Field` WHERE name IN (%s, %s) OR fieldname IN (%s, %s)",
        (SYNTH_LINK_CF_NAME, SYNTH_DYN_CF_NAME, SYNTH_LINK_CF_FIELDNAME, SYNTH_DYN_CF_FIELDNAME),
    )
    frappe.db.commit()

    for cf_name in (SYNTH_LINK_CF_NAME, SYNTH_DYN_CF_NAME):
        if frappe.db.exists("Custom Field", cf_name):
            failed_docs.append(f"Custom Field: {cf_name}")

    dept_cols = [c[0] for c in frappe.db.sql("DESCRIBE `tabDepartment`")]
    if SYNTH_LINK_CF_FIELDNAME in dept_cols:
        frappe.db.commit()
        frappe.db.sql_ddl(f"ALTER TABLE `tabDepartment` DROP COLUMN `{SYNTH_LINK_CF_FIELDNAME}`")
        frappe.db.commit()

    dept_cols_after = [c[0] for c in frappe.db.sql("DESCRIBE `tabDepartment`")]
    if SYNTH_LINK_CF_FIELDNAME in dept_cols_after:
        failed_cols.append(f"tabDepartment.{SYNTH_LINK_CF_FIELDNAME}")

    frappe.db.sql("DELETE FROM `tabWorkspace Sidebar Item` WHERE name LIKE %s", (f"{PREFIX}%",))
    frappe.db.commit()
    remaining_sb = frappe.db.sql("SELECT name FROM `tabWorkspace Sidebar Item` WHERE name LIKE %s", (f"{PREFIX}%",))
    if remaining_sb:
        failed_docs.extend([f"Workspace Sidebar Item: {r[0]}" for r in remaining_sb])

    # 5. Fail visibly on synthetic-cleanup errors
    if failed_docs or failed_cols:
        raise RuntimeError(
            f"Synthetic cleanup failed to remove tracked resources: "
            f"documents={failed_docs}, columns={failed_cols}"
        )




def test_production_allowlist_and_separate_test_injection():
    # Production entry points must not accept arbitrary candidate/fingerprint injection.
    with pytest.raises(TypeError):
        install.remove_retired_dashboard_artifacts(candidates=[])  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        install.remove_retired_dashboard_artifacts(fingerprints={})  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        install.plan_retired_dashboard_artifacts(candidates=[])  # type: ignore[call-arg]

    # Calling dry-run production plan returns canonical eleven in removable
    # (staging has no functional references).
    plan = install.plan_retired_dashboard_artifacts()
    removable_names = {item["name"] for item in plan["removable"]}
    for name in CANONICAL_CARDS:
        assert name in removable_names
    for name in CANONICAL_CHARTS:
        assert name in removable_names

    # Historical aliases are reportable but non-deletable in production.
    # Create a synthetic alias that is in RETIRED_NUMBER_CARDS but not canonical.
    alias_name = "TradeX Active Employees"
    alias_created = False
    if not frappe.db.exists("Number Card", alias_name):
        _synthetic_card(alias_name)
        alias_created = True
    try:
        alias_plan = install.plan_retired_dashboard_artifacts()
        alias_items = {item["name"]: item["reason"] for item in alias_plan["retained"]}
        assert alias_name in alias_items
        assert "historical alias; non-deletable" in alias_items[alias_name]
    finally:
        if alias_created and frappe.db.exists("Number Card", alias_name):
            frappe.delete_doc("Number Card", alias_name, force=True, ignore_permissions=True)


def test_unused_identifiable_artifact_is_removed_and_second_run_is_idempotent(tmp_path, monkeypatch):
    _cleanup_synthetic()
    ref_name, checksum, _ = _synthetic_backup(tmp_path)
    monkeypatch.setattr(install, "_backup_directory", lambda: tmp_path)

    owned = _synthetic_card(f"{PREFIX}-OWNED")
    customized = _synthetic_card(f"{PREFIX}-CUSTOM", color="Red")
    absent = f"{PREFIX}-ABSENT"
    fingerprints = {
        ("Number Card", owned): _card_fingerprint(f"{PREFIX}-OWNED"),
        ("Number Card", customized): _card_fingerprint(f"{PREFIX}-CUSTOM"),  # record is Red
    }
    candidates = (("Number Card", (owned, customized, absent)),)
    try:
        plan = install._plan_retired_dashboard_artifacts_for_tests(candidates, fingerprints)
        assert [item["name"] for item in plan["removable"]] == [owned]
        assert [item["name"] for item in plan["retained"]] == [customized]
        assert "differs from the retired app definition" in plan["retained"][0]["reason"]

        result = install._remove_retired_dashboard_artifacts_for_tests(
            apply=True,
            backup_reference=ref_name,
            backup_checksum=checksum,
            candidates=candidates,
            fingerprints=fingerprints,
        )
        assert result["applied"] is True
        assert [item["name"] for item in result["removed"]] == [owned]
        assert not frappe.db.exists("Number Card", owned)
        assert frappe.db.exists("Number Card", customized), "customized artifact must survive"

        second = install._remove_retired_dashboard_artifacts_for_tests(
            apply=True,
            backup_reference=ref_name,
            backup_checksum=checksum,
            candidates=candidates,
            fingerprints=fingerprints,
        )
        assert second["removed"] == [], "second execution must be harmless"
        assert frappe.db.exists("Number Card", customized)
    finally:
        _cleanup_synthetic()
    assert not frappe.get_all("Number Card", filters={"name": ["like", f"{PREFIX}%"]}, pluck="name")


def test_customizations_survive_including_previously_omitted_properties(tmp_path, monkeypatch):
    _cleanup_synthetic()
    ref_name, checksum, _ = _synthetic_backup(tmp_path)
    monkeypatch.setattr(install, "_backup_directory", lambda: tmp_path)

    foreign = _synthetic_card(f"{PREFIX}-FOREIGN", module=None)
    drift = _synthetic_card(f"{PREFIX}-DRIFT", label="A user renamed this card")
    custom_bg = _synthetic_card(f"{PREFIX}-BG", background_color="#123456")
    custom_pct = _synthetic_card(f"{PREFIX}-PCT", show_percentage_stats=0)
    custom_dyn = _synthetic_card(
        f"{PREFIX}-DYN",
        dynamic_filters_json=json.dumps([["Employee", "department", "=", "Operations", False]]),
    )
    custom_vals = _synthetic_chart(f"{PREFIX}-VALS", show_values_over_chart=1)
    custom_opts = _synthetic_chart(f"{PREFIX}-OPTS", custom_options='{"colors": ["#000"]}')

    fingerprints = {
        ("Number Card", foreign): _card_fingerprint(f"{PREFIX}-FOREIGN"),
        ("Number Card", drift): _card_fingerprint(f"{PREFIX}-DRIFT"),
        ("Number Card", custom_bg): _card_fingerprint(f"{PREFIX}-BG", background_color=None),
        ("Number Card", custom_pct): _card_fingerprint(f"{PREFIX}-PCT", show_percentage_stats=1),
        ("Number Card", custom_dyn): _card_fingerprint(f"{PREFIX}-DYN", dynamic_filters_json=None),
        ("Dashboard Chart", custom_vals): _chart_fingerprint(f"{PREFIX}-VALS", show_values_over_chart=0),
        ("Dashboard Chart", custom_opts): _chart_fingerprint(f"{PREFIX}-OPTS", custom_options=None),
    }
    candidates = (
        ("Number Card", (foreign, drift, custom_bg, custom_pct, custom_dyn)),
        ("Dashboard Chart", (custom_vals, custom_opts)),
    )
    try:
        plan = install._plan_retired_dashboard_artifacts_for_tests(candidates, fingerprints)
        assert plan["removable"] == []
        reasons = {item["name"]: item["reason"] for item in plan["retained"]}
        assert "module is None" in reasons[foreign]
        assert "label" in reasons[drift] and "differs" in reasons[drift]
        assert "background_color" in reasons[custom_bg] and "differs" in reasons[custom_bg]
        assert "show_percentage_stats" in reasons[custom_pct] and "differs" in reasons[custom_pct]
        assert "dynamic_filters_json" in reasons[custom_dyn] and "differs" in reasons[custom_dyn]
        assert "show_values_over_chart" in reasons[custom_vals] and "differs" in reasons[custom_vals]
        assert "custom_options" in reasons[custom_opts] and "differs" in reasons[custom_opts]

        result = install._remove_retired_dashboard_artifacts_for_tests(
            apply=True,
            backup_reference=ref_name,
            backup_checksum=checksum,
            candidates=candidates,
            fingerprints=fingerprints,
        )
        assert result["removed"] == []
        assert frappe.db.exists("Number Card", foreign)
        assert frappe.db.exists("Number Card", drift)
        assert frappe.db.exists("Number Card", custom_bg)
        assert frappe.db.exists("Number Card", custom_pct)
        assert frappe.db.exists("Number Card", custom_dyn)
        assert frappe.db.exists("Dashboard Chart", custom_vals)
        assert frappe.db.exists("Dashboard Chart", custom_opts)
    finally:
        _cleanup_synthetic()


def test_referenced_artifact_is_retained_across_native_and_custom_surfaces(tmp_path, monkeypatch):
    _cleanup_synthetic()
    initial_dept_cols = {c[0] for c in frappe.db.sql("DESCRIBE `tabDepartment`")}
    had_orphan_col = "custom_cf_12319_card" in initial_dept_cols

    ref_name, checksum, _ = _synthetic_backup(tmp_path)
    monkeypatch.setattr(install, "_backup_directory", lambda: tmp_path)

    card_block = _synthetic_card(f"{PREFIX}-REF-BLOCK")
    card_desktop = _synthetic_card(f"{PREFIX}-REF-DESKTOP")
    card_sidebar = _synthetic_card(f"{PREFIX}-REF-SIDEBAR")
    card_custom_field = _synthetic_card(f"{PREFIX}-REF-CUSTFIELD")

    # 1. Custom HTML Block
    _synthetic_block(f"{PREFIX}-BLK", html=f"<p>{card_block}</p>")

    # 2. Desktop Icon link
    icon_name = f"{PREFIX}-ICON"
    frappe.get_doc({
        "doctype": "Desktop Icon",
        "label": icon_name,
        "link_type": "External",
        "link": f"/app/number-card/{card_desktop}",
        "standard": 0,
    }).insert(ignore_permissions=True)
    _track_doc("Desktop Icon", icon_name)

    # 3. Workspace Sidebar Item (url / route_options / filters)
    sidebar_item_name = f"{PREFIX}-SIDEBAR-ITEM"
    frappe.db.sql(
        """
        insert into `tabWorkspace Sidebar Item`
        (name, parent, parenttype, parentfield, link_type, url, route_options, filters)
        values (%s, 'HR', 'Workspace Sidebar', 'items', 'URL', %s, %s, %s)
        """,
        (
            sidebar_item_name,
            f"/app/number-card/{card_sidebar}",
            f'{{"card": "{card_sidebar}"}}',
            f'[["Number Card", "name", "=", "{card_sidebar}"]]',
        ),
    )
    _track_doc("Workspace Sidebar Item", sidebar_item_name)

    # 4. Custom Field linking to Number Card
    col_name = SYNTH_LINK_CF_FIELDNAME
    cf_doc = frappe.get_doc({
        "doctype": "Custom Field",
        "dt": SYNTH_LINK_CF_DT,
        "fieldname": col_name,
        "label": "Synthetic Linked Card",
        "fieldtype": "Link",
        "options": "Number Card",
    }).insert(ignore_permissions=True)
    _track_doc("Custom Field", cf_doc.name)
    _track_column(SYNTH_LINK_CF_DT, col_name)

    # Put a reference value in the table
    dept = frappe.db.get_value("Department", {"company": "Tradexcel Ceramics Ltd."}, "name")
    frappe.db.sql(f"update `tabDepartment` set `{col_name}`=%s where name=%s", (card_custom_field, dept))

    fingerprints = {
        ("Number Card", card_block): _card_fingerprint(f"{PREFIX}-REF-BLOCK"),
        ("Number Card", card_desktop): _card_fingerprint(f"{PREFIX}-REF-DESKTOP"),
        ("Number Card", card_sidebar): _card_fingerprint(f"{PREFIX}-REF-SIDEBAR"),
        ("Number Card", card_custom_field): _card_fingerprint(f"{PREFIX}-REF-CUSTFIELD"),
    }
    candidates = (("Number Card", (card_block, card_desktop, card_sidebar, card_custom_field)),)

    try:
        plan = install._plan_retired_dashboard_artifacts_for_tests(candidates, fingerprints)
        assert plan["removable"] == []
        retained_map = {item["name"]: item["reason"] for item in plan["retained"]}
        for card in (card_block, card_desktop, card_sidebar, card_custom_field):
            assert card in retained_map
            assert "functional reference(s) still exist" in retained_map[card]

        result = install._remove_retired_dashboard_artifacts_for_tests(
            apply=True,
            backup_reference=ref_name,
            backup_checksum=checksum,
            candidates=candidates,
            fingerprints=fingerprints,
        )
        assert result["removed"] == []
        assert frappe.db.exists("Number Card", card_block)
        assert frappe.db.exists("Number Card", card_desktop)
        assert frappe.db.exists("Number Card", card_sidebar)
        assert frappe.db.exists("Number Card", card_custom_field)
    finally:
        if dept:
            frappe.db.sql(f"update `tabDepartment` set `{col_name}`=NULL where name=%s", (dept,))
        frappe.delete_doc("Custom Field", cf_doc.name, force=True, ignore_permissions=True)
        frappe.db.commit()
        frappe.db.sql_ddl(f"alter table `tabDepartment` drop column `{col_name}`")
        _cleanup_synthetic()

        # Enforce synthetic database-schema cleanup: verify absence of CF, column, and references
        assert not frappe.db.exists("Custom Field", cf_doc.name)
        assert not frappe.db.exists("Custom Field", {"fieldname": col_name})
        cols_now = {c[0] for c in frappe.db.sql("DESCRIBE `tabDepartment`")}
        assert col_name not in cols_now, f"Synthetic column {col_name} was not dropped from tabDepartment"
        assert ("custom_cf_12319_card" in cols_now) == had_orphan_col, (
            f"Historical column custom_cf_12319_card state mutated (was present={had_orphan_col}, now={'custom_cf_12319_card' in cols_now})"
        )
        assert not frappe.db.exists("Desktop Icon", icon_name)
        assert not frappe.db.exists("Custom HTML Block", f"{PREFIX}-BLK")
        assert len(frappe.db.sql("select name from `tabWorkspace Sidebar Item` where name=%s", (sidebar_item_name,))) == 0
        assert not frappe.db.exists("Number Card", card_block)
        assert not frappe.db.exists("Number Card", card_desktop)
        assert not frappe.db.exists("Number Card", card_sidebar)
        assert not frappe.db.exists("Number Card", card_custom_field)



def test_unresolvable_custom_dynamic_link_fails_closed():
    _cleanup_synthetic()
    card = _synthetic_card(f"{PREFIX}-DYNLINK")
    fingerprints = {("Number Card", card): _card_fingerprint(f"{PREFIX}-DYNLINK")}
    candidates = (("Number Card", (card,)),)

    # Insert a synthetic Custom Field of type Dynamic Link directly in DB
    cf_name = SYNTH_DYN_CF_NAME
    col_name = SYNTH_DYN_CF_FIELDNAME
    frappe.db.sql(
        """
        insert into `tabCustom Field` (name, dt, fieldname, label, fieldtype, options)
        values (%s, %s, %s, 'Synthetic Dynamic Link', 'Dynamic Link', 'department_name')
        """,
        (cf_name, SYNTH_DYN_CF_DT, col_name),
    )
    frappe.db.commit()
    _track_doc("Custom Field", cf_name)

    try:
        with pytest.raises(RuntimeError, match="Unresolvable custom Dynamic Link field"):
            install._custom_reference_surfaces()

        plan = install._plan_retired_dashboard_artifacts_for_tests(candidates, fingerprints)
        assert plan["removable"] == []
        assert "reference surfaces could not be inspected" in plan["retained"][0]["reason"]
    finally:
        if frappe.db.exists("Custom Field", cf_name):
            frappe.delete_doc("Custom Field", cf_name, force=True, ignore_permissions=True)
        frappe.db.sql("delete from `tabCustom Field` where name=%s", (cf_name,))
        frappe.db.commit()
        _cleanup_synthetic()
        assert not frappe.db.exists("Custom Field", cf_name)


def test_inaccessible_reference_surface_fails_closed(tmp_path, monkeypatch):
    _cleanup_synthetic()
    ref_name, checksum, _ = _synthetic_backup(tmp_path)
    monkeypatch.setattr(install, "_backup_directory", lambda: tmp_path)

    card = _synthetic_card(f"{PREFIX}-OPAQUE")
    fingerprints = {("Number Card", card): _card_fingerprint(f"{PREFIX}-OPAQUE")}
    candidates = (("Number Card", (card,)),)

    def broken_surface(_name):
        raise RuntimeError("synthetic reference surface failure")

    monkeypatch.setattr(install, "_functional_reference_count", broken_surface)
    try:
        plan = install._plan_retired_dashboard_artifacts_for_tests(candidates, fingerprints)
        assert plan["removable"] == []
        assert "could not be inspected" in plan["retained"][0]["reason"]
        result = install._remove_retired_dashboard_artifacts_for_tests(
            apply=True,
            backup_reference=ref_name,
            backup_checksum=checksum,
            candidates=candidates,
            fingerprints=fingerprints,
        )
        assert result["removed"] == []
        assert frappe.db.exists("Number Card", card), "uninspectable candidate must be retained"
    finally:
        _cleanup_synthetic()


def test_dry_run_and_ordinary_migration_never_delete(monkeypatch):
    _cleanup_synthetic()
    card = _synthetic_card(f"{PREFIX}-DRYRUN")
    fingerprints = {("Number Card", card): _card_fingerprint(f"{PREFIX}-DRYRUN")}
    candidates = (("Number Card", (card,)),)
    deletions = []
    monkeypatch.setattr(install.frappe, "delete_doc", lambda *args, **kwargs: deletions.append(args))
    try:
        plan = install._plan_retired_dashboard_artifacts_for_tests(candidates, fingerprints)
        assert plan["removable"] == [{"doctype": "Number Card", "name": card}]
        dry = install._remove_retired_dashboard_artifacts_for_tests(
            candidates=candidates, fingerprints=fingerprints
        )
        assert dry["applied"] is False and dry["dry_run"] is True
        assert deletions == [], "planning/dry-run must not delete anything"
        assert frappe.db.exists("Number Card", card)

        for installer in (install.after_install, install.after_migrate):
            called = _called_function_names(installer)
            assert "remove_retired_dashboard_artifacts" not in called
            assert "plan_retired_dashboard_artifacts" not in called
    finally:
        monkeypatch.undo()
        _cleanup_synthetic()


def test_backup_preflight_verification(tmp_path, monkeypatch):
    monkeypatch.setattr(install, "_backup_directory", lambda: tmp_path)
    site = frappe.local.site or "hrms-v16.localhost"
    site_tag = site.replace(".", "_")
    valid_name, valid_checksum, valid_file = _synthetic_backup(tmp_path, site_name=site)

    # 1. Empty reference throws
    with pytest.raises(frappe.ValidationError, match="reference from BACKUPS.md is required"):
        install.verify_backup_preflight("")

    # 2. Path traversal throws (both relative and subdirectory)
    with pytest.raises(frappe.ValidationError, match="must be a pure filename"):
        install.verify_backup_preflight(f"../{valid_name}", valid_checksum)
    with pytest.raises(frappe.ValidationError, match="must be a pure filename"):
        install.verify_backup_preflight(f"subdir/{valid_name}", valid_checksum)

    # 3. Wrong site identity throws
    wrong_site_name = "20260930_012059-wrong_site_name-database.sql.gz"
    _synthetic_file(tmp_path, wrong_site_name)
    with pytest.raises(frappe.ValidationError, match="not a supported full database backup archive"):
        install.verify_backup_preflight(wrong_site_name, valid_checksum)

    # 4. Ambiguous substring site match is rejected
    ambig_name = f"20260930_012059-prefix_{site_tag}-database.sql.gz"
    _synthetic_file(tmp_path, ambig_name)
    with pytest.raises(frappe.ValidationError, match="not a supported full database backup archive"):
        install.verify_backup_preflight(ambig_name, valid_checksum)

    # 5. Arbitrary .txt file rejected (even if supplied with valid matching SHA-256)
    txt_name, txt_chk, _ = _synthetic_file(tmp_path, f"notes-{site_tag}.txt")
    with pytest.raises(frappe.ValidationError, match="not a supported full database backup archive"):
        install.verify_backup_preflight(txt_name, txt_chk)

    # 6. Non-database .tar files archive rejected (even with valid matching SHA-256)
    tar_name, tar_chk, _ = _synthetic_file(tmp_path, f"20260930_012059-{site_tag}-files.tar")
    with pytest.raises(frappe.ValidationError, match="not a supported full database backup archive"):
        install.verify_backup_preflight(tar_name, tar_chk)

    # 7. Non-database site config backup .json rejected (even with valid matching SHA-256)
    json_name, json_chk, _ = _synthetic_file(tmp_path, f"20260930_012059-{site_tag}-site_config_backup.json")
    with pytest.raises(frappe.ValidationError, match="not a supported full database backup archive"):
        install.verify_backup_preflight(json_name, json_chk)

    # 8. Uncompressed .sql rejected (even with valid matching SHA-256)
    sql_name, sql_chk, _ = _synthetic_file(tmp_path, f"20260930_012059-{site_tag}-database.sql")
    with pytest.raises(frappe.ValidationError, match="not a supported full database backup archive"):
        install.verify_backup_preflight(sql_name, sql_chk)

    # 9. Partial database backup is rejected (even if intact gzip with matching SHA-256)
    partial_name = f"20260930_012059-{site_tag}-partial-database.sql.gz"
    partial_file = tmp_path / partial_name
    with gzip.open(partial_file, "wb") as gz:
        gz.write(b"CREATE TABLE partial_backup (id int);\n")
    partial_chk = hashlib.sha256(partial_file.read_bytes()).hexdigest()
    with pytest.raises(frappe.ValidationError, match="not a supported full database backup archive"):
        install.verify_backup_preflight(partial_name, partial_chk)

    # 10. Non-existent file throws
    missing_name = f"20260930_012050-{site_tag}-database.sql.gz"
    with pytest.raises(frappe.ValidationError, match="does not exist or is empty"):
        install.verify_backup_preflight(missing_name, valid_checksum)

    # 11. Empty file throws
    empty_name, empty_chk, _ = _synthetic_file(tmp_path, f"20260930_012051-{site_tag}-database.sql.gz", content=b"")
    with pytest.raises(frappe.ValidationError, match="does not exist or is empty"):
        install.verify_backup_preflight(empty_name, empty_chk)

    # 12. Missing checksum throws
    with pytest.raises(frappe.ValidationError, match="verified SHA-256 checksum from BACKUPS.md is required"):
        install.verify_backup_preflight(valid_name, "")

    # 13. Checksum mismatch throws
    with pytest.raises(frappe.ValidationError, match="checksum verification failed"):
        install.verify_backup_preflight(valid_name, "0000000000000000000000000000000000000000000000000000000000000000")

    # 14. Corrupt gzip archive (with matching supplied SHA-256) throws
    corrupt_name, corrupt_checksum, _ = _synthetic_corrupt_backup(tmp_path, site_name=site)
    with pytest.raises(frappe.ValidationError, match="failed gzip integrity validation"):
        install.verify_backup_preflight(corrupt_name, corrupt_checksum)

    # 15. Truncated gzip archive (with matching supplied SHA-256) throws
    truncated_name, truncated_checksum, _ = _synthetic_truncated_backup(tmp_path, site_name=site)
    with pytest.raises(frappe.ValidationError, match="failed gzip integrity validation"):
        install.verify_backup_preflight(truncated_name, truncated_checksum)

    # 16. Valid database backup archive and checksum succeeds
    verified_path = install.verify_backup_preflight(valid_name, valid_checksum)
    assert verified_path == valid_file

    # 17. Non-System Manager is rejected by remove_retired_dashboard_artifacts
    monkeypatch.setattr(install.frappe.session, "user", "txux013p05-nonadmin@example.test", raising=False)
    monkeypatch.setattr(install.frappe, "get_roles", lambda: ["HR User"])
    with pytest.raises(frappe.PermissionError, match="System Manager"):
        install.remove_retired_dashboard_artifacts(
            apply=True, backup_reference=valid_name, backup_checksum=valid_checksum
        )


def test_allowlist_and_fingerprints_cover_only_the_reviewed_canonical_artifacts():
    expected = {("Number Card", name) for name in CANONICAL_CARDS}
    expected |= {("Dashboard Chart", name) for name in CANONICAL_CHARTS}
    assert set(install.RETIRED_ARTIFACT_FINGERPRINTS) == expected

    # Historical aliases and prototype duplicates stay in the allowlist for
    # reporting, but have no fingerprint and are therefore retained.
    assert ("Number Card", "TradeX Active Employees") not in install.RETIRED_ARTIFACT_FINGERPRINTS
    assert ("Dashboard Chart", "TradeX Checkins by Day") not in install.RETIRED_ARTIFACT_FINGERPRINTS

    # Native referenced cards are not candidates and never appear in a plan.
    native = (
        "Expense Claims (This Month)",
        "Number of Employees on Leave (This Month)",
        "Number of Employees on Leave (Today)",
    )
    assert not set(native).intersection(install.RETIRED_NUMBER_CARDS)
    plan = install.plan_retired_dashboard_artifacts()
    planned = {item["name"] for item in plan["removable"] + plan["retained"]}
    assert not set(native).intersection(planned)

    # Historical Version/UI Version rows are not reference surfaces.
    surfaces = {table for table, _column in install.RETIRED_ARTIFACT_REFERENCE_SURFACES}
    assert not any("Version" in table for table in surfaces)


def test_source_tree_has_no_retired_artifact_json_or_creation_paths():
    app_root = Path(__file__).resolve().parents[1]
    module_root = app_root / "tradexcel_hr"
    assert not list(module_root.glob("dashboard_chart/*/*.json"))
    assert not list(module_root.glob("number_card/*/*.json"))
    install_source = (app_root / "install.py").read_text()
    for retired_helper in (
        "def ensure_number_cards",
        "def ensure_dashboard_charts",
        "def rename_legacy_dashboard_charts",
        "def rename_legacy_number_cards",
        "def remove_orphaned_dashboard_records",
    ):
        assert retired_helper not in install_source

    # Fingerprints are verification data only; installer entry points never
    # create or delete through them (no direct or indirect call).
    for installer in (install.after_install, install.after_migrate):
        called = _called_function_names(installer)
        assert "RETIRED_ARTIFACT_FINGERPRINTS" not in inspect.getsource(installer)
        assert "remove_retired_dashboard_artifacts" not in called
        assert "plan_retired_dashboard_artifacts" not in called


def test_cleanup_synthetic_fails_visibly_on_unremovable_resource(monkeypatch):
    synth_name = f"{PREFIX}-FAIL-DOC"
    _TRACKED_DOCS.add(("Number Card", synth_name))

    orig_exists = frappe.db.exists

    def mock_exists(dt, name=None):
        if dt == "Number Card" and name == synth_name:
            return True
        return orig_exists(dt, name)

    monkeypatch.setattr(frappe.db, "exists", mock_exists)
    try:
        with pytest.raises(RuntimeError, match="Synthetic cleanup failed to remove tracked resources"):
            _cleanup_synthetic()
        # Verify the tracking entry was retained rather than silently cleared
        assert ("Number Card", synth_name) in _TRACKED_DOCS
    finally:
        monkeypatch.undo()
        _TRACKED_DOCS.discard(("Number Card", synth_name))


def test_cleanup_synthetic_fails_visibly_on_unremovable_column(monkeypatch):
    synth_col = f"custom_{TASK_TAG.lower()}_fail_col"
    _TRACKED_COLUMNS.add(("Department", synth_col))

    orig_sql = frappe.db.sql

    def mock_sql(query, *args, **kwargs):
        if "DESCRIBE `tabDepartment`" in str(query):
            res = orig_sql(query, *args, **kwargs)
            return list(res) + [(synth_col,)]
        return orig_sql(query, *args, **kwargs)

    monkeypatch.setattr(frappe.db, "sql", mock_sql)
    monkeypatch.setattr(frappe.db, "sql_ddl", lambda query: None)
    try:
        with pytest.raises(RuntimeError, match="Synthetic cleanup failed to remove tracked resources"):
            _cleanup_synthetic()
        # Verify the column tracking entry was retained rather than silently cleared
        assert ("Department", synth_col) in _TRACKED_COLUMNS
    finally:
        monkeypatch.undo()
        _TRACKED_COLUMNS.discard(("Department", synth_col))
