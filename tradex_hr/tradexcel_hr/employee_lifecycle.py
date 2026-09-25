"""Guard native HRMS employee movement and employment-spell boundaries.

Employee, Employee Transfer, Employee Promotion, and Salary Structure Assignment
remain the authoritative records. This module only validates their relationships.
"""

import frappe
from frappe import _
from frappe.utils import getdate


def validate_employee_transfer(doc, method=None):
	"""Require HRMS's new Employee ID path when a transfer changes company."""
	if not doc.get("employee"):
		return

	current_company = frappe.db.get_value("Employee", doc.employee, "company")
	new_company = doc.get("new_company")
	if current_company and new_company and current_company != new_company and not doc.get("create_new_employee_id"):
		frappe.throw(
			_("A cross-company transfer must create a new Employee ID. Use the native Employee Transfer option."),
			frappe.ValidationError,
		)


def validate_employee_promotion(doc, method=None):
	"""Keep salary changes on a new, effective native Salary Structure Assignment."""
	if not doc.get("employee") or not doc.get("promotion_date"):
		return

	current_ctc = doc.get("current_ctc")
	revised_ctc = doc.get("revised_ctc")
	if revised_ctc in (None, "") or revised_ctc == current_ctc:
		return

	assignment = frappe.db.get_value(
		"Salary Structure Assignment",
		{
			"employee": doc.employee,
			"from_date": getdate(doc.promotion_date),
			"docstatus": 1,
		},
		["name", "company", "salary_structure"],
		as_dict=True,
	)
	if not assignment:
		frappe.throw(
			_("Create and submit a new Salary Structure Assignment effective on the promotion date before recording a salary revision."),
			frappe.ValidationError,
		)

	company = frappe.db.get_value("Employee", doc.employee, "company")
	if assignment.company != company:
		frappe.throw(
			_("The effective Salary Structure Assignment must use the Employee's current Company."),
			frappe.ValidationError,
		)

	pay_basis = frappe.db.get_value("Salary Structure", assignment.salary_structure, "custom_tradex_pay_basis")
	if not pay_basis:
		frappe.throw(
			_("Set the explicit Tradexcel pay basis on the Salary Structure before recording a salary revision."),
			frappe.ValidationError,
		)


def validate_employee_employment_spell(doc, method=None):
	"""Do not rewrite a completed employment spell to model a rehire."""
	if doc.is_new():
		return

	previous = frappe.db.get_value(
		"Employee", doc.name, ["date_of_joining", "relieving_date", "status"], as_dict=True
	)
	if not previous or not previous.relieving_date:
		return

	if getattr(frappe.flags, "tradex_transfer_cancellation_employee", None) == doc.name:
		return

	if (
		getdate(doc.date_of_joining) != getdate(previous.date_of_joining)
		or not doc.get("relieving_date")
		or getdate(doc.get("relieving_date")) != getdate(previous.relieving_date)
		or (previous.status == "Left" and doc.status != "Left")
	):
		frappe.throw(
			_("A completed employment spell is immutable. Create a new Employee record for a rehire."),
			frappe.ValidationError,
		)


class EmployeeTransferLifecycleMixin:
	"""Permit HRMS transfer cancellation to reverse only its own spell changes."""

	def on_cancel(self):
		previous_employee = getattr(frappe.flags, "tradex_transfer_cancellation_employee", None)
		if self.get("create_new_employee_id"):
			frappe.flags.tradex_transfer_cancellation_employee = self.employee
		try:
			super().on_cancel()
		finally:
			frappe.flags.tradex_transfer_cancellation_employee = previous_employee
