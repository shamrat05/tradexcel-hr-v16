#!/usr/bin/env python3
"""Dependency-free source wiring audit for the renamed Frappe app.

Checks paths, app-owned metadata and hook targets without importing Frappe or
starting a database. This is not a substitute for a bench integration test.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "workforce_suite"
MODULE = APP / "workforce_suite"
HOOKS = APP / "hooks.py"
BAD = []


def fail(why: str) -> None:
    BAD.append(why)


def scrub(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def module_path(name: str) -> Path | None:
    path = ROOT.joinpath(*name.split("."))
    for candidate in (path.with_suffix(".py"), path / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def _source_hook_assignments() -> dict:
    tree = ast.parse(HOOKS.read_text(encoding="utf-8"), filename=str(HOOKS))
    result = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                result[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                pass
    return result


def _iter_strings(item):
    if isinstance(item, str):
        yield item
    elif isinstance(item, (list, tuple, set)):
        for member in item:
            yield from _iter_strings(member)
    elif isinstance(item, dict):
        for member in item.values():
            yield from _iter_strings(member)


hooks = _source_hook_assignments()
for hook in (
    "extend_doctype_class", "doc_events", "has_permission",
    "permission_query_conditions", "after_install", "after_migrate",
    "before_job", "scheduler_events",
):
    for value in _iter_strings(hooks.get(hook, {})):
        if not value.startswith("workforce_suite."):
            continue
        module, sep, member = value.rpartition(".")
        path = module_path(module)
        if not sep or not path:
            fail(f"Hook {hook}: missing Python module for {value}")
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        defined = {
            n.name for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }
        # Hook callables and mixins are directly declared in their own modules.
        if member not in defined:
            fail(f"Hook {hook}: missing member {member} in {path.relative_to(ROOT)}")

for key, folder in (
    ("doctype_js", "js"), ("doctype_list_js", "js"),
):
    for value in _iter_strings(hooks.get(key, {})):
        path = APP / "public" / value
        if not path.is_file():
            fail(f"{key}: missing asset {value}")

for key, folder in (
    ("app_include_css", "css"), ("app_include_js", "js"),
):
    for value in _iter_strings(hooks.get(key, [])):
        if not (APP / "public" / folder / value).is_file():
            fail(f"{key}: missing asset {folder}/{value}")

for app in hooks.get("add_to_apps_screen", []):
    url = app.get("logo", "")
    prefix = "/assets/workforce_suite/"
    if url.startswith(prefix) and not (APP / "public" / url[len(prefix):]).is_file():
        fail(f"Missing app logo {url}")

for doctype in (MODULE / "doctype").glob("*/*.json"):
    payload = json.loads(doctype.read_text(encoding="utf-8"))
    if payload.get("doctype") != "DocType":
        continue
    if payload.get("name") != doctype.stem.replace("_", " ").title() and scrub(payload.get("name", "")) != doctype.stem:
        fail(f"DocType name/file disagreement: {doctype}")
    if payload.get("module") != "Workforce Suite":
        fail(f"Wrong app module in DocType {doctype}")
    if not doctype.with_suffix(".py").is_file():
        fail(f"No controller file for {doctype}")

for report in (MODULE / "report").glob("*/*.json"):
    payload = json.loads(report.read_text(encoding="utf-8"))
    if payload.get("doctype") != "Report":
        continue
    if scrub(payload.get("name", "")) != report.stem:
        fail(f"Report name/file disagreement: {report}")
    if payload.get("module") != "Workforce Suite":
        fail(f"Wrong app module in report {report}")

if BAD:
    print("White-label wiring check failed:")
    for failure in BAD[:100]:
        print(" -", failure)
    raise SystemExit(1)

print("White-label wiring verified: hooks, assets, DocType controllers and report paths")
