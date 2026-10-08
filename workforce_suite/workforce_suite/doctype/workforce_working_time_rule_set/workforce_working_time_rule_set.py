import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime

from workforce_suite.workforce_suite.company_context import assert_company_access


APPROVER_ROLE = "Workforce Owner/Director"


class WorkforceWorkingTimeRuleSet(Document):
	def validate(self):
		assert_company_access(self.company, require_explicit_scope=True)
		if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
			frappe.throw(_("Effective To must be on or after Effective From."))
		if self.branch and frappe.db.get_value("Branch", self.branch, "company") != self.company:
			frappe.throw(_("The establishment Branch must belong to the selected Company."))
		if (self.daily_max_hours or 0) < (self.daily_standard_hours or 0):
			frappe.throw(_("Daily Maximum Hours cannot be below Daily Standard Hours."))
		if (self.weekly_max_hours or 0) < (self.weekly_standard_hours or 0):
			frappe.throw(_("Weekly Maximum Hours cannot be below Weekly Standard Hours."))
		if not (self.legal_review_notes or "").strip():
			frappe.throw(_("Record the legal source and establishment applicability review."))
		self._validate_sources()
		self._validate_no_overlap()

	def _validate_sources(self):
		if not self.sources:
			frappe.throw(_("At least one approved authority source is required."))
		for source in self.sources:
			expected = "Approved Company Rule" if self.legal_regime == "Approved Company Service Rules" else "Final Official Source"
			if source.authority_status != expected:
				frappe.throw(_("Draft, proposal, or unreviewed sources cannot support an approved Working Time Rule Set."))
			if not (source.source_title and source.act_or_rule and source.section_reference and source.effective_date and source.official_reference):
				frappe.throw(_("Each supporting source needs a title, authority/section reference, legal effective date, and official or approved internal reference."))
			if getdate(source.effective_date) > getdate(self.effective_from):
				frappe.throw(_("Rule Set Effective From cannot precede a supporting source's legal effective date."))
		if not (self.overtime_type and self.overtime_multiplier and self.overtime_components):
			frappe.throw(_("Map the native Overtime Type, multiplier, and reviewed statutory wage components."))

	def _validate_no_overlap(self):
		others = frappe.get_all(
			self.doctype,
			filters={"company": self.company, "legal_regime": self.legal_regime, "docstatus": 1, "name": ["!=", self.name]},
			fields=["name", "branch", "effective_from", "effective_to"],
		)
		for other in others:
			branches_overlap = not self.branch or not other.branch or self.branch == other.branch
			date_overlap = (not other.effective_to or getdate(other.effective_to) >= getdate(self.effective_from)) and (
				not self.effective_to or getdate(other.effective_from) <= getdate(self.effective_to)
			)
			if branches_overlap and date_overlap:
				frappe.throw(_("This Working Time Rule Set overlaps approved rule {0} for the same establishment scope.").format(other.name))

	def before_submit(self):
		assert_company_access(self.company, require_explicit_scope=True)
		if frappe.session.user != "Administrator" and (
			APPROVER_ROLE not in frappe.get_roles() or self.owner == frappe.session.user
		):
			frappe.throw(_("A different company-scoped Workforce Owner/Director must approve this rule."))
		self.reviewed_by = frappe.session.user
		self.reviewed_at = now_datetime()

	def before_update_after_submit(self):
		frappe.throw(_("Approved Working Time Rule Sets are immutable; create a new effective version."))

	def before_cancel(self):
		frappe.throw(_("Approved Working Time Rule Sets remain historical evidence; supersede them with a new version."))
