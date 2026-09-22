"""Declarative salary setup: create/converge Salary Components and Structures.

Reads `salary_setup.yaml` (the single source of truth) and makes the site match
it. Idempotent: run it any number of times, it converges rather than duplicating.

    dry run :  python -c "from tradex_hr.tradexcel_hr.salary_setup import ..."
    apply   :  ensure_salary_setup(commit=True)

Deliberately separate from `payroll_setup.py`, which creates demo-ish defaults for
the older migration structures. This module owns only the configuration declared
in the YAML.
"""

from __future__ import annotations

import pathlib

import frappe

SPEC_PATH = pathlib.Path(__file__).with_name("salary_setup.yaml")


def load_spec() -> dict:
    import yaml

    with open(SPEC_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _component_defaults(spec_comp: dict) -> dict:
    """Build the Salary Component payload from the spec.

    Only fields that genuinely exist on Frappe's Salary Component are set. The
    Selevo `is_basic` / `is_gratuity_base` flags have no Frappe equivalent, so
    they are not invented here.
    """
    doc = {
        "doctype": "Salary Component",
        "salary_component": spec_comp["name"],
        "salary_component_abbr": spec_comp["abbr"],
        "type": spec_comp["type"],
        "description": spec_comp.get("description", ""),
    }
    for field, want in (spec_comp.get("fields") or {}).items():
        meta = frappe.get_meta("Salary Component")
        if not meta.has_field(field):
            raise frappe.ValidationError(
                f"salary_setup.yaml sets {field!r} on {spec_comp['name']!r}, but "
                f"Salary Component has no such field. Fix the spec rather than "
                f"adding a custom field."
            )
        doc[field] = 1 if want is True else 0 if want is False else want
    return doc


def ensure_components(spec: dict, *, commit: bool) -> list[str]:
    """Create or converge each Salary Component. Returns lines describing changes."""
    log = []
    for c in spec["components"]:
        name = c["name"]
        desired = _component_defaults(c)
        if frappe.db.exists("Salary Component", name):
            doc = frappe.get_doc("Salary Component", name)
            changed = []
            for field, want in desired.items():
                if field in ("doctype", "salary_component", "description"):
                    continue
                have = doc.get(field)
                # Checkbox fields come back as 0/1 ints; text fields are strings.
                if isinstance(want, int):
                    same = int(have or 0) == int(want or 0)
                else:
                    same = str(have or "") == str(want or "")
                if not same:
                    changed.append(f"{field}: {have!r} -> {want!r}")
                    doc.set(field, want)
            if changed:
                doc.flags.ignore_permissions = True
                doc.save()
                log.append(f"  UPDATE component {name}: " + "; ".join(changed))
            else:
                log.append(f"  ok     component {name}")
        else:
            doc = frappe.get_doc(desired)
            doc.flags.ignore_permissions = True
            doc.insert()
            log.append(f"  CREATE component {name} ({c['abbr']})")
    if commit:
        frappe.db.commit()
    return log


def ensure_structures(spec: dict, *, commit: bool) -> list[str]:
    """Create or converge each Salary Structure, including its earnings rows."""
    log = []
    company = spec["company"]
    currency = spec.get("currency", "BDT")

    for st in spec["structures"]:
        name = st["name"]
        # a structure may override the company (e.g. EFL Standard); Frappe
        # requires the structure's company to match the employee's.
        st_company = st.get("company") or company
        rows = []
        for e in st["earnings"]:
            row = {"salary_component": e["component"]}
            comp = frappe.get_doc("Salary Component", e["component"])
            row["abbr"] = comp.salary_component_abbr
            row["depends_on_payment_days"] = int(comp.depends_on_payment_days or 0)
            if "formula" in e:
                row["amount_based_on_formula"] = 1
                row["formula"] = e["formula"]
                row["amount"] = 0
            else:
                row["amount"] = e.get("amount", 0)
            rows.append(row)

        if frappe.db.exists("Salary Structure", name):
            doc = frappe.get_doc("Salary Structure", name)
            if not frappe.get_meta("Salary Structure").has_field("custom_tradex_pay_basis"):
                raise frappe.ValidationError(
                    "Salary Structure is missing custom_tradex_pay_basis; run the Tradexcel HR migration first"
                )
            before = [
                (r.salary_component, r.formula or "", float(r.amount or 0), int(r.depends_on_payment_days or 0))
                for r in doc.earnings
            ]
            after = [
                (r["salary_component"], r.get("formula", ""), float(r.get("amount") or 0), int(r.get("depends_on_payment_days") or 0))
                for r in rows
            ]
            basis_changed = doc.custom_tradex_pay_basis != st["pay_basis"]
            if before == after and not basis_changed:
                log.append(f"  ok     structure {name} (earnings already match)")
                continue
            if doc.docstatus == 1:
                linked = frappe.db.count(
                    "Salary Structure Assignment", {"salary_structure": name, "docstatus": 1}
                )
                if linked:
                    raise frappe.ValidationError(
                        f"Cannot rewrite submitted Salary Structure {name}: {linked} submitted assignment(s) link to it. "
                        "Create a new effective-dated structure/assignment instead."
                    )
                doc.flags.ignore_permissions = True
                doc.cancel()
            doc.earnings = []
            for r in rows:
                doc.append("earnings", r)
            doc.custom_tradex_pay_basis = st["pay_basis"]
            doc.flags.ignore_permissions = True
            doc.save()
            if doc.docstatus == 0:
                doc.submit()
            log.append(f"  UPDATE structure {name}: earnings rows replaced")
        else:
            doc = frappe.get_doc({
                "doctype": "Salary Structure",
                "name": name,
                "company": st_company,
                "currency": currency,
                "payroll_frequency": "Monthly",
                "is_active": "Yes",
                "custom_tradex_pay_basis": st["pay_basis"],
                "earnings": rows,
            })
            doc.flags.ignore_permissions = True
            doc.insert()
            doc.submit()
            log.append(f"  CREATE structure {name} ({len(rows)} earnings)")
    if commit:
        frappe.db.commit()
    return log


def ensure_pay_basis_metadata(spec: dict | None = None, *, commit: bool = False) -> list[str]:
    """Persist only declarative pay-basis metadata on existing structures.

    This deliberately does not infer from structure names or employee type.
    It is the safe migration step for sites where structures already exist;
    earnings convergence remains an explicit ``ensure_salary_setup`` action.
    """
    spec = spec or load_spec()
    if not frappe.get_meta("Salary Structure").has_field("custom_tradex_pay_basis"):
        raise frappe.ValidationError(
            "Salary Structure is missing custom_tradex_pay_basis; run the Tradexcel HR migration first"
        )
    log = []
    for structure in spec["structures"]:
        name = structure["name"]
        if not frappe.db.exists("Salary Structure", name):
            log.append(f"  SKIP   structure {name} (not found)")
            continue
        doc = frappe.get_doc("Salary Structure", name)
        wanted = structure["pay_basis"]
        if doc.custom_tradex_pay_basis == wanted:
            log.append(f"  ok     pay basis {name} = {wanted}")
            continue
        # This is metadata only. Salary Structures are linked by submitted
        # assignments, so cancel/re-submit would be both unnecessary and
        # rejected by native Frappe link protection.
        frappe.db.set_value(
            "Salary Structure", name, "custom_tradex_pay_basis", wanted, update_modified=False
        )
        log.append(f"  UPDATE pay basis {name}: {wanted}")
    if commit:
        frappe.db.commit()
    return log


def ensure_retired(spec: dict, *, commit: bool) -> list[str]:
    """Disable structures we have deliberately retired. Never delete them."""
    log = []
    for name in spec.get("retired_structures", []):
        if not frappe.db.exists("Salary Structure", name):
            log.append(f"  ok     retired {name} (absent)")
            continue
        doc = frappe.get_doc("Salary Structure", name)
        used = frappe.db.count("Salary Structure Assignment", {"salary_structure": name})
        if used:
            log.append(f"  KEEP   {name}: still referenced by {used} assignment(s)")
            continue
        if doc.is_active == "Yes":
            if doc.docstatus == 1:
                doc.flags.ignore_permissions = True
                doc.cancel()
            doc.is_active = "No"
            doc.flags.ignore_permissions = True
            doc.save()
            log.append(f"  RETIRE {name} (is_active -> No)")
        else:
            log.append(f"  ok     {name} already inactive")
    if commit:
        frappe.db.commit()
    return log


def ensure_salary_setup(*, commit: bool = False) -> dict:
    """Converge components, structures and retirements to match the spec."""
    spec = load_spec()
    log = {"pay_basis": ensure_pay_basis_metadata(spec, commit=commit),
           "components": ensure_components(spec, commit=commit),
           "structures": ensure_structures(spec, commit=commit),
           "retired": ensure_retired(spec, commit=commit)}
    if commit:
        frappe.clear_cache()
    return log


def report(log: dict) -> str:
    out = []
    for section in ("components", "structures", "retired"):
        out.append(f"[{section}]")
        out.extend(log[section])
    return "\n".join(out)
