"""Employee joining/leaving events from canonical Employee dates."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate, get_first_day, today

from tradex_hr.tradexcel_hr.company_context import resolve_company
from tradex_hr.tradexcel_hr.report_scope import permitted_employee_names


def normalize_filters(filters: dict | None = None) -> frappe._dict:
    values = frappe._dict(filters or {})
    values.company = resolve_company(values)
    values.from_date = getdate(values.get("from_date") or get_first_day(today())).isoformat()
    values.to_date = getdate(values.get("to_date") or today()).isoformat()
    values.branch = values.get("branch") or ""
    values.department = values.get("department") or ""
    if values.from_date > values.to_date:
        frappe.throw(_("From Date must be on or before To Date."))
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
        {"label": _("Movement"), "fieldname": "movement", "fieldtype": "Data", "width": 90},
        {"label": _("Date"), "fieldname": "movement_date", "fieldtype": "Date", "width": 100},
    ]
    if not employee_names:
        return columns, []

    rows = frappe.db.sql(
        """
        SELECT e.name AS employee, e.employee_name, e.company, e.branch, e.department,
               'Joined' AS movement, e.date_of_joining AS movement_date
        FROM `tabEmployee` e
        WHERE e.company=%(company)s AND e.name IN %(employee_names)s
          AND e.date_of_joining BETWEEN %(from_date)s AND %(to_date)s
          AND (%(branch)s='' OR e.branch=%(branch)s)
          AND (%(department)s='' OR e.department=%(department)s)
        UNION ALL
        SELECT e.name, e.employee_name, e.company, e.branch, e.department,
               'Left', e.relieving_date
        FROM `tabEmployee` e
        WHERE e.company=%(company)s AND e.name IN %(employee_names)s
          AND e.relieving_date BETWEEN %(from_date)s AND %(to_date)s
          AND (%(branch)s='' OR e.branch=%(branch)s)
          AND (%(department)s='' OR e.department=%(department)s)
        ORDER BY movement_date, movement, employee
        """,
        {**filters, "employee_names": employee_names},
        as_dict=True,
    )
    return columns, rows
