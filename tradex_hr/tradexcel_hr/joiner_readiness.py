"""Joiner checks around native Employee, recruitment, and payroll records."""
from __future__ import annotations

from datetime import datetime

import frappe
from frappe import _
from frappe.utils import get_first_day, get_last_day, getdate

from tradex_hr.tradexcel_hr.company_context import assert_company_access
from tradex_hr.tradexcel_hr.daily_wage_input import inspect_daily_wage_structure
from tradex_hr.tradexcel_hr.native_payroll import inspect_native_payroll_readiness
from tradex_hr.tradexcel_hr.pay_basis import DAILY, MONTHLY, resolve_daily_rate, resolve_pay_basis

MAKER_ROLES = {"Tradexcel HR Manager", "Tradexcel Payroll Manager"}
READ_ROLES = MAKER_ROLES | {"Tradexcel Payroll Approver", "Tradexcel Owner/Director"}
PRIVILEGED_ROLES = {"System Manager"}


def _privileged(user: str) -> bool:
    return user == "Administrator" or bool(set(frappe.get_roles(user)) & PRIVILEGED_ROLES)


def _company_scope(user: str) -> list[str]:
    return frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": "Company"},
        pluck="for_value",
    )


def _sql_company_clause(user: str, column: str | tuple[str, str]) -> str:
    if _privileged(user):
        return ""
    companies = sorted(set(_company_scope(user)))
    roles = set(frappe.get_roles(user))
    if not companies:
        return "1=0" if roles & READ_ROLES else ""
    values = ", ".join(frappe.db.escape(company) for company in companies)
    if column == "job_opening_company":
        return (
            "`tabJob Applicant`.job_title in (select name from `tabJob Opening` "
            f"where company in ({values}))"
        )
    if column == "interview_job_opening_company":
        return (
            "`tabInterview`.job_opening = (select job_title from `tabJob Applicant` "
            "where name = `tabInterview`.job_applicant) and "
            "`tabInterview`.job_opening in (select name from `tabJob Opening` "
            f"where company in ({values}))"
        )
    if column == "feedback_job_opening_company":
        return (
            "`tabInterview Feedback`.job_applicant = (select job_applicant from `tabInterview` "
            "where name = `tabInterview Feedback`.interview) and "
            "`tabInterview Feedback`.job_applicant in (select name from `tabJob Applicant` "
            "where job_title in (select name from `tabJob Opening` "
            f"where company in ({values})))"
        )
    return f"`tab{column[0]}`.`{column[1]}` in ({values})"


def job_opening_query_conditions(user: str | None = None) -> str:
    return _sql_company_clause(user or frappe.session.user, ("Job Opening", "company"))


def job_offer_query_conditions(user: str | None = None) -> str:
    return _sql_company_clause(user or frappe.session.user, ("Job Offer", "company"))


def employee_onboarding_query_conditions(user: str | None = None) -> str:
    return _sql_company_clause(user or frappe.session.user, ("Employee Onboarding", "company"))


def job_applicant_query_conditions(user: str | None = None) -> str:
    return _sql_company_clause(user or frappe.session.user, "job_opening_company")


def interview_query_conditions(user: str | None = None) -> str:
    return _sql_company_clause(user or frappe.session.user, "interview_job_opening_company")


def interview_feedback_query_conditions(user: str | None = None) -> str:
    return _sql_company_clause(user or frappe.session.user, "feedback_job_opening_company")


def _applicant_company(applicant: str | None) -> str | None:
    opening = frappe.db.get_value("Job Applicant", applicant, "job_title") if applicant else None
    return frappe.db.get_value("Job Opening", opening, "company") if opening else None


def _interview_company(interview: str | None) -> str | None:
    if not interview:
        return None
    opening, applicant = frappe.db.get_value(
        "Interview", interview, ["job_opening", "job_applicant"]
    ) or (None, None)
    applicant_opening = frappe.db.get_value("Job Applicant", applicant, "job_title") if applicant else None
    if opening and applicant_opening and opening != applicant_opening:
        return None
    return frappe.db.get_value("Job Opening", opening, "company") if opening else _applicant_company(applicant)


