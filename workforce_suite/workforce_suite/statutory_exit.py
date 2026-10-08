"""Versioned statutory exit applicability. It never calculates legal money."""
from __future__ import annotations
from datetime import timedelta
import frappe
from frappe import _
from frappe.utils import getdate

RULESET = "Workforce Statutory Rule Set"
STATUS_FIELD = "custom_workforce_statutory_review_status"
RULESET_FIELD = "custom_workforce_statutory_rule_set"
CLASSIFICATION_FIELD = "custom_workforce_legal_classification"
APPLICABILITY_DATE_FIELD = "custom_workforce_statutory_applicability_date"
SEPARATION_TYPE = "custom_workforce_separation_type"
APPROVED = "Workforce Statutory Approved"
FROZEN = ("title", "company", "branch", "jurisdiction", "legal_regime", "effective_from",
          "effective_to", "legal_review_notes", "sources", "entitlements",
          "service_calculation_method", "applicability_date_basis", "settlement_deadline_working_days", "holiday_list",
          "reviewed_by", "reviewed_at")


def _scope(company):
    from workforce_suite.workforce_suite.company_context import assert_company_access
    assert_company_access(company, require_explicit_scope=True)


def _freeze_submitted(doc):
    if doc.is_new() or int(doc.docstatus or 0) != 1 or doc.flags.in_insert or doc._action == "submit":
        return
    old = doc.get_doc_before_save()
    if old and any(old.get(field) != doc.get(field) for field in FROZEN):
        frappe.throw(_("Approved rule meaning is immutable. Create a new version."),
                     title=_("STATUTORY_RULESET_IMMUTABLE"))


def validate_statutory_ruleset(doc, method=None):
    if doc.company:
        _scope(doc.company)
    _freeze_submitted(doc)
    if doc.branch and frappe.db.has_column("Branch", "company"):
        branch_company = frappe.db.get_value("Branch", doc.branch, "company")
        if branch_company and branch_company != doc.company:
            frappe.throw(_("Branch must belong to the Rule Set company."))
    seen = set()
    for row in doc.get("sources", []):
        key = (row.source_title, row.section_reference, row.official_reference)
        if key in seen:
            frappe.throw(_("Duplicate statutory source row."))
        seen.add(key)
    seen = set()
    for row in doc.get("entitlements", []):
        key = (row.separation_type, row.classification, row.entitlement_type)
        if key in seen:
            frappe.throw(_("Duplicate entitlement mapping."))
        seen.add(key)


def _validate_for_approval(doc):
    if doc.workflow_state != APPROVED:
        frappe.throw(_("Approve Rule Sets through the configured workflow."))
    if doc.owner == frappe.session.user:
        frappe.throw(_("The Rule Set maker cannot approve their own draft."))
    if not (doc.company and doc.jurisdiction and doc.legal_regime and doc.effective_from
            and doc.service_calculation_method and doc.applicability_date_basis
            and (doc.legal_review_notes or "").strip()):
        frappe.throw(_("Company, jurisdiction, regime, service method, effective date and review notes are required."))
    if doc.effective_to and getdate(doc.effective_to) < getdate(doc.effective_from):
        frappe.throw(_("Effective To cannot be earlier than Effective From."))
    if not doc.sources:
        frappe.throw(_("At least one reviewed source is required."), title=_("STATUTORY_SOURCE_REQUIRED"))
    for row in doc.sources:
        if not all((row.source_title, row.section_reference, row.effective_date, row.official_reference)):
            frappe.throw(_("Each source needs title, section, effective date and official reference."))
    source_sections = {row.section_reference for row in doc.sources}
    if not doc.entitlements:
        frappe.throw(_("Explicit entitlement applicability rows are required."))
    for row in doc.entitlements:
        if not all((row.separation_type, row.classification, row.entitlement_type,
                    row.handling, row.source_section)):
            frappe.throw(_("Every mapping must specify exit type, classification, entitlement, handling and source."))
        if row.source_section not in source_sections:
            frappe.throw(_("Entitlement source section {0} is not present in the source table.").format(row.source_section),
                         title=_("STATUTORY_SOURCE_REQUIRED"))
    has_deadline = any(row.entitlement_type == "Final dues deadline" and row.handling == "Deadline Only"
                       for row in doc.entitlements)
    if has_deadline and (int(doc.settlement_deadline_working_days or 0) <= 0 or not doc.holiday_list):
        frappe.throw(_("A deadline needs positive working days and an explicit Holiday List."))
    if not has_deadline and int(doc.settlement_deadline_working_days or 0):
        frappe.throw(_("Set deadline days only when a Deadline Only mapping exists."))
    _scope(doc.company)
    _check_overlap(doc)


