"""Immutable generation audit, not a financial or filing ledger."""
import frappe
from frappe import _
from frappe.model.document import Document
from workforce_suite.workforce_suite.statutory_access import check_company

class WorkforceStatutoryExport(Document):
    def validate(self):
        check_company(self.company)
        if not self.is_new():
            frappe.throw(_("Generated statutory audit records are immutable."))
        if not getattr(frappe.flags, "statutory_generation", False):
            frappe.throw(_("Export audit records are created only by the authorized exporter."), frappe.PermissionError)
    def on_trash(self):
        frappe.throw(_("Generated statutory audit records cannot be deleted."))
