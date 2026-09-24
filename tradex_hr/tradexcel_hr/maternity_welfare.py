"""Restricted maternity review and establishment welfare readiness."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, InvalidOperation
from math import ceil

import frappe
from dateutil.relativedelta import relativedelta
from frappe import _
from frappe.utils import flt, getdate, now_datetime, today

from tradex_hr.tradexcel_hr.company_context import assert_company_access

MATERNITY_RULE = "Tradexcel Maternity Rule Set"
MATERNITY_REVIEW = "Tradexcel Maternity Review"
MATERNITY_SEPARATION_REVIEW = "Tradexcel Maternity Separation Review"
WELFARE_REVIEW = "Tradexcel Workplace Welfare Review"
SENSITIVE_ROLES = {"Tradexcel HR Manager", "Tradexcel Owner/Director"}
WELFARE_READ_ROLES = SENSITIVE_ROLES | {"Tradexcel Compliance Auditor"}
WORK_STATUSES = {"Present", "Half Day", "Work From Home"}


def _roles(user=None):
    return set(frappe.get_roles(user or frappe.session.user))


def _has_company_scope(user, company):
    return user == "Administrator" or bool(company and frappe.db.exists(
        "User Permission", {"user": user, "allow": "Company", "for_value": company}
    ))


def _query_conditions(user=None, allowed_roles=SENSITIVE_ROLES):
    user = user or frappe.session.user
    if user == "Administrator":
        return ""
    if not _roles(user).intersection(allowed_roles):
        return "1=0"
    companies = sorted(set(frappe.get_all(
        "User Permission", filters={"user": user, "allow": "Company"}, pluck="for_value"
    )))
    if not companies:
        return "1=0"
    values = ", ".join(frappe.db.escape(company) for company in companies)
    return f"company in ({values})"


def maternity_sensitive_query_conditions(user=None):
    return _query_conditions(user, SENSITIVE_ROLES)


def maternity_rule_query_conditions(user=None):
    return _query_conditions(user, WELFARE_READ_ROLES)


def welfare_query_conditions(user=None):
    return maternity_rule_query_conditions(user)


def maternity_sensitive_has_permission(doc, user=None, permission_type=None):
    user = user or frappe.session.user
    return user == "Administrator" or (
        bool(_roles(user).intersection(SENSITIVE_ROLES))
        and (doc is None or _has_company_scope(user, doc.get("company")))
    )


def maternity_rule_has_permission(doc, user=None, permission_type=None):
    user = user or frappe.session.user
    return user == "Administrator" or (
        bool(_roles(user).intersection(WELFARE_READ_ROLES))
        and (doc is None or _has_company_scope(user, doc.get("company")))
    )


def welfare_has_permission(doc, user=None, permission_type=None):
    return maternity_rule_has_permission(doc, user, permission_type)


def _scope(doc):
    assert_company_access(doc.company, require_explicit_scope=True)
    if doc.get("branch"):
        branch_company = frappe.db.get_value("Branch", doc.branch, "company")
        if branch_company != doc.company:
            frappe.throw(_("The Branch must belong to the selected Company."))


def _freeze_submitted(doc):
    fields = {
        MATERNITY_RULE: RULE_FROZEN_FIELDS,
        MATERNITY_REVIEW: REVIEW_FROZEN_FIELDS,
        MATERNITY_SEPARATION_REVIEW: SEPARATION_FROZEN_FIELDS,
        WELFARE_REVIEW: WELFARE_FROZEN_FIELDS,
    }.get(doc.doctype, ())
    _freeze_submitted_fields(doc, fields)


def _validate_period(start, end, label):
    if not start or (end and getdate(end) < getdate(start)):
        frappe.throw(_("{0} effective dates are invalid.").format(label))


def _source_rows(doc):
    rows = doc.get("sources") or []
    accepted_types = {"Act", "Amendment Act", "Rule", "Gazette", "Company Service Rule"}
    if not rows or any(
        not all((r.source_title, r.source_type, r.section_reference, r.effective_date, r.official_reference))
        or r.source_type not in accepted_types
        for r in rows
    ):
        frappe.throw(_("At least one complete authoritative legal source row is required."),
                     title=_("LEGAL_SOURCE_REQUIRED"))
    return rows


def _branch_scopes_overlap(left, right):
    return not left or not right or left == right


def benefit_rate_configuration_error(method, divisor, reference_months):
    if method == "Monthly Gross / Divisor":
        return "MATERNITY_RATE_DIVISOR_REQUIRED" if flt(divisor) <= 0 else None
    if method == "Average Wages / Actual Days Worked":
        return "MATERNITY_REFERENCE_PERIOD_REQUIRED" if int(reference_months or 0) <= 0 else None
    if method == "Manual Legal Review":
        return None
    return "MATERNITY_RATE_METHOD_REQUIRED"


def validate_maternity_rule_set(doc, method=None):
    _scope(doc)
    _freeze_submitted(doc)
    _validate_period(doc.effective_from, doc.effective_to, _("Maternity Rule Set"))
    positive = (
        "minimum_service_months", "pre_delivery_days", "post_delivery_days",
        "post_delivery_work_protection_days", "leave_max_continuous_days",
    )
    nonnegative = ("separation_protection_before_months", "separation_protection_after_days")
    if any(int(doc.get(f) or 0) <= 0 for f in positive):
        frappe.throw(_("Minimum service and native leave maximum must be positive."))
    if any(int(doc.get(f) or 0) < 0 for f in nonnegative):
        frappe.throw(_("Reviewed maternity rule values must be valid and non-negative."))
    rate_error = benefit_rate_configuration_error(
        doc.benefit_rate_method,
        doc.benefit_daily_rate_divisor,
        doc.benefit_reference_period_months,
    )
    if rate_error:
        frappe.throw(_("Maternity benefit rate basis needs explicit legal review."),
                     title=_(rate_error))
    sources = _source_rows(doc)
    if getdate(doc.effective_from) < max(getdate(r.effective_date) for r in sources):
        frappe.throw(_("The Rule Set cannot precede its latest supporting legal source."),
                     title=_("MATERNITY_RULE_PRECEDES_SOURCE"))
    existing = frappe.get_all(
        MATERNITY_RULE,
        filters={"company": doc.company, "legal_regime": doc.legal_regime, "docstatus": 1},
        fields=["name", "branch", "effective_from", "effective_to"],
    )
    start, end = getdate(doc.effective_from), getdate(doc.effective_to) if doc.effective_to else None
    for row in existing:
        if row.name == doc.name or not _branch_scopes_overlap(doc.branch, row.branch):
            continue
        old_start, old_end = getdate(row.effective_from), getdate(row.effective_to) if row.effective_to else None
        if (end is None or old_start <= end) and (old_end is None or start <= old_end):
            frappe.throw(_("An approved maternity Rule Set overlaps this establishment period."),
                         title=_("MATERNITY_RULE_CONFLICT"))


def before_submit_maternity_rule_set(doc, method=None):
    _scope(doc)
    if frappe.session.user != "Administrator":
        if "Tradexcel Owner/Director" not in _roles() or doc.owner == frappe.session.user:
            frappe.throw(_("A different company-scoped Owner/Director must approve the maternity Rule Set."),
                         frappe.PermissionError)
    sources = _source_rows(doc)
    if getdate(doc.effective_from) < max(getdate(r.effective_date) for r in sources):
        frappe.throw(_("The Rule Set cannot precede its latest supporting legal source."),
                     title=_("MATERNITY_RULE_PRECEDES_SOURCE"))
    doc.reviewed_by = frappe.session.user
    doc.reviewed_at = now_datetime()


def prevent_maternity_rule_update(doc, method=None):
    frappe.throw(_("Approved maternity Rule Sets are immutable; create a new version."))


def prevent_maternity_rule_cancel(doc, method=None):
    frappe.throw(_("Approved maternity Rule Sets are historical evidence and cannot be cancelled."))


def _employee_row(employee):
    row = frappe.db.get_value(
        "Employee", employee,
        ["name", "company", "branch", "date_of_joining", "relieving_date", "status"],
        as_dict=True,
    )
    if not row:
        frappe.throw(_("Employee not found."))
    return row


def _approved_rule(rule_name, company, branch, event_date):
    rule = frappe.get_doc(MATERNITY_RULE, rule_name)
    if int(rule.docstatus or 0) != 1 or rule.company != company:
        frappe.throw(_("Select an approved maternity Rule Set for the same Company."),
                     title=_("MATERNITY_RULESET_REQUIRED"))
    if rule.branch and rule.branch != (branch or ""):
        frappe.throw(_("The maternity Rule Set does not cover the reviewed establishment."),
                     title=_("MATERNITY_RULESET_SCOPE_MISMATCH"))
    day = getdate(event_date)
    if day < getdate(rule.effective_from) or (rule.effective_to and day > getdate(rule.effective_to)):
        frappe.throw(_("The maternity Rule Set is not effective on the reviewed event date."),
                     title=_("MATERNITY_RULE_NOT_EFFECTIVE"))
    return rule


def service_months_result(joining_date, reference_date, minimum_months):
    if not joining_date or not reference_date or int(minimum_months or 0) <= 0:
        return "REVIEW"
    try:
        return "MEETS" if getdate(joining_date) + relativedelta(months=int(minimum_months)) <= getdate(reference_date) else "BELOW"
    except (TypeError, ValueError):
        return "REVIEW"


def calculate_maternity_benefit_preview(monthly_gross, divisor, covered_days):
    """Rule-driven arithmetic fixture; callers still need an approved wage authority."""
    try:
        gross, divisor, days = Decimal(str(monthly_gross)), Decimal(str(divisor)), Decimal(str(covered_days))
        if gross < 0 or divisor <= 0 or days < 0:
            return None
        return float(gross / divisor * days)
    except (InvalidOperation, TypeError, ValueError, ZeroDivisionError):
        return None


def _validate_native_leave_type(rule):
    values = frappe.db.get_value(
        "Leave Type", rule.maternity_leave_type,
        ["is_lwp", "is_ppl", "include_holiday", "max_continuous_days_allowed"],
        as_dict=True,
    )
    if not values:
        return [{"code": "MATERNITY_LEAVE_TYPE_REQUIRED"}]
    expected = {
        "is_lwp": int(rule.leave_is_lwp or 0),
        "is_ppl": int(rule.leave_is_ppl or 0),
        "include_holiday": int(rule.leave_include_holidays or 0),
        "max_continuous_days_allowed": int(rule.leave_max_continuous_days or 0),
    }
    mismatch = [field for field, value in expected.items() if int(values.get(field) or 0) != value]
    return [{"code": "MATERNITY_LEAVE_CONFIGURATION_MISMATCH", "fields": mismatch}] if mismatch else []


RULE_FROZEN_FIELDS = (
    "title", "company", "branch", "legal_regime", "effective_from", "effective_to",
    "minimum_service_months", "pre_delivery_days", "post_delivery_days",
    "post_delivery_work_protection_days", "separation_protection_before_months",
    "separation_protection_after_days", "benefit_rate_method",
    "benefit_daily_rate_divisor", "benefit_reference_period_months",
    "maternity_leave_type", "leave_is_lwp", "leave_is_ppl", "leave_include_holidays",
    "leave_max_continuous_days", "benefit_payment_child_condition_review_required",
    "sources", "legal_review_notes",
)
REVIEW_FROZEN_FIELDS = (
    "employee", "company", "branch", "rule_set", "notice_date", "expected_delivery_date",
    "actual_delivery_date", "benefit_eligibility", "eligibility_reason",
    "native_leave_applications", "evidence_reference", "review_notes",
    "historical_work_evidence_reviewed",
)
WELFARE_FROZEN_FIELDS = (
    "company", "branch", "legal_regime", "effective_from", "effective_to",
    "first_aid_applicability", "reviewed_worker_count", "worker_count_as_of",
    "worker_count_evidence_reference", "workers_per_first_aid_box", "first_aid_box_count", "first_aid_accessibility_evidence",
    "trained_custodian_evidence", "child_room_applicability", "reviewed_women_worker_count",
    "women_count_as_of", "women_count_evidence_reference", "child_room_status",
    "child_room_evidence_reference", "sources", "review_notes",
)
SEPARATION_FROZEN_FIELDS = (
    "employee", "company", "employee_separation", "maternity_review",
    "decision", "review_notes", "evidence_reference",
)


def _assert_maker_checker(doc):
    user = frappe.session.user
    if user != "Administrator":
        if "Tradexcel Owner/Director" not in _roles(user):
            frappe.throw(_("A company-scoped Owner/Director must approve this review."), frappe.PermissionError)
        if doc.owner == user:
            frappe.throw(_("The maker cannot approve their own legal review."), frappe.PermissionError)
    _scope(doc)


def _freeze_submitted_fields(doc, fields):
    if doc.is_new() or int(doc.docstatus or 0) != 1 or doc.flags.in_insert or doc._action == "submit":
        return
    old = doc.get_doc_before_save()
    if old and any(old.get(field) != doc.get(field) for field in fields):
        frappe.throw(_("Approved compliance meaning is immutable; create a new reviewed version."),
                     title=_("COMPLIANCE_REVIEW_IMMUTABLE"))


def _validate_sources_effective(doc):
    rows = _source_rows(doc)
    if getdate(doc.effective_from) < max(getdate(row.effective_date) for row in rows):
        frappe.throw(_("Effective date cannot precede a supporting legal source."),
                     title=_("RULE_PRECEDES_SOURCE"))


def validate_maternity_review(doc, method=None):
    _scope(doc)
    _freeze_submitted_fields(doc, REVIEW_FROZEN_FIELDS)
    employee = _employee_row(doc.employee)
    if employee.company != doc.company:
        frappe.throw(_("Employee and maternity review must belong to the same Company."))
    reference_date = doc.actual_delivery_date or doc.expected_delivery_date or doc.notice_date
    if not reference_date:
        frappe.throw(_("Provide a notice, expected delivery, or actual delivery date."))
    rule = _approved_rule(doc.rule_set, doc.company, doc.branch, reference_date)
    if rule.legal_regime not in ("Bangladesh Labour Act", "Bangladesh EPZ Labour Act", "Other Reviewed Regime"):
        frappe.throw(_("Select an explicit reviewed legal regime."))
    allowed_reason = {
        "Pending Review": "Pending",
        "Eligible": "Eligible",
        "Leave Only — Statutory Benefit Not Payable": "Leave Only",
        "Not Applicable": "Not Applicable",
    }
    if doc.eligibility_reason != allowed_reason.get(doc.benefit_eligibility):
        frappe.throw(_("Eligibility outcome and reason code must agree."))
    if not doc.review_notes:
        frappe.throw(_("Restricted reviewer notes are required."))
    if doc.benefit_eligibility == "Eligible" and not doc.actual_delivery_date:
        frappe.throw(_("Confirm actual delivery and restricted eligibility evidence before marking the benefit eligible."))
    if doc.benefit_eligibility in ("Eligible", "Leave Only — Statutory Benefit Not Payable") and not doc.evidence_reference:
        frappe.throw(_("Benefit eligibility outcome requires a restricted evidence reference."))
    if doc.actual_delivery_date and _historical_work_evidence(doc, rule):
        if not doc.historical_work_evidence_reviewed or not doc.review_notes:
            frappe.throw(_("Existing work evidence in the protected period requires restricted review."),
                         title=_("MATERNITY_PROTECTED_WORK_EVIDENCE_REVIEW_REQUIRED"))
    if (doc.benefit_eligibility == "Eligible"
            and service_months_result(employee.date_of_joining, reference_date, rule.minimum_service_months) == "BELOW"):
        frappe.throw(_("Recorded service is below the reviewed eligibility threshold."),
                     title=_("MATERNITY_SERVICE_REQUIREMENT_NOT_MET"))
    for application_name in doc.get("native_leave_applications") or []:
        name = application_name.leave_application
        app = frappe.db.get_value(
            "Leave Application", name,
            ["employee", "company", "leave_type", "docstatus", "status"], as_dict=True
        )
        if not app or app.employee != doc.employee or app.company != doc.company:
            frappe.throw(_("Linked Leave Application must match the employee and Company."))
        if app.leave_type != rule.maternity_leave_type or app.docstatus != 1 or app.status != "Approved":
            frappe.throw(_("Linked maternity Leave Application must be submitted and approved."))


def before_submit_maternity_review(doc, method=None):
    _assert_maker_checker(doc)
    validate_maternity_review(doc)
    employee = _employee_row(doc.employee)
    rule = frappe.get_doc(MATERNITY_RULE, doc.rule_set)
    event_date = doc.actual_delivery_date or doc.expected_delivery_date or doc.notice_date
    service_result = service_months_result(employee.date_of_joining, event_date, rule.minimum_service_months)
    if service_result == "REVIEW" or frappe.db.exists(
        "Employee Separation",
        {"employee": doc.employee, "docstatus": 1, "relieving_date": ["<", event_date]},
    ):
        frappe.throw(_("Employment history needs legal review."), title=_("MATERNITY_SERVICE_HISTORY_REVIEW_REQUIRED"))
    if service_result == "BELOW" and doc.benefit_eligibility not in (
        "Leave Only — Statutory Benefit Not Payable", "Not Applicable"
    ):
        frappe.throw(_("Employment service is below the reviewed threshold; keep eligibility pending or record the reviewed leave-only outcome."),
                     title=_("MATERNITY_SERVICE_REQUIREMENT_NOT_MET"))
    doc.reviewed_by = frappe.session.user
    doc.reviewed_at = now_datetime()


def before_update_after_submit_maternity_review(doc, method=None):
    _freeze_submitted_fields(doc, REVIEW_FROZEN_FIELDS)


def before_cancel_maternity_review(doc, method=None):
    if frappe.session.user != "Administrator":
        frappe.throw(_("Submitted maternity reviews are immutable; supersede with a new review."),
                     frappe.PermissionError)


def validate_maternity_rule_submit(doc, method=None):
    _assert_maker_checker(doc)
    validate_maternity_rule_set(doc)
    _validate_native_leave_type(doc)
    doc.reviewed_by = frappe.session.user
    doc.reviewed_at = now_datetime()


def before_update_after_submit_maternity_rule(doc, method=None):
    _freeze_submitted_fields(doc, RULE_FROZEN_FIELDS)


def _has_role(user, roles):
    return bool(_roles(user).intersection(roles))


def _maternity_schema_installed():
    return frappe.db.table_exists(MATERNITY_REVIEW)


def _active_maternity_reviews(employee, start, end):
    if not _maternity_schema_installed():
        return []
    names = frappe.get_all(
        MATERNITY_REVIEW,
        filters={"employee": employee, "docstatus": 1},
        pluck="name",
    )
    rows = []
    for name in names:
        review = frappe.get_doc(MATERNITY_REVIEW, name)
        rule = frappe.get_doc(MATERNITY_RULE, review.rule_set)
        if rule.legal_regime not in ("Bangladesh Labour Act", "Bangladesh EPZ Labour Act", "Other Reviewed Regime"):
            continue
        if review.benefit_eligibility not in ("Pending Review", "Eligible", "Leave Only — Statutory Benefit Not Payable"):
            continue
        # Leave planning follows expected dates. Protected-work validation requires actual delivery.
        anchor = review.actual_delivery_date or review.expected_delivery_date
        if not anchor:
            continue
        benefit_start = getdate(anchor) - timedelta(days=int(rule.pre_delivery_days or 0))
        benefit_end = getdate(anchor) + timedelta(days=int(rule.post_delivery_days or 0) - 1)
        protected_start = protected_end = None
        if review.actual_delivery_date:
            protected_start = getdate(review.actual_delivery_date)
            protected_end = protected_start + timedelta(days=int(rule.post_delivery_work_protection_days or 0) - 1)
        overlaps_benefit = getdate(start) <= benefit_end and getdate(end) >= benefit_start
        overlaps_protected_work = (
            protected_start is not None
            and getdate(start) <= protected_end
            and getdate(end) >= protected_start
        )
        if not overlaps_benefit and not overlaps_protected_work:
            continue
        rows.append((review, rule, protected_start, protected_end))
    return rows


def prepare_maternity_payroll_context(company, employee_ids, start, end):
    """Batch-resolve generic maternity payroll findings for the requested population."""
    if not employee_ids or not _maternity_schema_installed():
        return {}
    rows = frappe.get_all(
        MATERNITY_REVIEW,
        filters={"company": company, "employee": ["in", employee_ids], "docstatus": 1},
        fields=[
            "employee", "company", "rule_set", "actual_delivery_date",
            "expected_delivery_date", "benefit_eligibility",
        ],
    )
    rule_cache = {}
    leave_cache = {}
    findings = {}
    period_start, period_end = getdate(start), getdate(end)
    for review in rows:
        anchor = review.actual_delivery_date or review.expected_delivery_date
        if not anchor:
            continue
        rule = rule_cache.get(review.rule_set)
        if rule is None:
            rule = frappe.get_doc(MATERNITY_RULE, review.rule_set)
            if int(rule.docstatus or 0) != 1 or rule.company != company:
                continue
            rule_cache[review.rule_set] = rule
        benefit_start = getdate(anchor) - timedelta(days=int(rule.pre_delivery_days or 0))
        benefit_end = getdate(anchor) + timedelta(days=int(rule.post_delivery_days or 0) - 1)
        if period_start > benefit_end or period_end < benefit_start:
            continue
        codes = findings.setdefault(review.employee, [])
        if review.benefit_eligibility == "Pending Review":
            codes.append("MATERNITY_BENEFIT_ELIGIBILITY_REVIEW_REQUIRED")
        elif review.benefit_eligibility == "Eligible":
            if review.rule_set not in leave_cache:
                leave_cache[review.rule_set] = _validate_native_leave_type(rule)
            codes.extend(item["code"] for item in leave_cache[review.rule_set])
            codes.append("MATERNITY_BENEFIT_PAYMENT_PATH_REVIEW_REQUIRED")
    return {employee: sorted(set(codes)) for employee, codes in findings.items()}


def maternity_payroll_review_codes(employee, start, end, company=None):
    """Expose generic payment findings only; never return case dates or family evidence."""
    if not company:
        company = frappe.db.get_value("Employee", employee, "company")
    return prepare_maternity_payroll_context(company, [employee], start, end).get(employee, [])


def inspect_maternity_benefit(employee, reference_date):
    employee_row = _employee_row(employee)
    if not _has_role(frappe.session.user, SENSITIVE_ROLES) and frappe.session.user != "Administrator":
        frappe.throw(_("Maternity detail access is restricted."), frappe.PermissionError)
    assert_company_access(employee_row.company, require_explicit_scope=True)
    reviews = frappe.get_all(
        MATERNITY_REVIEW, filters={"employee": employee, "docstatus": 1},
        pluck="name", order_by="creation desc", limit=1,
    )
    if not reviews:
        return {"status": "NO_CASE"}
    review = frappe.get_doc(MATERNITY_REVIEW, reviews[-1])
    rule = frappe.get_doc(MATERNITY_RULE, review.rule_set)
    service = service_months_result(_employee_row(employee).date_of_joining, reference_date, rule.minimum_service_months)
    payment_path = {
        "Pending Review": "MATERNITY_BENEFIT_ELIGIBILITY_REVIEW_REQUIRED",
        "Eligible": "MATERNITY_BENEFIT_PAYMENT_PATH_REVIEW_REQUIRED",
        "Leave Only — Statutory Benefit Not Payable": "STATUTORY_BENEFIT_NOT_PAYABLE",
        "Not Applicable": "NOT_APPLICABLE",
    }.get(review.benefit_eligibility, "MATERNITY_BENEFIT_ELIGIBILITY_REVIEW_REQUIRED")
    return {
        "rule_set": rule.name,
        "service_eligibility": service,
        "benefit_eligibility": review.benefit_eligibility,
        "benefit_rate_method": rule.benefit_rate_method,
        "benefit_reference_period_months": rule.benefit_reference_period_months,
        "expected_amount": None,
        "leave_findings": _validate_native_leave_type(rule),
        "payment_path": payment_path,
    }


def _review_for_protected_period(employee, day):
    for review, rule, start, end in _active_maternity_reviews(employee, day, day):
        if start and start <= getdate(day) <= end:
            return review, rule
    return None, None


def validate_maternity_protected_work(doc, method=None):
    if not getattr(doc, "employee", None):
        return
    start = getattr(doc, "attendance_date", None) or getattr(doc, "start_date", None) or getattr(doc, "duty_date", None)
    end = getattr(doc, "end_date", None) or start
    if not start or not end:
        return
    start, end = getdate(start), getdate(end)
    if not _maternity_schema_installed():
        return
    if (end - start).days > 370:
        frappe.throw(_("The document interval is too large for protected-period validation."))
    days = (start + timedelta(days=offset) for offset in range((end - start).days + 1))
    protected = any(_review_for_protected_period(doc.employee, day)[0] for day in days)
    if protected:
        frappe.throw(_("Actual work is within a reviewed protected post-delivery period."),
                     title=_("MATERNITY_PROTECTED_WORK_PERIOD"))


def _historical_work_evidence(review, rule):
    if not review.actual_delivery_date:
        return False
    start = getdate(review.actual_delivery_date)
    end = start + timedelta(days=int(rule.post_delivery_work_protection_days or 0) - 1)
    return bool(frappe.db.exists("Attendance", {
        "employee": review.employee, "docstatus": 1, "attendance_date": ["between", [start, end]],
        "status": ["in", tuple(WORK_STATUSES)], "working_hours": [">", 0],
    }))


def validate_maternity_separation_review(doc, method=None):
    _scope(doc)
    _freeze_submitted_fields(doc, SEPARATION_FROZEN_FIELDS)
    separation = frappe.db.get_value(
        "Employee Separation", doc.employee_separation,
        ["employee", "company", "relieving_date"], as_dict=True,
    )
    if not separation or separation.employee != doc.employee or separation.company != doc.company:
        frappe.throw(_("The separation review must match the Employee Separation."))
    review = frappe.get_doc(MATERNITY_REVIEW, doc.maternity_review)
    if review.employee != doc.employee or review.company != doc.company or review.docstatus != 1:
        frappe.throw(_("The linked maternity review must be submitted for this employee."))
    rule = frappe.get_doc(MATERNITY_RULE, review.rule_set)
    duplicates = frappe.get_all(
        MATERNITY_SEPARATION_REVIEW,
        filters={
            "employee_separation": doc.employee_separation,
            "maternity_review": doc.maternity_review,
            "docstatus": 1,
        },
        pluck="name",
    )
    if duplicates and doc.name not in duplicates:
        frappe.throw(_("Only one immutable legal review may decide this separation and maternity case."))
    day = getdate(separation.relieving_date)
    anchor = review.actual_delivery_date or review.expected_delivery_date
    start = getdate(anchor) - relativedelta(months=int(rule.separation_protection_before_months or 0)) if anchor else None
    end = getdate(anchor) + timedelta(days=int(rule.separation_protection_after_days or 0)) if anchor else None
    if not start or not (start <= day <= end):
        frappe.throw(_("The separation date does not overlap the reviewed protected period."))
    if doc.decision not in ("Proceed After Legal Review", "Hold"):
        frappe.throw(_("Select a reviewed separation decision."))


def before_submit_maternity_separation_review(doc, method=None):
    _assert_maker_checker(doc)
    validate_maternity_separation_review(doc)
    doc.reviewed_by = frappe.session.user
    doc.reviewed_at = now_datetime()


def before_update_after_submit_maternity_separation_review(doc, method=None):
    _freeze_submitted_fields(doc, SEPARATION_FROZEN_FIELDS)


def _separation_maternity_review(employee_separation):
    row = frappe.db.get_value(
        "Employee Separation", employee_separation,
        ["employee", "company", "relieving_date"], as_dict=True,
    )
    if not row:
        return False
    cases = frappe.get_all(MATERNITY_REVIEW, filters={"employee": row.employee, "company": row.company, "docstatus": 1}, pluck="name")
    for name in cases:
        review = frappe.get_doc(MATERNITY_REVIEW, name)
        anchor = review.actual_delivery_date or review.expected_delivery_date
        if not anchor:
            continue
        rule = frappe.get_doc(MATERNITY_RULE, review.rule_set)
        day = getdate(row.relieving_date)
        protected_from = getdate(anchor) - relativedelta(months=int(rule.separation_protection_before_months or 0))
        protected_to = getdate(anchor) + timedelta(days=int(rule.separation_protection_after_days or 0))
        if protected_from <= day <= protected_to:
            found = frappe.get_all(
                MATERNITY_SEPARATION_REVIEW,
                filters={"employee_separation": employee_separation, "maternity_review": name, "docstatus": 1},
                fields=["name", "decision"],
            )
            if len(found) != 1 or found[0].decision != "Proceed After Legal Review":
                return True
    return False


def validate_maternity_separation(doc, method=None):
    if _separation_maternity_review(doc.name):
        frappe.throw(_("A protected maternity period requires independent legal separation review."),
                     title=_("MATERNITY_SEPARATION_LEGAL_REVIEW_REQUIRED"))


def evaluate_first_aid_readiness(data):
    applicability = data.get("first_aid_applicability")
    if applicability == "Not Applicable":
        return []
    if applicability != "Applicable":
        return [{"code": "FIRST_AID_APPLICABILITY_REVIEW_REQUIRED"}]
    try:
        workers = int(data.get("reviewed_worker_count"))
        per_box = int(data.get("workers_per_first_aid_box"))
        boxes = int(data.get("first_aid_box_count"))
    except (TypeError, ValueError):
        return [{"code": "FIRST_AID_APPLICABILITY_REVIEW_REQUIRED"}]
    findings = []
    if workers <= 0 or per_box <= 0 or boxes < ceil(workers / per_box):
        findings.append({"code": "FIRST_AID_BOX_COUNT_INSUFFICIENT"})
    if not data.get("trained_custodian_evidence"):
        findings.append({"code": "FIRST_AID_TRAINED_CUSTODIAN_REQUIRED"})
    if not data.get("first_aid_accessibility_evidence"):
        findings.append({"code": "FIRST_AID_ACCESSIBILITY_EVIDENCE_REQUIRED"})
    return findings


def evaluate_child_room_readiness(data):
    state = data.get("child_room_applicability")
    if state == "Not Applicable":
        return []
    if state != "Applicable":
        return [{"code": "CHILD_ROOM_APPLICABILITY_REVIEW_REQUIRED"}]
    if data.get("child_room_status") != "Available" or not data.get("child_room_evidence_reference"):
        return [{"code": "CHILD_ROOM_FACILITY_REQUIRED"}]
    return []


def inspect_workplace_welfare_readiness(name, as_of_date=None):
    doc = frappe.get_doc(WELFARE_REVIEW, name)
    if int(doc.docstatus or 0) != 1:
        return {"status": "NEEDS_REVIEW", "findings": [{"code": "WORKPLACE_WELFARE_REVIEW_REQUIRED"}]}
    _scope(doc)
    day = getdate(as_of_date or today())
    if day < getdate(doc.effective_from) or (doc.effective_to and day > getdate(doc.effective_to)):
        return {"status": "NOT_APPLICABLE", "findings": []}
    findings = evaluate_first_aid_readiness(doc.as_dict())
    findings.extend(evaluate_child_room_readiness(doc.as_dict()))
    return {"status": "READY" if not findings else "NEEDS_REVIEW", "findings": findings}


def validate_workplace_welfare_review(doc, method=None):
    _scope(doc)
    _freeze_submitted_fields(doc, WELFARE_FROZEN_FIELDS)
    _validate_period(doc.effective_from, doc.effective_to, _("Workplace Welfare Review"))
    _validate_sources_effective(doc)
    existing = frappe.get_all(
        WELFARE_REVIEW,
        filters={"company": doc.company, "legal_regime": doc.legal_regime, "docstatus": 1},
        fields=["name", "branch", "effective_from", "effective_to"],
    )
    start = getdate(doc.effective_from)
    end = getdate(doc.effective_to) if doc.effective_to else None
    for row in existing:
        if row.name == doc.name or not _branch_scopes_overlap(doc.branch, row.branch):
            continue
        old_start = getdate(row.effective_from)
        old_end = getdate(row.effective_to) if row.effective_to else None
        if (end is None or old_start <= end) and (old_end is None or start <= old_end):
            frappe.throw(_("An approved workplace welfare review overlaps this establishment period."),
                         title=_("WORKPLACE_WELFARE_REVIEW_CONFLICT"))
    if doc.first_aid_applicability == "Applicable":
        if not doc.reviewed_worker_count or not doc.worker_count_as_of or not doc.worker_count_evidence_reference:
            frappe.throw(_("Applicable first-aid review requires a reviewed aggregate count and evidence."))
        if int(doc.workers_per_first_aid_box or 0) <= 0:
            frappe.throw(_("Enter the reviewed first-aid worker-to-box ratio."))
    if doc.child_room_applicability == "Applicable":
        if not doc.reviewed_women_worker_count or not doc.women_count_as_of or not doc.women_count_evidence_reference:
            frappe.throw(_("Child-room applicability requires reviewed aggregate workforce evidence."))


def before_submit_workplace_welfare_review(doc, method=None):
    _assert_maker_checker(doc)
    validate_workplace_welfare_review(doc)
    doc.reviewed_by = frappe.session.user
    doc.reviewed_at = now_datetime()


def before_update_after_submit_workplace_welfare_review(doc, method=None):
    _freeze_submitted_fields(doc, WELFARE_FROZEN_FIELDS)


def before_cancel_workplace_welfare_review(doc, method=None):
    if frappe.session.user != "Administrator":
        frappe.throw(_("Approved welfare evidence is immutable; create a new review."),
                     frappe.PermissionError)


def validate_maternity_attendance(doc, method=None):
    if doc.status in WORK_STATUSES and flt(doc.working_hours) > 0:
        validate_maternity_protected_work(doc, method)


def validate_maternity_overtime(doc, method=None):
    validate_maternity_protected_work(doc, method)


def validate_maternity_field_duty(doc, method=None):
    validate_maternity_protected_work(doc, method)


def validate_maternity_salary_slip(doc, method=None):
    if not doc.employee or not doc.start_date or not doc.end_date:
        return
    codes = maternity_payroll_review_codes(doc.employee, doc.start_date, doc.end_date)
    if codes:
        code = codes[0]
        frappe.throw(_("Maternity payment needs restricted HR/legal review: {0}").format(code), title=_(code))


def validate_maternity_employee_separation(doc, method=None):
    if not _maternity_schema_installed() or not doc.employee or not doc.company or not doc.relieving_date:
        return
    cases = frappe.get_all(
        MATERNITY_REVIEW,
        filters={"employee": doc.employee, "company": doc.company, "docstatus": 1},
        pluck="name",
    )
    for name in cases:
        review = frappe.get_doc(MATERNITY_REVIEW, name)
        anchor = review.actual_delivery_date or review.expected_delivery_date
        if not anchor:
            continue
        rule = frappe.get_doc(MATERNITY_RULE, review.rule_set)
        day = getdate(doc.relieving_date)
        start = getdate(anchor) - relativedelta(months=int(rule.separation_protection_before_months or 0))
        end = getdate(anchor) + timedelta(days=int(rule.separation_protection_after_days or 0))
        if start <= day <= end:
            decisions = frappe.get_all(
                MATERNITY_SEPARATION_REVIEW,
                filters={"employee_separation": doc.name, "maternity_review": name, "docstatus": 1},
                pluck="decision",
            )
            if decisions != ["Proceed After Legal Review"]:
                frappe.throw(_("A protected maternity period requires independent legal separation review."),
                             title=_("MATERNITY_SEPARATION_LEGAL_REVIEW_REQUIRED"))


def validate_maternity_full_and_final(doc, method=None):
    if not _maternity_schema_installed():
        return
    separation = frappe.db.get_value(
        "Employee Separation",
        {"employee": doc.employee, "docstatus": 1},
        ["name", "relieving_date"],
        as_dict=True,
        order_by="relieving_date desc",
    )
    if separation and _separation_maternity_review(separation.name):
        frappe.throw(_("A protected maternity period requires independent legal settlement review."),
                     title=_("MATERNITY_SEPARATION_LEGAL_REVIEW_REQUIRED"))


def before_cancel_maternity_separation_review(doc, method=None):
    if frappe.session.user != "Administrator":
        frappe.throw(_("Submitted legal separation reviews are immutable."), frappe.PermissionError)
