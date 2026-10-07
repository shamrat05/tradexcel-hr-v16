from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_script(name: str):
    path = REPO_ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(f"_white_label_{name}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_source_codemod_maps_legacy_identifiers_to_generic_names():
    tool = _load_script("genericize_to_workforce_suite.py")

    old_brand = "Trade" + "xcel"
    old_short_brand = "Trade" + "x"
    old_app = old_short_brand.lower() + "_hr"
    old_module = old_brand + " HR"

    assert tool.transform_text(old_module) == "Workforce Suite"
    assert tool.transform_text(old_app) == "workforce_suite"
    assert tool.transform_text(f"{old_brand} Payroll Policy") == "Workforce Payroll Policy"
    assert tool.transform_text(f"custom_{old_short_brand.lower()}_pay_basis") == "custom_workforce_pay_basis"


def test_source_codemod_maps_paths_to_generic_package():
    tool = _load_script("genericize_to_workforce_suite.py")
    old_package = "trade" + "x_hr"
    old_module = "trade" + "xcel_hr"

    path = Path(old_package) / old_module / "doctype" / "work_item"
    assert tool.transform_relpath(path) == Path("workforce_suite/workforce_suite/doctype/work_item")


def test_database_migration_identifier_mapping_matches_source_codemod():
    migration = _load_script("migrate_legacy_site.py")

    old_brand = "Trade" + "xcel"
    old_short_brand = "Trade" + "x"
    assert migration.rebrand_identifier(old_brand + " Attendance Policy") == "Workforce Attendance Policy"
    assert migration.rebrand_identifier(old_short_brand + " Mobile Event") == "Workforce Mobile Event"
    assert migration.rebrand_identifier(old_short_brand.lower() + "_hr") == "workforce_suite"
    assert migration.rebrand_identifier("custom_" + old_brand.lower() + "_review_status") == "custom_workforce_review_status"
