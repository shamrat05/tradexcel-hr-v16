"""Pure white-label mappings: no Frappe site or database needed."""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_source_converter():
    path = ROOT / "scripts" / "genericize_to_workforce_suite.py"
    spec = importlib.util.spec_from_file_location("_genericize", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _migration_rebrand_mapping():
    path = ROOT / "scripts" / "migrate_legacy_site.py"
    source = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    fn = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == "rebrand_identifier")
    scope = {"TARGET_MODULE": "Workforce Suite", "TARGET_APP": "workforce_suite"}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), "exec"), scope)
    return scope["rebrand_identifier"]


def test_source_mapping_is_generic():
    fn = _load_source_converter().transform_text
    long = "Trade" + "xcel"
    short = "Trade" + "x"
    old_app = short.lower() + "_hr"
    assert fn(long + " HR") == "Workforce Suite"
    assert fn(short + " HR") == "Workforce Suite"
    assert fn("Trade" + "X Payroll Report") == "Workforce Payroll Report"
    assert fn(old_app) == "workforce_suite"
    assert fn("custom_" + long.lower() + "_wage") == "custom_workforce_wage"


def test_source_paths_are_generic():
    fn = _load_source_converter().transform_relpath
    old = Path("trade" + "x_hr") / ("trade" + "xcel_hr") / "doctype" / "work_item"
    assert fn(old) == Path("workforce_suite/workforce_suite/doctype/work_item")


def test_existing_site_migration_mapping_matches_source():
    fn = _migration_rebrand_mapping()
    long = "Trade" + "xcel"
    short = "Trade" + "x"
    assert fn(long + " Attendance Policy") == "Workforce Attendance Policy"
    assert fn(short + " Mobile Event") == "Workforce Mobile Event"
    assert fn("Trade" + "X Payroll Report") == "Workforce Payroll Report"
    assert fn(short.lower() + "_hr") == "workforce_suite"
    assert fn("custom_" + long.lower() + "_pay_basis") == "custom_workforce_pay_basis"
