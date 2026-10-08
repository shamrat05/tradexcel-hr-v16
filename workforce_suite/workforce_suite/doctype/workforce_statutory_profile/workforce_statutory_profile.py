"""Reviewed establishment configuration; never a source of computed wages."""
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime
from workforce_suite.workforce_suite.statutory_access import check_company

class WorkforceStatutoryProfile(Document):
    def validate(self):
        check_company(self.company)
        if self.branch and frappe.db.get_value("Branch", self.branch, "company") != self.company:
            frappe.throw(_("Profile Branch must belong to its Company."))
        if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
            frappe.throw(_("Profile effective dates are invalid."))
        types = [self.get(x) for x in ("annual_leave_type", "casual_leave_type", "sick_leave_type") if self.get(x)]
        if len(types) != len(set(types)):
            frappe.throw(_("Map each statutory leave category to a distinct native Leave Type."))
        if not self.docstatus:
            self.reviewed_by = self.reviewed_at = None
    def before_submit(self):
        if self.owner == frappe.session.user:
            frappe.throw(_("A separate reviewer must approve establishment configuration."), frappe.PermissionError)
        unresolved = []
        for label, number_field, state_field, evidence_field in (
            (_("registration"), "registration_no", "registration_applicability", "registration_evidence"),
            (_("licence"), "licence_no", "licence_applicability", "licence_evidence"),
        ):
            state = (self.get(state_field) or "Pending Review").strip()
            number = (self.get(number_field) or "").strip()
            evidence = (self.get(evidence_field) or "").strip()
            if state == "Pending Review":
                unresolved.append(f"{label}: applicability review")
            elif state == "Required" and not number:
                unresolved.append(f"{label}: required value")
            elif state == "Not Applicable" and not evidence:
                unresolved.append(f"{label}: non-applicability evidence")
        for fieldname in ("address_en", "legal_reference", "review_notes"):
            value = self.get(fieldname)
            if not value or str(value).strip().lower().startswith("pending"):
                unresolved.append(fieldname)
        if unresolved:
            frappe.throw(_("Complete reviewed statutory fields before submission: {0}.").format(", ".join(unresolved)))
        self.reviewed_by = frappe.session.user
        self.reviewed_at = now_datetime()
