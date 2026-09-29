"""Native Employee Separation and Full & Final controls; no parallel ledger."""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate, today

SEPARATION_TYPE_FIELD = "custom_tradex_separation_type"
STATUTORY_STATUS_FIELD = "custom_tradex_statutory_review_status"
STATUTORY_REVIEWER_FIELD = "custom_tradex_statutory_reviewed_by"
STATUTORY_REVIEWED_AT_FIELD = "custom_tradex_statutory_reviewed_at"
STATUTORY_NOTES_FIELD = "custom_tradex_statutory_review_notes"
FNF_APPROVED_STATE = "Tradexcel F&F Approved"


def classify_evidence_date(device_time, received_at, relieving_date) -> str:
    """Captured event time, not later server receipt, determines history date."""
    if not device_time:
        return "CAPTURE_TIME_MISSING"
    if not relieving_date:
        return "RELIEVING_DATE_MISSING"
    return "PRE_EXIT_HISTORY" if getdate(device_time) <= getdate(relieving_date) else "POST_EXIT_REVIEW"


def validate_no_payable_work_after_relieving_date(doc, method=None):
    employee = getattr(doc, "employee", None)
    if not employee:
        return
    relieving = frappe.db.get_value("Employee", employee, "relieving_date")
    if not relieving:
        return
    dates = []
    if doc.doctype == "Attendance":
        dates = [getattr(doc, "attendance_date", None)]
    elif doc.doctype == "Attendance Request":
        dates = [getattr(doc, "from_date", None), getattr(doc, "to_date", None)]
    elif doc.doctype == "Overtime Slip":
        dates = [getattr(row, "date", None) for row in (getattr(doc, "overtime_details", None) or [])]
    elif doc.doctype == "Tradexcel Field Duty" and getattr(doc, "status", None) == "Approved":
        dates = [getattr(doc, "duty_date", None)]
    if any(value and getdate(value) > getdate(relieving) for value in dates):
        frappe.throw(
            _("Approved attendance or payable work cannot be dated after the employee's relieving date. Review the relieving date or separation first."),
            title=_("Work after relieving date"),
        )


def validate_employee_separation(doc, method=None):
    employee = frappe.get_doc("Employee", doc.employee)
    from tradex_hr.tradexcel_hr.company_context import assert_company_access
    assert_company_access(employee.company, require_explicit_scope=True)
    if doc.company and doc.company != employee.company:
        frappe.throw(_("Employee Separation company must match the employee's company."))
    doc.company = employee.company
    if not employee.relieving_date:
        frappe.throw(_("Set Employee.relieving_date before starting Employee Separation."))
    if employee.date_of_joining and getdate(employee.relieving_date) < getdate(employee.date_of_joining):
        frappe.throw(_("Relieving date cannot be before the date of joining."))
    if not doc.get(SEPARATION_TYPE_FIELD):
        frappe.throw(_("Select a structured separation type."))
    if not doc.get("employee_separation_template"):
        template = frappe.db.get_value("Employee Separation Template", {"title": "Tradexcel Standard Exit Checklist"}, "name")
        if template:
            doc.employee_separation_template = template


def _authorized_employee(employee_name):
    employee = frappe.get_doc("Employee", employee_name)
    from tradex_hr.tradexcel_hr.company_context import assert_company_access
    assert_company_access(employee.company, require_explicit_scope=True)
    if not frappe.has_permission("Employee", "read", employee):
        frappe.throw(_("You do not have permission to inspect this employee."), frappe.PermissionError)
    return employee


def _latest_separation(employee_name):
    rows = frappe.get_all(
        "Employee Separation", filters={"employee": employee_name, "docstatus": ["!=", 2]},
        fields=["name", "docstatus", "project", SEPARATION_TYPE_FIELD, STATUTORY_STATUS_FIELD],
        order_by="creation desc", limit=1,
    )
    return rows[0] if rows else None


