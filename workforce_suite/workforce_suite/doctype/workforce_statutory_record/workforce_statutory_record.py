"""Reviewed missing-field evidence; native financial/work records are immutable."""
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime
from workforce_suite.workforce_suite.statutory_access import check_company
from workforce_suite.workforce_suite.statutory_forms import FIELD_KEY_RE, WORKER_MANUAL_FORMS

# Explicit non-native evidence only: these cannot override canonical payroll,
# attendance hours, leave balances, Company or Employee identity.
SUPPLEMENTAL_FIELDS = frozenset({
    "national_id", "father_name", "mother_name", "worker_register_no", "card_no",
    "due_leave", "working_period", "break_time", "weekly_holiday", "group_name",
    "shift_relay", "group_relay", "group_transfer", "remarks", "grade", "acknowledgement",
    "grant_date", "rejection_reason", "annual_encashment", "worker_signature",
    "employer_signature", "worker_father", "worker_mother", "employment_category",
    "probation_terms", "authorized_signature", "employee_acknowledgement", "service_change",
    "declaration_designation", "declaration", "consent_date", "withdrawal_date", "withdrawal_effective_date", "card_number", "section", "card_issue_date", "card_expiry_date", "card_section", "token_number", "telephone", "blood_group", "emergency_contact", "return_instructions", "portrait_evidence",
})


def permitted_supplemental_fields(layout):
    """Source keys plus explicit companions to combined prescribed cells."""
    from workforce_suite.workforce_suite.statutory_structure import repeated_keys
    source = {c.field_key for c in layout.columns}
    aliases = {"form_8": {"national_id", "grade"},
               "form_9": {"worker_register_no", "card_no"},
               "form_34": {"card_no", "group_relay"}}.get(layout.form_code, set())
    allowed = (SUPPLEMENTAL_FIELDS & source) | aliases | repeated_keys(layout.form_code)
    if layout.form_code == "form_7":
        allowed |= source - {"employee_name", "date_of_birth", "permanent_address"}
    if layout.form_code == "appointment_letter_sample":
        allowed |= source - {"worker_name", "appointment_date", "job_title", "place_of_work", "permanent_address"}
    return allowed

