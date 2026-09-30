"""TXUX-260930-013-P01: explicit retired-artifact cleanup contract tests.

Synthetic records only; the real staging records are never deleted here. The
plan/apply functions under test are the same ones the deployment checkpoint
uses, driven with an explicit synthetic allowlist and fingerprints.
"""
import ast
import inspect
import os
from pathlib import Path
from unittest.mock import patch

import frappe
import pytest

from tradex_hr import install

PREFIX = "TXUX013P01-SYNTH"
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
    # search rebuilds into the shared staging queue.
    original_enqueue = frappe.enqueue

    def fixture_enqueue(method=None, *args, **kwargs):
        if method == "frappe.model.delete_doc.delete_dynamic_links":
            if str(kwargs.get("name", "")).startswith(PREFIX):
                return None
        if method == "frappe.utils.global_search.rebuild_for_doctype":
            if kwargs.get("doctype") in ("Number Card", "Dashboard Chart", "Custom HTML Block"):
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


def _synthetic_card(name, *, label=None, module="Tradexcel HR", color="Green"):
    fields = {
        "doctype": "Number Card",
        "label": label or name,
        "type": "Document Type",
        "document_type": "Employee",
        "function": "Count",
        "filters_json": "[]",
        "is_public": 1,
        "color": color,
    }
    if module:
        fields["module"] = module
    doc = frappe.get_doc(fields)
    doc.insert(ignore_permissions=True)
    if doc.name != name:
        frappe.rename_doc("Number Card", doc.name, name, force=True)
    return name


def _card_fingerprint(label, *, color="Green"):
    return {
        "label": label, "type": "Document Type", "document_type": "Employee",
        "function": "Count", "filters_json": "[]", "is_standard": 0, "is_public": 1,
        "color": color,
    }


def _synthetic_block(name, html):
    return frappe.get_doc({
        "doctype": "Custom HTML Block",
        "name": name,
        "html": html,
        "private": 1,
    }).insert(ignore_permissions=True).name


def _cleanup_synthetic():
    for doctype in ("Number Card", "Dashboard Chart", "Custom HTML Block"):
        for name in frappe.get_all(doctype, filters={"name": ["like", f"{PREFIX}%"]}, pluck="name"):
            frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
    frappe.db.commit()


def test_unused_identifiable_artifact_is_removed_and_second_run_is_idempotent():
    _cleanup_synthetic()
    owned = _synthetic_card(f"{PREFIX}-OWNED")
    customized = _synthetic_card(f"{PREFIX}-CUSTOM", color="Red")
    absent = f"{PREFIX}-ABSENT"
    fingerprints = {
        ("Number Card", owned): _card_fingerprint(f"{PREFIX}-OWNED"),
        ("Number Card", customized): _card_fingerprint(f"{PREFIX}-CUSTOM"),  # record is Red
    }
    candidates = (("Number Card", (owned, customized, absent)),)
    try:
        plan = install.plan_retired_dashboard_artifacts(candidates, fingerprints)
        assert [item["name"] for item in plan["removable"]] == [owned]
        assert [item["name"] for item in plan["retained"]] == [customized]
        assert "differs from the retired app definition" in plan["retained"][0]["reason"]

        result = install.remove_retired_dashboard_artifacts(
            apply=True, backup_reference="TXUX013P01 synthetic BACKUPS.md row",
            candidates=candidates, fingerprints=fingerprints,
        )
        assert result["applied"] is True
        assert [item["name"] for item in result["removed"]] == [owned]
        assert not frappe.db.exists("Number Card", owned)
        assert frappe.db.exists("Number Card", customized), "customized artifact must survive"

        second = install.remove_retired_dashboard_artifacts(
            apply=True, backup_reference="TXUX013P01 synthetic BACKUPS.md row",
            candidates=candidates, fingerprints=fingerprints,
        )
        assert second["removed"] == [], "second execution must be harmless"
        assert frappe.db.exists("Number Card", customized)
    finally:
        _cleanup_synthetic()
    assert not frappe.get_all("Number Card", filters={"name": ["like", f"{PREFIX}%"]}, pluck="name")


