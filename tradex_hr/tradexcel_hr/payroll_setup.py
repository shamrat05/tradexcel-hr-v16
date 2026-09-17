"""Idempotent setup for TradeX worker wages and editable payroll policies."""

from __future__ import annotations

import frappe
from frappe.utils import getdate


TCL = "Tradexcel Ceramics Ltd."
EFL = "Elegance Footwear Ltd."
FACTORY = "TCL Factory"
HEADQUARTERS = "Tradexcel Headquarters"
STAFF_STRUCTURE = "BD Labour Law - Staff & Executive Salary Structure"
WORKER_STRUCTURE = "TCL Factory Daily Wage Worker Structure"
EFFECTIVE_FROM = "2026-08-01"


def _ensure_component(name: str, abbr: str, *, depends_on_payment_days: int = 0, formula: str | None = None):
    if frappe.db.exists("Salary Component", name):
        return frappe.get_doc("Salary Component", name)
    doc = frappe.get_doc(
        {
            "doctype": "Salary Component",
            "salary_component": name,
            "salary_component_abbr": abbr,
            "type": "Earning",
            "depends_on_payment_days": depends_on_payment_days,
            "amount_based_on_formula": int(bool(formula)),
            "formula": formula,
            "amount": 0,
            "is_tax_applicable": 0,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc


def ensure_salary_components():
    daily = _ensure_component(
        "Daily Wage", "DW", depends_on_payment_days=1, formula="base * payment_days"
    )
    recreation = _ensure_component("Recreation Allowance", "RA")
    _ensure_component("Overtime Pay", "OT")
    return {"daily_wage": daily.name, "recreation": recreation.name}


def ensure_worker_structure():
    if frappe.db.exists("Salary Structure", WORKER_STRUCTURE):
        return WORKER_STRUCTURE
    doc = frappe.get_doc(
        {
            "doctype": "Salary Structure",
            "name": WORKER_STRUCTURE,
            "company": TCL,
            "currency": "BDT",
            "payroll_frequency": "Monthly",
            "is_active": "Yes",
            "earnings": [
                {
                    "salary_component": "Daily Wage",
                    "abbr": "DW",
                    "amount": 0,
                    "depends_on_payment_days": 1,
                    "amount_based_on_formula": 1,
                    "formula": "base * payment_days",
                },
                {
                    "salary_component": "Overtime Pay",
                    "abbr": "OT",
                    "amount": 0,
                    "depends_on_payment_days": 0,
                },
            ],
        }
    )
    doc.insert(ignore_permissions=True)
    doc.submit()
    return doc.name


def _policy(name: str, values: dict):
    if frappe.db.exists("Tradexcel Payroll Policy", name):
        doc = frappe.get_doc("Tradexcel Payroll Policy", name)
        requested = getdate(values["effective_from"])
        current = getdate(doc.effective_from) if doc.effective_from else None
        if current is None or current > requested:
            doc.effective_from = requested
            doc.save(ignore_permissions=True)
        return doc.name
    doc = frappe.get_doc({"doctype": "Tradexcel Payroll Policy", "policy_name": name, **values})
    doc.insert(ignore_permissions=True)
    return doc.name


def ensure_policies(worker_structure: str, effective_from: str):
    common_staff = {
        "enabled": 1,
        "employee_category": "Staff",
        "pay_basis": "Monthly Salary",
        "salary_structure": STAFF_STRUCTURE,
        "standard_hours_per_day": 8,
        "break_minutes": 60,
        "overtime_enabled": 0,
        "overtime_after_hours": 8,
        "overtime_grace_minutes": 10,
        "overtime_rounding_minutes": 60,
        "overtime_multiplier": 2,
        "max_daily_overtime_hours": 2,
        "max_weekly_hours": 60,
        "effective_from": effective_from,
        "legal_review_required": 1,
        "source_reference": "TradeX operating policy; verify source compensation before payroll",
    }
    _policy(
        "TCL Factory Worker Wage Policy",
        {
            "enabled": 1,
            "company": TCL,
            "branch": FACTORY,
            "employee_category": "Worker",
            "pay_basis": "Daily Wage",
            "salary_structure": worker_structure,
            "daily_wage": 350,
            "standard_hours_per_day": 8,
            "break_minutes": 0,
            "overtime_enabled": 1,
            "overtime_after_hours": 8,
            "overtime_grace_minutes": 10,
            "overtime_rounding_minutes": 60,
            "overtime_multiplier": 2,
            "max_daily_overtime_hours": 2,
            "max_weekly_hours": 60,
            "effective_from": effective_from,
            "legal_review_required": 1,
            "source_reference": "User-approved Tk 350 per 8-hour day; ceramics minimum wage Gazette still requires verification",
            "notes": "50 minutes beyond 8 hours rounds to 1 billable overtime hour. No factory worker break is deducted by default.",
        },
    )
    _policy(
        "TCL Factory Administration Staff Policy",
        {**common_staff, "company": TCL, "branch": FACTORY, "department": "Administration - TCL"},
    )
    _policy(
        "TCL Head Office Staff Policy",
        {**common_staff, "company": TCL, "branch": HEADQUARTERS},
    )
    _policy(
        "TCL Staff Default Policy",
        {**common_staff, "company": TCL},
    )
    _policy(
        "EFL Staff Policy",
        {
            "enabled": 1,
            "company": EFL,
            "employee_category": "Staff",
            "pay_basis": "Monthly Salary",
            "standard_hours_per_day": 8,
            "break_minutes": 60,
            "overtime_enabled": 0,
            "overtime_after_hours": 8,
            "overtime_grace_minutes": 10,
            "overtime_rounding_minutes": 60,
            "overtime_multiplier": 2,
            "max_daily_overtime_hours": 2,
            "max_weekly_hours": 60,
            "effective_from": effective_from,
            "legal_review_required": 1,
            "source_reference": "Source compensation required; no EFL salary assumption was made",
            "notes": "Assign an EFL-owned Salary Structure after the source salary is verified.",
        },
    )


def classify_employees():
    rows = frappe.get_all(
        "Employee",
        filters={"company": ["in", [TCL, EFL]]},
        fields=["name", "company", "branch", "department", "employment_type"],
    )
    changed = 0
    for row in rows:
        branch = (row.branch or "").strip()
        department = (row.department or "").strip().lower()
        category = "Worker" if row.company == TCL and branch == FACTORY and not department.startswith("administration") else "Staff"
        if row.employment_type != category:
            frappe.db.set_value("Employee", row.name, "employment_type", category, update_modified=False)
            changed += 1
    return changed


def ensure_factory_assignments(worker_structure: str, effective_from: str):
    employees = frappe.get_all(
        "Employee",
        filters={"company": TCL, "branch": FACTORY, "employment_type": "Worker", "status": "Active"},
        fields=["name", "employee_name", "date_of_joining"],
    )
    created = 0
    for employee in employees:
        assignment_from = max(
            getdate(effective_from),
            getdate(employee.date_of_joining) if employee.date_of_joining else getdate(effective_from),
        ).isoformat()
        if frappe.db.exists(
            "Salary Structure Assignment",
            {"employee": employee.name, "salary_structure": worker_structure, "from_date": assignment_from, "docstatus": ["<", 2]},
        ):
            continue
        assignment = frappe.get_doc(
            {
                "doctype": "Salary Structure Assignment",
                "employee": employee.name,
                "salary_structure": worker_structure,
                "from_date": assignment_from,
                "base": 350,
                "variable": 0,
                "company": TCL,
            }
        )
        assignment.insert(ignore_permissions=True)
        assignment.submit()
        created += 1
    return created


def setup_payroll_configuration(effective_from: str = EFFECTIVE_FROM):
    effective_from = getdate(effective_from).isoformat()
    components = ensure_salary_components()
    worker_structure = ensure_worker_structure()
    changed_employees = classify_employees()
    ensure_policies(worker_structure, effective_from)
    assignments = ensure_factory_assignments(worker_structure, effective_from)
    frappe.db.commit()
    return {
        "effective_from": effective_from,
        "worker_structure": worker_structure,
        "components": components,
        "employees_reclassified": changed_employees,
        "factory_worker_assignments_created": assignments,
    }
