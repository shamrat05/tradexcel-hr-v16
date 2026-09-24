import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, today

from tradex_hr.tradexcel_hr.company_context import assert_company_access


APPROVER_ROLE = "Tradexcel Owner/Director"


class TradexcelWorkingTimeClassification(Document):
	def validate(self):
		assert_company_access(self.company, require_explicit_scope=True)
		if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
			frappe.throw(_("Effective To must be on or after Effective From."))
		employee = frappe.db.get_value("Employee", self.employee, ["company", "branch"], as_dict=True)
		if not employee or employee.company != self.company:
			frappe.throw(_("Working-time classification Company must match the Employee."))
		if self.branch and frappe.db.get_value("Branch", self.branch, "company") != self.company:
			frappe.throw(_("The reviewed Branch must belong to the Employee's Company."))
		historical = bool(self.effective_to and getdate(self.effective_to) < getdate(today()))
		if historical:
			if employee.branch and not self.branch:
				frappe.throw(_("A historical classification after a Branch transfer must record the reviewed historical establishment."))
			# The reviewed historical Branch is supplied explicitly; it is not inferred from today's Employee record.
		elif (employee.branch or "") != (self.branch or ""):
			frappe.throw(_("A current or future working-time classification must match the Employee's current Branch."))
		rule = frappe.db.get_value(
			"Tradexcel Working Time Rule Set",
			self.rule_set,
			["docstatus", "company", "branch", "legal_regime", "effective_from", "effective_to"],
			as_dict=True,
		)
		if not rule or rule.docstatus != 1 or rule.company != self.company:
			frappe.throw(_("Select a submitted Working Time Rule Set for the same Company."))
		if rule.branch and rule.branch != self.branch:
			frappe.throw(_("The classification Branch must match a branch-specific Rule Set."))
		if getdate(self.effective_from) < getdate(rule.effective_from) or (
			rule.effective_to and (not self.effective_to or getdate(self.effective_to) > getdate(rule.effective_to))
		):
			frappe.throw(_("Classification dates must fall inside the approved Rule Set dates."))
		if not (self.review_notes or "").strip():
			frappe.throw(_("Record the independent legal classification decision."))
		self._validate_no_overlap()

	def _validate_no_overlap(self):
		others = frappe.get_all(
			self.doctype,
			filters={"employee": self.employee, "company": self.company, "docstatus": ["!=", 2], "name": ["!=", self.name]},
			fields=["name", "effective_from", "effective_to"],
		)
		for other in others:
			if (not other.effective_to or getdate(other.effective_to) >= getdate(self.effective_from)) and (
				not self.effective_to or getdate(other.effective_from) <= getdate(self.effective_to)
			):
				frappe.throw(_("This Employee already has a working-time classification overlapping {0}.").format(other.name))

	def before_submit(self):
		assert_company_access(self.company, require_explicit_scope=True)
		if frappe.session.user != "Administrator" and (
			APPROVER_ROLE not in frappe.get_roles() or self.owner == frappe.session.user
		):
			frappe.throw(_("A different company-scoped Tradexcel Owner/Director must approve this classification."))
		self.reviewed_by = frappe.session.user
		self.reviewed_at = now_datetime()

	def before_update_after_submit(self):
		frappe.throw(_("Submitted working-time classifications are immutable; create a new effective record."))

	def before_cancel(self):
		frappe.throw(_("Submitted working-time classifications are historical evidence and cannot be cancelled."))
