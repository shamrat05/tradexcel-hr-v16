"""Workforce Daily Attendance Board — file-backed Script Report.

Promoted from a DB-backed Query Report (2026-09-23). See the Payroll Register
module docstring for the rationale; it is identical.

`attendance_date` had a UI default but `company` did not, and neither was
validated before SQL interpolation. Both are now defaulted in Python, so a
direct API call with `{}` returns a normal result instead of a `KeyError`.

Raw report SQL is constrained to Employees resolved through Frappe's
permission-aware list API; SQL itself does not apply User Permissions.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import today


def _normalise(filters) -> frappe._dict:
    filters = frappe._dict(filters or {})

    company = filters.get("company") or frappe.defaults.get_user_default("Company")
    if not company:
        frappe.throw(_("Select a Company. Set a Company default for your user or choose one in the filter."))
    filters.company = company

    filters.attendance_date = filters.get("attendance_date") or today()

    return filters


def execute(filters=None):
    filters = _normalise(filters)
    from workforce_suite.workforce_suite.report_scope import permitted_employee_names

    employees = permitted_employee_names(
        filters.company,
        branch=filters.get("branch"),
        department=filters.get("department"),
    )

    columns = [
        {"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link",
         "options": "Employee", "width": 120},
        {"label": _("Employee ID"), "fieldname": "employee_number",
         "fieldtype": "Data", "width": 100},
        {"label": _("Employee Name"), "fieldname": "employee_name",
         "fieldtype": "Data", "width": 180},
        {"label": _("Company"), "fieldname": "company", "fieldtype": "Link",
         "options": "Company", "width": 160},
        {"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link",
         "options": "Branch", "width": 130},
        {"label": _("Department"), "fieldname": "department", "fieldtype": "Link",
         "options": "Department", "width": 160},
        {"label": _("Attendance"), "fieldname": "attendance", "fieldtype": "Link",
         "options": "Attendance", "width": 150},
        {"label": _("Attendance State"), "fieldname": "attendance_state", "fieldtype": "Data",
         "width": 150},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data",
         "width": 90},
        {"label": _("In Time"), "fieldname": "in_time", "fieldtype": "Datetime",
         "width": 140},
        {"label": _("Out Time"), "fieldname": "out_time", "fieldtype": "Datetime",
         "width": 140},
        {"label": _("Late"), "fieldname": "late_entry", "fieldtype": "Check",
         "width": 60},
        {"label": _("Early Exit"), "fieldname": "early_exit",
         "fieldtype": "Check", "width": 80},
        {"label": _("Punches"), "fieldname": "punches", "fieldtype": "Int",
         "width": 70},
    ]

    if not employees:
        return columns, []

    data = frappe.db.sql(
        """
        SELECT e.name AS employee, e.employee_number, e.employee_name, e.company,
               e.branch, e.department,
               a.name AS attendance,
               CASE WHEN a.name IS NULL THEN 'Not Marked'
                    WHEN a.docstatus = 0 THEN 'Draft Attendance'
                    ELSE 'Submitted Attendance' END AS attendance_state,
               CASE WHEN a.name IS NULL THEN 'Not Marked' ELSE a.status END AS status,
               a.in_time, a.out_time,
               COALESCE(a.late_entry, 0) AS late_entry,
               COALESCE(a.early_exit, 0) AS early_exit,
               COUNT(c.name) AS punches
        FROM `tabEmployee` e
        LEFT JOIN `tabAttendance` a
               ON a.employee = e.name
              AND a.attendance_date = %(attendance_date)s
              AND a.docstatus < 2
        LEFT JOIN `tabEmployee Checkin` c
               ON c.employee = e.name
              AND DATE(c.time) = %(attendance_date)s
        WHERE e.company = %(company)s
          AND e.name IN %(employee_names)s
          AND (e.status = 'Active' OR e.relieving_date >= %(attendance_date)s)
        GROUP BY e.name, a.name
        ORDER BY e.branch, e.department, e.name
        """,
        {**filters, "employee_names": employees},
        as_dict=True,
    )

    return columns, data
