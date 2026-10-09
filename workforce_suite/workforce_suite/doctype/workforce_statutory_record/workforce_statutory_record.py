"""Reviewed missing-field evidence; native financial/work records are immutable."""
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime
from workforce_suite.workforce_suite.statutory_access import check_company
from workforce_suite.workforce_suite.statutory_forms import FIELD_KEY_RE

# Explicit non-native evidence only: these cannot override canonical payroll,
# attendance hours, leave balances, Company or Employee identity.
SUPPLEMENTAL_FIELDS = frozenset({
    "national_id", "father_name", "mother_name", "worker_register_no", "card_no",
    "due_leave", "working_period", "break_time", "weekly_holiday", "group_name",
    "shift_relay", "group_relay", "group_transfer", "remarks", "grade", "acknowledgement",
    "grant_date", "rejection_reason", "annual_encashment", "worker_signature",
    "employer_signature", "worker_father", "worker_mother", "employment_category",
    "probation_terms", "authorized_signature", "employee_acknowledgement", "service_change",
})

class WorkforceStatutoryRecord(Document):
    def validate(self):
        check_company(self.company)
        layout = frappe.get_doc("Workforce Statutory Print Layout", self.layout)
        layout.check_permission("read")
        if layout.company != self.company:
            frappe.throw(_("The statutory record Company must match its layout Company."))
        keys = {c.field_key for c in layout.columns}
        if layout.data_source != "Manual":
            if not self.employee:
                frappe.throw(_("Supplemental evidence requires an Employee."))
            person = frappe.get_doc("Employee", self.employee)
            person.check_permission("read")
            if person.company != self.company or (layout.branch and person.branch != layout.branch):
                frappe.throw(_("Employee evidence is outside the establishment scope."), frappe.PermissionError)
            keys = SUPPLEMENTAL_FIELDS
        elif self.employee:
            frappe.throw(_("Use native-source layouts for individual worker evidence."))
        if len(self.get("entries") or []) > 240:
            frappe.throw(_("Split large evidence records into separate entries."))
        requitals = self.get("requitals") or []
        if layout.form_code == "form_40":
            if len(requitals) > 2000:
                frappe.throw(_("Split large Form 40 repayment histories into separate evidence records."))
            for row in requitals:
                if float(row.amount or 0) <= 0:
                    frappe.throw(_("Each Form 40 requital amount must be positive."))
                if not row.collection_date:
                    frappe.throw(_("Each Form 40 requital needs a collection date."))
        elif requitals:
            frappe.throw(_("Requital history is only valid for Form 40 evidence."))
        seen = set()
        generated_requital_keys = {"requital_amount", "requital_date", "requital_reference", "requital_remarks"}
        for item in self.get("entries") or []:
            key = (item.field_key or "").strip()
            if layout.form_code == "form_40" and key in generated_requital_keys:
                frappe.throw(_("Form 40 repayment values must be entered in the Requital History table."))
            if not FIELD_KEY_RE.fullmatch(key) or key not in keys:
                frappe.throw(_("Unknown or native-owned statutory evidence key: {0}").format(key))
            if key in seen:
                frappe.throw(_("Duplicate field key: {0}").format(key))
            seen.add(key)
        if self.effective_to and getdate(self.effective_to) < getdate(self.entry_date):
            frappe.throw(_("Evidence effective dates are invalid."))
        if self.evidence_file:
            files = frappe.get_list("File", filters={"file_url": self.evidence_file}, fields=["name", "is_private"], limit_page_length=2)
            if len(files) != 1 or not files[0].is_private:
                frappe.throw(_("Supporting evidence must be a readable, private Frappe File."), frappe.PermissionError)
            frappe.get_doc("File", files[0].name).check_permission("read")
        if not self.docstatus:
            self.reviewed_by = self.reviewed_at = None

    def before_submit(self):
        # Evidence review is independent of official template approval. Reviewing
        # a personnel fact does not certify a legal form or create pay money.
        if self.owner == frappe.session.user:
            frappe.throw(_("A separate reviewer must submit the evidence."), frappe.PermissionError)
        if not (self.evidence_note or "").strip():
            frappe.throw(_("Record the source and review justification."))
        self.reviewed_by = frappe.session.user
        self.reviewed_at = now_datetime()
