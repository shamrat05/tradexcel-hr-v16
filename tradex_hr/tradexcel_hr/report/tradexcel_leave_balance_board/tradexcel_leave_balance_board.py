"""Tradexcel Leave Balance Board — file-backed Script Report.

Promoted from a DB-backed Query Report (2026-09-23). See the Payroll Register
module docstring for the rationale; it is identical.

The `as_of_date` placeholder previously had no declaration in some call paths,
which produced `KeyError: b'as_of_date'` from SQL interpolation. It is now
defaulted and validated in Python before the query runs.

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

    filters.as_of_date = filters.get("as_of_date") or today()

    return filters


def execute(filters=None):
    filters = _normalise(filters)
    from tradex_hr.tradexcel_hr.report_scope import permitted_employee_names

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
        {"label": _("Leave Type"), "fieldname": "leave_type", "fieldtype": "Link",
         "options": "Leave Type", "width": 150},
        {"label": _("From Date"), "fieldname": "from_date", "fieldtype": "Date",
         "width": 90},
        {"label": _("To Date"), "fieldname": "to_date", "fieldtype": "Date",
         "width": 90},
        {"label": _("Allocated"), "fieldname": "new_leaves_allocated",
         "fieldtype": "Float", "width": 90},
        {"label": _("Total Allocated"), "fieldname": "total_leaves_allocated",
         "fieldtype": "Float", "width": 100},
    ]

    if not employees:
        return columns, []

    data = frappe.db.sql(
        """
        SELECT e.name AS employee, e.employee_number, e.employee_name, e.company,
               la.leave_type, la.from_date, la.to_date,
               la.new_leaves_allocated, la.total_leaves_allocated
        FROM `tabLeave Allocation` la
        JOIN `tabEmployee` e ON e.name = la.employee
        WHERE e.company = %(company)s
          AND e.name IN %(employee_names)s
          AND la.from_date <= %(as_of_date)s
          AND la.to_date >= %(as_of_date)s
        ORDER BY e.department, e.employee_name, la.leave_type
        """,
        {**filters, "employee_names": employees},
        as_dict=True,
    )

    return columns, data