def _check_overlap(doc):
    rows = frappe.get_all(RULESET, filters={
        "docstatus": 1, "company": doc.company, "legal_regime": doc.legal_regime,
    }, fields=["name", "branch", "effective_from", "effective_to"])
    start = getdate(doc.effective_from)
    end = getdate(doc.effective_to) if doc.effective_to else None
    for row in rows:
        if row.branch and doc.branch and row.branch != doc.branch:
            continue
        old_start = getdate(row.effective_from)
        old_end = getdate(row.effective_to) if row.effective_to else None
        if (end is None or old_start <= end) and (old_end is None or start <= old_end):
            frappe.throw(_("Approved Rule Set {0} overlaps this period.").format(row.name),
                         title=_("LEGAL_RULESET_CONFLICT"))

def before_submit_statutory_ruleset(doc, method=None):
    _validate_for_approval(doc)
    doc.reviewed_by = frappe.session.user
    doc.reviewed_at = frappe.utils.now_datetime()


def before_update_after_submit_statutory_ruleset(doc, method=None):
    _scope(doc.company)
    _freeze_submitted(doc)


def before_cancel_statutory_ruleset(doc, method=None):
    _scope(doc.company)
    if frappe.db.exists("Employee Separation", {RULESET_FIELD: doc.name}):
        frappe.throw(_("A Rule Set used by an Employee Separation cannot be cancelled."))


def statutory_ruleset_query_conditions(user=None):
    user = user or frappe.session.user
    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        return ""
    companies = frappe.get_all("User Permission",
        filters={"user": user, "allow": "Company"}, pluck="for_value")
    if not companies:
        return "1=0"
    values = ", ".join(frappe.db.escape(company) for company in sorted(set(companies)))
    return "company in (" + values + ")"


def _separation(name):
    doc = frappe.get_doc("Employee Separation", name)
    _scope(doc.company)
    return doc


def _resolve(separation, name, classification):
    if not name:
        frappe.throw(_("Select the exact approved Rule Set."), title=_("LEGAL_RULESET_MISSING"))
    rule = frappe.get_doc(RULESET, name)
    if rule.docstatus != 1:
        frappe.throw(_("The selected Rule Set is not approved."), title=_("LEGAL_RULESET_NOT_APPROVED"))
    if rule.company != separation.company:
        frappe.throw(_("The Rule Set belongs to another company."), frappe.PermissionError)
    branch = frappe.db.get_value("Employee", separation.employee, "branch") or ""
    if rule.branch and rule.branch != branch:
        frappe.throw(_("The Rule Set does not cover this establishment."), title=_("LEGAL_RULESET_CONFLICT"))
    relief = frappe.db.get_value("Employee", separation.employee, "relieving_date")
    if not relief:
        frappe.throw(_("Set Employee.relieving_date before legal review."),
                     title=_("LEGAL_DATE_BASIS_REVIEW_REQUIRED"))
    if rule.applicability_date_basis != "Employee Relieving Date (Legal Review)":
        frappe.throw(_("This Rule Set requires a separate legal date-basis decision."),
                     title=_("LEGAL_DATE_BASIS_REVIEW_REQUIRED"))
    event_date = getdate(relief)
    if event_date < getdate(rule.effective_from) or (rule.effective_to and event_date > getdate(rule.effective_to)):
        frappe.throw(_("The Rule Set is not effective on the relieving date."),
                     title=_("LEGAL_RULESET_NOT_EFFECTIVE"))
    if classification not in {"Worker under selected regime", "Outside worker scope",
                               "Other approved service-rule category"}:
        frappe.throw(_("Select a reviewed legal classification."),
                     title=_("LEGAL_CLASSIFICATION_REVIEW_REQUIRED"))
    mappings = [row for row in rule.entitlements if
                row.separation_type == separation.get(SEPARATION_TYPE)
                and row.classification == classification]
    if not mappings:
        frappe.throw(_("No reviewed mapping matches the exit type and classification."),
                     title=_("SEPARATION_RULE_REVIEW_REQUIRED"))
    return rule, mappings, event_date

