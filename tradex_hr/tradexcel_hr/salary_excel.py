"""Export the Tradexcel salary data to Xcel, and import Salary Structure Assignments.

Two jobs, both driven by `salary_setup.yaml` (structures/components) and the CSV
extracted from the VPS backup (people and amounts).

    export_xcel()                     -> write the workbook, with documentation
    import_assignments(commit=False)  -> dry run; prints reconciliation
    import_assignments(commit=True)   -> writes Salary Structure Assignments

Scope: Tradexcel only. The VPS dump holds other tenants (aftab-textile, aftab-it,
levelaxis) in the same database, so the source CSV was already filtered to the
`tradex` organisation by `extract_tradexcel_salary.py`. This module never reads
the dump itself.
"""

from __future__ import annotations

import csv
import pathlib

import frappe

EXTRACT_DIR = pathlib.Path(
    "/mnt/c/Users/Sanchita/Desktop/tradex_hr_backup_20260918/vps_tradexcel_salary_20260918"
)
XLSX_PATH = EXTRACT_DIR / "tradexcel_salary.xlsx"

STAFF_STRUCTURE = "TCL Standard"
EFL_STRUCTURE = "EFL Standard"
WORKER_STRUCTURE = "TCL Daily Wage"
WORKER_DAILY_RATE = 350.0

# Frappe validates that a Salary Structure's company matches the employee's, so
# a salaried employee gets the structure belonging to their own company.
# The components and formulas are identical; only the wrapper differs.
STRUCTURE_BY_COMPANY = {
    "Tradexcel Ceramics Ltd.": STAFF_STRUCTURE,
    "Elegance Footwear Ltd.": EFL_STRUCTURE,
}

# Two staff have a gross but no component breakdown in the VPS, so their split
# cannot be derived. Excluded by explicit owner instruction.
SKIP = {"TCL-0026", "TCL-0038"}


# --------------------------------------------------------------------------- #
# employees in scope
# --------------------------------------------------------------------------- #

