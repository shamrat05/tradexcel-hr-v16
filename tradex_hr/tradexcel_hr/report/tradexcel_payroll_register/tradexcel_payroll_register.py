"""Tradexcel Payroll Register — file-backed Script Report.

Promoted from a DB-backed Query Report (2026-09-23) for three reasons:

1. **A Query Report cannot defend itself.** Frappe runs
   `frappe.db.sql(query, filters)` directly, so any missing placeholder raises
   from the DB driver — `KeyError: b'from_date'` or `ProgrammingError: format
   requires a mapping` — *before MariaDB sees the query*. A Script Report
   normalises in Python first, so a direct API call with `{}` resolves defaults
   instead of producing a traceback.

2. **Deployment reproducibility.** The definition lived only in a `tabReport`
   row, recreated by `install.py`. As a standard report the JSON/Python/JS are
   committed and loaded by `bench migrate`.

3. **Permission scoping.** `frappe.db.sql` does not enforce row-level
   permissions; the company filter is applied explicitly here.

The SQL is unchanged from the original Query Report — only filter handling was
added. Payroll calculation logic is deliberately untouched.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate, today


def _normalise(filters) -> frappe._dict:
    """Fill and validate the filters this report's SQL requires.

    Every placeholder in the query must exist before `frappe.db.sql` runs, or the
    driver raises. Defaults mirror the report's declared UI filters.
    """
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

    from tradex_hr.tradexcel_hr.company_context import assert_company_access

    assert_company_access(filters.company)
    return filters


def execute(filters=None):
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

    data = frappe.db.sql(
        """
        SELECT s.name, s.employee, s.employee_name, s.company,
               s.start_date, s.end_date, s.gross_pay, s.total_deduction,
               s.net_pay, s.docstatus
        FROM `tabSalary Slip` s
        WHERE s.company = %(company)s
          AND s.start_date >= %(from_date)s
          AND s.end_date <= %(to_date)s
        ORDER BY s.start_date, s.employee
        """,
        filters,
        as_dict=True,
    )

    return columns, data
