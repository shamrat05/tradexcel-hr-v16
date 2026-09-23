from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from tradex_hr.tradexcel_hr.company_context import assert_company_access


REVIEW_ROLES = {"Tradexcel Owner/Director", "System Manager"}


class TradexcelWageFloorClassification(Document):
	def validate(self):
		frappe.has_permission("Employee", "read", self.employee, throw=True)
		assert_company_access(self.company, require_explicit_scope=True)
		employee = frappe.db.get_value("Employee", self.employee, ["company", "branch"], as_dict=True)
		if not employee:
			frappe.throw(_("Select an existing Employee."))
		if employee.company != self.company or (employee.branch or "") != (self.branch or ""):
			frappe.throw(_("Classification Company and Branch must match the Employee's employment location."))
		if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
			frappe.throw(_("Effective To must be on or after Effective From."))
		if not (self.legal_review_notes or "").strip():
			frappe.throw(_("Record the independent wage-scope and classification review."))
		if self.coverage_decision == "Covered":
			self._validate_covered()
		elif self.coverage_decision == "Reviewed Outside Scope":
			if self.worker_category or self.gazette_grade or self.location_category:
				frappe.throw(_("An Outside Scope decision cannot carry a statutory category, grade, or location."))
			self._validate_rule_set()
		else:
			frappe.throw(_("Choose Covered or Reviewed Outside Scope explicitly."))
		self._validate_no_overlap()

	def _validate_covered(self):
		if not self.rule_set or not self.worker_category or not self.gazette_grade or not self.location_category:
			frappe.throw(_("Covered employees need an approved Rule Set, legal category, grade, and location category."))
		rule = self._validate_rule_set()
		if not any(row.worker_category == self.worker_category and row.gazette_grade == self.gazette_grade and row.location_category == self.location_category for row in rule.floor_rows):
			frappe.throw(_("The selected category, grade, and location are not present in the approved Rule Set."))

	def _validate_rule_set(self):
		if not self.rule_set:
			frappe.throw(_("Every wage coverage decision must reference the exact approved Rule Set it reviews."))
		rule = frappe.get_doc("Tradexcel Wage Floor Rule Set", self.rule_set)
		if rule.docstatus != 1:
			frappe.throw(_("The linked wage-floor Rule Set must be approved and submitted."))
		if rule.company != self.company or (rule.branch and rule.branch != (self.branch or "")):
			frappe.throw(_("The wage-floor Rule Set must match the Employee's Company and Establishment."))
		if getdate(self.effective_from) < getdate(rule.effective_from) or (rule.effective_to and (not self.effective_to or getdate(self.effective_to) > getdate(rule.effective_to))):
			frappe.throw(_("The classification effective dates must remain inside the linked wage Rule Set version."))
		return rule

	def _validate_no_overlap(self):
		rows = frappe.get_all(
			"Tradexcel Wage Floor Classification",
			filters={"employee": self.employee, "docstatus": 1},
			fields=["name", "effective_from", "effective_to"],
		)
		start = getdate(self.effective_from)
		end = getdate(self.effective_to) if self.effective_to else getdate("9999-12-31")
		for row in rows:
			if row.name == self.name:
				continue
			other_start = getdate(row.effective_from)
			other_end = getdate(row.effective_to) if row.effective_to else getdate("9999-12-31")
			if start <= other_end and other_start <= end:
				frappe.throw(_("This Employee already has an approved wage classification covering an overlapping period: {0}.").format(row.name), title=_("WAGE_CLASSIFICATION_CONFLICT"))

	def before_submit(self):
		roles = set(frappe.get_roles())
		if frappe.session.user != "Administrator" and not roles.intersection(REVIEW_ROLES):
			frappe.throw(_("A Tradexcel Owner/Director must approve the employee wage classification."), frappe.PermissionError)
		if frappe.session.user != "Administrator" and self.owner == frappe.session.user:
			frappe.throw(_("The classification maker cannot approve the same employee classification."), frappe.PermissionError)
		self.reviewed_by = frappe.session.user
		self.reviewed_at = frappe.utils.now_datetime()

	def before_update_after_submit(self):
		frappe.throw(_("Approved wage classifications are immutable. Create a new effective-dated decision."))

	def before_cancel(self):
		assert_company_access(self.company, require_explicit_scope=True)
		start = getdate(self.effective_from)
		end = self.effective_to or "9999-12-31"
		if frappe.db.exists("Salary Slip", {"employee": self.employee, "company": self.company, "docstatus": 1, "start_date": ["<=", end], "end_date": [">=", start]}):
			frappe.throw(_("A submitted Salary Slip has consumed this classification. Preserve it and use a new reviewed effective-dated decision."))
