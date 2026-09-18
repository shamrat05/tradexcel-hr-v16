"""Guard: destructive one-off scripts must not live inside the importable app.

Three scripts were found sitting in `tradex_hr/tradexcel_hr/` while being
git-ignored, so they were invisible to version control yet importable as
`tradex_hr.tradexcel_hr.<name>` by any code path or REPL:

  cleanup_false_import_employees.py   deleted/merged employee records
  source_staff_salary.py              wrote salary values
  purge_cancelled_salary_slips.py     purged cancelled slips

Anyone (or any agent) with a bench python shell could have triggered a data
rewrite by importing them. They now live in `sync/quarantine/`, outside the app.

This test fails if a similar script reappears in the package.
"""

from __future__ import annotations

import ast
import pathlib

PACKAGE = pathlib.Path(__file__).resolve().parents[1] / "tradexcel_hr"

# Names that must never exist inside the importable package.
FORBIDDEN_STEMS = {
    "cleanup_false_import_employees",
    "source_staff_salary",
    "purge_cancelled_salary_slips",
}

# A module is treated as a destructive one-off if it calls any of these at module
# scope or inside a function.
DESTRUCTIVE_CALLS = {
    "delete_doc",
    "delete_permanently",
    "cancel",
    "truncate",
}


def _called_names(tree: ast.AST) -> set[str]:
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Attribute):
                names.add(fn.attr)
            elif isinstance(fn, ast.Name):
                names.add(fn.id)
    return names


def test_forbidden_one_off_scripts_absent_from_package() -> None:
    present = sorted(
        p.stem for p in PACKAGE.rglob("*.py") if p.stem in FORBIDDEN_STEMS
    )
    assert not present, (
        f"destructive one-off scripts are back inside the importable package: {present}. "
        f"Keep them in sync/quarantine/, outside the app."
    )


def test_no_module_scope_destructive_calls_in_package() -> None:
    """A destructive call at import time would fire simply by importing the module."""
    offenders = []
    for path in PACKAGE.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue
        for node in tree.body:                      # module scope only
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    fn = sub.func
                    name = fn.attr if isinstance(fn, ast.Attribute) else \
                        (fn.id if isinstance(fn, ast.Name) else None)
                    if name in DESTRUCTIVE_CALLS and isinstance(node, ast.Expr):
                        offenders.append(f"{path.relative_to(PACKAGE)}:{sub.lineno} {name}()")
    assert not offenders, (
        "destructive calls at module scope run on import and must move inside a "
        f"function guarded by __main__: {offenders}"
    )