@frappe.whitelist()
def review_separation_statutory_status(separation_name, status, notes, rule_set=None, classification=None):
    if status not in {"Approved", "Not Applicable"} or not (notes or "").strip():
        frappe.throw(_("Choose a review outcome and record notes."))
    if "Workforce Owner/Director" not in frappe.get_roles() and frappe.session.user != "Administrator":
        frappe.throw(_("Owner/Director review is required."), frappe.PermissionError)
    separation = _separation(separation_name)
    if frappe.session.user != "Administrator" and separation.owner == frappe.session.user:
        frappe.throw(
            _("The Employee Separation maker cannot review its statutory applicability."),
            frappe.PermissionError,
        )
    if separation.docstatus != 1:
        frappe.throw(_("Submit the Employee Separation before recording legal review."))

    existing_status = separation.get(STATUS_FIELD)
    existing_rule = separation.get(RULESET_FIELD)
    existing_classification = separation.get(CLASSIFICATION_FIELD)
    existing_notes = (separation.get("custom_workforce_statutory_review_notes") or "").strip()
    reviewed_date = separation.get(APPLICABILITY_DATE_FIELD)
    reviewed_by = separation.get("custom_workforce_statutory_reviewed_by")
    reviewed_at = separation.get("custom_workforce_statutory_reviewed_at")
    complete_existing = bool(
        existing_status in {"Approved", "Not Applicable"}
        and existing_notes and reviewed_by and reviewed_at and reviewed_date
        and (existing_status != "Approved" or existing_rule)
        and (existing_status != "Not Applicable" or existing_classification == "Outside worker scope")
    )
    requested_rule = rule_set if status == "Approved" else None
    if complete_existing:
        same_decision = (
            status == existing_status
            and requested_rule == existing_rule
            and classification == existing_classification
            and notes.strip() == existing_notes
        )
        if not same_decision:
            frappe.throw(
                _("A completed statutory decision is immutable. Create an explicit new separation review."),
                title=_("STATUTORY_REVIEW_IMMUTABLE"),
            )
        return {"status": existing_status, "reviewed_by": reviewed_by,
                "rule_set": existing_rule, "applicability_date": reviewed_date}

    employee_relief = frappe.db.get_value("Employee", separation.employee, "relieving_date")
    if not employee_relief:
        frappe.throw(_("Set Employee.relieving_date before recording statutory review."),
                     title=_("LEGAL_DATE_BASIS_REVIEW_REQUIRED"))
    if status == "Approved":
        _rule, _mappings, reviewed_date = _resolve(separation, rule_set, classification)
    else:
        if classification != "Outside worker scope":
            frappe.throw(
                _("Not Applicable is valid only for a reviewed finding that the employee is outside worker scope."),
                title=_("LEGAL_CLASSIFICATION_REVIEW_REQUIRED"),
            )
        if rule_set:
            frappe.throw(_("Do not attach an applicable Rule Set to a Not Applicable decision."))
        reviewed_date = getdate(employee_relief)

    now = frappe.utils.now_datetime()
    separation.db_set({
        STATUS_FIELD: status, RULESET_FIELD: requested_rule,
        CLASSIFICATION_FIELD: classification,
        APPLICABILITY_DATE_FIELD: reviewed_date,
        "custom_workforce_statutory_reviewed_by": frappe.session.user,
        "custom_workforce_statutory_reviewed_at": now,
        "custom_workforce_statutory_review_notes": notes.strip(),
    })
    return {"status": status, "reviewed_by": frappe.session.user,
            "rule_set": requested_rule, "applicability_date": reviewed_date}


def _deadline(rule, relieving_date):
    days = int(rule.settlement_deadline_working_days or 0)
    if not days:
        return None
    if not rule.holiday_list:
        return {"code": "LEGAL_DATE_BASIS_REVIEW_REQUIRED"}
    frappe.get_cached_doc("Holiday List", rule.holiday_list)
    from erpnext.setup.doctype.holiday_list.holiday_list import is_holiday

    due, counted = getdate(relieving_date), 0
    while counted < days:
        due += timedelta(days=1)
        if not is_holiday(rule.holiday_list, due):
            counted += 1
    return {"due_date": due, "working_days": days, "holiday_list": rule.holiday_list}