def load_employees() -> list[dict]:
    """All Tradexcel employees, split by whether the VPS stored a monthly amount.

    The 69 with a salary live in `10_crossref_with_salary.csv`; the other 159
    (factory workers, paid a gross daily rate, so no monthly figure) live in
    `11_crossref_no_salary.csv`. Both must be read or the workers are silently
    dropped.
    """
    out = []
    for fname, has_salary in (("10_crossref_with_salary.csv", True),
                              ("11_crossref_no_salary.csv", False)):
        with open(EXTRACT_DIR / fname, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                r["_has_salary"] = has_salary
                out.append(r)
    return out


def load_breakdown() -> dict[str, dict]:
    path = EXTRACT_DIR / "20_tradexcel_salary_breakdown.csv"
    out: dict[str, dict] = {}
    if not path.exists():
        return out
    with open(path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out.setdefault(r["employee_number"], {})[r["component"]] = r["amount_bdt"]
    return out


def plan() -> dict:
    """Decide who gets which structure and base. Returns a full, auditable plan."""
    employees = load_employees()
    breakdown = load_breakdown()
    staff, workers, skipped, unresolved = [], [], [], []

    for e in employees:
        num = (e["employee_number"] or "").strip()
        name = e["vps_name"]
        frappe_emp = e["frappe_employee"]
        # the two source files use different column names for the amount
        salary = (e.get("salary_bdt") or e.get("salary_taka") or "").strip()

        if num in SKIP:
            skipped.append({"number": num, "name": name, "reason": "no component breakdown in VPS"})
            continue
        if not frappe_emp:
            unresolved.append({"number": num, "name": name, "reason": "no Frappe employee"})
            continue

        if salary and float(salary) > 0:
            comps = breakdown.get(num, {})
            # route to the structure of the employee's own company
            company = frappe.db.get_value("Employee", frappe_emp, "company") \
                if frappe.db.exists("Employee", frappe_emp) else None
            struct = STRUCTURE_BY_COMPANY.get(company, STAFF_STRUCTURE)
            staff.append({
                "number": num, "name": name, "frappe": frappe_emp,
                "structure": struct, "base": float(salary),
                "components": comps, "company": company,
            })
        else:
            # no monthly amount => factory worker on a gross daily rate
            workers.append({
                "number": num, "name": name, "frappe": frappe_emp,
                "structure": WORKER_STRUCTURE, "base": WORKER_DAILY_RATE,
                "components": {},
            })
    return {"staff": staff, "workers": workers, "skipped": skipped, "unresolved": unresolved}


# --------------------------------------------------------------------------- #
# Xcel export
# --------------------------------------------------------------------------- #

def export_xcel() -> pathlib.Path:
    """Write a documented workbook: README, structures, then the people."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill

    p = plan()
    wb = Workbook()

    head = Font(bold=True, size=12)
    bold = Font(bold=True)
    wrap = Alignment(wrap_text=True, vertical="top")
    fill = PatternFill("solid", fgColor="DDEBF7")

    # ---- README sheet -------------------------------------------------------
    ws = wb.active
    ws.title = "README"
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 96
    rows = [
        ("Tradexcel salary setup", ""),
        ("", ""),
        ("Source", "Selevo VPS backup, database `selevohr`, organisation slug `tradex`."),
        ("Scope", "Tradexcel Ceramics Ltd. only. Other tenants in the same dump "
                  "(aftab-textile, aftab-it, levelaxis) are excluded."),
        ("Generated", "by tradex_hr/tradexcel_hr/salary_excel.py"),
        ("", ""),
        ("HOW THE PAY IS BUILT", ""),
        ("Components", "Global masters, created once and reused. A structure references "
                       "them; it does not own them."),
        ("Structures", "Templates only — two of them. The individual amount is NOT here."),
        ("Assignments", "One per employee. Carries `base`, the person's own figure."),
        ("Policies", "Tradexcel Payroll Policy sets pay_basis, daily_wage and overtime "
                     "rules by scope (company/branch/department)."),
        ("Exceptions", "Tradexcel Policy Exception overrides a policy for specific people "
                       "or groups, is dated, requires a preview, and records a reason."),
        ("", ""),
        ("STRUCTURE: TCL Standard", "Salaried staff"),
        ("  Basic Salary (BS)", "base x 0.60   — 60% of gross"),
        ("  House Rent Allowance (HRA)", "base x 0.30   — 30% of gross"),
        ("  Medical Allowance (MED)", "base x 0.05   — 5% of gross"),
        ("  Conveyance Allowance (CON)", "base x 0.05   — 5% of gross"),
        ("  Entertainment Allowance (ENT)", "always 0 in the structure; paid to an "
                                            "individual via Additional Salary"),
        ("", ""),
        ("STRUCTURE: TCL Daily Wage", "Factory workers"),
        ("  Daily Wage (DW)", "base x payment_days   — base is the GROSS daily rate"),
        ("  Overtime Pay (OT)", "from the Payroll Policy and overtime rules"),
        ("", ""),
        ("WHY ONLY TWO STRUCTURES", "The VPS held 28 structures named after individuals "
                                    "(abdullah, alim, miraz...). Those existed only because "
                                    "Selevo had nowhere else to store a personal amount. "
                                    "In Frappe that value lives on the assignment's base, "
                                    "so one structure serves everyone on that basis. "
                                    "One place to change the split; no drift."),
        ("", ""),
        ("Overrides", "Anything that differs for a person is an exception or an Additional "
                      "Salary — never a new structure. Both are dated and visible in the app."),
    ]
    for i, (a, b) in enumerate(rows, 1):
        ws.cell(i, 1, a).font = head if a and not b and a.isupper() else bold
        ws.cell(i, 2, b).alignment = wrap

    # ---- Structures sheet ---------------------------------------------------
    ws2 = wb.create_sheet("Structures")
    ws2.append(["structure", "pay basis", "component", "abbr", "how it is calculated"])
    for c in ws2[1]:
        c.font = bold
        c.fill = fill
    for st in (("TCL Standard", "Monthly Salary",
                [("Basic Salary", "BS", "base x 0.60"),
                 ("House Rent Allowance", "HRA", "base x 0.30"),
                 ("Medical Allowance", "MED", "base x 0.05"),
                 ("Conveyance Allowance", "CON", "base x 0.05"),
                 ("Entertainment Allowance", "ENT", "0 (Additional Salary if granted)")]),
               ("TCL Daily Wage", "Daily Wage",
                [("Daily Wage", "DW", "base x payment_days (base = gross daily rate)"),
                 ("Overtime Pay", "OT", "per Payroll Policy overtime rules")])):
        for comp, abbr, how in st[2]:
            ws2.append([st[0], st[1], comp, abbr, how])
    for col, w in zip("ABCDE", (20, 16, 26, 8, 52)):
        ws2.column_dimensions[col].width = w

    # ---- Staff sheet --------------------------------------------------------
    ws3 = wb.create_sheet("Staff (monthly)")
    ws3.append(["employee number", "name", "frappe employee", "structure", "gross (base)",
                "Basic Salary", "House Rent Allowance", "Medical Allowance",
                "Conveyance Allowance", "Entertainment Allowance", "remarks"])
    for c in ws3[1]:
        c.font = bold
        c.fill = fill
    for r in sorted(p["staff"], key=lambda x: -x["base"]):
        c = r["components"]
        ws3.append([
            r["number"], r["name"], r["frappe"], r["structure"], r["base"],
            float(c.get("Basic Salary") or 0), float(c.get("House Rent Allowance") or 0),
            float(c.get("Medical Allowance") or 0), float(c.get("Conveyance Allowance") or 0),
            float(c.get("Entertainment Allowance") or 0),
            "gross is base; components derive from the structure formula",
        ])
    for col, w in zip("ABCDEFGHIJK", (16, 30, 16, 16, 13, 14, 20, 16, 20, 22, 52)):
        ws3.column_dimensions[col].width = w

    # ---- Workers sheet ------------------------------------------------------
    ws4 = wb.create_sheet("Workers (daily)")
    ws4.append(["employee number", "name", "frappe employee", "structure",
                "gross daily rate", "remarks"])
    for c in ws4[1]:
        c.font = bold
        c.fill = fill
    for r in sorted(p["workers"], key=lambda x: x["name"] or ""):
        ws4.append([r["number"], r["name"], r["frappe"], r["structure"], r["base"],
                    "paid base x attendance days"])
    for col, w in zip("ABCDEF", (16, 30, 16, 16, 16, 40)):
        ws4.column_dimensions[col].width = w

    # ---- Excluded sheet -----------------------------------------------------
    ws5 = wb.create_sheet("Excluded")
    ws5.append(["employee number", "name", "reason"])
    for c in ws5[1]:
        c.font = bold
        c.fill = fill
    for r in p["skipped"]:
        ws5.append([r["number"], r["name"], r["reason"]])
    for r in p["unresolved"]:
        ws5.append([r["number"], r["name"], r["reason"]])
    for col, w in zip("ABC", (16, 30, 60)):
        ws5.column_dimensions[col].width = w

    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    wb.save(XLSX_PATH)
    return XLSX_PATH


# --------------------------------------------------------------------------- #
# Assignment import
# --------------------------------------------------------------------------- #

def import_assignments(*, commit: bool = False, effective_from: str = "2026-08-01") -> dict:
    """Create one Salary Structure Assignment per employee.

    Idempotent: skips an employee who already has an assignment for that
    structure. Never overwrites an existing amount.

    `effective_from` is a FLOOR, not a fixed date: Frappe rejects an assignment
    dated before the employee's joining date, so anyone who joined later gets
    their joining date instead.
    """
    p = plan()
    log = {"create": [], "skip": [], "error": []}
    struct_company = {
        st.name: st.company
        for st in frappe.get_all("Salary Structure", fields=["name", "company"])
    }

    for bucket in ("staff", "workers"):
        for r in p[bucket]:
            emp, struct, base = r["frappe"], r["structure"], r["base"]
            if not frappe.db.exists("Employee", emp):
                log["error"].append(f"  ERROR  employee {emp} does not exist")
                continue

            emp_row = frappe.db.get_value(
                "Employee", emp, ["company", "date_of_joining"], as_dict=True)
            emp_company = emp_row["company"]

            if struct_company.get(struct) and struct_company[struct] != emp_company:
                log["error"].append(
                    f"  COMPANY {r['number']:<11}{r['name'][:22]:<24}is in {emp_company}, "
                    f"but {struct} belongs to {struct_company[struct]}")
                continue

            # Frappe refuses a from_date earlier than the joining date.
            start = effective_from
            joined = emp_row["date_of_joining"]
            if joined and str(joined) > str(effective_from):
                start = str(joined)

            existing = frappe.db.get_value(
                "Salary Structure Assignment",
                {"employee": emp, "salary_structure": struct, "docstatus": ["<", 2]},
                ["name", "base"], as_dict=True,
            )
            if existing:
                log["skip"].append(
                    f"  skip   {r['number']:<11}{r['name'][:24]:<26}{struct:<16}"
                    f"already {existing['name']} (base {existing['base']})")
                continue
            if not frappe.db.exists("Salary Structure", struct):
                log["error"].append(
                    f"  ERROR  structure {struct} does not exist (run ensure_salary_setup)")
                continue
            existing = frappe.db.get_value(
                "Salary Structure Assignment",
                {"employee": emp, "salary_structure": struct, "docstatus": ["<", 2]},
                ["name", "base"], as_dict=True,
            )
            if existing:
                log["skip"].append(
                    f"  skip   {r['number']:<11}{r['name'][:26]:<28}{struct:<16}"
                    f"already {existing['name']} (base {existing['base']})")
                continue
            if not frappe.db.exists("Salary Structure", struct):
                log["error"].append(f"  ERROR  structure {struct} does not exist (run ensure_salary_setup)")
                continue
            if not frappe.db.exists("Employee", emp):
                log["error"].append(f"  ERROR  employee {emp} does not exist")
                continue
            if commit:
                try:
                    # create the savepoint first; rollback-to-savepoint only
                    # undoes THIS row, not structures created earlier.
                    frappe.db.savepoint("imp")
                    doc = frappe.get_doc({
                        "doctype": "Salary Structure Assignment",
                        "employee": emp,
                        "salary_structure": struct,
                        "from_date": start,
                        "base": base,
                        "company": frappe.db.get_value("Employee", emp, "company"),
                        "currency": "BDT",
                    })
                    doc.flags.ignore_permissions = True
                    doc.insert()
                    doc.submit()
                except Exception as exc:  # noqa: BLE001
                    # A savepoint, NOT a full rollback: `frappe.db.rollback()`
                    # would also discard structures created earlier in the same
                    # transaction and cascade the failure across every later row.
                    frappe.db.rollback(save_point="imp")
                    log["error"].append(
                        f"  ERROR  {r['number']} {emp}: {type(exc).__name__}: {str(exc)[:110]}")
                    continue
            log["create"].append(
                f"  {'CREATE' if commit else 'would'}  {r['number']:<11}"
                f"{r['name'][:26]:<28}{struct:<16}base={base:,.2f}")

    if commit:
        frappe.db.commit()
    return log
