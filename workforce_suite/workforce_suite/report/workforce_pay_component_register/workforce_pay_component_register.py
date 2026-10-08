"""Submitted native Salary Slip component detail with permission-aware scope."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate, today

from workforce_suite.workforce_suite.company_context import resolve_company
from workforce_suite.workforce_suite.report_scope import permitted_employee_names, permitted_salary_slips


COMPONENT_TYPES = {"All", "Earning", "Deduction"}


def normalize_filters(filters=None):
	values = frappe._dict(filters or {})
	values.company = resolve_company(values)
	values.from_date = getdate(values.get("from_date") or frappe.utils.get_first_day(today())).isoformat()
	values.to_date = getdate(values.get("to_date") or frappe.utils.get_last_day(today())).isoformat()
	values.branch = values.get("branch") or ""
	values.department = values.get("department") or ""
	values.component = values.get("component") or ""
	values.component_type = values.get("component_type") or "All"
	if values.from_date > values.to_date:
		frappe.throw(_("Period From must be on or before Period To."))
	if values.component_type not in COMPONENT_TYPES:
		frappe.throw(_("Choose Earning, Deduction, or All for Type."))
	if values.component:
		component_type = frappe.db.get_value("Salary Component", values.component, "type")
		if not component_type:
			frappe.throw(_("Choose a valid Salary Component."))
		if values.component_type != "All" and component_type != values.component_type:
			frappe.throw(_("The selected Salary Component does not match the chosen Type."))
	return values


def execute(filters=None):
	filters = normalize_filters(filters)
	columns = [
		{"label": _("Salary Slip"), "fieldname": "salary_slip", "fieldtype": "Link", "options": "Salary Slip", "width": 150},
		{"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 120},
		{"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 180},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 160},
		{"label": _("Branch at Payroll"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 140},
		{"label": _("Department at Payroll"), "fieldname": "department", "fieldtype": "Link", "options": "Department", "width": 160},
		{"label": _("Period From"), "fieldname": "start_date", "fieldtype": "Date", "width": 100},
		{"label": _("Period To"), "fieldname": "end_date", "fieldtype": "Date", "width": 100},
		{"label": _("Type"), "fieldname": "component_type", "fieldtype": "Data", "width": 95},
		{"label": _("Salary Component"), "fieldname": "salary_component", "fieldtype": "Link", "options": "Salary Component", "width": 180},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Slip Status"), "fieldname": "slip_status", "fieldtype": "Data", "width": 90},
	]

	employees = permitted_employee_names(filters.company)
	slips = permitted_salary_slips(
		filters.company, employees, from_date=filters.from_date, to_date=filters.to_date,
		branch=filters.branch, department=filters.department,
	)
	if not slips:
		return columns, []

	rows = frappe.db.sql(
		"""
		SELECT s.name AS salary_slip, s.employee, s.employee_name, s.company,
		       s.branch, s.department, s.start_date, s.end_date,
		       CASE WHEN d.parentfield='earnings' THEN 'Earning' ELSE 'Deduction' END AS component_type,
		       d.salary_component, d.amount, 'Submitted' AS slip_status
		FROM `tabSalary Detail` d
		JOIN `tabSalary Slip` s ON s.name=d.parent AND d.parenttype='Salary Slip'
		WHERE s.name IN %(slip_names)s
		  AND d.parentfield IN ('earnings', 'deductions')
		  AND (%(branch)s='' OR s.branch=%(branch)s)
		  AND (%(department)s='' OR s.department=%(department)s)
		  AND (%(component)s='' OR d.salary_component=%(component)s)
		  AND (%(component_type)s='All'
		       OR (%(component_type)s='Earning' AND d.parentfield='earnings')
		       OR (%(component_type)s='Deduction' AND d.parentfield='deductions'))
		ORDER BY s.start_date, s.branch, s.department, s.employee,
		         d.parentfield, d.idx
		""",
		{
			"slip_names": tuple(row.name for row in slips),
			"branch": filters.branch,
			"department": filters.department,
			"component": filters.component,
			"component_type": filters.component_type,
		},
		as_dict=True,
	)
	return columns, rows
