#!/usr/bin/env python3
"""Two-phase migration from the legacy branded app to Workforce Suite.

This file intentionally contains legacy identifiers so an existing site can be
upgraded. Runtime/product code should not contain those identifiers.

Run from the bench root after a verified fresh backup:

  env/bin/python apps/workforce_suite/scripts/migrate_legacy_site.py \
      --site <site> --phase prepare --yes
  bench --site <site> migrate
  env/bin/python apps/workforce_suite/scripts/migrate_legacy_site.py \
      --site <site> --phase finalize --yes
  env/bin/python apps/workforce_suite/scripts/migrate_legacy_site.py \
      --site <site> --phase verify
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys

import frappe
from frappe.installer import update_site_config
from frappe.model.utils.rename_field import rename_field

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
    "Custom Block",
    "Desktop Icon",
    "Workspace Sidebar",
    "Dashboard Chart",
    "Number Card",
)

LEGACY_TOKEN = re.compile(r"tradexcel|tradex", re.IGNORECASE)


def rebrand_identifier(value: str) -> str:
    replacements = (
        ("Tradexcel HR", TARGET_MODULE),
        ("Tradex HR", TARGET_MODULE),
        ("tradexcel_hr", TARGET_APP),
        ("tradex_hr", TARGET_APP),
        ("Tradexcel", "Workforce"),
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
    names = set(frappe.get_all("DocType", filters={"module": LEGACY_MODULE}, pluck="name"))
    names.update(frappe.get_all("DocType", filters=[["name", "like", "Tradexcel %"]], pluck="name"))
    names.update(frappe.get_all("DocType", filters=[["name", "like", "Tradex %"]], pluck="name"))
    return sorted(names)


def _metadata_names(doctype: str, legacy_app_doctypes: set[str]) -> list[str]:
    if not _exists(doctype):
        return []
    names: set[str] = set()
    meta = frappe.get_meta(doctype)
    if meta.has_field("module"):
        names.update(frappe.get_all(doctype, filters={"module": LEGACY_MODULE}, pluck="name"))
    for prefix in ("Tradexcel%", "Tradex%", "tradexcel%", "tradex%"):
        names.update(frappe.get_all(doctype, filters=[["name", "like", prefix]], pluck="name"))
    if doctype == "DocType":
        names.intersection_update(legacy_app_doctypes)
    return sorted(names)


def _rename_one(doctype: str, old: str, new: str) -> None:
    if old == new or not frappe.db.exists(doctype, old):
        return
    if frappe.db.exists(doctype, new):
        frappe.throw(f"Cannot migrate {doctype} {old!r}: target {new!r} already exists")
    frappe.rename_doc(
        doctype,
        old,
        new,
        force=True,
        ignore_permissions=True,
        show_alert=False,
        rebuild_search=False,
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


def prepare() -> None:
    legacy_doctypes = _legacy_app_doctypes()
    app_counts = {name: int(frappe.db.count(name)) for name in legacy_doctypes if _exists(name)}
    snapshot = {
        "version": 1,
        "site": frappe.local.site,
        "legacy_app": LEGACY_APP,
        "target_app": TARGET_APP,
        "business_counts": _business_counts(),
        "app_doctype_counts": app_counts,
        "doctype_map": {name: rebrand_identifier(name) for name in legacy_doctypes},
    }
    _write_snapshot(snapshot)

    old_in_patch = getattr(frappe.flags, "in_patch", False)
    frappe.flags.in_patch = True
    try:
        if frappe.db.exists("Module Def", LEGACY_MODULE):
            _rename_one("Module Def", LEGACY_MODULE, TARGET_MODULE)

        legacy_set = set(legacy_doctypes)
        for doctype in RENAMABLE_METADATA_DOCTYPES:
            names = legacy_doctypes if doctype == "DocType" else _metadata_names(doctype, legacy_set)
            for old in names:
                _rename_one(doctype, old, rebrand_identifier(old))

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
    try:
        return sorted(c for c in frappe.db.get_table_columns(doctype) if LEGACY_TOKEN.search(c))
    except Exception:
        return []


def _remove_old_custom_field_metadata(doctype: str, old_fieldname: str) -> None:
    if not _exists("Custom Field"):
        return
    for name in frappe.get_all(
        "Custom Field",
        filters={"dt": doctype, "fieldname": old_fieldname},
        pluck="name",
    ):
        frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)


def finalize(drop_legacy_columns: bool = False) -> None:
    snapshot = _read_snapshot()
    apps = frappe.get_installed_apps()
    if TARGET_APP not in apps or LEGACY_APP in apps:
        frappe.throw("installed_apps has not been switched cleanly to workforce_suite")

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
            _remove_old_custom_field_metadata(doctype, old_fieldname)
            copied.append((doctype, old_fieldname, new_fieldname))
            if drop_legacy_columns and not meta.issingle and frappe.db.has_column(doctype, old_fieldname):
                frappe.db.drop_column(doctype, old_fieldname)

    if _exists("Custom Field"):
        for row in frappe.get_all("Custom Field", fields=["name", "label", "description", "options", "default"]):
            updates = {}
            for field in ("label", "description", "options", "default"):
                value = row.get(field)
                if isinstance(value, str) and LEGACY_TOKEN.search(value):
                    updates[field] = rebrand_identifier(value)
            if updates:
                frappe.db.set_value("Custom Field", row.name, updates, update_modified=False)

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

    for doctype in RENAMABLE_METADATA_DOCTYPES + ("Module Def",):
        if not _exists(doctype):
            continue
        for name in frappe.get_all(doctype, pluck="name"):
            if isinstance(name, str) and LEGACY_TOKEN.search(name):
                errors.append(f"legacy metadata identifier: {doctype} {name}")

    if _exists("Custom Field"):
        for row in frappe.get_all("Custom Field", fields=["dt", "fieldname"]):
            if LEGACY_TOKEN.search(row.fieldname or ""):
                errors.append(f"legacy custom field: {row.dt}.{row.fieldname}")

    snapshot = _read_snapshot()
    if _business_counts() != snapshot.get("business_counts", {}):
        errors.append("business-record counts do not match the pre-migration snapshot")

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
    parser.add_argument("--phase", choices=("prepare", "finalize", "verify"), required=True)
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--drop-legacy-columns", action="store_true")
    args = parser.parse_args()

    if args.phase in {"prepare", "finalize"} and not args.yes:
        parser.error("--yes is required for migration mutations")

    _enter_site(args.site)
    try:
        if args.phase == "prepare":
            prepare()
        elif args.phase == "finalize":
            finalize(drop_legacy_columns=args.drop_legacy_columns)
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