@frappe.whitelist()
def inspect_employee_exit_readiness(employee_name: str) -> dict:
    """Return operational blockers and informational native-record findings."""
    employee = _authorized_employee(employee_name)
    relieving = getdate(employee.relieving_date) if employee.relieving_date else None
    separation = _latest_separation(employee.name)
    blockers, findings = [], []
    if not relieving:
        blockers.append({"code": "RELIEVING_DATE_MISSING", "message": _("Set the employee's last working day.")})
    if not separation or int(separation.docstatus or 0) != 1:
        blockers.append({"code": "SEPARATION_NOT_APPROVED", "message": _("Submit the native Employee Separation first.")})
    elif not separation.get(SEPARATION_TYPE_FIELD):
        blockers.append({"code": "SEPARATION_TYPE_REQUIRED", "message": _("Choose the separation type.")})
    if not relieving:
        return {"status": "BLOCKED", "employee": employee.name, "blockers": blockers, "findings": findings,
                "ready_for_access_finalization": False, "settlement_is_separate": True}

    attendance = frappe.get_all("Attendance", filters={"employee": employee.name, "docstatus": 1,
        "attendance_date": [">", relieving]}, fields=["name"], limit=20)
    if attendance:
        blockers.append({"code": "ATTENDANCE_AFTER_RELIEVING_DATE", "count": len(attendance),
            "message": _("Attendance dated after the last working day needs HR review.")})
    if frappe.db.exists("DocType", "Tradexcel Field Duty"):
        field_duty = frappe.get_all("Tradexcel Field Duty", filters={"employee": employee.name,
            "docstatus": ["<", 2], "status": ["in", ["Draft", "Submitted", "Approved", "In Progress", "Completed"]],
            "duty_date": [">", relieving]}, fields=["name"], limit=20)
        if field_duty:
            blockers.append({"code": "FIELD_DUTY_AFTER_RELIEVING_DATE", "count": len(field_duty),
                "message": _("Field duty dated after the last working day needs HR review.")})
    final_period_start = relieving.replace(day=1)
    requests = frappe.get_all("Attendance Request", filters={"employee": employee.name,
        "docstatus": 0, "from_date": ["<=", relieving], "to_date": [">=", final_period_start]},
        fields=["name"], limit=20)
    if requests:
        blockers.append({"code": "ATTENDANCE_REQUEST_PENDING", "count": len(requests),
            "message": _("Attendance requests extend beyond the last working day.")})
    events = frappe.get_all("Tradex Mobile Event", filters={"employee": employee.name, "status": "Pending"},
        fields=["device_time", "received_at"], limit=100)
    relevant = [row for row in events if row.device_time
        and final_period_start <= getdate(row.device_time) <= relieving]
    if relevant:
        blockers.append({"code": "MOBILE_EVIDENCE_PENDING", "count": len(relevant),
            "message": _("Captured attendance evidence for the final payroll period still needs review.")})
    post_exit_checkins = frappe.get_all("Employee Checkin", filters={"employee": employee.name,
        "time": [">", f"{relieving} 23:59:59"]}, fields=["name"], limit=20)
    if post_exit_checkins:
        blockers.append({"code": "POST_EXIT_EVIDENCE_REVIEW", "count": len(post_exit_checkins),
            "message": _("Attendance evidence captured after the last working day needs review.")})
    assignments = frappe.get_all("Shift Assignment", filters={"employee": employee.name,
        "docstatus": 1, "end_date": [">", relieving]}, fields=["name"], limit=50)
    if assignments:
        blockers.append({"code": "FUTURE_SHIFT_ASSIGNMENT", "count": len(assignments),
            "message": _("A shift assignment extends beyond the last working day. Shorten or cancel the native assignment.")})
    overtime_rows = frappe.get_all("Overtime Details", filters={"parenttype": "Overtime Slip",
        "date": [">", relieving]}, fields=["parent"], limit=100)
    overtime_names = sorted({row.parent for row in overtime_rows})
    overtime = frappe.get_all("Overtime Slip", filters={"name": ["in", overtime_names],
        "employee": employee.name, "docstatus": ["<", 2]}, fields=["name"], limit=20) if overtime_names else []
    if overtime:
        blockers.append({"code": "OVERTIME_REVIEW_PENDING", "count": len(overtime),
            "message": _("Draft overtime after the last working day needs review.")})
    if separation and separation.project:
        pending_tasks = frappe.db.count("Task", {"project": separation.project, "status": ["!=", "Completed"]})
        if pending_tasks:
            findings.append({"code": "SEPARATION_TASKS_PENDING", "count": pending_tasks,
                "message": _("Some separation checklist tasks remain open.")})
    return {"status": "BLOCKED" if blockers else "READY", "employee": employee.name,
        "company": employee.company, "relieving_date": relieving,
        "separation": separation.name if separation else None, "blockers": blockers,
        "findings": findings, "ready_for_access_finalization": not blockers,
        "settlement_is_separate": True}


