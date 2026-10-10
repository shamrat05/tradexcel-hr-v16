"""Compare native submitted Salary Slip totals across adjacent periods."""

from __future__ import annotations

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, add_months, flt, get_first_day, get_last_day, getdate, today

from workforce_suite.workforce_suite.company_context import resolve_company
from workforce_suite.workforce_suite.report_scope import permitted_employee_names, permitted_salary_slips


def normalize_filters(filters=None):
	values = frappe._dict(filters or {})
	values.company = resolve_company(values)
	values.from_date = getdate(values.get("from_date") or frappe.utils.get_first_day(today())).isoformat()
	values.to_date = getdate(values.get("to_date") or frappe.utils.get_last_day(today())).isoformat()
	values.branch = values.get("branch") or ""
	values.department = values.get("department") or ""
	if values.from_date > values.to_date:
		frappe.throw(_("Period From must be on or before Period To."))
	return values


def _total_rows(slips):
	grouped = defaultdict(list)
	for slip in slips:
		grouped[slip.employee].append(slip)
	return grouped


def _previous_period(from_date, to_date):
	"""Choose the preceding comparable interval without stretching partial ranges."""
	start = getdate(from_date)
	end = getdate(to_date)
	if start.day == 1 and end == getdate(get_last_day(start)) and start.month == end.month:
		return get_first_day(add_months(start, -1)), add_days(start, -1)
	previous_to = add_days(start, -1)
	period_days = (end - start).days
	return add_days(previous_to, -period_days), previous_to


def execute(filters=None):
	filters = normalize_filters(filters)
	columns = [
		{"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 120},
		{"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 180},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 160},
		{"label": _("Branch at Payroll"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 140},
		{"label": _("Department at Payroll"), "fieldname": "department", "fieldtype": "Link", "options": "Department", "width": 160},
		{"label": _("Submitted Slips"), "fieldname": "slip_count", "fieldtype": "Int", "width": 105},
		{"label": _("Gross"), "fieldname": "gross", "fieldtype": "Currency", "width": 110},
		{"label": _("Deductions"), "fieldname": "deductions", "fieldtype": "Currency", "width": 110},
		{"label": _("Current Net"), "fieldname": "current_net", "fieldtype": "Currency", "width": 120},
		{"label": _("Previous Net"), "fieldname": "previous_net", "fieldtype": "Currency", "width": 120},
		{"label": _("Change"), "fieldname": "change", "fieldtype": "Currency", "width": 110},
		{"label": _("Review"), "fieldname": "review", "fieldtype": "Data", "width": 170},
	]

	employees = permitted_employee_names(filters.company)
	if not employees:
		return columns, []
	current = permitted_salary_slips(
		filters.company, employees, from_date=filters.from_date, to_date=filters.to_date,
		branch=filters.branch, department=filters.department,
	)
	if not current:
		return columns, []

	previous_from, previous_to = _previous_period(filters.from_date, filters.to_date)
	previous = permitted_salary_slips(
		filters.company, employees, from_date=previous_from, to_date=previous_to,
		branch=filters.branch, department=filters.department,
	)
	previous_by_employee = _total_rows(previous)
	current_by_employee = _total_rows(current)

	rows = []
	for employee, slips in current_by_employee.items():
		# Branch/Department are native Salary Slip snapshots, never today's
		# Employee values; get_list applies these narrowing filters before totals.
		gross = sum(flt(slip.gross_pay) for slip in slips)
		deductions = sum(flt(slip.total_deduction) for slip in slips)
		current_net = sum(flt(slip.net_pay) for slip in slips)
		prior_slips = previous_by_employee.get(employee, [])
		previous_net = sum(flt(slip.net_pay) for slip in prior_slips) if prior_slips else None
		if current_net == 0:
			review = _("Zero pay — review")
		elif not prior_slips:
			review = _("No previous payroll")
		elif len(slips) > 1:
			review = _("Multiple slips — review")
		else:
			review = _("Compare")
		rows.append(frappe._dict(
			employee=employee,
			employee_name=slips[0].employee_name,
			company=slips[0].company,
			branch=slips[0].branch,
			department=slips[0].department,
			slip_count=len(slips),
			gross=gross,
			deductions=deductions,
			current_net=current_net,
			previous_net=previous_net,
			change=current_net - (previous_net or 0),
			review=review,
		))
	rows.sort(key=lambda row: (row.branch or "", row.department or "", row.employee))
	return columns, rows
