"""Scoped Tradexcel preparation on the native HRMS salary assignment tool.

Tradexcel makers use HRMS' native filters and employee picker, but this path
only creates draft native Salary Structure Assignments. An independent native
SSA list-view submit remains the approval action.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import math

import frappe
from frappe import _
from frappe.utils import cint, get_link_to_form, getdate

from hrms.hr.utils import validate_bulk_tool_fields

from tradex_hr.tradexcel_hr.pay_basis import DAILY, MONTHLY
from tradex_hr.tradexcel_hr.bulk_execution_safety import private_bulk_results


MAKER_ROLES = {"Tradexcel HR Manager", "Tradexcel Payroll Manager"}
NATIVE_HR_ROLES = {"HR User", "HR Manager"}
VALID_PAY_BASES = {MONTHLY, DAILY}


def _roles() -> set[str]:
	return set(frappe.get_roles())


def _tool_mode() -> str:
	if frappe.session.user == "Administrator":
		return "native"
	roles = _roles()
	# Preserve the installed HRMS one-step action for users who already have a
	# native HR role, including mixed native/Tradexcel role accounts.
	if roles & NATIVE_HR_ROLES:
		return "native"
	if roles & MAKER_ROLES:
		return "tradexcel_maker"
	frappe.throw(_("You are not permitted to prepare salary assignments."), frappe.PermissionError)


def _amount(value, label: str) -> float:
	if isinstance(value, bool):
		frappe.throw(_("{0} must be a valid number.").format(_(label)))
	try:
		amount = Decimal(str(value if value not in (None, "") else 0))
	except (InvalidOperation, ValueError, TypeError):
		frappe.throw(_("{0} must be a valid number.").format(_(label)))
	if not amount.is_finite() or amount < 0:
		frappe.throw(_("{0} must be a finite, non-negative amount.").format(_(label)))
	result = float(amount)
	if not math.isfinite(result):
		frappe.throw(_("{0} is outside the supported numeric range.").format(_(label)))
	return result


class TradexcelBulkSalaryStructureAssignmentMixin:
	"""Add scoped preview and a draft-only path while delegating native users."""

	def _validate_structure_context(self):
		if not self.get("salary_structure") or not self.get("from_date"):
			return None

		structure = frappe.get_doc("Salary Structure", self.salary_structure)
		structure.check_permission("read")
		if structure.docstatus != 1 or structure.is_active != "Yes":
			frappe.throw(_("Choose an active, submitted Salary Structure."))
		if structure.custom_tradex_pay_basis not in VALID_PAY_BASES:
			frappe.throw(_("The Salary Structure needs an explicit Monthly Salary or Daily Wage pay basis."))
		if self.get("company") and self.company != structure.company:
			frappe.throw(_("The selected Company must match the Salary Structure."))
		from tradex_hr.tradexcel_hr.employee_lifecycle import _assert_company_visible

		_assert_company_visible(structure.company)
		if self.get("currency") and self.currency != structure.currency:
			frappe.throw(_("The selected currency must match the Salary Structure."))
		self.company = structure.company
		self.currency = structure.currency
		return structure

	def _permission_intersection(self, native_rows):
		"""Retain native eligible rows only when Employee read/User Permission allows them."""
		rows = list(native_rows or [])
		employee_names = [row.get("name") or row.get("employee") for row in rows]
		employee_names = [name for name in employee_names if name]
		if not employee_names:
			return []
		visible = set(
			frappe.get_list(
				"Employee",
				filters={"name": ["in", employee_names]},
				fields=["name"],
				pluck="name",
			)
		)
		return [row for row in rows if (row.get("name") or row.get("employee")) in visible]

	def _eligible_rows(self, advanced_filters=None):
		structure = self._validate_structure_context()
		if not structure:
			return []
		if self.get("company") != structure.company:
			frappe.throw(_("The selected Company must match the Salary Structure."))
		rows = super().get_employees(advanced_filters or [])
		rows = self._permission_intersection(rows)
		if _tool_mode() == "tradexcel_maker":
			# Native preview excludes submitted same-date authorities. Drafts must
			# also be excluded for a repeatable maker workflow.
			names = [row.get("name") or row.get("employee") for row in rows]
			if names:
				existing = set(
					frappe.get_all(
						"Salary Structure Assignment",
						filters={
							"employee": ["in", names],
							"from_date": getdate(self.from_date),
							"docstatus": ["in", [0, 1]],
						},
						pluck="employee",
					)
				)
				rows = [row for row in rows if (row.get("name") or row.get("employee")) not in existing]
		return rows

	@frappe.whitelist()
	def get_employees(self, advanced_filters: list | None = None) -> list:
		return self._eligible_rows(advanced_filters)

	def _validated_context(self, employees):
		mode = _tool_mode()
		mandatory_fields = ["salary_structure", "from_date", "company"]
		validate_bulk_tool_fields(self, mandatory_fields, employees)
		structure = self._validate_structure_context()
		if not structure or self.company != structure.company:
			frappe.throw(_("The selected Company must match the Salary Structure."))
		if not frappe.has_permission("Bulk Salary Structure Assignment", "write"):
			frappe.throw(_("You are not permitted to prepare salary assignments."), frappe.PermissionError)

		company = frappe.get_doc("Company", structure.company)
		if not frappe.has_permission("Company", "read", doc=company):
			frappe.throw(_("The Company is outside your permitted scope."), frappe.PermissionError)
		configured_account = company.default_payroll_payable_account
		account_name = self.get("payroll_payable_account") or configured_account
		if not account_name:
			frappe.throw(_("Set the Company's Default Payroll Payable Account before preparing assignments."))
		if mode == "tradexcel_maker" and account_name != configured_account:
			frappe.throw(_("Use the Company's configured Default Payroll Payable Account."))
		# This account comes from Company configuration rather than client choice.
		# Read the minimal native fields internally so account browsing permission
		# is not added to either maker role merely for an auto-filled link field.
		account = frappe.db.get_value(
			"Account", account_name, ["company", "root_type", "is_group", "account_currency"], as_dict=True
		)
		company_currency = frappe.db.get_value("Company", structure.company, "default_currency")
		if (
			not account
			or account.company != structure.company
			or account.root_type != "Liability"
			or cint(account.is_group)
			or account.account_currency not in {structure.currency, company_currency}
		):
			frappe.throw(_("The Company's configured Payroll Payable Account is not valid for this structure."))

		tax_slab_name = self.get("income_tax_slab")
		if tax_slab_name:
			tax_slab = frappe.get_doc("Income Tax Slab", tax_slab_name)
			tax_slab.check_permission("read")
			if (
				tax_slab.company != structure.company
				or tax_slab.currency != structure.currency
				or tax_slab.docstatus != 1
				or cint(tax_slab.disabled)
			):
				frappe.throw(_("Choose an active, submitted Income Tax Slab for this Company and currency."))
		# Normalize date objects/strings through Frappe, without accepting a
		# different client-side effective date than the server document.
		self.from_date = getdate(self.from_date)
		self.payroll_payable_account = account_name

		selected = []
		for row in employees:
			if not isinstance(row, dict) or not row.get("employee"):
				frappe.throw(_("Each selected row must identify an Employee."))
			selected.append(row["employee"])
		if len(selected) != len(set(selected)):
			frappe.throw(_("An Employee may only be selected once."))

		eligible = {
			row.get("name") or row.get("employee")
			for row in self._eligible_rows([])
		}
		if not set(selected).issubset(eligible):
			frappe.throw(
				_("A selected Employee is no longer eligible or is outside your permitted Company/Branch/Department scope."),
				frappe.PermissionError,
			)
		return structure, account_name

	@frappe.whitelist(methods=["POST"])
	def bulk_assign_structure(self, employees: list) -> None:
		mode = _tool_mode()
		if mode == "native":
			self._validated_context(employees)
			for row in employees:
				if not isinstance(row, dict) or not row.get("employee"):
					frappe.throw(_("Each selected row must identify an Employee."))
				_amount(row.get("base"), "Base")
				_amount(row.get("variable"), "Variable")
			return super().bulk_assign_structure(employees)

		self._validated_context(employees)
		if len(employees) <= 30:
			return self._bulk_prepare_drafts(employees)

		frappe.enqueue(self._bulk_prepare_drafts, timeout=3000, employees=employees)
		frappe.msgprint(
			_("Draft Salary Structure Assignments have been queued. Their scope will be checked again when processing starts."),
			alert=True,
			indicator="blue",
		)

	def _bulk_assign_structure(self, employees: list) -> None:
		"""Recheck the queued native path and preserve its one-step HRMS action."""
		self._validated_context(employees)
		previous = getattr(frappe.flags, "tradex_native_bulk_ssa_submission", False)
		frappe.flags.tradex_native_bulk_ssa_submission = True
		try:
			with private_bulk_results():
				return super()._bulk_assign_structure(employees)
		finally:
			frappe.flags.tradex_native_bulk_ssa_submission = previous

	def _bulk_prepare_drafts(self, employees: list) -> None:
		structure, account_name = self._validated_context(employees)
		success, failure = [], []
		for index, row in enumerate(employees, 1):
			employee = row["employee"]
			try:
				frappe.db.savepoint("before_tradex_salary_assignment")
				base = _amount(row.get("base"), "Base")
				variable = _amount(row.get("variable"), "Variable")
				if frappe.db.exists(
					"Salary Structure Assignment",
					{"employee": employee, "from_date": getdate(self.from_date), "docstatus": ["in", [0, 1]]},
				):
					frappe.throw(_("An assignment already exists for this Employee and effective date."))
				if frappe.db.exists(
					"Salary Slip",
					{
						"employee": employee,
						"docstatus": 1,
						"end_date": [">=", getdate(self.from_date)],
					},
				):
					frappe.throw(_("Submitted payroll already uses this effective date. Use a reviewed correction or a later effective assignment."))
				assignment = frappe.get_doc(
					{
						"doctype": "Salary Structure Assignment",
						"employee": employee,
						"salary_structure": structure.name,
						"company": structure.company,
						"currency": structure.currency,
						"payroll_payable_account": account_name,
						"from_date": self.from_date,
						"base": base,
						"variable": variable,
						"income_tax_slab": self.get("income_tax_slab"),
					}
				).insert()
			except Exception as exc:
				frappe.db.rollback(save_point="before_tradex_salary_assignment")
				frappe.log_error(
					f"Bulk Salary Structure Assignment draft failed for {employee}: {str(exc)}",
					reference_doctype="Salary Structure Assignment",
				)
				failure.append(employee)
			else:
				success.append({"doc": get_link_to_form("Salary Structure Assignment", assignment.name), "employee": employee})
			frappe.publish_progress(index * 100 / len(employees), title=_("Preparing Draft Assignments..."))
		frappe.publish_realtime(
			"completed_bulk_salary_structure_assignment",
			message={"success": success, "failure": failure},
			user=frappe.session.user,
			after_commit=True,
		)
