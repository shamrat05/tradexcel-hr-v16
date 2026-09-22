"""Salary structure coverage and effective assignment report."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate, today


from tradex_hr.tradexcel_hr.company_context import assert_company_access, resolve_company


def normalize_filters(filters: dict | None = None) -> frappe._dict:
    values = frappe._dict(filters or {})
    values.company = resolve_company(values)
    values.as_of_date = getdate(values.get("as_of_date") or today()).isoformat()
    values.employee_status = values.get("employee_status") or "Active"
    values.assignment_status = values.get("assignment_status") or "All"
    values.branch = values.get("branch") or ""
    values.department = values.get("department") or ""

    if values.employee_status not in {"All", "Active", "Inactive", "Left"}:
        raise ValueError(_("Invalid employee status"))
    if values.assignment_status not in {"All", "Assigned", "Missing", "Company Mismatch"}:
        raise ValueError(_("Invalid assignment status"))
    return values


def execute(filters: dict | None = None) -> tuple[list[dict], list[dict]]:
    filters = normalize_filters(filters)
    assert_company_access(filters.company)
    columns = [
        {"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 120},
        {"label": _("Employee ID"), "fieldname": "employee_id", "fieldtype": "Data", "width": 100},
        {"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 180},
        {"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 160},
        {"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 130},
        {"label": _("Department"), "fieldname": "department", "fieldtype": "Link", "options": "Department", "width": 160},
        {"label": _("Designation"), "fieldname": "designation", "fieldtype": "Link", "options": "Designation", "width": 150},
        {"label": _("Employee Status"), "fieldname": "employee_status", "fieldtype": "Data", "width": 100},
        {"label": _("Assignment Status"), "fieldname": "assignment_status", "fieldtype": "Data", "width": 110},
        {"label": _("Salary Structure"), "fieldname": "salary_structure", "fieldtype": "Data", "width": 230},
        {"label": _("Salary Basis / Source Status"), "fieldname": "salary_basis", "fieldtype": "Data", "width": 170},
        {"label": _("Structure Company"), "fieldname": "structure_company", "fieldtype": "Link", "options": "Company", "width": 160},
        {"label": _("Effective From"), "fieldname": "effective_from", "fieldtype": "Date", "width": 100},
        {"label": _("Base"), "fieldname": "base", "fieldtype": "Currency", "width": 110},
        {"label": _("Variable"), "fieldname": "variable", "fieldtype": "Currency", "width": 110},
    ]
    query = """
        WITH ranked_assignments AS (
            SELECT ssa.employee, ssa.salary_structure, ss.company AS structure_company,
                   ssa.base, ssa.variable, ssa.from_date,
                   ROW_NUMBER() OVER (
                       PARTITION BY ssa.employee
                       ORDER BY ssa.from_date DESC, ssa.modified DESC, ssa.name DESC
                   ) AS rank_no
            FROM `tabSalary Structure Assignment` ssa
            JOIN `tabSalary Structure` ss ON ss.name=ssa.salary_structure
            WHERE ssa.docstatus=1 AND ssa.from_date <= %(as_of_date)s
        ), report_rows AS (
            SELECT e.name AS employee, e.employee_number AS employee_id,
                   e.employee_name, e.company, e.branch, e.department, e.designation,
                   e.status AS employee_status,
                   CASE
                       WHEN ra.employee IS NULL THEN 'Missing'
                       WHEN ra.structure_company <> e.company THEN 'Company Mismatch'
                       ELSE 'Assigned'
                   END AS assignment_status,
                   COALESCE(ra.salary_structure, '') AS salary_structure,
                   CASE
                       WHEN e.employment_type = 'Worker' AND e.branch = 'TCL Factory'
                           AND ra.salary_structure = 'TCL Factory Daily Wage Worker Structure'
                           THEN 'Daily Wage Policy'
                       WHEN ra.salary_structure IN ('TCL Source Staff Monthly Salary Structure',
                                                     'EFL Source Staff Monthly Salary Structure')
                           THEN 'Selevo Source Salary'
                       WHEN e.employment_type <> 'Worker' THEN 'Source Salary Pending'
                       ELSE 'Review'
                   END AS salary_basis,
                   COALESCE(ra.structure_company, '') AS structure_company,
                   COALESCE(ra.base, 0) AS base,
                   COALESCE(ra.variable, 0) AS variable,
                   ra.from_date AS effective_from
            FROM `tabEmployee` e
            LEFT JOIN ranked_assignments ra
                ON ra.employee=e.name AND ra.rank_no=1
            WHERE e.company=%(company)s
              AND (%(employee_status)s='All' OR e.status=%(employee_status)s)
              AND (%(branch)s='' OR e.branch=%(branch)s)
              AND (%(department)s='' OR e.department=%(department)s)
        )
        SELECT employee, employee_id, employee_name, company, branch, department, designation,
               employee_status, assignment_status, salary_structure, salary_basis, structure_company,
               effective_from, base, variable
        FROM report_rows
        WHERE %(assignment_status)s='All' OR assignment_status=%(assignment_status)s
        ORDER BY assignment_status DESC, branch, department, employee
    """
    return columns, frappe.db.sql(query, filters, as_dict=True)
