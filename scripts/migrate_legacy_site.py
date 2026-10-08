#!/usr/bin/env python3
"""Two-phase migration from the legacy branded app to Workforce Suite.

This file intentionally contains legacy identifiers so an existing site can be
upgraded. Runtime/product code should not contain those identifiers.

Run from the bench root after a verified fresh backup:

  env/bin/python apps/workforce_suite/scripts/migrate_legacy_site.py \
      --site <site> --phase prepare --yes --backup-file <verified-backup.sql.gz>
  bench --site <site> migrate
  env/bin/python apps/workforce_suite/scripts/migrate_legacy_site.py \
      --site <site> --phase finalize --yes
  env/bin/python apps/workforce_suite/scripts/migrate_legacy_site.py \
      --site <site> --phase verify
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

import frappe
from frappe.installer import update_site_config
from frappe.model.utils.rename_field import rename_field
from frappe.model.rename_doc import rename_doc

LEGACY_APP = "tradex_hr"
TARGET_APP = "workforce_suite"
LEGACY_MODULE = "Tradexcel HR"
TARGET_MODULE = "Workforce Suite"
SNAPSHOT_FILE = "workforce_suite_legacy_migration_snapshot.json"

BUSINESS_DOCTYPES = (
    "Company",
    "Employee",
    "Branch",
    "Department",
    "Designation",
    "Employee Checkin",
    "Attendance",
    "Attendance Request",
    "Leave Application",
    "Leave Allocation",
    "Salary Structure",
    "Salary Structure Assignment",
    "Payroll Entry",
    "Salary Slip",
    "Additional Salary",
    "Shift Type",
    "Shift Assignment",
    "Employee Separation",
    "Full and Final Statement",
    "Job Applicant",
)

RENAMABLE_METADATA_DOCTYPES = (
    "DocType",
    "Role",
    "Report",
    "Page",
    "Workspace",
    "Custom HTML Block",
    "Desktop Icon",
    "Workspace Sidebar",
    "Dashboard Chart",
    "Number Card",
    "Workflow",
    "Workflow State",
    "Patch Log",
)

LEGACY_TOKEN = re.compile(r"tradexcel|tradex", re.IGNORECASE)


def rebrand_identifier(value: str) -> str:
    # Workspace/page slugs are identifiers, not customer-entered labels.
    value = value.replace("tradexcel-hr", "workforce-suite").replace("tradex-hr", "workforce-suite")
    replacements = (
        ("Tradexcel HR", TARGET_MODULE),
        ("Tradex HR", TARGET_MODULE),
        ("TradeX HR", TARGET_MODULE),
        ("tradexcel_hr", TARGET_APP),
        ("tradex_hr", TARGET_APP),
        ("Tradexcel", "Workforce"),
        ("TradeX", "Workforce"),
        ("Tradex", "Workforce"),
        ("tradexcel", "workforce"),
        ("tradex", "workforce"),
        ("TRADEXCEL", "WORKFORCE"),
        ("TRADEX", "WORKFORCE"),
    )
    result = value
    for old, new in replacements:
        result = result.replace(old, new)
    return result


def _exists(doctype: str) -> bool:
    return bool(frappe.db.exists("DocType", doctype))


def _count(doctype: str) -> int | None:
    if not _exists(doctype):
        return None
    # A Single has one logical document stored in tabSingles, not tab<DocType>.
    if frappe.get_meta(doctype).issingle:
        return 1
    return int(frappe.db.count(doctype))


def _snapshot_path() -> Path:
    return Path(frappe.get_site_path("private", SNAPSHOT_FILE))


def _write_snapshot(payload: dict) -> None:
    path = _snapshot_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.chmod(path, 0o600)


def _read_snapshot() -> dict:
    path = _snapshot_path()
    if not path.exists():
        frappe.throw(f"Migration snapshot not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _business_counts() -> dict[str, int]:
    return {dt: count for dt in BUSINESS_DOCTYPES if (count := _count(dt)) is not None}


def _legacy_app_doctypes() -> list[str]:
    # Module ownership, not a brand-shaped name, determines what belongs to
    # this app. A customer may legitimately own documents with branded names.
    return sorted(frappe.get_all("DocType", filters={"module": LEGACY_MODULE}, pluck="name"))


def _old_name(name: str) -> str:
    """Known product-name inverse used only for exact app-owned inventories."""
    return name.replace("Workforce Suite", LEGACY_MODULE).replace("Workforce", "Tradexcel")


def _metadata_names(doctype: str, legacy_app_doctypes: set[str]) -> list[str]:
    if not _exists(doctype):
        return []
    if doctype == "DocType":
        return sorted(legacy_app_doctypes)

    if doctype == "Role":
        from workforce_suite.role_setup import ROLE_NAMES
        return sorted(name for current in ROLE_NAMES
                      if (name := _old_name(current)) and frappe.db.exists("Role", name))

    if doctype in {"Workflow", "Workflow State"}:
        from workforce_suite.approval_setup import WORKFLOWS
        current = set(WORKFLOWS) if doctype == "Workflow" else {
            row[0] for workflow in WORKFLOWS.values() for row in workflow["states"]
        }
        return sorted(name for generic in current
                      if (name := _old_name(generic)) and frappe.db.exists(doctype, name))

    if doctype == "Custom HTML Block":
        old = "Tradexcel Work Needing Attention"
        return [old] if frappe.db.exists(doctype, old) else []

    if doctype == "Patch Log":
        return sorted(name for name in frappe.get_all(doctype, pluck="name")
                      if name.startswith((LEGACY_APP + ".", "tradexcel_hr.")))

    # Retired prototypes/number cards are not authoritative app data. Leave
    # historical and customer-owned artifacts alone for manual review.
    if doctype in {"Dashboard Chart", "Number Card"}:
        return []

    meta = frappe.get_meta(doctype)
    # Workspace can have an app owner while its optional module is blank.
    # Union both explicit ownership fields; never infer ownership from a label.
    owned = set()
    if meta.has_field("module"):
        owned.update(frappe.get_all(doctype, filters={"module": LEGACY_MODULE}, pluck="name"))
    if meta.has_field("app"):
        owned.update(frappe.get_all(doctype, filters={"app": LEGACY_APP}, pluck="name"))
    return sorted(owned)


def _rename_plan(legacy_doctypes: list[str]) -> dict[str, dict[str, str]]:
    plan = {}
    if frappe.db.exists("Module Def", LEGACY_MODULE):
        plan["Module Def"] = {LEGACY_MODULE: TARGET_MODULE}
    for doctype in RENAMABLE_METADATA_DOCTYPES:
        names = _metadata_names(doctype, set(legacy_doctypes))
        mapped = {old: rebrand_identifier(old) for old in names}
        plan[doctype] = {old: new for old, new in mapped.items() if old != new}
    return plan


def _verify_backup(backup_file: str, expected_sha256: str | None = None) -> dict:
    path = Path(backup_file).expanduser().resolve()
    if not path.is_file() or path.stat().st_size < 1024:
        frappe.throw(f"A nonempty, verified database backup file is required: {path}")
    if not path.name.endswith(".sql.gz"):
        frappe.throw("Use a database *.sql.gz backup from bench backup")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    if expected_sha256 and digest.hexdigest().lower() != expected_sha256.lower():
        frappe.throw("Backup SHA-256 does not match the provided checksum")
    try:
        with gzip.open(path, "rb") as handle:
            for _ in iter(lambda: handle.read(1024 * 1024), b""):
                pass
    except (EOFError, OSError) as exc:
        frappe.throw(f"Backup gzip integrity check failed: {exc}")
    return {"path": str(path), "sha256": digest.hexdigest(), "bytes": path.stat().st_size}


def _verify_bench_package() -> None:
    apps_txt = Path.cwd() / "apps.txt"
    if not apps_txt.is_file() or TARGET_APP not in apps_txt.read_text().splitlines():
        frappe.throw("sites/apps.txt must register workforce_suite before prepare")
    if importlib.util.find_spec(TARGET_APP) is None:
        frappe.throw("Python cannot import workforce_suite; install the editable app in the bench first")



def _rename_one(doctype: str, old: str, new: str) -> None:
    if old == new or not frappe.db.exists(doctype, old):
        return
    if frappe.db.exists(doctype, new):
        frappe.throw(f"Cannot migrate {doctype} {old!r}: target {new!r} already exists")
    rename_doc(
        doctype,
        old,
        new,
        force=True,
        ignore_permissions=True,
        show_alert=False,
        rebuild_search=False,
        # The exact source-owned module is preflight-validated. v16 otherwise
        # permits renaming only custom modules; retain standard ownership.
        validate=doctype != "Module Def",
    )


def _switch_installed_app() -> None:
    apps = list(frappe.get_installed_apps())
    if TARGET_APP in apps and LEGACY_APP not in apps:
        update_site_config("installed_apps", apps)
        return
    if LEGACY_APP not in apps:
        frappe.throw(f"Legacy app is not installed: {apps}")
    apps = [TARGET_APP if app == LEGACY_APP else app for app in apps]
    apps = list(dict.fromkeys(apps))
    frappe.db.set_global("installed_apps", json.dumps(apps))
    update_site_config("installed_apps", apps)


def _update_app_fields() -> None:
    for doctype in ("Desktop Icon", "Workspace Sidebar", "Sidebar", "Dock", "Workspace"):
        if not _exists(doctype):
            continue
        meta = frappe.get_meta(doctype)
        if meta.has_field("app"):
            frappe.db.set_value(doctype, {"app": LEGACY_APP}, "app", TARGET_APP, update_modified=False)
    if frappe.db.exists("Module Def", TARGET_MODULE):
        meta = frappe.get_meta("Module Def")
        if meta.has_field("app_name"):
            frappe.db.set_value("Module Def", TARGET_MODULE, "app_name", TARGET_APP, update_modified=False)


def preflight(
    backup_file: str,
    expected_sha256: str | None = None,
    *,
    show_report: bool = True,
) -> tuple[list[str], dict, dict]:
    """Read-only validation before any DDL, settings or data changes."""
    _verify_bench_package()
    apps = frappe.get_installed_apps()
    if LEGACY_APP not in apps or TARGET_APP in apps:
        frappe.throw(f"Expected only the old app installed in site DB; got {apps}")
    backup = _verify_backup(backup_file, expected_sha256)
    legacy_doctypes = _legacy_app_doctypes()
    if not legacy_doctypes:
        frappe.throw("No app-owned legacy DocTypes found; refusing to migrate a possibly wrong site")
    plan = _rename_plan(legacy_doctypes)
    for doctype, mapping in plan.items():
        destinations = list(mapping.values())
        if len(set(destinations)) != len(destinations):
            frappe.throw(f"Duplicate rename targets in {doctype}: {mapping}")
        for old, new in mapping.items():
            if frappe.db.exists(doctype, old) and frappe.db.exists(doctype, new):
                frappe.throw(f"Migration conflict: {doctype} {old!r} -> existing {new!r}")
    if show_report:
        print(json.dumps({
            "status": "READ_ONLY_PREFLIGHT_PASS",
            "backup": backup,
            "installed_apps": apps,
            "app_owned_doctypes": len(legacy_doctypes),
            "metadata_renames": {doctype: len(mapping) for doctype, mapping in plan.items()},
            "business_counts": _business_counts(),
        }, indent=2))
    return legacy_doctypes, plan, backup


def _migrate_workflow_state_values() -> list[dict]:
    """Translate only known app workflow-state values on native business documents.

    Workflow State is a linked metadata document, but an HRMS document's
    `workflow_state` is a Data field, not a Link. Frappe's metadata rename
    does not update those values automatically.
    """
    from workforce_suite.approval_setup import WORKFLOWS

    changes: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for workflow in WORKFLOWS.values():
        doctype = workflow["document_type"]
        if not _exists(doctype):
            continue
        meta = frappe.get_meta(doctype)
        if not meta.has_field("workflow_state"):
            continue
        for state in workflow["states"]:
            new = state[0]
            old = _old_name(new)
            key = (doctype, old)
            if old == new or key in seen:
                continue
            seen.add(key)
            count = int(frappe.db.count(doctype, {"workflow_state": old}))
            if count:
                frappe.db.set_value(
                    doctype, {"workflow_state": old},
                    "workflow_state", new, update_modified=False,
                )
                if frappe.db.count(doctype, {"workflow_state": old}):
                    frappe.throw(f"Could not translate {doctype}.workflow_state {old!r}")
                changes.append({"doctype": doctype, "old": old, "new": new, "count": count})
    return changes


def prepare(backup_file: str, expected_sha256: str | None = None) -> None:
    if _snapshot_path().exists():
        frappe.throw("A migration snapshot already exists; restore/review it before restarting prepare")
    legacy_doctypes, plan, backup = preflight(backup_file, expected_sha256, show_report=False)

    app_counts = {name: _count(name) for name in legacy_doctypes if _exists(name)}
    snapshot = {
        "version": 2,
        "site": frappe.local.site,
        "legacy_app": LEGACY_APP,
        "target_app": TARGET_APP,
        "verified_backup": backup,
        "business_counts": _business_counts(),
        "app_doctype_counts": app_counts,
        "doctype_map": {name: rebrand_identifier(name) for name in legacy_doctypes},
        "metadata_map": plan,
    }
    _write_snapshot(snapshot)

    old_in_patch = getattr(frappe.flags, "in_patch", False)
    frappe.flags.in_patch = True
    try:
        if "Module Def" in plan:
            for old, new in plan["Module Def"].items():
                _rename_one("Module Def", old, new)
        for doctype in RENAMABLE_METADATA_DOCTYPES:
            for old, new in plan.get(doctype, {}).items():
                _rename_one(doctype, old, new)

        # Preserve native business records while translating only the
        # exact metadata state values used by the app's former workflows.
        snapshot["workflow_state_renames"] = _migrate_workflow_state_values()
        _write_snapshot(snapshot)
        _update_app_fields()
        _switch_installed_app()
        frappe.clear_cache()

        for old, expected in app_counts.items():
            new = rebrand_identifier(old)
            actual = _count(new)
            if actual != expected:
                frappe.throw(f"Row-count mismatch after DocType rename {old!r} -> {new!r}: {expected} != {actual}")
        if _business_counts() != snapshot["business_counts"]:
            frappe.throw("Business-record counts changed during prepare")
    finally:
        frappe.flags.in_patch = old_in_patch



def _candidate_field_doctypes() -> set[str]:
    candidates = set(frappe.get_all("DocType", filters={"module": TARGET_MODULE}, pluck="name"))
    if _exists("Custom Field"):
        candidates.update(
            frappe.get_all("Custom Field", filters=[["fieldname", "like", "%workforce%"]], pluck="dt")
        )
        candidates.update(
            frappe.get_all("Custom Field", filters=[["fieldname", "like", "%tradex%"]], pluck="dt")
        )
    return {dt for dt in candidates if _exists(dt)}


def _legacy_columns(doctype: str) -> list[str]:
    meta = frappe.get_meta(doctype, cached=False)
    if meta.issingle:
        fields = frappe.db.sql(
            "select distinct field from tabSingles where doctype=%s",
            (doctype,),
            pluck=True,
        )
        return sorted({f for f in fields if f and LEGACY_TOKEN.search(f)})
    if meta.is_virtual:
        return []
    try:
        columns = frappe.db.get_table_columns(doctype)
    except Exception as exc:
        frappe.throw(f"Unable to inspect physical columns for {doctype}: {exc}")
    return sorted(c for c in columns if LEGACY_TOKEN.search(c))


def _remove_old_custom_field_metadata(doctype: str, old_fieldname: str) -> None:
    if not _exists("Custom Field"):
        return
    for name in frappe.get_all(
        "Custom Field",
        filters={"dt": doctype, "fieldname": old_fieldname},
        pluck="name",
    ):
        frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)


def _assert_field_values_copied(doctype: str, old_fieldname: str, new_fieldname: str) -> None:
    meta = frappe.get_meta(doctype)
    if meta.issingle:
        if frappe.db.sql(
            "select count(*) from tabSingles where doctype=%s and field=%s",
            (doctype, old_fieldname),
        )[0][0]:
            frappe.throw(f"Single value field did not migrate: {doctype}.{old_fieldname}")
        return
    if not (re.fullmatch(r"[A-Za-z0-9_ ]+", doctype)
            and re.fullmatch(r"[A-Za-z0-9_]+", old_fieldname)
            and re.fullmatch(r"[A-Za-z0-9_]+", new_fieldname)):
        frappe.throw("Unsafe SQL identifier in custom field migration")
    mismatches = frappe.db.sql(
        f"SELECT COUNT(*) FROM `tab{doctype}` "
        f"WHERE NOT (`{old_fieldname}` <=> `{new_fieldname}`)"
    )[0][0]
    if mismatches:
        frappe.throw(
            f"Failed to preserve {mismatches} values: {doctype}.{old_fieldname} -> {new_fieldname}"
        )


def _ensure_import_reference_field() -> None:
    """Preserve the known legacy import ID used by the biometric audit report.

    This field was installed by the historical import, not generic setup. Copy
    its actual metadata through Frappe; do not invent an ID or touch employees.
    Unknown customer fields still fail closed instead of being guessed.
    """
    old = "tradex_source_employee_id"
    new = "workforce_source_employee_id"
    if frappe.get_meta("Employee", cached=False).get_field(new):
        return
    name = frappe.db.get_value("Custom Field", {"dt": "Employee", "fieldname": old}, "name")
    if not name:
        return
    field = frappe.get_doc("Custom Field", name)
    if field.fieldtype != "Data":
        frappe.throw("Legacy employee import reference must be a Data field; review its customization")
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    definition = field.as_dict()
    for key in ("name", "doctype", "dt", "owner", "creation", "modified", "modified_by", "docstatus", "idx"):
        definition.pop(key, None)
    definition["fieldname"] = new
    if definition.get("insert_after"):
        definition["insert_after"] = rebrand_identifier(definition["insert_after"])
    create_custom_fields({"Employee": [definition]}, update=False)


def finalize() -> None:
    snapshot = _read_snapshot()
    apps = frappe.get_installed_apps()
    if TARGET_APP not in apps or LEGACY_APP in apps:
        frappe.throw("installed_apps has not been switched cleanly to workforce_suite")

    _ensure_import_reference_field()
    copied: list[tuple[str, str, str]] = []
    for doctype in sorted(_candidate_field_doctypes()):
        meta = frappe.get_meta(doctype, cached=False)
        for old_fieldname in _legacy_columns(doctype):
            new_fieldname = rebrand_identifier(old_fieldname)
            if old_fieldname == new_fieldname:
                continue
            if not meta.get_field(new_fieldname):
                frappe.throw(
                    f"Target field {doctype}.{new_fieldname} is missing after model sync; "
                    f"refusing to discard data from {old_fieldname}"
                )
            rename_field(doctype, old_fieldname, new_fieldname, validate=True)
            _assert_field_values_copied(doctype, old_fieldname, new_fieldname)
            _remove_old_custom_field_metadata(doctype, old_fieldname)
            copied.append((doctype, old_fieldname, new_fieldname))
            # Preserve old physical columns for audited rollback and recovery.

    # Do not alter arbitrary Custom Field labels/defaults/options. They may
    # contain a customer's *actual* registered company name, which is data.
    current_business = _business_counts()
    if current_business != snapshot.get("business_counts", {}):
        frappe.throw(
            "Business-record count mismatch after migration. "
            f"before={snapshot.get('business_counts')} after={current_business}"
        )

    for old, expected in snapshot.get("app_doctype_counts", {}).items():
        new = snapshot["doctype_map"][old]
        actual = _count(new)
        if actual != expected:
            frappe.throw(f"App row-count mismatch {old!r} -> {new!r}: {expected} != {actual}")

    frappe.clear_cache()
    print(json.dumps({"phase": "finalize", "copied_fields": copied, "business_counts": current_business}, indent=2))


def verify() -> None:
    errors: list[str] = []
    apps = frappe.get_installed_apps()
    if LEGACY_APP in apps:
        errors.append(f"legacy app still installed: {LEGACY_APP}")
    if TARGET_APP not in apps:
        errors.append(f"target app missing: {TARGET_APP}")

    snapshot = _read_snapshot()
    for doctype, mapping in snapshot.get("metadata_map", {}).items():
        for old, new in mapping.items():
            if frappe.db.exists(doctype, old):
                errors.append(f"legacy app-owned metadata still exists: {doctype} {old}")
            if not frappe.db.exists(doctype, new):
                errors.append(f"renamed metadata missing: {doctype} {new}")


    if _business_counts() != snapshot.get("business_counts", {}):
        errors.append("business-record counts do not match the pre-migration snapshot")
    for change in snapshot.get("workflow_state_renames", []):
        if frappe.db.count(change["doctype"], {"workflow_state": change["old"]}):
            errors.append(f"legacy workflow state remains: {change['doctype']} {change['old']}")
    for old, count in snapshot.get("app_doctype_counts", {}).items():
        target = snapshot.get("doctype_map", {}).get(old)
        if not target or _count(target) != count:
            errors.append(f"app record count changed during migration: {old} -> {target}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
    print(json.dumps({"status": "PASS", "site": frappe.local.site, "installed_app": TARGET_APP}, indent=2))


def _enter_site(site: str) -> None:
    cwd = Path.cwd()
    if (cwd / "sites").is_dir():
        os.chdir(cwd / "sites")
    frappe.init(site=site, force=True)
    frappe.connect()
    frappe.set_user("Administrator")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--phase", choices=("preflight", "prepare", "finalize", "verify"), required=True)
    parser.add_argument("--yes", action="store_true")
    # No destructive column-drop option. That is a separate approved project.
    parser.add_argument("--backup-file", help="Database *.sql.gz backup; required for preflight and prepare")
    parser.add_argument("--backup-sha256", help="Optional expected SHA-256 of database backup")
    args = parser.parse_args()

    if args.phase in {"prepare", "finalize"} and not args.yes:
        parser.error("--yes is required for migration mutations")

    if args.phase in {"preflight", "prepare"} and not args.backup_file:
        parser.error("--backup-file is required for preflight and prepare")
    # Resolve paths before _enter_site changes cwd into bench/sites.
    backup_file = str(Path(args.backup_file).expanduser().resolve()) if args.backup_file else None
    _enter_site(args.site)
    try:
        if args.phase == "preflight":
            preflight(backup_file, args.backup_sha256)
        elif args.phase == "prepare":
            prepare(backup_file, args.backup_sha256)
        elif args.phase == "finalize":
            finalize()
        else:
            verify()
        frappe.db.commit()
        return 0
    except BaseException:
        frappe.db.rollback()
        raise
    finally:
        frappe.destroy()


if __name__ == "__main__":
    raise SystemExit(main())