def _dedicated_employee_user(employee):
    user_name = employee.user_id
    if not user_name:
        return None, None
    if user_name == "Administrator":
        return None, "ACCESS_SHARED_USER_REVIEW"
    other = frappe.get_all("Employee", filters={"user_id": user_name, "status": "Active",
        "name": ["!=", employee.name]}, fields=["name"], limit=1)
    if other:
        return None, "ACCESS_SHARED_USER_REVIEW"
    user = frappe.get_doc("User", user_name)
    roles = {row.role for row in user.get("roles") or []}
    if user.user_type != "System User" or roles - {"Employee", "Tradexcel Employee/Worker"}:
        return None, "ACCESS_SHARED_USER_REVIEW"
    return user, None


@frappe.whitelist(methods=["POST"])
def finalize_employee_exit_access(employee_name: str) -> dict:
    """Disable dedicated app/biometric access and mark employment Left, never settle money."""
    employee = _authorized_employee(employee_name)
    roles = set(frappe.get_roles())
    if not roles.intersection({"Tradexcel HR Manager", "Tradexcel Owner/Director"}) and frappe.session.user != "Administrator":
        frappe.throw(_("HR Manager authorization is required to finalize exit access."), frappe.PermissionError)
    readiness = inspect_employee_exit_readiness(employee.name)
    if not readiness["ready_for_access_finalization"]:
        frappe.throw(_("Resolve the operational exit blockers before closing access."))
    if not employee.relieving_date or getdate(employee.relieving_date) > getdate(today()):
        frappe.throw(_("Exit access can only be finalized on or after the relieving date."))
    user, review = _dedicated_employee_user(employee)
    if review:
        frappe.throw(_("The linked User is shared or privileged and needs IT review before disabling."), title=_(review))
    if employee.status not in ("Active", "Left"):
        frappe.throw(_("Only an Active or already Left employee can have exit access finalized."))
    if employee.status != "Left":
        employee.status = "Left"
        employee.save()
    if user and user.enabled:
        user.reload()
        user.enabled = 0
        user.save(ignore_permissions=True)
    mappings = frappe.get_all("Tradexcel Employee Biometric", filters={"employee": employee.name,
        "enabled": 1}, pluck="name")
    for name in mappings:
        frappe.db.set_value("Tradexcel Employee Biometric", name,
            {"enabled": 0, "enrollment_status": "Disabled"}, update_modified=False)
    return {"status": "EXIT_ACCESS_FINALIZED", "employee": employee.name,
        "user_disabled": bool(user and not user.enabled), "biometric_mappings_disabled": len(mappings),
        "financial_settlement_pending_allowed": True}


@frappe.whitelist()
def review_separation_statutory_status(separation_name, status, notes, rule_set=None, classification=None):
    """Compatibility endpoint delegates to the versioned legal review service."""
    from tradex_hr.tradexcel_hr.statutory_exit import review_separation_statutory_status as review
    return review(separation_name, status, notes, rule_set, classification)

def validate_full_and_final_before_submit(doc, method=None):
    from tradex_hr.tradexcel_hr.company_context import assert_company_access
    assert_company_access(doc.company, require_explicit_scope=True)
    if doc.workflow_state != FNF_APPROVED_STATE:
        frappe.throw(_("Full & Final must be approved through the Finance workflow before submission."))
    if doc.owner == frappe.session.user and frappe.session.user != "Administrator":
        frappe.throw(_("The preparer cannot approve their own Full & Final Statement."))
    if "Tradexcel Finance/Accounts Officer" not in frappe.get_roles() and frappe.session.user != "Administrator":
        frappe.throw(_("Finance authorization is required to submit Full & Final."), frappe.PermissionError)
    if not frappe.has_permission("Full and Final Statement", "submit", doc):
        frappe.throw(_("You do not have permission to submit this Full & Final Statement."), frappe.PermissionError)
    separation = _latest_separation(doc.employee)
    if not separation or int(separation.docstatus or 0) != 1:
        frappe.throw(_("Submit the native Employee Separation before Full & Final."))
    from tradex_hr.tradexcel_hr.statutory_exit import inspect_statutory_exit_readiness
    statutory = inspect_statutory_exit_readiness(separation.name)
    if statutory.get("status") not in {"READY_FOR_STATUTORY_REVIEW", "NOT_APPLICABLE"}:
        code = next((row.get("code") for row in statutory.get("findings", [])),
                    "LEGAL_CLASSIFICATION_REVIEW_REQUIRED")
        frappe.throw(_("Complete statutory review before settlement: {0}").format(code), title=_(code))
    _validate_asset_recovery_inputs(doc)