class WorkforceStatutoryRecord(Document):
    def validate(self):
        check_company(self.company)
        layout = frappe.get_doc("Workforce Statutory Print Layout", self.layout)
        layout.check_permission("read")
        if layout.company != self.company:
            frappe.throw(_("The statutory record Company must match its layout Company."))
        from workforce_suite.workforce_suite.statutory_structure import repeated_keys
        from workforce_suite.workforce_suite.statutory_forms import spec_for
        history_keys = repeated_keys(layout.form_code)
        keys = {c.field_key for c in layout.columns}
        if layout.data_source != "Manual":
            if not self.employee:
                frappe.throw(_("Supplemental evidence requires an Employee."))
            person = frappe.get_doc("Employee", self.employee)
            person.check_permission("read")
            if person.company != self.company or (layout.branch and person.branch != layout.branch):
                frappe.throw(_("Employee evidence is outside the establishment scope."), frappe.PermissionError)
            keys = permitted_supplemental_fields(layout)
        elif self.employee and layout.form_family != "Evidence Only" and layout.form_code not in WORKER_MANUAL_FORMS:
            frappe.throw(_("Use native-source layouts for individual worker evidence."))
        if len(self.get("entries") or []) > 500:
            frappe.throw(_("Split large evidence records into separate entries."))
        if layout.data_source == "Manual" and self.employee:
            person = frappe.get_doc("Employee", self.employee)
            person.check_permission("read")
            if person.company != self.company or (layout.branch and person.branch != layout.branch):
                frappe.throw(_("Certificate evidence is outside the worker establishment scope."), frappe.PermissionError)
        requitals = self.get("requitals") or []
        if layout.form_code == "form_40":
            if len(requitals) > 2000:
                frappe.throw(_("Split large Form 40 repayment histories into separate evidence records."))
            for row in requitals:
                from decimal import Decimal
                value = Decimal(str(row.amount or 0))
                if not value.is_finite() or value <= 0:
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
            row_number = int(item.get("row_number") or 0)
            if (key in history_keys and row_number < 1) or row_number < 0 or row_number > 2000 or (row_number and key not in history_keys):
                frappe.throw(_("History row numbers apply only to prescribed repeatable fields."))
            identity = (key, row_number)
            if identity in seen:
                frappe.throw(_("Duplicate field key: {0}").format(key))
            seen.add(identity)
            labels = {c.field_key: c.label_en for c in layout.columns}
            item.field_label = labels.get(key, key)
            if item.get("value_status") == "Not Applicable":
                if not (item.get("applicability_note") or "").strip():
                    frappe.throw(_("Not Applicable requires a source-linked applicability reason."))
                item.field_value = "Not Applicable"
        from workforce_suite.workforce_suite.statutory_period_calculation import resolve_record_workforce
        try:
            calculated = resolve_record_workforce(self, layout)
        except (ValueError, TypeError) as exc:
            if self.docstatus:
                frappe.throw(str(exc))
            calculated = None
            self.calculation_provenance = "Unresolved: " + str(exc)
            # A previously successful draft must not display stale derived facts.
            from workforce_suite.workforce_suite.statutory_period_calculation import CATEGORIES
            derived = set(CATEGORIES.values()) | {"foreign_male", "foreign_female", "contractor_male", "contractor_female", "working_days", "annual_working_days"}
            for cell in self.get("entries") or []:
                if cell.field_key in derived:
                    cell.field_value = ""
                    cell.value_status = "Unresolved"
                    cell.source_reference = ""
        if calculated:
            import json
            values, provenance = calculated
            for key, value in values.items():
                cells = [c for c in self.get("entries") or [] if c.field_key == key]
                if cells:
                    cells[0].field_value = value
                    cells[0].value_status = "Evidence Entered"
                    cells[0].source_reference = provenance["method"]
                else:
                    self.append("entries", {"field_key": key, "field_value": value, "value_status": "Evidence Entered", "source_reference": provenance["method"]})
            self.calculation_provenance = json.dumps(provenance, ensure_ascii=False)
        elif self.get("calculation_mode") != "Reviewed Workforce Evidence" and (self.get("workforce_members") or self.get("workforce_calendar")):
            frappe.throw(_("Select Reviewed Workforce Evidence before entering calculation tables."))
        elif self.get("calculation_mode") != "Reviewed Workforce Evidence":
            self.calculation_provenance = None
        from workforce_suite.workforce_suite.statutory_structure import validate_evidence_values
        from workforce_suite.workforce_suite.statutory_forms import spec_for
        try:
            grouped = {}
            for cell in self.get("entries") or []:
                if cell.get("value_status") != "Not Applicable":
                    grouped.setdefault(int(cell.get("row_number") or 0), {})[cell.field_key] = cell.field_value
            for values in grouped.values():
                validate_evidence_values(spec_for(layout.form_code), values)
        except ValueError as exc:
            frappe.throw(str(exc))
        if self.effective_to and getdate(self.effective_to) < getdate(self.entry_date):
            frappe.throw(_("Evidence effective dates are invalid."))
        if self.evidence_file:
            files = frappe.get_list("File", filters={"file_url": self.evidence_file}, fields=["name", "is_private"], limit_page_length=2)
            if len(files) != 1 or not files[0].is_private:
                frappe.throw(_("Supporting evidence must be a readable, private Frappe File."), frappe.PermissionError)
            frappe.get_doc("File", files[0].name).check_permission("read")
        if self.get("portrait_file"):
            if layout.form_code not in {"form_6", "form_7"} or not self.employee:
                frappe.throw(_("Worker portraits belong to an individual identity card or service book."))
            from workforce_suite.workforce_suite.statutory_evidence_files import checked_original
            checked_original(self.portrait_file, image_only=True)
        from workforce_suite.workforce_suite.statutory_financial_evidence import validate_financial_evidence
        validate_financial_evidence(self, layout)
        if not self.docstatus:
            self.reviewed_by = self.reviewed_at = None

    def before_submit(self):
        # Evidence review is independent of official template approval. Reviewing
        # a personnel fact does not certify a legal form or create pay money.
        if self.owner == frappe.session.user:
            frappe.throw(_("A separate reviewer must submit the evidence."), frappe.PermissionError)
        if not (self.evidence_note or "").strip():
            frappe.throw(_("Record the source and review justification."))
        layout = frappe.get_doc("Workforce Statutory Print Layout", self.layout)
        if (self.get("evidence_kind") or "Supplemental Facts") == "Supplemental Facts" and not self.get("entries"):
            if layout.form_family != "Evidence Only" or not self.evidence_file:
                frappe.throw(_("Enter the actual source facts before submitting evidence."))
        if any(cell.get("value_status") == "Unresolved" and cell.field_value for cell in self.get("entries") or []):
            frappe.throw(_("Review unresolved evidence states before submission."))
        if layout.form_code in {"form_80", "form_81"}:
            from workforce_suite.workforce_suite.statutory_export_policy import normalize_period
            from workforce_suite.workforce_suite.statutory_forms import spec_for
            from workforce_suite.workforce_suite.statutory_schema import missing_findings
            try:
                start, end = normalize_period(layout.form_code, layout.data_source,
                                              self.get("reporting_from"), self.get("reporting_to"))
            except ValueError as exc:
                frappe.throw(str(exc))
            if not start <= str(self.entry_date) <= end:
                frappe.throw(_("Record date must be in the exact reporting period."))
            cells = self.get("entries") or []
            values = {c.field_key: c.field_value for c in cells}
            missing = missing_findings(spec_for(layout.form_code), [values])
            if missing:
                frappe.throw(_("Complete each required prescribed field before review: {0}").format(", ".join(f["field"] for f in missing)))
        from workforce_suite.workforce_suite.statutory_structure import repeatable_for, evidence_rows
        tables = repeatable_for(layout.form_code)
        if tables:
            history = evidence_rows(self.get("entries") or [], layout.form_code)["_history"]
            if not any(history.values()):
                frappe.throw(_("Enter source-supported history or examination rows before review."))
            for table in tables:
                for values in history.get(table["id"], []):
                    # Signed acknowledgements may remain blank in a working copy.
                    required = [key for key in table["keys"] if "signature" not in key and not key.endswith(("_authority", "_worker", "_left"))]
                    if any(values.get(key) in (None, "") for key in required):
                        frappe.throw(_("Complete every field in each entered history row, or record reviewed non-applicability."))
        if layout.form_code == "form_38" and any(c.field_key == "acknowledgement" and c.field_value for c in self.get("entries") or []):
            frappe.throw(_("Use Worker Acknowledgement evidence linked to the submitted Salary Slip and private original."))
        if layout.form_code == "appointment_letter_sample" and any(c.field_key not in {"worker_father", "worker_mother", "spouse_name", "national_id", "present_address"} and c.field_value for c in self.get("entries") or []):
            if not self.evidence_file:
                frappe.throw(_("Attach the actual reviewed contract / offer terms; neither clauses nor wage rates are inferred from payroll."))
        if layout.form_family == "Evidence Only" and not self.evidence_file:
            frappe.throw(_("Retain the actual private externally issued original; a generated certificate is prohibited."))
        if (self.get("evidence_kind") or "Supplemental Facts") != "Supplemental Facts" and not self.evidence_file:
            frappe.throw(_("Attach private original payment, acknowledgement or historical rate evidence before review."))
        from workforce_suite.workforce_suite.statutory_evidence_files import checked_original
        if self.evidence_file:
            self.evidence_sha256 = checked_original(self.evidence_file)[1]
        if self.get("portrait_file"):
            self.portrait_sha256 = checked_original(self.portrait_file, image_only=True)[1]
        self.reviewed_by = frappe.session.user
        self.reviewed_at = now_datetime()
