from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

import frappe

from workforce_suite.workforce_suite.company_context import assert_company_access


APPROVER_ROLE = "Workforce Owner/Director"


class WorkforceStatutoryBenefitEnrollment(Document):
	def validate(self):
		assert_company_access(self.company, require_explicit_scope=True)
		employee = frappe.db.get_value("Employee", self.employee, ["company", "branch"], as_dict=True)
		if not employee or employee.company != self.company:
			frappe.throw(_("The enrollment Company must match the Employee's Company."))
		if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
			frappe.throw(_("Effective To must be on or after Effective From."))
		if self.branch and frappe.db.get_value("Branch", self.branch, "company") != self.company:
			frappe.throw(_("The enrollment establishment must belong to the Employee's Company."))
		is_current_or_future = not self.effective_to or getdate(self.effective_to) >= getdate(frappe.utils.today())
		if is_current_or_future and (employee.branch or "") != (self.branch or ""):
			frappe.throw(_("A current or future enrollment must match the current Employee Branch."))
		self._validate_rule()
		self._validate_status_evidence()
		self._validate_no_overlap()

	def _validate_rule(self):
		rule = frappe.db.get_value(
			"Workforce Statutory Benefit Rule Set",
			self.rule_set,
			["docstatus", "company", "branch", "benefit_type", "applicability", "effective_from", "effective_to"],
			as_dict=True,
		)
		if not rule or rule.docstatus != 1:
			frappe.throw(_("Select an approved benefit rule set."))
		if rule.company != self.company or rule.benefit_type != self.benefit_type or rule.applicability != "Applicable":
			frappe.throw(_("The approved rule must match the enrollment Company, benefit type, and Applicable decision."))
		if rule.branch and rule.branch != self.branch:
			frappe.throw(_("A branch-specific benefit rule requires an enrollment for that same Branch."))
		if getdate(self.effective_from) < getdate(rule.effective_from) or (
			rule.effective_to and (not self.effective_to or getdate(self.effective_to) > getdate(rule.effective_to))
		):
			frappe.throw(_("The enrollment period must be inside the approved rule-set period."))

	def _validate_status_evidence(self):
		if self.benefit_type == "Group Insurance":
			if self.participation_status == "Opted Out in Writing":
				frappe.throw(_("Written opt-out is not an employee coverage status for Group Insurance."))
			if self.participation_status == "Enrolled" and not (self.external_reference or "").strip():
				frappe.throw(_("Record the insurer coverage certificate/member reference."))
		else:
			if self.benefit_type == "Provident Fund" and self.participation_status == "Opted Out in Writing":
				frappe.throw(_("An employee PF opt-out is not represented by the approved PF rule; obtain legal review."))
			if self.participation_status == "Enrolled" and not (self.external_reference or "").strip():
				frappe.throw(_("Record the external fund / pension member reference."))
		if self.benefit_type == "Progoti Pension" and self.participation_status == "Enrolled" and not self.selected_monthly_contribution:
			frappe.throw(_("Enter the approved external Progoti contribution package for enrolled participation."))
		if self.participation_status == "Opted Out in Writing" and not (self.participation_evidence or "").strip():
			frappe.throw(_("A written opt-out evidence reference is required."))
		if self.participation_status == "Enrolled" and not (self.participation_evidence or "").strip():
			frappe.throw(_("Record the employee's written participation evidence."))
		if not (self.review_notes or "").strip():
			frappe.throw(_("Record the reviewed participation decision."))

	def _validate_no_overlap(self):
		others = frappe.get_all(
			self.doctype,
			filters={"employee": self.employee, "benefit_type": self.benefit_type, "docstatus": 1},
			fields=["name", "effective_from", "effective_to"],
		)
		start = getdate(self.effective_from)
		end = getdate(self.effective_to) if self.effective_to else getdate("9999-12-31")
		for other in others:
			if other.name == self.name:
				continue
			other_start = getdate(other.effective_from)
			other_end = getdate(other.effective_to) if other.effective_to else getdate("9999-12-31")
			if start <= other_end and other_start <= end:
				frappe.throw(_("An approved enrollment already overlaps this Employee / benefit period: {0}.").format(other.name))

	def before_submit(self):
		if frappe.session.user != "Administrator":
			if APPROVER_ROLE not in frappe.get_roles():
				frappe.throw(_("A Workforce Owner/Director must approve the enrollment."), frappe.PermissionError)
			if self.owner == frappe.session.user:
				frappe.throw(_("The enrollment maker cannot approve the same participation record."), frappe.PermissionError)
		self.reviewed_by = frappe.session.user
		self.reviewed_at = frappe.utils.now_datetime()

	def before_update_after_submit(self):
		frappe.throw(_("Approved enrollments are immutable. Create a new effective version."))

	def before_cancel(self):
		if self._used_by_submitted_salary_slip():
			frappe.throw(_("This enrollment was consumed by submitted payroll. Preserve it and create a new effective version."))

	def _used_by_submitted_salary_slip(self):
		components = frappe.db.get_value(
			"Workforce Statutory Benefit Rule Set", self.rule_set,
			["employee_component", "employer_component"], as_dict=True,
		)
		component_names = [getattr(components, field) for field in ("employee_component", "employer_component") if components and getattr(components, field)]
		if not component_names:
			return False
		slips = frappe.get_all(
			"Salary Slip",
			filters={
				"employee": self.employee,
				"company": self.company,
				"docstatus": 1,
				"start_date": ["<=", self.effective_to or "9999-12-31"],
				"end_date": [">=", self.effective_from],
			},
			pluck="name",
		)
		return bool(slips and frappe.db.exists("Salary Detail", {
			"parenttype": "Salary Slip", "parent": ["in", slips],
			"salary_component": ["in", component_names],
		}))