def _validate_asset_recovery_inputs(doc):
    """Require a reviewed positive amount and usable same-company account."""
    for row in doc.get("assets_allocated", []):
        if row.action != "Recover Cost":
            continue
        if frappe.utils.flt(row.cost) <= 0 or not row.account:
            frappe.throw(
                _("Enter a positive approved recovery cost and account for asset {0}.").format(row.asset_name),
                title=_("Asset recovery needs review"),
            )
        account = frappe.db.get_value(
            "Account", row.account, ["company", "is_group", "disabled"], as_dict=True
        )
        if (not account or account.company != doc.company or account.is_group or account.disabled):
            frappe.throw(
                _("Choose an enabled posting account belonging to company {0} for asset {1}.").format(
                    doc.company, row.asset_name
                ),
                title=_("Asset recovery account invalid"),
            )


def _native_settlement_pending_count(payables, receivables, assets) -> int:
    """Count native rows that HRMS itself will not accept at F&F submission."""
    pending = sum(row.status != "Settled" for row in (*payables, *receivables))
    for row in assets:
        if row.action == "Return" and row.status == "Owned":
            pending += 1
        elif row.action == "Recover Cost" and (frappe.utils.flt(row.cost) <= 0 or not row.account):
            pending += 1
        elif row.action not in {"Return", "Recover Cost"}:
            pending += 1
    return pending


@frappe.whitelist()
def inspect_full_and_final_readiness(employee_name: str) -> dict:
    """Summarize native settlement sources without calculating or duplicating money."""
    employee = _authorized_employee(employee_name)
    if not employee.relieving_date:
        return {"status": "BLOCKED", "employee": employee.name, "findings": [{"code": "RELIEVING_DATE_MISSING"}]}
    separation = _latest_separation(employee.name)
    findings = []
    statutory = None
    if separation:
        from tradex_hr.tradexcel_hr.statutory_exit import inspect_statutory_exit_readiness
        statutory = inspect_statutory_exit_readiness(separation.name)
        findings.extend(statutory.get("findings", []))
        if separation.get(SEPARATION_TYPE_FIELD) == "Death":
            from tradex_hr.tradexcel_hr.statutory_benefits import inspect_statutory_benefit_readiness
            benefit_readiness = inspect_statutory_benefit_readiness(
                employee.name, employee.relieving_date, employee.relieving_date
            )
            if any(
                item.get("benefit_type") == "Group Insurance" and item.get("status") == "READY"
                for item in benefit_readiness.get("benefits", [])
            ):
                findings.append({"code": "GROUP_INSURANCE_CLAIM_REQUIRED"})
    else:
        findings.append({"code": "LEGAL_CLASSIFICATION_REVIEW_REQUIRED"})
    slips = frappe.get_all("Salary Slip", filters={"employee": employee.name,
        "end_date": ["<=", employee.relieving_date], "docstatus": ["!=", 2]},
        fields=["name", "docstatus", "status", "end_date"], order_by="end_date desc", limit=10)
    final_slips = [row for row in slips if int(row.docstatus) == 1]
    if not final_slips:
        findings.append({"code": "FINAL_PAYROLL_PENDING"})
    fnf = frappe.get_all("Full and Final Statement", filters={"employee": employee.name,
        "docstatus": ["!=", 2]}, fields=["name", "docstatus", "status"], order_by="creation desc", limit=1)
    preview = frappe.get_doc({"doctype": "Full and Final Statement", "employee": employee.name,
        "company": employee.company, "relieving_date": employee.relieving_date,
        "payables": [], "receivables": [], "assets_allocated": []})
    preview.get_outstanding_statements()
    native_sources = {
        "payables": [{"component": row.component, "status": row.status} for row in preview.payables],
        "receivables": [{"component": row.component, "status": row.status} for row in preview.receivables],
        "assets": [{"asset_name": row.asset_name, "action": row.action, "status": row.status}
                    for row in preview.assets_allocated],
    }
    pending_native_items = _native_settlement_pending_count(
        preview.payables, preview.receivables, preview.assets_allocated
    )
    if pending_native_items:
        findings.append({
            "code": "NATIVE_SETTLEMENT_ITEMS_PENDING",
            "count": pending_native_items,
            "message": _("Resolve the unsettled payables, receivables, and asset actions in the native Full & Final Statement."),
        })
    adjustments = []
    for dt in ("Payroll Correction", "Arrear"):
        for adjustment in frappe.get_all(dt, filters={"employee": employee.name, "docstatus": 1},
                fields=["name"], limit=20):
            additional_salaries = frappe.get_all("Additional Salary", filters={
                "ref_doctype": dt, "ref_docname": adjustment.name, "docstatus": 1,
            }, pluck="name")
            if not additional_salaries:
                adjustments.append(adjustment.name)
                continue
            consumed = frappe.get_all("Salary Detail", filters={
                "additional_salary": ["in", additional_salaries],
                "parenttype": "Salary Slip", "parentfield": "earnings",
                "docstatus": 1,
            }, pluck="name", limit=1)
            if not consumed:
                adjustments.append(adjustment.name)
    if adjustments:
        findings.append({"code": "PAYROLL_ADJUSTMENT_PENDING", "count": len(adjustments)})
    payment_status = _full_and_final_payment_status(fnf)
    return {"status": "REVIEW_REQUIRED" if findings else "READY", "employee": employee.name,
        "company": employee.company, "relieving_date": employee.relieving_date,
        "final_salary_slips": final_slips, "full_and_final_statements": fnf,
        "native_outstanding_sources": native_sources,
        "pending_adjustments": len(adjustments), "findings": findings,
        "statutory_review": statutory,
        "payment_status": payment_status["status"],
        "payment_journal_entries": payment_status["journal_entries"],
        "native_settlement_hub": "Full and Final Statement"}


