"""Guards around native HRMS employee movement and salary records."""

from contextlib import contextmanager

import frappe
from frappe import _
from frappe.utils import flt, getdate


MOVEMENT_FIELDS = (
	"company",
	"branch",
	"department",
	"designation",
	"grade",
	"employment_type",
	"ctc",
)
HISTORY_FIELDS = ("branch", "department", "designation", "from_date", "to_date")
EMPLOYEE_REVIEW_SNAPSHOTS = {
	"Tradexcel Statutory Benefit Enrollment": ("effective_from",),
	"Tradexcel Wage Floor Classification": ("effective_from",),
	"Tradexcel Working Time Classification": ("effective_from",),
	"Tradexcel Maternity Review": ("notice_date", "expected_delivery_date", "actual_delivery_date"),
}


def _throw(message, exc=frappe.ValidationError):
	frappe.throw(_(message), exc)


def _employee_doc(employee):
	return frappe.get_doc("Employee", employee)


def _assert_employee_visible(employee):
	if frappe.session.user == "Administrator":
		return
	doc = _employee_doc(employee)
	if not frappe.has_permission("Employee", "read", doc=doc):
		_throw("Employee is outside your permitted Company scope.", frappe.PermissionError)


def _assert_company_visible(company):
	if not company or frappe.session.user == "Administrator":
		return
	from tradex_hr.tradexcel_hr.company_context import assert_company_access

	assert_company_access(company, require_explicit_scope=True)


def validate_employee_transfer(doc, method=None):
	"""Require native new-ID cross-company moves and enforce source/destination scope."""
	if not doc.get("employee"):
		return

	_employee = frappe.db.get_value("Employee", doc.employee, ["company", "name"], as_dict=True)
	if not _employee:
		return
	if doc.get("company") and doc.company != _employee.company:
		_throw("Transfer Company must match the Employee's current Company.")
	_assert_employee_visible(doc.employee)

	new_company = doc.get("new_company")
	if new_company:
		_assert_company_visible(new_company)
	if _employee.company and new_company and _employee.company != new_company and not doc.get("create_new_employee_id"):
		_throw(
			"A cross-company transfer must create a new Employee ID. Use the native Employee Transfer option."
		)
	if any(row.fieldname == "company" for row in doc.get("transfer_details", [])):
		_throw("Change Company using the native new Employee ID transfer option, not a Transfer detail row.")


def validate_employee_promotion(doc, method=None):
	"""Keep promotion fields in the current Company and salary changes on a submitted SSA."""
	if not doc.get("employee") or not doc.get("promotion_date"):
		return

	_employee = frappe.db.get_value("Employee", doc.employee, ["company", "ctc", "name"], as_dict=True)
	if not _employee:
		return
	_assert_employee_visible(doc.employee)
	if doc.get("company") and doc.company != _employee.company:
		_throw("Employee Promotion must remain in the Employee's current Company.")
	if any(row.fieldname == "company" for row in doc.get("promotion_details", [])):
		_throw("Change Company only through a native cross-company Employee Transfer with a new Employee ID.")
	if any(row.fieldname == "ctc" for row in doc.get("promotion_details", [])):
		_throw("Use Revised CTC for a salary change; do not add CTC as a Promotion detail.")

	current_ctc = doc.get("current_ctc")
	revised_ctc = doc.get("revised_ctc")
	if revised_ctc in (None, "") or flt(revised_ctc) == flt(current_ctc):
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
		_throw(
			"Create and submit a new Salary Structure Assignment effective on the promotion date before recording a salary revision."
		)

	if assignment.company != _employee.company:
		_throw("The effective Salary Structure Assignment must use the Employee's current Company.")

	pay_basis = frappe.db.get_value("Salary Structure", assignment.salary_structure, "custom_tradex_pay_basis")
	if not pay_basis:
		_throw("Set the explicit Tradexcel pay basis on the Salary Structure before recording a salary revision.")


def _same_field_value(fieldname, current, previous):
	if fieldname == "ctc":
		return flt(current) == flt(previous)
	return (current or None) == (previous or None)


def _current_employee_history(doc):
	return [
		{field: row.get(field) for field in HISTORY_FIELDS}
		for row in doc.get("internal_work_history", [])
	]


def _stored_employee_history(employee):
	if not frappe.db.exists("DocType", "Employee Internal Work History"):
		return []
	return frappe.get_all(
		"Employee Internal Work History",
		filters={"parent": employee, "parenttype": "Employee", "parentfield": "internal_work_history"},
		fields=HISTORY_FIELDS,
		order_by="idx asc",
	)


