from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

import frappe

from workforce_suite.workforce_suite.company_context import assert_company_access


APPROVER_ROLE = "Workforce Owner/Director"


class WorkforceStatutoryBenefitRuleSet(Document):
	def validate(self):
		assert_company_access(self.company, require_explicit_scope=True)
		if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
			frappe.throw(_("Effective To must be on or after Effective From."))
		if self.branch and frappe.db.get_value("Branch", self.branch, "company") != self.company:
			frappe.throw(_("The establishment Branch must belong to the selected Company."))
		if not (self.legal_review_notes or "").strip():
			frappe.throw(_("Record the legal applicability review before saving."))
		self._validate_benefit_setup()
		self._validate_no_overlap()

	def _validate_benefit_setup(self):
		if self.applicability == "Applicable" and not (self.sources or []):
			frappe.throw(_("An applicable benefit rule needs at least one official source."))
		if self.benefit_type == "Provident Fund":
			if self.applicability == "Applicable" and self.pf_trigger_status in ("Not Determined", "Not Triggered"):
				frappe.throw(_("Resolve the PF legal trigger before approving an applicable PF rule."))
			if self.pf_trigger_status not in ("Not Determined", "Not Triggered") and not (self.trigger_evidence or "").strip():
				frappe.throw(_("Record the reviewed PF demand, exemption, or regime evidence."))
			if self.pf_trigger_status == "Written Demand Received":
				if self.legal_regime != "Bangladesh Labour Act":
					frappe.throw(_("The written-demand PF trigger applies only to a reviewed Bangladesh Labour Act rule."))
				worker_count = self.reviewed_permanent_worker_count or 0
				demand_count = self.written_demand_worker_count or 0
				minimum_workers = self.minimum_permanent_workers_required or 0
				numerator = self.written_demand_numerator or 0
				denominator = self.written_demand_denominator or 0
				if minimum_workers < 1 or worker_count < minimum_workers or not self.worker_count_as_of:
					frappe.throw(_("Record the reviewed permanent-worker threshold, supporting count, and as-of date."))
				if numerator < 1 or denominator < numerator:
					frappe.throw(_("Record the reviewed written-demand fraction from the approved source."))
				minimum_demand = (numerator * worker_count + denominator - 1) // denominator
				if demand_count < minimum_demand or demand_count > worker_count:
					frappe.throw(_("The reviewed written-demand count must be at least two-thirds of the permanent-worker count."))
			if self.pf_trigger_status == "EPZ Mandatory Rule" and self.legal_regime != "Bangladesh EPZ Labour Act":
				frappe.throw(_("An EPZ PF trigger requires the Bangladesh EPZ Labour Act regime."))
		elif self.pf_trigger_status:
			frappe.throw(_("PF trigger status is only valid for Provident Fund rules."))

		if self.applicability != "Applicable":
			return
		if self.benefit_type == "Progoti Pension" and not (self.institution_registration_reference or "").strip():
			frappe.throw(_("Record the National Pension Authority institutional registration reference."))
		if self.benefit_type == "Group Insurance":
			if not self.policy_reference or not self.policy_effective_from:
				frappe.throw(_("Record the approved group insurance policy reference and effective date."))
			if self.policy_effective_to and getdate(self.policy_effective_to) < getdate(self.policy_effective_from):
				frappe.throw(_("The policy end date must be on or after its effective date."))
		if self.benefit_type in ("Provident Fund", "Progoti Pension"):
			self._validate_component(self.employee_component, "Deduction")
			self._validate_component(self.employer_component, "Employer Contribution")

	def _validate_component(self, name, expected_type):
		component = frappe.db.get_value("Salary Component", name, ["type", "disabled"], as_dict=True)
		if not component or component.type != expected_type or component.disabled:
			frappe.throw(_("Map an existing {0} Salary Component.").format(expected_type))
		account_name = frappe.db.get_value(
			"Salary Component Account",
			{"parent": name, "parenttype": "Salary Component", "parentfield": "accounts", "company": self.company},
			"account",
		)
		account = frappe.db.get_value("Account", account_name, ["company", "disabled", "is_group"], as_dict=True) if account_name else None
		if not account or account.company != self.company or account.disabled or account.is_group:
			frappe.throw(_("Map the {0} Salary Component to an enabled, non-group account in the selected Company.").format(expected_type))

	def _validate_no_overlap(self):
		others = frappe.get_all(
			self.doctype,
			filters={
				"company": self.company,
				"benefit_type": self.benefit_type,
				"legal_regime": self.legal_regime,
				"docstatus": 1,
			},
			fields=["name", "branch", "effective_from", "effective_to"],
		)
		start = getdate(self.effective_from)
		end = getdate(self.effective_to) if self.effective_to else getdate("9999-12-31")
		for other in others:
			if other.name == self.name or (self.branch and other.branch and self.branch != other.branch):
				continue
			other_start = getdate(other.effective_from)
			other_end = getdate(other.effective_to) if other.effective_to else getdate("9999-12-31")
			if start <= other_end and other_start <= end:
				frappe.throw(_("An approved benefit rule overlaps this Company / establishment / period: {0}.").format(other.name), title=_("BENEFIT_RULE_CONFLICT"))

	def before_submit(self):
		if self.applicability == "Review Required":
			frappe.throw(_("Resolve legal applicability as Applicable or Not Applicable before approval."))
		if frappe.session.user != "Administrator":
			if APPROVER_ROLE not in frappe.get_roles():
				frappe.throw(_("A Workforce Owner/Director must approve this benefit rule."), frappe.PermissionError)
			if self.owner == frappe.session.user:
				frappe.throw(_("The rule maker cannot approve the same benefit rule."), frappe.PermissionError)
		if not self.sources:
			frappe.throw(_("Add the official legal or approved policy source before approval."))
		if any(not row.effective_date or not row.section_reference or not row.official_reference for row in self.sources):
			frappe.throw(_("Each source needs its effective date, section/reference, and official reference."))
		if getdate(self.effective_from) < max(getdate(row.effective_date) for row in self.sources):
			frappe.throw(_("The rule cannot take effect before its latest supporting source effective date."))
		self.reviewed_by = frappe.session.user
		self.reviewed_at = frappe.utils.now_datetime()

	def before_update_after_submit(self):
		frappe.throw(_("Approved benefit rule sets are immutable. Create a new effective version."))

	def before_cancel(self):
		if frappe.db.exists("Workforce Statutory Benefit Enrollment", {"rule_set": self.name, "docstatus": 1}):
			frappe.throw(_("This approved benefit rule is referenced by an enrollment. Supersede it with a new version."))