def _account_is_valid_for_company(account_name, company):
    if not account_name or not frappe.db.exists("Account", account_name):
        return False
    account = frappe.get_cached_doc("Account", account_name)
    return account.company == company and not account.disabled and not account.is_group


def _native_fnf_settlement_rows(statement):
    """Describe non-balancing rows native HRMS derives from this F&F."""
    from collections import Counter
    precision = int(frappe.get_precision("Journal Entry Account", "debit_in_account_currency") or 2)
    expected = Counter()

    def add(account, side, amount):
        amount = frappe.utils.flt(amount, precision)
        if amount > 0:
            expected[(account, side, amount)] += 1

    for row in statement.payables:
        if frappe.utils.flt(row.amount) > 0 and not row.paid_via_salary_slip:
            add(row.account, "debit", row.amount)
    for row in statement.receivables:
        if frappe.utils.flt(row.amount) > 0:
            add(row.account, "credit", row.amount)
    for row in statement.assets_allocated:
        if row.action == "Recover Cost":
            add(row.account, "credit", row.cost)
    return expected


def _validate_native_fnf_journal_entry(statement, journal):
    """Validate a linked JE against native F&F rows; do not recompute settlement amounts."""
    from collections import Counter
    if (journal.company != statement.company or journal.docstatus == 2
            or journal.voucher_type not in ("Bank Entry", "Cash Entry")):
        frappe.throw(_("FNF_PAYMENT_ENTRY_INVALID: company, state, or voucher type is invalid."))
    refs = [row for row in journal.accounts if row.reference_type == "Full and Final Statement"]
    if len(refs) != 1 or refs[0].reference_name != statement.name:
        frappe.throw(_("FNF_PAYMENT_ENTRY_INVALID: settlement reference is missing or ambiguous."))
    ref_row = refs[0]
    if not _account_is_valid_for_company(ref_row.account, statement.company):
        if journal.docstatus == 0 and not ref_row.account:
            mode = None  # Native HRMS creates an unselected draft before Finance chooses the account.
        else:
            frappe.throw(_("FNF_PAYMENT_ENTRY_INVALID: balancing account is missing or invalid."))
    else:
        mode = frappe.db.get_value("Account", ref_row.account, "account_type")
        if mode not in ("Bank", "Cash"):
            frappe.throw(_("FNF_PAYMENT_ENTRY_INVALID: balancing account must be Bank or Cash."))

    precision = int(frappe.get_precision("Journal Entry Account", "debit_in_account_currency") or 2)
    actual = Counter()
    for row in journal.accounts:
        if not _account_is_valid_for_company(row.account, statement.company):
            frappe.throw(_("FNF_PAYMENT_ENTRY_INVALID: an account is invalid for this company."))
        if row is ref_row:
            continue
        debit = frappe.utils.flt(row.debit_in_account_currency, precision)
        credit = frappe.utils.flt(row.credit_in_account_currency, precision)
        if debit > 0 and credit == 0:
            actual[(row.account, "debit", debit)] += 1
        elif credit > 0 and debit == 0:
            actual[(row.account, "credit", credit)] += 1
        else:
            frappe.throw(_("FNF_PAYMENT_ENTRY_INVALID: settlement row debit/credit shape is invalid."))
    if actual != _native_fnf_settlement_rows(statement):
        frappe.throw(_("FNF_PAYMENT_ENTRY_INVALID: Journal Entry rows do not match native Full & Final rows."))
    if journal.docstatus == 1:
        precision = int(frappe.get_precision("Journal Entry", "total_debit") or 2)
        if abs(frappe.utils.flt(journal.total_debit) - frappe.utils.flt(journal.total_credit)) >= 10 ** (-precision):
            frappe.throw(_("FNF_PAYMENT_ENTRY_INVALID: submitted Journal Entry is not balanced."))
    return mode