@frappe.whitelist()
def inspect_statutory_exit_readiness(separation_name):
    """Resolve the separation's frozen rule and reviewed event date without calculating money."""
    separation = _separation(separation_name)
    status = separation.get(STATUS_FIELD)
    classification = separation.get(CLASSIFICATION_FIELD)
    name = separation.get(RULESET_FIELD)
    reviewed_date = separation.get(APPLICABILITY_DATE_FIELD)
    reviewed_by = separation.get("custom_workforce_statutory_reviewed_by")
    reviewed_at = separation.get("custom_workforce_statutory_reviewed_at")
    notes = separation.get("custom_workforce_statutory_review_notes")
    current_relief = frappe.db.get_value("Employee", separation.employee, "relieving_date")

    if not (reviewed_date and reviewed_by and reviewed_at and (notes or "").strip()):
        return {"status": "REVIEW_REQUIRED",
                "findings": [{"code": "LEGAL_CLASSIFICATION_REVIEW_REQUIRED"}], "entitlements": []}
    if not current_relief or getdate(current_relief) != getdate(reviewed_date):
        return {"status": "REVIEW_REQUIRED",
                "findings": [{"code": "LEGAL_DATE_BASIS_REVIEW_REQUIRED"}],
                "applicability_date": reviewed_date, "entitlements": []}

    if status == "Not Applicable":
        if name or classification != "Outside worker scope":
            return {"status": "REVIEW_REQUIRED",
                    "findings": [{"code": "LEGAL_CLASSIFICATION_REVIEW_REQUIRED"}], "entitlements": []}
        return {"status": "NOT_APPLICABLE", "findings": [],
                "classification": classification, "applicability_date": reviewed_date,
                "reviewed_by": reviewed_by, "reviewed_at": reviewed_at,
                "review_notes": notes, "entitlements": []}

    if status != "Approved":
        return {"status": "REVIEW_REQUIRED",
                "findings": [{"code": "LEGAL_CLASSIFICATION_REVIEW_REQUIRED"}], "entitlements": []}
    if not name:
        return {"status": "REVIEW_REQUIRED",
                "findings": [{"code": "STATUTORY_ENTITLEMENT_RULESET_REQUIRED"}], "entitlements": []}
    if not frappe.db.exists(RULESET, name):
        return {"status": "REVIEW_REQUIRED", "findings": [{"code": "LEGAL_RULESET_MISSING"}], "entitlements": []}
    rule = frappe.get_doc(RULESET, name)
    if rule.docstatus != 1:
        return {"status": "REVIEW_REQUIRED", "findings": [{"code": "LEGAL_RULESET_NOT_APPROVED"}], "entitlements": []}
    branch = frappe.db.get_value("Employee", separation.employee, "branch") or ""
    if rule.company != separation.company or (rule.branch and rule.branch != branch):
        return {"status": "REVIEW_REQUIRED", "findings": [{"code": "LEGAL_RULESET_CONFLICT"}], "entitlements": []}
    if rule.applicability_date_basis != "Employee Relieving Date (Legal Review)":
        return {"status": "REVIEW_REQUIRED", "findings": [{"code": "LEGAL_DATE_BASIS_REVIEW_REQUIRED"}], "entitlements": []}
    event_date = getdate(reviewed_date)
    if event_date < getdate(rule.effective_from) or (rule.effective_to and event_date > getdate(rule.effective_to)):
        return {"status": "REVIEW_REQUIRED", "findings": [{"code": "LEGAL_RULESET_NOT_EFFECTIVE"}], "entitlements": []}
    mappings = [row for row in rule.entitlements if
                row.separation_type == separation.get(SEPARATION_TYPE)
                and row.classification == classification]
    if not mappings:
        return {"status": "REVIEW_REQUIRED", "findings": [{"code": "SEPARATION_RULE_REVIEW_REQUIRED"}], "entitlements": []}

    sections = {row.section_reference for row in rule.sources}
    findings, resolved = [], []
    for row in mappings:
        resolved.append({"entitlement_type": row.entitlement_type, "handling": row.handling,
                         "source_section": row.source_section})
        if row.source_section not in sections:
            findings.append({"code": "STATUTORY_SOURCE_REQUIRED", "entitlement_type": row.entitlement_type})
        if row.handling == "Manual Legal Calculation":
            findings.append({"code": "MANUAL_STATUTORY_CALCULATION_REQUIRED",
                             "entitlement_type": row.entitlement_type})
        elif row.entitlement_type == "Gratuity comparison" and row.handling == "Native Gratuity":
            if not frappe.db.count("Gratuity Rule"):
                findings.append({"code": "GRATUITY_CONFIGURATION_REQUIRED"})
        elif row.entitlement_type == "Leave encashment review" and row.handling == "Native Leave Encashment":
            if not frappe.db.count("Leave Type", {"allow_encashment": 1}):
                findings.append({"code": "LEAVE_ENCASHMENT_CONFIGURATION_REQUIRED"})
    deadline = None
    if any(row.entitlement_type == "Final dues deadline" and row.handling == "Deadline Only"
           for row in mappings):
        deadline = _deadline(rule, reviewed_date)
        if deadline and deadline.get("code"):
            findings.append({"code": deadline["code"]})
    return {"status": "READY_FOR_STATUTORY_REVIEW" if not findings else "REVIEW_REQUIRED",
            "findings": findings, "company": rule.company, "jurisdiction": rule.jurisdiction,
            "legal_regime": rule.legal_regime, "rule_set": rule.name,
            "effective_from": rule.effective_from, "effective_to": rule.effective_to,
            "classification": classification, "applicability_date": reviewed_date,
            "reviewed_by": reviewed_by, "reviewed_at": reviewed_at,
            "source_sections": sorted(sections), "entitlements": resolved,
            "settlement_deadline": deadline}
