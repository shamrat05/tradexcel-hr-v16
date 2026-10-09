"""Company-scoped, user-editable and versioned legal-form layout controls."""
from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime

from workforce_suite.workforce_suite.statutory_access import check_company, checked_profile
from workforce_suite.workforce_suite.statutory_schema import validate_schema
from workforce_suite.workforce_suite.statutory_forms import (
    FIELD_KEY_RE, spec_for, COMPONENT_KEYS,
)


class WorkforceStatutoryPrintLayout(Document):
    def validate(self):
        check_company(self.company)
        source = spec_for(self.form_code)
        if self.form_family != source["kind"]:
            frappe.throw(_("This document style must match the verified source category."))
        if self.branch:
            branch_company = frappe.db.get_value("Branch", self.branch, "company")
            if branch_company != self.company:
                frappe.throw(_("Establishment Branch must belong to the selected Company."))
        if self.data_source != source["data_source"]:
            frappe.throw(_("The data source must match the DIFE source category. Do not relabel a different dataset as an official form."))
        if self.orientation not in {"Portrait", "Landscape"}:
            frappe.throw(_("Use A4 portrait or landscape."))
        if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
            frappe.throw(_("Effective To cannot precede Effective From."))
        if not (self.columns or []):
            frappe.throw(_("Add print columns or load the suggested draft layout."))
        try:
            validate_schema(source, self.columns)
        except ValueError as exc:
            frappe.throw(str(exc))
        if len(self.columns) > 22 and self.form_family == "Register":
            frappe.throw(_("Split this document rather than printing more than 22 columns on A4."))
        if self.form_family == "Register" and len(self.columns) > 11 and self.orientation == "Portrait":
            frappe.throw(_("Wide table must be A4 landscape; choose landscape."))
        seen = set()
        protected = {c["field_key"]: c for c in source["columns"]}
        for col in self.columns:
            key = (col.field_key or "").strip()
            if not FIELD_KEY_RE.fullmatch(key):
                frappe.throw(_("Invalid field key: {0}.").format(key))
            if key in seen:
                frappe.throw(_("Column {0} is duplicated.").format(key))
            seen.add(key)
            # Required fields and section identity are source owned. A client
            # cannot turn them off or move fields into a different return.
            definition = protected[key]
            col.required_value = int(definition.get("required_value", True))
            col.section_key = definition.get("section_key", "")
            if col.section_key:
                col.section_en = definition["section_en"]
                col.section_bn = definition["section_bn"]
            if not (col.label_bn or col.label_en):
                frappe.throw(_("Every printed column needs a visible label."))
            if not (1 <= int(col.width_weight or 1) <= 5):
                frappe.throw(_("Column width weights must be between 1 and 5."))
            if col.salary_component:
                if self.data_source != "Salary Slip" or key not in COMPONENT_KEYS:
                    frappe.throw(_("Salary Component mappings are only permitted on known wage-detail fields."))
                if not frappe.db.exists("Salary Component", col.salary_component):
                    frappe.throw(_("Mapped Salary Component does not exist."))
                component = frappe.get_doc("Salary Component", col.salary_component)
                component.check_permission("read")
                if component.type != "Earning" or component.get("disabled") or component.get("is_statistical_component"):
                    frappe.throw(_("Wage mappings require an enabled, non-statistical earning component."))
        mappings = [c for c in self.columns if c.salary_component] + list(self.get("salary_mappings") or [])
        if len(mappings) > 200:
            frappe.throw(_("Use at most 200 explicit earning mappings."))
        for mapping in mappings:
            if self.data_source != "Salary Slip" or mapping.field_key not in COMPONENT_KEYS:
                frappe.throw(_("Only protected wage columns accept earning mappings."))
            component = frappe.get_doc("Salary Component", mapping.salary_component)
            component.check_permission("read")
            if component.type != "Earning" or component.get("disabled") or component.get("is_statistical_component"):
                frappe.throw(_("Map enabled, non-statistical earning components only."))
        mapped = [c.salary_component for c in mappings]
        if len(mapped) != len(set(mapped)):
            frappe.throw(_("An earning component cannot be counted in two wage columns."))
        if self.get("statutory_profile"):
            checked_profile(self, language="en")
        if not self.docstatus:
            self.approved_by = self.approved_at = None
        # The source ID/hash may not be modified through UI or API. Employer
        # and reviewed legal changes are separately versioned via this doc.
        self.source_url = source["source_pdf_url"]
        self.source_sha256 = source.get("source_sha256") or ""

    def before_submit(self):
        if self.owner == frappe.session.user:
            frappe.throw(_("A separate reviewer must approve the template."), frappe.PermissionError)
        source = spec_for(self.form_code)
        if not source["legal_approved"] or source.get("source_issue"):
            frappe.throw(_(
                "This source form still needs field-by-field legal and layout approval. "
                "Use Draft Preview; do not issue a document as an official register."
            ))
        if not (self.legal_review_reference or "").strip() or not (self.legal_review_notes or "").strip():
            frappe.throw(_("Record the reviewed law/version and evidence before approving this template."))
        self.approved_by = frappe.session.user
        self.approved_at = now_datetime()
