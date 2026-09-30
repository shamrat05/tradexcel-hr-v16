"""TXUX-260930-013: isolated cleanup-contract tests for retired HR UI artifacts.

Synthetic records only; the real staging records are never deleted here. The
migration path is exercised through the same function used by ``after_migrate``
with explicitly supplied synthetic names.
"""
import os
from pathlib import Path
from unittest.mock import patch

import frappe
import pytest

from tradex_hr.install import (
    RETIRED_ARTIFACTS,
    RETIRED_DASHBOARD_CHARTS,
    RETIRED_NUMBER_CARDS,
    remove_retired_dashboard_artifacts,
)

PREFIX = "TXUX013-SYNTH"


@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(
        site=os.environ.get("FRAPPE_TEST_SITE", "hrms-v16.localhost"),
        sites_path=os.environ.get("FRAPPE_TEST_SITES_PATH", "/home/sanchita/frappe-bench-v16/sites"),
        force=True,
    )
    frappe.connect()
    frappe.set_user("Administrator")

    # Fixture-only housekeeping: the shared staging queue is already over the
    # framework's soft limit, so synthetic rename/delete must not enqueue
    # search rebuilds. Only these two synthetic-housekeeping methods and
    # doctypes are suppressed; every other enqueue path stays untouched.
    original_enqueue = frappe.enqueue

    def fixture_enqueue(method=None, *args, **kwargs):
        if method == "frappe.model.delete_doc.delete_dynamic_links":
            if str(kwargs.get("name", "")).startswith(PREFIX):
                return None
        if method == "frappe.utils.global_search.rebuild_for_doctype":
            if kwargs.get("doctype") in ("Number Card", "Dashboard Chart"):
                return None
        return original_enqueue(method, *args, **kwargs)

    with patch.object(frappe, "enqueue", new=fixture_enqueue):
        yield
    frappe.set_user("Administrator")
    frappe.destroy()


def _synthetic_card(name, module):
    fields = {
        "doctype": "Number Card",
        "label": f"Synthetic {name}",
        "type": "Document Type",
        "document_type": "Employee",
        "function": "Count",
        "filters_json": "[]",
        "is_public": 1,
    }
    if module:
        fields["module"] = module
    doc = frappe.get_doc(fields)
    doc.insert(ignore_permissions=True)
    if doc.name != name:
        frappe.rename_doc("Number Card", doc.name, name, force=True)
    return name


def _synthetic_chart(name, module):
    fields = {
        "doctype": "Dashboard Chart",
        "chart_name": name,
        "chart_type": "Count",
        "document_type": "Employee",
        "based_on": "creation",
        "timeseries": 1,
        "timespan": "Last Year",
        "time_interval": "Monthly",
        "type": "Line",
        "is_public": 1,
        "filters_json": "[]",
    }
    if module:
        fields["module"] = module
    doc = frappe.get_doc(fields)
    doc.insert(ignore_permissions=True)
    if doc.name != name:
        frappe.rename_doc("Dashboard Chart", doc.name, name, force=True)
    return name


def _cleanup_synthetic():
    for doctype in ("Number Card", "Dashboard Chart"):
        for name in frappe.get_all(doctype, filters={"name": ["like", f"{PREFIX}%"]}, pluck="name"):
            frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
    frappe.db.commit()


def test_cleanup_removes_only_app_owned_records_and_is_idempotent():
    _cleanup_synthetic()
    owned_card = _synthetic_card(f"{PREFIX}-OWNED-CARD", "Tradexcel HR")
    user_card = _synthetic_card(f"{PREFIX}-USER-CARD", None)
    owned_chart = _synthetic_chart(f"{PREFIX}-OWNED-CHART", "Tradexcel HR")
    user_chart = _synthetic_chart(f"{PREFIX}-USER-CHART", None)
    frappe.db.commit()
    try:
        retired = (
            ("Number Card", (owned_card, user_card)),
            ("Dashboard Chart", (owned_chart, user_chart)),
        )
        first = remove_retired_dashboard_artifacts(retired=retired)
        assert set(first["removed"]) == {
            f"Number Card:{owned_card}",
            f"Dashboard Chart:{owned_chart}",
        }
        assert set(first["retained"]) == {
            f"Number Card:{user_card} (module=None)",
            f"Dashboard Chart:{user_chart} (module=None)",
        }
        assert not frappe.db.exists("Number Card", owned_card)
        assert frappe.db.exists("Number Card", user_card)
        assert not frappe.db.exists("Dashboard Chart", owned_chart)
        assert frappe.db.exists("Dashboard Chart", user_chart)

        second = remove_retired_dashboard_artifacts(retired=retired)
        assert second["removed"] == []
        assert set(second["retained"]) == set(first["retained"])
    finally:
        _cleanup_synthetic()
    assert not frappe.get_all("Number Card", filters={"name": ["like", f"{PREFIX}%"]})
    assert not frappe.get_all("Dashboard Chart", filters={"name": ["like", f"{PREFIX}%"]})


def test_cleanup_default_allowlist_is_the_reviewed_exact_set():
    assert dict(RETIRED_ARTIFACTS) == {
        "Number Card": RETIRED_NUMBER_CARDS,
        "Dashboard Chart": RETIRED_DASHBOARD_CHARTS,
    }
    assert len(RETIRED_NUMBER_CARDS) == len(set(RETIRED_NUMBER_CARDS)) == 24
    assert len(RETIRED_DASHBOARD_CHARTS) == len(set(RETIRED_DASHBOARD_CHARTS)) == 14


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


def test_native_number_cards_are_outside_the_allowlist():
    """Native/company cards with stored references are outside the allowlist."""
    native = (
        "Expense Claims (This Month)",
        "Number of Employees on Leave (This Month)",
        "Number of Employees on Leave (Today)",
    )
    assert not set(native).intersection(RETIRED_NUMBER_CARDS)
    assert not set(native).intersection(RETIRED_DASHBOARD_CHARTS)
