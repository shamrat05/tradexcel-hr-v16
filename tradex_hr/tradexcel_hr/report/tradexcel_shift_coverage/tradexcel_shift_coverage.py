"""Native Employee and Shift Assignment coverage, scoped to visible Employees."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate, today

from tradex_hr.tradexcel_hr.company_context import resolve_company
from tradex_hr.tradexcel_hr.report_scope import permitted_employee_names


COVERAGE_FILTERS = {"All", "Overlap", "Missing", "Assigned", "Default only"}


def normalize_filters(filters: dict | None = None) -> frappe._dict:
    values = frappe._dict(filters or {})
    values.company = resolve_company(values)
    values.as_of_date = getdate(values.get("as_of_date") or today()).isoformat()
    values.branch = values.get("branch") or ""
    values.department = values.get("department") or ""
    values.coverage = values.get("coverage") or "All"
    if values.coverage not in COVERAGE_FILTERS:
        frappe.throw(_("Choose a valid shift coverage option."))
    return values


def execute(filters=None):
    filters = normalize_filters(filters)
    employee_names = permitted_employee_names(
        filters.company,
        branch=filters.branch,
        department=filters.department,
    )
    columns = [
        {"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 120},
        {"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 180},
        {"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 160},
        {"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 130},
        {"label": _("Department"), "fieldname": "department", "fieldtype": "Link", "options": "Department", "width": 150},
        {"label": _("Assignments"), "fieldname": "assignment_count", "fieldtype": "Int", "width": 90},
        {"label": _("Assigned Shifts"), "fieldname": "assigned_shifts", "fieldtype": "Data", "width": 170},
        {"label": _("Default Shift"), "fieldname": "default_shift", "fieldtype": "Link", "options": "Shift Type", "width": 140},
        {"label": _("Coverage"), "fieldname": "coverage", "fieldtype": "Data", "width": 190},
    ]
    if not employee_names:
        return columns, []

    rows = frappe.db.sql(
        """
        WITH active_assignments AS (
            SELECT employee, COUNT(*) AS assignment_count,
                   GROUP_CONCAT(DISTINCT shift_type ORDER BY shift_type SEPARATOR ', ') AS assigned_shifts
            FROM `tabShift Assignment`
            WHERE docstatus=1 AND start_date<=%(as_of_date)s
              AND (end_date IS NULL OR end_date>=%(as_of_date)s)
              AND employee IN %(employee_names)s
            GROUP BY employee
        )
        SELECT e.name AS employee, e.employee_name, e.company, e.branch, e.department,
               COALESCE(a.assignment_count, 0) AS assignment_count,
               COALESCE(a.assigned_shifts, '') AS assigned_shifts,
               COALESCE(e.default_shift, '') AS default_shift,
               CASE
                   WHEN a.assignment_count>1 THEN 'Multiple active assignments — review'
                   WHEN a.assignment_count=1 THEN 'Assigned'
                   WHEN e.default_shift IS NOT NULL AND e.default_shift<>'' THEN 'Default shift only'
                   ELSE 'No shift assigned — review'
               END AS coverage
        FROM `tabEmployee` e
        LEFT JOIN active_assignments a ON a.employee=e.name
        WHERE e.company=%(company)s AND e.name IN %(employee_names)s
          AND (%(branch)s='' OR e.branch=%(branch)s)
          AND (%(department)s='' OR e.department=%(department)s)
          AND e.status='Active'
          AND (e.date_of_joining IS NULL OR e.date_of_joining<=%(as_of_date)s)
          AND (e.relieving_date IS NULL OR e.relieving_date>=%(as_of_date)s)
          AND (%(coverage)s='All'
               OR (%(coverage)s='Overlap' AND a.assignment_count>1)
               OR (%(coverage)s='Assigned' AND a.assignment_count=1)
               OR (%(coverage)s='Missing' AND a.assignment_count IS NULL
                   AND (e.default_shift IS NULL OR e.default_shift=''))
               OR (%(coverage)s='Default only' AND a.assignment_count IS NULL
                   AND e.default_shift IS NOT NULL AND e.default_shift<>''))
        ORDER BY CASE WHEN a.assignment_count>1 THEN 0
                      WHEN a.assignment_count IS NULL AND (e.default_shift IS NULL OR e.default_shift='') THEN 1
                      ELSE 2 END, e.branch, e.department, e.name
        """,
        {**filters, "employee_names": employee_names},
        as_dict=True,
    )
    return columns, rows