def recruitment_has_permission(doc, ptype: str, user: str | None = None, **_kwargs):
    """Deny cross-company direct document reads while leaving DocPerm grants intact."""
    user = user or frappe.session.user
    if not doc or ptype not in {"read", "select", "report", "export", "print", "email"}:
        return None
    if _privileged(user):
        return None

    if doc.doctype == "Job Applicant":
        opening = doc.get("job_title")
        company = frappe.db.get_value("Job Opening", opening, "company") if opening else None
        # Applicants without a company-owned Job Opening cannot safely be
        # exposed to company-scoped recruitment users.
        if set(frappe.get_roles(user)) & READ_ROLES and not company:
            return False
    elif doc.doctype == "Interview":
        opening = doc.get("job_opening")
        applicant_opening = frappe.db.get_value("Job Applicant", doc.get("job_applicant"), "job_title") if doc.get("job_applicant") else None
        if opening and applicant_opening and opening != applicant_opening:
            return False
        opening = opening or applicant_opening
        company = frappe.db.get_value("Job Opening", opening, "company") if opening else _applicant_company(doc.get("job_applicant"))
    elif doc.doctype == "Interview Feedback":
        interview_applicant = frappe.db.get_value("Interview", doc.get("interview"), "job_applicant") if doc.get("interview") else None
        if interview_applicant and doc.get("job_applicant") and interview_applicant != doc.get("job_applicant"):
            return False
        company = _applicant_company(interview_applicant or doc.get("job_applicant"))
    else:
        company = doc.get("company")

    if set(frappe.get_roles(user)) & READ_ROLES:
        if not company or company not in _company_scope(user):
            return False
    return None


def _authorize_company(company: str) -> None:
    if not company:
        frappe.throw(_("Select the employee's company first."))
    assert_company_access(company, require_explicit_scope=True)


def validate_recruitment_company_scope(doc, _method=None) -> None:
    """Keep Tradexcel recruitment writes inside the user's explicit Company scope."""
    roles = set(frappe.get_roles())
    if _privileged(frappe.session.user) or not roles.intersection(READ_ROLES):
        return

    if doc.doctype == "Job Applicant":
        if not doc.job_title:
            frappe.throw(
                _("Company-scoped recruitment users must link Job Applicants to a company Job Opening."),
                frappe.PermissionError,
            )
        company = frappe.db.get_value("Job Opening", doc.job_title, "company")
    elif doc.doctype == "Interview":
        applicant_opening = frappe.db.get_value("Job Applicant", doc.job_applicant, "job_title") if doc.job_applicant else None
        if doc.job_opening and applicant_opening and doc.job_opening != applicant_opening:
            frappe.throw(_("Interview Job Opening must match the applicant's opening."), frappe.PermissionError)
        opening = doc.job_opening or applicant_opening
        company = frappe.db.get_value("Job Opening", opening, "company") if opening else None
    elif doc.doctype == "Interview Feedback":
        interview_applicant = frappe.db.get_value("Interview", doc.interview, "job_applicant") if doc.interview else None
        if interview_applicant and doc.job_applicant and interview_applicant != doc.job_applicant:
            frappe.throw(_("Interview Feedback applicant must match its Interview."), frappe.PermissionError)
        company = _applicant_company(interview_applicant or doc.job_applicant)
    else:
        company = doc.company
    if not company:
        frappe.throw(_("The recruitment record must resolve to a company Job Opening."), frappe.PermissionError)
    _authorize_company(company)


