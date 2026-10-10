"""Static, dependency-free product naming and metadata contracts."""
from __future__ import annotations

import json
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "workforce_suite"
ALLOWED_LEGACY = {
    "scripts/genericize_to_workforce_suite.py",
    "scripts/migrate_legacy_site.py",
    "docs/white_label_migration.md",
}
TEXT_SUFFIXES = {".py", ".js", ".cjs", ".json", ".css", ".html", ".md",
                 ".txt", ".toml", ".yaml", ".yml", ".csv", ".sh", ".svg"}
EXCLUDED_PARTS = {".git", ".pytest_cache", "__pycache__", "node_modules", ".venv"}
# Assemble the legacy names to avoid tripping the scanner on its own source.
LEGACY_PATTERN = re.compile("trade" + "x(?:cel)?|" + "t" + "cl\\b|" + "e" + "fl\\b", re.IGNORECASE)


def test_white_label_app_identifiers():
    assert (APP / "modules.txt").read_text(encoding="utf-8").strip() == "Workforce Suite"
    assert (APP / "workforce_suite" / "doctype" / "workforce_biometric_device" / "workforce_biometric_device.json").is_file()
    assert (APP / "workforce_suite" / "doctype" / "workforce_employee_biometric" / "workforce_employee_biometric.json").is_file()
    assert (APP / "workforce_suite" / "doctype" / "workforce_payroll_policy" / "workforce_payroll_policy.json").is_file()


def test_fresh_workspace_install_keeps_required_module_metadata():
    install_source = (ROOT / "workforce_suite" / "install.py").read_text(encoding="utf-8")
    workspace = json.loads(
        (APP / "workforce_suite" / "workspace" / "workforce_suite" / "workforce_suite.json")
        .read_text(encoding="utf-8")
    )
    assert 'doc.module = "Workforce Suite"' in install_source
    assert workspace["module"] == "Workforce Suite"


def test_no_customer_branded_source_or_paths():
    violations = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if any(part in EXCLUDED_PARTS for part in rel.parts):
            continue
        name = rel.as_posix()
        if name in ALLOWED_LEGACY:
            continue
        if LEGACY_PATTERN.search(name):
            violations.append(f"legacy file path: {name}")
        if p.suffix.lower() not in TEXT_SUFFIXES and p.name not in {"MANIFEST.in", ".gitignore"}:
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if LEGACY_PATTERN.search(line):
                violations.append(f"{name}:{i}: {line[:120]}")
    assert not violations, "\\n".join(violations[:100])


@pytest.mark.parametrize("subdir,expected_doctype", [
    ("workforce_biometric_device", "Workforce Biometric Device"),
    ("workforce_employee_biometric", "Workforce Employee Biometric"),
    ("workforce_payroll_policy", "Workforce Payroll Policy"),
])
def test_doctype_module_metadata(subdir, expected_doctype):
    path = APP / "workforce_suite" / "doctype" / subdir / f"{subdir}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["name"] == expected_doctype
    assert data["module"] == "Workforce Suite"
