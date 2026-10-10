#!/usr/bin/env python3
"""Deterministically turn the client-branded app tree into Workforce Suite.

This tool changes source code and paths only. It does NOT touch a Frappe site
or database. Existing sites must be migrated with ``migrate_legacy_site.py``
before the first ``bench migrate`` on the renamed app.

Run from the repository root:

    python scripts/genericize_to_workforce_suite.py --check
    python scripts/genericize_to_workforce_suite.py --apply

The only files allowed to retain legacy identifiers after conversion are the
legacy migration/verification tools and the white-label migration runbook,
because they need to recognize old database identifiers.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".py", ".js", ".cjs", ".json", ".css", ".html", ".md", ".txt",
    ".toml", ".yaml", ".yml", ".csv", ".sh", ".svg", ".ini", ".cfg",
}
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache"}
LEGACY_ALLOWED = {
    Path("scripts/genericize_to_workforce_suite.py"),
    Path("scripts/migrate_legacy_site.py"),
    Path("docs/white_label_migration.md"),
}

LITERAL_REPLACEMENTS = (
    ("shamrat05/tradexcel-hr-v16", "shamrat05/workforce-suite"),
    ("tradexcel-hr-v16", "workforce-suite"),
    ("tradexcel-hr", "workforce-suite"),
    ("Tradexcel Ceramics Ltd.", "Example Company A"),
    ("Tradexcel Ceramics Ltd", "Example Company A"),
    ("Elegance Footwear Ltd.", "Example Company B"),
    ("Elegance Footwear Ltd", "Example Company B"),
    ("TCL Daily Wage", "Example Daily Wage"),
    ("TCL Standard", "Example Monthly"),
    ("EFL Standard", "Example Secondary Monthly"),
    ("TCL Factory", "Example Factory"),
    ("hr@tradexcel.com", "support@example.com"),
    ("tradexcel_hr", "workforce_suite"),
    ("tradex_hr", "workforce_suite"),
    ("Tradexcel HR", "Workforce Suite"),
    ("Tradex HR", "Workforce Suite"),
    ("TRADEXCEL", "WORKFORCE"),
    ("Tradexcel", "Workforce"),
    ("tradexcel", "workforce"),
    ("TRADEX", "WORKFORCE"),
    ("TradeX", "Workforce"),
    ("Tradex", "Workforce"),
    ("tradex", "workforce"),
)
PATH_REPLACEMENTS = (
    ("tradexcel_hr", "workforce_suite"),
    ("tradex_hr", "workforce_suite"),
    ("tradexcel", "workforce"),
    ("tradex", "workforce"),
)
FORBIDDEN = re.compile(r"tradexcel|tradex|\bTCL\b|\bEFL\b", re.IGNORECASE)


def _iter_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        files.append(path)
    return sorted(files)


def _is_text(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES or path.name in {
        "MANIFEST.in", "Procfile", "LICENSE", ".gitignore", ".gitattributes"
    }


def transform_text(text: str) -> str:
    for old, new in LITERAL_REPLACEMENTS:
        text = text.replace(old, new)
    text = re.sub(r"\bTCL\b", "COMPANY_A", text)
    text = re.sub(r"\bEFL\b", "COMPANY_B", text)
    return text


def transform_relpath(rel: Path) -> Path:
    value = rel.as_posix()
    for old, new in PATH_REPLACEMENTS:
        value = value.replace(old, new)
    return Path(value)


def plan() -> list[tuple[Path, Path, bool]]:
    changes: list[tuple[Path, Path, bool]] = []
    for old_path in _iter_files():
        rel = old_path.relative_to(ROOT)
        new_rel = transform_relpath(rel)
        content_changes = False
        if _is_text(old_path) and rel not in LEGACY_ALLOWED:
            text = old_path.read_text(encoding="utf-8", errors="strict")
            content_changes = transform_text(text) != text
        if new_rel != rel or content_changes:
            changes.append((rel, new_rel, content_changes))
    return changes


def scan_forbidden() -> list[tuple[Path, int, str]]:
    violations: list[tuple[Path, int, str]] = []
    for path in _iter_files():
        rel = path.relative_to(ROOT)
        if rel in LEGACY_ALLOWED or not _is_text(path):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line_no, line in enumerate(text.splitlines(), 1):
            if FORBIDDEN.search(line):
                violations.append((rel, line_no, line.strip()[:240]))
    return violations


def apply() -> None:
    changes = plan()
    targets: dict[Path, Path] = {}
    for old_rel, new_rel, _ in changes:
        previous = targets.get(new_rel)
        if previous and previous != old_rel:
            raise SystemExit(f"path collision: {previous} and {old_rel} -> {new_rel}")
        targets[new_rel] = old_rel

    for old_rel, new_rel, _ in changes:
        old_path = ROOT / old_rel
        new_path = ROOT / new_rel
        mode = stat.S_IMODE(old_path.stat().st_mode)
        data = old_path.read_bytes()
        if _is_text(old_path) and old_rel not in LEGACY_ALLOWED:
            data = transform_text(data.decode("utf-8")).encode("utf-8")
        if new_path != old_path:
            new_path.parent.mkdir(parents=True, exist_ok=True)
        new_path.write_bytes(data)
        os.chmod(new_path, mode)
        if new_path != old_path:
            old_path.unlink()

    for path in sorted((p for p in ROOT.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        try:
            path.rmdir()
        except OSError:
            pass

    violations = scan_forbidden()
    if violations:
        print("White-label conversion completed, but legacy identifiers remain:", file=sys.stderr)
        for rel, line_no, line in violations[:200]:
            print(f"  {rel}:{line_no}: {line}", file=sys.stderr)
        raise SystemExit(2)
    print(f"White-label conversion applied to {len(changes)} files.")


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply:
        apply()
        return 0
    changes = plan()
    violations = scan_forbidden()
    print(f"planned file changes: {len(changes)}")
    print(f"legacy identifier occurrences outside migration allowlist: {len(violations)}")
    for rel, line_no, line in violations[:100]:
        print(f"{rel}:{line_no}: {line}")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