def validate_employee_onboarding(doc, _method=None) -> None:
    """Enforce the accepted-offer identity links that native UI filters cannot."""
    _authorize_company(doc.company)
    if not doc.job_applicant or not doc.job_offer:
        frappe.throw(_("Recruitment onboarding requires an Applicant and Job Offer."))

    offer = frappe.get_doc("Job Offer", doc.job_offer)
    if offer.docstatus != 1 or offer.status != "Accepted":
        frappe.throw(_("Employee Onboarding requires a submitted, accepted Job Offer."))
    if offer.job_applicant != doc.job_applicant:
        frappe.throw(_("The Job Offer and Employee Onboarding must reference the same applicant."))
    if offer.company != doc.company:
        frappe.throw(_("The Job Offer and Employee Onboarding must belong to the same company."))

    applicant = frappe.get_doc("Job Applicant", doc.job_applicant)
    if not applicant.job_title:
        frappe.throw(_("Recruitment onboarding requires a Job Applicant linked to a Job Opening."))
    opening_company = frappe.db.get_value("Job Opening", applicant.job_title, "company")
    if not opening_company or opening_company != doc.company:
        frappe.throw(_("The applicant's Job Opening must belong to the onboarding company."))
    if doc.designation and offer.designation and doc.designation != offer.designation:
        frappe.throw(_("The onboarding designation must match the accepted Job Offer."))

    existing_employee = frappe.db.get_value("Employee", {"job_applicant": applicant.name}, "name")
    if existing_employee and doc.employee != existing_employee:
        frappe.throw(_("This applicant already has Employee {0}.").format(frappe.bold(existing_employee)))


def validate_unique_employee_job_applicant(doc, _method=None) -> None:
    """Keep one Employee identity per recruited applicant, including API inserts."""
    if not doc.job_applicant:
        return
    existing = frappe.db.get_value("Employee", {"job_applicant": doc.job_applicant}, "name")
    if existing and existing != doc.name:
        frappe.throw(
            _("Job Applicant {0} is already linked to Employee {1}.").format(
                frappe.bold(doc.job_applicant), frappe.bold(existing)
            )
        )


def _finding(code: str, message: str, severity: str = "blocker") -> dict:
    return {"code": code, "message": _(message), "severity": severity}


