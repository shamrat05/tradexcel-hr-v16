from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

from tradex_hr.tradexcel_hr.company_context import assert_company_access


REVIEW_ROLES = {"Tradexcel Owner/Director", "System Manager"}


class TradexcelWageFloorRuleSet(Document):
	def validate(self):
		assert_company_access(self.company, require_explicit_scope=True)
		if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
			frappe.throw(_("Effective To must be on or after Effective From."))
		if self.branch:
			branch_company = frappe.db.get_value("Branch", self.branch, "company")
			if branch_company != self.company:
				frappe.throw(_("The Branch / Establishment must belong to the selected Company."))
		company_currency = frappe.db.get_value("Company", self.company, "default_currency")
		if company_currency and self.currency != company_currency:
			frappe.throw(_("The wage-floor currency must match the Company's currency."))
		if not (self.legal_review_notes or "").strip():
			frappe.throw(_("Record the legal/source review notes before saving."))
		if not (self.establishment_reference or "").strip():
			frappe.throw(_("Record the verified establishment or licence reference before activating a wage order."))
		self._validate_floor_rows()
		self._validate_effective_scope()

	def _validate_floor_rows(self):
		if not self.floor_rows:
			frappe.throw(_("Add reviewed wage-floor component and total rows."))
		groups = {}
		for row in self.floor_rows:
			key = (row.worker_category, row.gazette_grade, row.location_category, row.rate_basis)
			groups.setdefault(key, []).append(row)
			if row.minimum_amount is None or flt(row.minimum_amount) < 0:
				frappe.throw(_("Wage-floor values must be zero or positive."))
			if row.floor_type == "Total":
				if row.component_key != "TOTAL" or row.salary_component or row.include_in_total_floor:
					frappe.throw(_("A Total row must use key TOTAL and cannot map a Salary Component."))
			else:
				if not row.component_key or row.component_key == "TOTAL" or not row.salary_component:
					frappe.throw(_("Each Component row needs a legal key and explicit native Salary Component."))
				component = frappe.db.get_value(
					"Salary Component",
					row.salary_component,
					["type", "statistical_component", "accrual_component", "do_not_include_in_total"],
					as_dict=True,
				)
				if not component or component.type != "Earning" or component.statistical_component or component.accrual_component or component.do_not_include_in_total:
					frappe.throw(_("Wage-floor mappings must point to ordinary payable earning components."))
		for group_key, rows in groups.items():
			total_rows = [row for row in rows if row.floor_type == "Total"]
			component_rows = [row for row in rows if row.floor_type == "Component"]
			if len(total_rows) != 1 or not component_rows:
				frappe.throw(_("Each category, grade, location, and rate-basis group needs component floors and exactly one Total floor."))
			components = [row.salary_component for row in component_rows]
			keys = [row.component_key for row in component_rows]
			if len(set(components)) != len(components) or len(set(keys)) != len(keys):
				frappe.throw(_("A floor group cannot map a Salary Component or legal component key more than once."))
			if not any(row.include_in_total_floor for row in component_rows):
				frappe.throw(_("At least one explicitly mapped fixed earning must contribute to the Total floor."))

	def _validate_effective_scope(self):
		if not self.legal_regime or not self.industry_sector:
			frappe.throw(_("Select the reviewed legal regime and registered industry sector."))
		others = frappe.get_all(
			"Tradexcel Wage Floor Rule Set",
			filters={"company": self.company, "legal_regime": self.legal_regime, "industry_sector": self.industry_sector, "docstatus": 1},
			fields=["name", "branch", "effective_from", "effective_to"],
		)
		start = getdate(self.effective_from)
		end = getdate(self.effective_to) if self.effective_to else None
		for other in others:
			if other.name == self.name:
				continue
			# Company-wide scope intersects every branch. There is no implicit branch precedence.
			if self.branch and other.branch and self.branch != other.branch:
				continue
			other_start = getdate(other.effective_from)
			other_end = getdate(other.effective_to) if other.effective_to else None
			if start <= (other_end or getdate("9999-12-31")) and other_start <= (end or getdate("9999-12-31")):
				frappe.throw(_("Approved wage-floor periods overlap for an intersecting Company / Establishment scope: {0}.").format(other.name), title=_("WAGE_FLOOR_RULE_CONFLICT"))

	def before_submit(self):
		roles = set(frappe.get_roles())
		if frappe.session.user != "Administrator" and not roles.intersection(REVIEW_ROLES):
			frappe.throw(_("A Tradexcel Owner/Director must approve the wage-floor rule set."), frappe.PermissionError)
		if frappe.session.user != "Administrator" and self.owner == frappe.session.user:
			frappe.throw(_("The rule-set maker cannot approve the same wage-floor rule set."), frappe.PermissionError)
		if not self.sources or any(row.authority_status != "Final Gazette" for row in self.sources):
			frappe.throw(_("Every source supporting an active wage-floor rule must be reviewed as a Final Gazette."))
		if any(not all((row.source_title, row.issuing_authority, row.notification_number,
						row.publication_date, row.effective_date, row.section_reference,
						row.official_reference)) for row in self.sources):
			frappe.throw(_("Each wage-order source needs its issuing authority, notification, publication and effective dates, section, and official reference."))
		latest_source_effective_date = max(getdate(row.effective_date) for row in self.sources)
		if getdate(self.effective_from) < latest_source_effective_date:
			frappe.throw(_("A wage-floor rule cannot become effective before its latest supporting legal source effective date."))
		self.reviewed_by = frappe.session.user
		self.reviewed_at = frappe.utils.now_datetime()

	def before_update_after_submit(self):
		frappe.throw(_("Approved wage-floor rule sets are immutable. Create a new effective version."))

	def before_cancel(self):
		if frappe.db.exists("Tradexcel Wage Floor Classification", {"rule_set": self.name, "docstatus": 1}):
			frappe.throw(_("This approved wage-floor rule is referenced by an employee classification. Supersede it with a new version instead."))