def _full_and_final_payment_status(statements):
    """Classify validated native F&F JEs and Bank Transaction matches."""
    if not statements:
        return {"status": "FULL_AND_FINAL_NOT_PREPARED", "journal_entries": []}
    statement_by_name = {statement.name: statement for statement in statements}
    parents = []
    for statement in statements:
        parents.extend(frappe.get_all("Journal Entry Account", filters={
            "reference_type": "Full and Final Statement", "reference_name": statement.name,
        }, pluck="parent"))
    names = sorted(set(parents))
    entries = frappe.get_all("Journal Entry", filters={"name": ["in", names], "docstatus": ["!=", 2]},
        fields=["name", "docstatus", "voucher_type", "clearance_date"], order_by="creation desc") if names else []
    if len(entries) > 1:
        return {"status": "PAYMENT_ENTRY_AMBIGUOUS", "journal_entries": entries}
    if not entries:
        return {"status": "FULL_AND_FINAL_NOT_PREPARED", "journal_entries": []}
    entry = entries[0]
    journal = frappe.get_doc("Journal Entry", entry.name)
    target = next((row.reference_name for row in journal.accounts
                   if row.reference_type == "Full and Final Statement"), None)
    statement = statement_by_name.get(target)
    if not statement:
        return {"status": "PAYMENT_ENTRY_INVALID", "journal_entries": entries}
    try:
        mode = _validate_native_fnf_journal_entry(statement, journal)
    except frappe.ValidationError:
        return {"status": "PAYMENT_ENTRY_INVALID", "journal_entries": entries}
    if entry.docstatus == 0:
        return {"status": "PAYMENT_ENTRY_DRAFT", "journal_entries": entries, "settlement_mode": mode}
    if entry.docstatus != 1:
        return {"status": "PAYMENT_ENTRY_INVALID", "journal_entries": entries}
    if mode == "Cash":
        return {"status": "CASH_SETTLEMENT_ACCOUNTING_POSTED", "journal_entries": entries, "settlement_mode": mode}
    if mode != "Bank":
        return {"status": "FNF_PAYMENT_ACCOUNT_REVIEW_REQUIRED", "journal_entries": entries}
    from tradex_hr.tradexcel_hr.payment_readiness import _bank_reconciled
    reconciled, transactions = _bank_reconciled(journal)
    return {"status": "BANK_RECONCILED" if reconciled else "AWAITING_BANK_RECONCILIATION",
        "journal_entries": entries, "bank_transactions": transactions,
        "clearance_date": entry.clearance_date, "settlement_mode": mode}

class FullAndFinalTradexcelMixin:
    """Add scope and retry safety around native Full & Final Journal Entry creation."""
    @frappe.whitelist()
    def create_journal_entry(self):
        self.check_permission("write")
        from tradex_hr.tradexcel_hr.company_context import assert_company_access
        assert_company_access(self.company, require_explicit_scope=True)
        if self.docstatus != 1 or self.workflow_state != FNF_APPROVED_STATE:
            frappe.throw(_("Finance can prepare settlement accounting only after the approved Full & Final is submitted."))
        if "Tradexcel Finance/Accounts Officer" not in frappe.get_roles() and frappe.session.user != "Administrator":
            frappe.throw(_("Finance authorization is required to prepare settlement accounting."), frappe.PermissionError)
        references = frappe.get_all("Journal Entry Account", filters={
            "reference_type": self.doctype, "reference_name": self.name}, pluck="parent")
        active = frappe.get_all("Journal Entry", filters={"name": ["in", references],
            "docstatus": ["!=", 2]}, fields=["name", "docstatus"], limit=3) if references else []
        if len(active) > 1:
            frappe.throw(_("More than one active settlement Journal Entry exists. Finance review is required."))
        if active:
            journal = frappe.get_doc("Journal Entry", active[0].name)
            _validate_native_fnf_journal_entry(self, journal)
            return journal
        return super().create_journal_entry()