def test_same_module_but_customized_and_foreign_records_survive():
    _cleanup_synthetic()
    foreign = _synthetic_card(f"{PREFIX}-FOREIGN", module=None)
    customized = _synthetic_card(f"{PREFIX}-DRIFT", label="A user renamed this card")
    fingerprints = {
        ("Number Card", foreign): _card_fingerprint(f"{PREFIX}-FOREIGN"),
        ("Number Card", customized): _card_fingerprint(f"{PREFIX}-DRIFT"),
    }
    candidates = (("Number Card", (foreign, customized)),)
    try:
        plan = install.plan_retired_dashboard_artifacts(candidates, fingerprints)
        assert plan["removable"] == []
        reasons = {item["name"]: item["reason"] for item in plan["retained"]}
        assert "module is None" in reasons[foreign]
        assert "label" in reasons[customized] and "differs" in reasons[customized]
        result = install.remove_retired_dashboard_artifacts(
            apply=True, backup_reference="TXUX013P01 synthetic row",
            candidates=candidates, fingerprints=fingerprints,
        )
        assert result["removed"] == []
        assert frappe.db.exists("Number Card", foreign)
        assert frappe.db.exists("Number Card", customized)
    finally:
        _cleanup_synthetic()


def test_referenced_artifact_is_retained():
    _cleanup_synthetic()
    card = _synthetic_card(f"{PREFIX}-REFERENCED")
    block = _synthetic_block(f"{PREFIX}-BLOCK", f"<p>See {card} for the current headcount.</p>")
    fingerprints = {("Number Card", card): _card_fingerprint(f"{PREFIX}-REFERENCED")}
    candidates = (("Number Card", (card,)),)
    try:
        plan = install.plan_retired_dashboard_artifacts(candidates, fingerprints)
        assert plan["removable"] == []
        assert plan["retained"][0]["name"] == card
        assert "functional reference(s) still exist" in plan["retained"][0]["reason"]
        result = install.remove_retired_dashboard_artifacts(
            apply=True, backup_reference="TXUX013P01 synthetic row",
            candidates=candidates, fingerprints=fingerprints,
        )
        assert result["removed"] == []
        assert frappe.db.exists("Number Card", card)
    finally:
        _cleanup_synthetic()


def test_inaccessible_reference_surface_fails_closed(monkeypatch):
    _cleanup_synthetic()
    card = _synthetic_card(f"{PREFIX}-OPAQUE")
    fingerprints = {("Number Card", card): _card_fingerprint(f"{PREFIX}-OPAQUE")}
    candidates = (("Number Card", (card,)),)

    def broken_surface(_name):
        raise RuntimeError("synthetic reference surface failure")

    monkeypatch.setattr(install, "_functional_reference_count", broken_surface)
    try:
        plan = install.plan_retired_dashboard_artifacts(candidates, fingerprints)
        assert plan["removable"] == []
        assert "could not be inspected" in plan["retained"][0]["reason"]
        result = install.remove_retired_dashboard_artifacts(
            apply=True, backup_reference="TXUX013P01 synthetic row",
            candidates=candidates, fingerprints=fingerprints,
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
        plan = install.plan_retired_dashboard_artifacts(candidates, fingerprints)
        assert plan["removable"] == [{"doctype": "Number Card", "name": card}]
        dry = install.remove_retired_dashboard_artifacts(candidates=candidates, fingerprints=fingerprints)
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


def test_apply_requires_backup_reference_and_system_manager(monkeypatch):
    _cleanup_synthetic()
    card = _synthetic_card(f"{PREFIX}-GATED")
    fingerprints = {("Number Card", card): _card_fingerprint(f"{PREFIX}-GATED")}
    candidates = (("Number Card", (card,)),)
    try:
        with pytest.raises(frappe.ValidationError, match="verified backup reference"):
            install.remove_retired_dashboard_artifacts(apply=True, candidates=candidates, fingerprints=fingerprints)
        assert frappe.db.exists("Number Card", card)

        monkeypatch.setattr(install.frappe.session, "user", "txux013p01-nonadmin@example.test", raising=False)
        with pytest.raises(frappe.PermissionError, match="System Manager"):
            install.remove_retired_dashboard_artifacts(
                apply=True, backup_reference="TXUX013P01 synthetic row",
                candidates=candidates, fingerprints=fingerprints,
            )
        assert frappe.db.exists("Number Card", card)
    finally:
        monkeypatch.undo()
        _cleanup_synthetic()


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
    module_root = Path(frappe.get_app_path("tradex_hr", "tradexcel_hr"))
    assert not list(module_root.glob("dashboard_chart/*/*.json"))
    assert not list(module_root.glob("number_card/*/*.json"))
    install_source = Path(frappe.get_app_path("tradex_hr", "install.py")).read_text()
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
