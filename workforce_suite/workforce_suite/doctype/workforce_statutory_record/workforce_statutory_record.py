"""Manually entered evidence for form categories not covered by native HRMS."""
from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from workforce_suite.workforce_suite.company_context import assert_company_access
from workforce_suite.workforce_suite.statutory_forms import FIELD_KEY_RE


class WorkforceStatutoryRecord(Document):
    def validate(self):
        assert_company_access(self.company, require_explicit_scope=True)
        layout = frappe.get_doc("Workforce Statutory Print Layout", self.layout)
        layout.check_permission("read")
        if layout.company != self.company:
            frappe.throw(_("The statutory record Company must match its layout Company."))
        if layout.data_source != "Manual":
            frappe.throw(_("Manual evidence must use a Manual data-source layout, not an Employee, Attendance, Leave or Payroll layout."))
        columns = {col.field_key: col for col in layout.columns}
        if len(self.get("entries") or []) > 80:
            frappe.throw(_("Split large evidence records into separate entries."))
        seen = set()
        for field in self.get("entries") or []:
            key = (field.field_key or "").strip()
            if not FIELD_KEY_RE.fullmatch(key) or key not in columns:
                frappe.throw(_("Unknown statutory column key: {0}").format(key))
            if key in seen:
                frappe.throw(_("Duplicate field key: {0}").format(key))
            seen.add(key)
        if self.docstatus == 1:
            self._verify_for_submit(layout, columns)

    def before_submit(self):
        layout = frappe.get_doc("Workforce Statutory Print Layout", self.layout)
        layout.check_permission("read")
        self._verify_for_submit(layout, {col.field_key: col for col in layout.columns})

    def _verify_for_submit(self, layout, columns):
        if layout.docstatus != 1:
            frappe.throw(_("Official evidence records require a reviewed, submitted print layout."))
        vals = {x.field_key: x.field_value for x in self.get("entries") or []}
        for key, col in columns.items():
            if col.required_value and not (vals.get(key) or "").strip():
                frappe.throw(_("Required statutory field {0} is empty.").format(col.label_en))
