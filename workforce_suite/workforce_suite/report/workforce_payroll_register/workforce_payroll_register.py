"""Submitted native Salary Slips within both Employee and payroll permissions."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate, today

from workforce_suite.workforce_suite.report_scope import permitted_employee_names, permitted_salary_slips


def _normalise(filters) -> frappe._dict:
    """Resolve the Company and validate the native payroll period filters."""
    filters = frappe._dict(filters or {})

    company = filters.get("company") or frappe.defaults.get_user_default("Company")
    if not company:
        frappe.throw(_("Select a Company. Set a Company default for your user or choose one in the filter."))
    filters.company = company

    filters.from_date = filters.get("from_date") or frappe.utils.get_first_day(today())
    filters.to_date = filters.get("to_date") or today()

    if getdate(filters.from_date) > getdate(filters.to_date):
        frappe.throw(
            _("From Date ({0}) cannot be after To Date ({1}).").format(
                filters.from_date, filters.to_date
            )
        )

    if not frappe.db.exists("Company", filters.company):
        frappe.throw(_("Company {0} does not exist.").format(filters.company))

    from workforce_suite.workforce_suite.company_context import assert_company_access

    assert_company_access(filters.company)
    return filters


def execute(filters=None):
    from frappe.desk.query_report import get_report_doc

    get_report_doc("Workforce Payroll Register")
    filters = _normalise(filters)

    columns = [
        {"label": _("Salary Slip"), "fieldname": "name", "fieldtype": "Link",
         "options": "Salary Slip", "width": 140},
        {"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link",
         "options": "Employee", "width": 120},
        {"label": _("Employee Name"), "fieldname": "employee_name",
         "fieldtype": "Data", "width": 180},
        {"label": _("Company"), "fieldname": "company", "fieldtype": "Link",
         "options": "Company", "width": 160},
        {"label": _("From Date"), "fieldname": "start_date", "fieldtype": "Date",
         "width": 90},
        {"label": _("To Date"), "fieldname": "end_date", "fieldtype": "Date",
         "width": 90},
        {"label": _("Gross Pay"), "fieldname": "gross_pay",
         "fieldtype": "Currency", "width": 110},
        {"label": _("Deductions"), "fieldname": "total_deduction",
         "fieldtype": "Currency", "width": 110},
        {"label": _("Net Pay"), "fieldname": "net_pay", "fieldtype": "Currency",
         "width": 110},
        {"label": _("Status"), "fieldname": "docstatus", "fieldtype": "Int",
         "width": 60},
    ]

    employees = permitted_employee_names(filters.company)
    data = permitted_salary_slips(
        filters.company, employees, from_date=filters.from_date, to_date=filters.to_date,
    )
    # Preserve this register's full-contained-period selection, unlike the
    # variance report's start-date comparison window.
    data = [row for row in data if getdate(row.end_date) <= getdate(filters.to_date)]
    return columns, data