@frappe.whitelist()
def inspect_joiner_readiness(employee_name: str) -> dict:
    """Summarize native employment/payroll/attendance/payment setup, without writes."""
    company = frappe.db.get_value("Employee", employee_name, "company")
    if not company:
        frappe.throw(_("Employee not found."))
    _authorize_company(company)
    employee = frappe.get_doc("Employee", employee_name)
    employee.check_permission("read")

    sections = {key: {"status": "READY", "findings": []}
                for key in ("employment", "payroll", "attendance", "payment", "access")}

    def add(section: str, code: str, message: str, severity: str = "blocker"):
        sections[section]["findings"].append(_finding(code, message, severity))
        if severity == "blocker":
            sections[section]["status"] = "NEEDS_ATTENTION"

    if not employee.date_of_joining:
        add("employment", "JOINING_DATE_REQUIRED", "Set the Employee joining date.")
    if employee.status != "Active":
        add("employment", "EMPLOYMENT_STATUS_REVIEW", "The Employee must be Active for a new joiner.")
    for field, label in (("branch", "Branch"), ("department", "Department"),
                         ("designation", "Designation"), ("employment_type", "Employment Type")):
        if not employee.get(field):
            add("employment", "EMPLOYMENT_DETAIL_REVIEW", f"Review the Employee {label}.", "review")

    if employee.date_of_joining:
        start = get_first_day(employee.date_of_joining)
        end = get_last_day(employee.date_of_joining)
        basis = resolve_pay_basis(employee.name, employee.date_of_joining, end)
        if basis.get("status") not in {MONTHLY, DAILY}:
            add("payroll", "SALARY_ASSIGNMENT_REQUIRED", basis.get("reason") or "A submitted Salary Structure Assignment is required.")
        else:
            structure = frappe.db.get_value(
                "Salary Structure", basis.get("salary_structure"),
                ["company", "currency", "is_active"], as_dict=True,
            )
            if not structure or structure.company != company or structure.is_active != "Yes":
                add("payroll", "SALARY_STRUCTURE_REVIEW_REQUIRED", "The effective Salary Structure is missing, inactive, or belongs to another company.")
            elif basis["status"] == DAILY:
                safe = inspect_daily_wage_structure(employee.name, employee.date_of_joining, end)
                rate = resolve_daily_rate(basis)
                if safe.get("status") != "READY":
                    add("payroll", safe.get("status", "DAILY_WAGE_STRUCTURE_REVIEW"), safe.get("reason") or "Review the Daily Wage Salary Structure.")
                if rate.get("status") != "READY":
                    add("payroll", rate.get("status", "DAILY_WAGE_RATE_REQUIRED"), rate.get("reason") or "A positive daily rate is required.")
        # Managed payroll is company-wide; the native readiness service rejects
        # employee-only populations. Inspect that canonical universe, then show
        # this employee's outcome without returning other employees' findings.
        native = inspect_native_payroll_readiness(company, start, end)
        outcome = next((row for row in native.get("outcomes", []) if row.get("employee") == employee.name), None)
        if not outcome:
            add("payroll", "FIRST_PAYROLL_REVIEW_REQUIRED", "The Employee is not in the native first-payroll population.")
        elif outcome.get("status") != "READY":
            add("payroll", outcome.get("status", "FIRST_PAYROLL_REVIEW_REQUIRED"), outcome.get("reason") or "First-period payroll readiness needs attention.")
        elif native.get("status") != "READY":
            add(
                "payroll",
                "FIRST_PAYROLL_COMPANY_POPULATION_REVIEW",
                "Managed payroll is blocked by other company-wide readiness items.",
            )

        from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee
        holiday_list = get_holiday_list_for_employee(employee.name, raise_exception=False)
        if not holiday_list:
            add("attendance", "HOLIDAY_LIST_REQUIRED", "Assign a Holiday List directly or through the Company.")
        first_work_time = datetime.combine(getdate(employee.date_of_joining), datetime.min.time()).replace(hour=9)
        from hrms.hr.doctype.shift_assignment.shift_assignment import get_employee_shift
        shift = get_employee_shift(employee.name, first_work_time, consider_default_shift=True)
        if not shift:
            add("attendance", "SHIFT_SETUP_REVIEW", "Confirm the employee's shift or flexible attendance arrangement.", "review")
        if not frappe.db.exists("Tradexcel Employee Biometric", {"employee": employee.name, "enabled": 1}):
            add("attendance", "BIOMETRIC_SETUP_REVIEW", "Confirm whether this employee requires biometric enrollment.", "review")

    mode = (employee.salary_mode or "").strip()
    if not mode:
        add("payment", "PAYMENT_MODE_REQUIRED", "Choose Bank, Cash, or Cheque salary mode.")
    elif mode == "Bank":
        if not employee.bank_name:
            add("payment", "BANK_NAME_REQUIRED", "Enter the employee's bank name.")
        if not employee.bank_ac_no:
            add("payment", "BANK_ACCOUNT_REQUIRED", "Enter the employee's bank account number.")
    elif mode == "Cheque":
        add("payment", "PAYMENT_MODE_REVIEW_REQUIRED", "Cheque payment needs confirmation with Finance before managed payroll payment.")
    elif mode != "Cash":
        add("payment", "PAYMENT_MODE_REVIEW_REQUIRED", "Confirm this salary mode with Finance.")

    if not employee.user_id:
        sections["access"]["message"] = _("Application access is not required by default.")
    else:
        user = frappe.db.get_value("User", employee.user_id, ["name", "enabled"], as_dict=True)
        shared = frappe.db.exists("Employee", {"user_id": employee.user_id, "name": ["!=", employee.name]})
        if shared or employee.user_id == "Administrator" or not user:
            add("access", "ACCESS_SHARED_USER_REVIEW", "Review this linked User before granting employee access.")
        elif not user.enabled:
            add("access", "USER_ACCESS_REVIEW", "The linked User is disabled; confirm whether access is required.", "review")

    findings = [item for section in sections.values() for item in section["findings"]]
    return {
        "employee": employee.name,
        "company": company,
        "status": "NEEDS_ATTENTION" if any(f["severity"] == "blocker" for f in findings) else "READY",
        "hire_source": "Recruitment" if employee.job_applicant else "Direct Hire",
        "sections": sections,
        "findings": findings,
        "first_payroll_period": {"from_date": start, "to_date": end} if employee.date_of_joining else None,
    }
