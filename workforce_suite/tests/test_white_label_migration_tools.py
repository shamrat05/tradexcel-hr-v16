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


def test_migration_workspace_slug_matches_installed_source():
    fn = _migration_rebrand_mapping()
    assert fn("trade" + "xcel-hr") == "workforce-suite"
    assert fn("trade" + "x-hr") == "workforce-suite"


def _migration_function(name, **scope):
    path = ROOT / "scripts" / "migrate_legacy_site.py"
    source = ast.parse(path.read_text(), filename=str(path))
    fn = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), "exec"), scope)
    return scope[name]


def test_single_document_count_never_queries_a_missing_physical_table():
    from types import SimpleNamespace
    calls = []
    fake = SimpleNamespace(get_meta=lambda _: SimpleNamespace(issingle=True),
                           db=SimpleNamespace(count=lambda dt: calls.append(dt)))
    count = _migration_function("_count", frappe=fake, _exists=lambda _: True)
    assert count("Example Settings") == 1
    assert not calls


def test_workspace_ownership_accepts_app_with_blank_module_and_excludes_customer_records():
    from types import SimpleNamespace
    fake = SimpleNamespace(get_meta=lambda _: SimpleNamespace(has_field=lambda field: field in {"module", "app"}),
        get_all=lambda dt, filters, pluck: ["owned-home"] if "app" in filters else [])
    names = _migration_function("_metadata_names", frappe=fake, _exists=lambda _: True,
                               LEGACY_MODULE="old-module", LEGACY_APP="old-app")
    assert names("Workspace", set()) == ["owned-home"]


def test_native_rename_arguments_keep_validation_except_preflight_owned_module():
    from types import SimpleNamespace
    calls = []
    fake = SimpleNamespace(db=SimpleNamespace(exists=lambda dt, name: name == "old"))
    rename = _migration_function("_rename_one", frappe=fake, rename_doc=lambda *a, **k: calls.append((a, k)))
    rename("Module Def", "old", "new")
    rename("DocType", "old", "new")
    assert calls[0][1]["validate"] is False
    assert calls[1][1]["validate"] is True
    assert all(call[1]["rebuild_search"] is False for call in calls)


def test_existing_target_is_rejected_before_native_rename():
    from types import SimpleNamespace
    import pytest
    calls = []
    def reject(message):
        raise ValueError(message)
    fake = SimpleNamespace(db=SimpleNamespace(exists=lambda *a: True), throw=reject)
    rename = _migration_function("_rename_one", frappe=fake, rename_doc=lambda *a, **k: calls.append(a))
    with pytest.raises(ValueError, match="already exists"):
        rename("DocType", "old", "new")
    assert not calls


def test_import_reference_migration_copies_existing_metadata_without_inventing_values(monkeypatch):
    from types import SimpleNamespace
    import sys
    from types import ModuleType
    captured = []
    custom_field = ModuleType("frappe.custom.doctype.custom_field.custom_field")
    custom_field.create_custom_fields = lambda definitions, **kwargs: captured.append((definitions, kwargs))
    monkeypatch.setitem(sys.modules, custom_field.__name__, custom_field)
    old = "trade" + "x_source_employee_id"
    definition = {"name": "Employee-" + old, "doctype": "Custom Field", "dt": "Employee", "fieldname": old,
                  "fieldtype": "Data", "label": "Historical import reference", "read_only": 1, "insert_after": "employee_name", "default": None}
    field = SimpleNamespace(fieldtype="Data", as_dict=lambda: dict(definition))
    fake = SimpleNamespace(get_meta=lambda *a, **k: SimpleNamespace(get_field=lambda _: None),
        db=SimpleNamespace(get_value=lambda *a, **k: definition["name"]), get_doc=lambda *a: field)
    preserve = _migration_function("_ensure_import_reference_field", frappe=fake, rebrand_identifier=_migration_rebrand_mapping())
    preserve()
    new = captured[0][0]["Employee"][0]
    assert new["fieldname"] == "workforce_source_employee_id"
    assert new["label"] == definition["label"] and new["read_only"] == 1 and new["default"] is None
    assert "name" not in new and "dt" not in new
    assert captured[0][1] == {"update": False}


def test_import_reference_migration_refuses_incompatible_legacy_customization():
    from types import SimpleNamespace
    import pytest
    def reject(message):
        raise ValueError(message)
    fake = SimpleNamespace(get_meta=lambda *a, **k: SimpleNamespace(get_field=lambda _: None),
        db=SimpleNamespace(get_value=lambda *a, **k: "synthetic-field"),
        get_doc=lambda *a: SimpleNamespace(fieldtype="Currency"), throw=reject)
    preserve = _migration_function("_ensure_import_reference_field", frappe=fake)
    with pytest.raises(ValueError, match="Data field"):
        preserve()


def test_packaged_desktop_logo_migration_preserves_customizations_and_retries(tmp_path):
    from types import SimpleNamespace
    packaged = tmp_path / "workforce-hr.svg"
    packaged.write_text("<svg/>")
    old_logo = "/assets/" + "trade" + "x_hr/images/" + "trade" + "x-hr.svg"
    saves = []
    docs = {
        "Workforce Suite": SimpleNamespace(app="workforce_suite", logo_url=old_logo),
        "Customized": SimpleNamespace(app="workforce_suite", logo_url="/files/customer-logo.svg"),
        "Unrelated": SimpleNamespace(app="other_app", logo_url=old_logo),
    }
    for name, doc in docs.items():
        doc.save = lambda name=name, **kwargs: saves.append((name, kwargs, flags.in_import))
    flags = SimpleNamespace(in_import=False)
    fake = SimpleNamespace(flags=flags, db=SimpleNamespace(exists=lambda *args: True),
        get_doc=lambda dt, name: docs[name], get_app_path=lambda *args: str(packaged))
    migrate = _migration_function("_migrate_owned_desktop_logos", frappe=fake, Path=Path, TARGET_APP="workforce_suite")
    snapshot = {"metadata_map": {"Desktop Icon": {"old": "Workforce Suite", "old-custom": "Customized"}}}
    assert migrate(snapshot) == ["Workforce Suite"]
    assert docs["Workforce Suite"].logo_url == "/assets/workforce_suite/images/workforce-hr.svg"
    assert docs["Customized"].logo_url == "/files/customer-logo.svg"
    assert docs["Unrelated"].logo_url == old_logo
    assert migrate(snapshot) == [] and len(saves) == 1
    assert saves == [("Workforce Suite", {"ignore_permissions": True}, True)]
    assert flags.in_import is False


def test_desktop_logo_migration_refuses_missing_asset_or_changed_ownership(tmp_path):
    from types import SimpleNamespace
    import pytest
    def reject(message):
        raise ValueError(message)
    old_logo = "/assets/" + "trade" + "x_hr/images/" + "trade" + "x-hr.svg"
    doc = SimpleNamespace(app="other_app", logo_url=old_logo)
    fake = SimpleNamespace(db=SimpleNamespace(exists=lambda *args: True), get_doc=lambda *args: doc,
        throw=reject, get_app_path=lambda *args: str(tmp_path / "missing.svg"))
    migrate = _migration_function("_migrate_owned_desktop_logos", frappe=fake, Path=Path, TARGET_APP="workforce_suite")
    snapshot = {"metadata_map": {"Desktop Icon": {"old": "Workforce Suite"}}}
    with pytest.raises(ValueError, match="ownership changed"):
        migrate(snapshot)
    doc.app = "workforce_suite"
    with pytest.raises(ValueError, match="logo is missing"):
        migrate(snapshot)
    assert doc.logo_url == old_logo