def validate_employee_lifecycle_fields(doc, method=None):
	"""Require native Transfer/Promotion context for movement and history changes."""
	if doc.is_new():
		return

	previous = frappe.db.get_value("Employee", doc.name, list(MOVEMENT_FIELDS), as_dict=True)
	if not previous:
		return

	changed = {
		field for field in MOVEMENT_FIELDS if not _same_field_value(field, doc.get(field), previous.get(field))
	}
	history_changed = _current_employee_history(doc) != _stored_employee_history(doc.name)
	if not changed and not history_changed:
		return

	context = getattr(frappe.flags, "tradex_employee_lifecycle_context", None)
	if (
		not context
		or context.get("employee") != doc.name
		or not changed.issubset(context.get("fields", set()))
		or (history_changed and not context.get("history"))
	):
		_throw(
			"Employee movement and Internal Work History fields must be changed through native Employee Transfer or Employee Promotion."
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
		_throw("A completed employment spell is immutable. Create a new Employee record for a rehire.")


@contextmanager
def _allow_native_employee_movement(record, fieldnames):
	previous = getattr(frappe.flags, "tradex_employee_lifecycle_context", None)
	allowed = {field for field in fieldnames if field in MOVEMENT_FIELDS}
	frappe.flags.tradex_employee_lifecycle_context = {
		"doctype": record.doctype,
		"employee": record.employee,
		"fields": allowed,
		# HRMS seeds the Employee's initial Internal Work History row whenever
		# update_employee_work_history receives any detail, including Promotion
		# details such as employment_type that do not themselves add a history row.
		"history": bool(allowed),
	}
	try:
		yield
	finally:
		frappe.flags.tradex_employee_lifecycle_context = previous


def _detail_fields(doc, fieldname):
	return {row.fieldname for row in doc.get(fieldname, []) if row.get("fieldname")}


def _date_field(doc):
	return doc.transfer_date if doc.doctype == "Employee Transfer" else doc.promotion_date


def _movement_employees(doc):
	return list(dict.fromkeys(filter(None, (doc.get("employee"), doc.get("new_employee_id")))))


def _has_matching(doctype, filters):
	return frappe.db.exists(doctype, filters) if frappe.db.exists("DocType", doctype) else False


def _throw_consumed():
	_throw("LIFECYCLE_CHANGE_ALREADY_CONSUMED: submitted downstream records depend on this effective-dated change.")


def _assert_lifecycle_change_unconsumed(doc):
	effective_date = getdate(_date_field(doc))
	employees = _movement_employees(doc)
	if not employees:
		return

	for employee in employees:
		if _has_matching(
			"Attendance",
			{"employee": employee, "attendance_date": [">=", effective_date], "docstatus": 1},
		):
			_throw_consumed()
		if _has_matching(
			"Salary Slip",
			{"employee": employee, "end_date": [">=", effective_date], "docstatus": 1},
		):
			_throw_consumed()
		if doc.doctype == "Employee Promotion" and doc.get("revised_ctc"):
			if _has_matching(
				"Salary Structure Assignment",
				{"employee": employee, "from_date": effective_date, "docstatus": 1},
			):
				_throw(
					"Cancel the exact effective submitted Salary Structure Assignment first, then retry Promotion cancellation."
				)
			if _has_matching(
				"Salary Structure Assignment",
				{"employee": employee, "from_date": [">=", effective_date], "docstatus": 1},
			):
				_throw_consumed()
		elif _has_matching(
				"Salary Structure Assignment",
				{"employee": employee, "from_date": [">=", effective_date], "docstatus": 1},
			):
			_throw("LIFECYCLE_CHANGE_ALREADY_CONSUMED: a submitted Salary Structure Assignment depends on this movement.")

	for doctype, date_fields in EMPLOYEE_REVIEW_SNAPSHOTS.items():
		if not frappe.db.exists("DocType", doctype):
			continue
		meta = frappe.get_meta(doctype)
		if not meta.has_field("employee") or not meta.has_field("docstatus"):
			continue
		for employee in employees:
			for date_field in date_fields:
				if meta.has_field(date_field) and _has_matching(
					doctype,
					{"employee": employee, date_field: [">=", effective_date], "docstatus": 1},
				):
					_throw_consumed()

	for doctype, date_field in (
		("Employee Transfer", "transfer_date"),
		("Employee Promotion", "promotion_date"),
	):
		for employee in employees:
			filters = {"employee": employee, date_field: [">=", effective_date], "docstatus": 1}
			if doctype == doc.doctype:
				filters["name"] = ["!=", doc.name]
			later_moves = frappe.get_all(doctype, filters=filters, fields=["name", date_field, "creation"])
			for move in later_moves:
				move_date = getdate(move[date_field])
				if move_date > effective_date or (
					move_date == effective_date and move.creation > doc.creation
				):
					_throw_consumed()


def validate_salary_structure_assignment(doc, method=None):
	"""Keep native salary assignments scoped to their Employee's actual Company."""
	if not doc.get("employee") or not doc.get("company") or not doc.get("salary_structure"):
		return

	employee_company = frappe.db.get_value("Employee", doc.employee, "company")
	structure_company = frappe.db.get_value("Salary Structure", doc.salary_structure, "company")
	if employee_company != doc.company or structure_company != doc.company:
		_throw("Salary Structure Assignment Employee, Company, and Salary Structure must belong to the same Company.")
	_assert_employee_visible(doc.employee)
	_assert_company_visible(doc.company)
	if frappe.session.user != "Administrator":
		structure = frappe.get_doc("Salary Structure", doc.salary_structure)
		if not frappe.has_permission("Salary Structure", "read", doc=structure):
			_throw("Salary Structure is outside your permitted Company scope.", frappe.PermissionError)


def validate_salary_structure_assignment_before_submit(doc, method=None):
	"""Enforce independent Payroll Approver submission even via HRMS bulk helpers."""
	if frappe.session.user == "Administrator":
		return
	if "Tradexcel Payroll Approver" not in frappe.get_roles():
		_throw("Only a Tradexcel Payroll Approver may submit a Salary Structure Assignment.", frappe.PermissionError)
	if doc.owner == frappe.session.user:
		_throw("SSA_MAKER_CHECKER: the Salary Structure Assignment maker cannot submit their own assignment.")
	if not frappe.has_permission("Salary Structure Assignment", "submit", doc=doc):
		_throw("Salary Structure Assignment is outside your permitted Company scope.", frappe.PermissionError)


def validate_salary_structure_assignment_before_cancel(doc, method=None):
	"""Do not cancel an assignment already used by payroll or superseded."""
	if not doc.get("employee") or not doc.get("from_date"):
		return
	_assert_employee_visible(doc.employee)
	_assert_company_visible(doc.get("company"))
	if _has_matching(
		"Salary Slip",
		{"employee": doc.employee, "end_date": [">=", getdate(doc.from_date)], "docstatus": 1},
	):
		_throw_consumed()
	if _has_matching(
		"Salary Structure Assignment",
		{
			"employee": doc.employee,
			"name": ["!=", doc.name],
			"from_date": [">", getdate(doc.from_date)],
			"docstatus": 1,
		},
	):
		_throw_consumed()


class EmployeeTransferLifecycleMixin:
	"""Keep native Transfer submit/cancel as the only existing Employee movement path."""

	def before_cancel(self):
		_assert_lifecycle_change_unconsumed(self)

	def on_submit(self):
		with _allow_native_employee_movement(self, _detail_fields(self, "transfer_details")):
			return super().on_submit()

	def on_cancel(self):
		previous_employee = getattr(frappe.flags, "tradex_transfer_cancellation_employee", None)
		if self.get("create_new_employee_id"):
			frappe.flags.tradex_transfer_cancellation_employee = self.employee
		try:
			with _allow_native_employee_movement(self, _detail_fields(self, "transfer_details")):
				return super().on_cancel()
		finally:
			frappe.flags.tradex_transfer_cancellation_employee = previous_employee


class EmployeePromotionLifecycleMixin:
	"""Run native Promotion mutations in a scoped Employee-update context."""

	def before_cancel(self):
		_assert_lifecycle_change_unconsumed(self)

	def on_submit(self):
		fields = _detail_fields(self, "promotion_details")
		if self.get("revised_ctc"):
			fields.add("ctc")
		with _allow_native_employee_movement(self, fields):
			return super().on_submit()

	def on_cancel(self):
		fields = _detail_fields(self, "promotion_details")
		if self.get("revised_ctc"):
			fields.add("ctc")
		with _allow_native_employee_movement(self, fields):
			return super().on_cancel()
