"""Read-only native evidence adapters; never calculate salary or legal rates."""
from datetime import timedelta
from decimal import Decimal

import frappe
from frappe.utils import getdate

from workforce_suite.workforce_suite.statutory_access import checked_profile

LIMIT = 2000


def bounded(records, label):
    if len(records) > LIMIT:
        frappe.throw(f"Too many {label}; narrow the reporting scope. Nothing was truncated.")
    return records


def supplemental(layout, employees, start="", end=""):
    """Only independently submitted missing-field evidence may supplement rows."""
    if not employees or not frappe.has_permission("Workforce Statutory Record", "read"):
        return {}
    at = getdate(end) if end else getdate()
    filters = {"company": layout.company, "layout": layout.name,
               "employee": ["in", employees], "docstatus": 1,
               "entry_date": ["<=", at]}
    records = bounded(frappe.get_list("Workforce Statutory Record", filters=filters,
        fields=["name"], limit_page_length=LIMIT + 1), "evidence records")
    output = {}
    for item in records:
        doc = frappe.get_doc("Workforce Statutory Record", item.name)
        doc.check_permission("read")
        if doc.effective_to and getdate(doc.effective_to) < at:
            continue
        if not doc.reviewed_by or doc.reviewed_by == doc.owner:
            frappe.throw("Supplemental evidence needs an independent recorded reviewer.")
        row = output.setdefault(doc.employee, {"_evidence": []})
        row["_evidence"].append(doc.name)
        for entry in doc.entries:
            from workforce_suite.workforce_suite.doctype.workforce_statutory_record.workforce_statutory_record import SUPPLEMENTAL_FIELDS
            if entry.field_key not in SUPPLEMENTAL_FIELDS:
                frappe.throw("Evidence cannot override native identity, leave or financial fields.")
            if entry.field_key in row:
                frappe.throw("Overlapping worker evidence: narrow or supersede the reviewed versions explicitly.")
            row[entry.field_key] = entry.field_value
    return output


def approved_overtime(layout, employees, start, end):
    """Hours from submitted Overtime Slip; money from its native Additional Salary.

    A partially intersecting slip has no safely attributable weekly amount.
    Never apportion that amount or recompute historical rates from current SSA.
    """
    if not employees:
        return {}, []
    if not frappe.has_permission("Overtime Slip", "read"):
        return {}, [{"code": "OVERTIME_ACCESS", "message": "Approved overtime source is not accessible; no zero hours were assumed."}]
    slips = bounded(frappe.get_list("Overtime Slip", filters={
        "employee": ["in", employees], "docstatus": 1,
        "start_date": ["<=", end], "end_date": [">=", start],
    }, fields=["name"], limit_page_length=LIMIT + 1), "overtime slips")
    result, findings = {}, []
    for item in slips:
        slip = frappe.get_doc("Overtime Slip", item.name)
        slip.check_permission("read")
        row = result.setdefault(slip.employee, {"hours": Decimal(0), "sources": [], "amount": Decimal(0), "complete": True})
        details = [d for d in slip.overtime_details if getdate(start) <= getdate(d.date) <= getdate(end)]
        if not details:
            continue
        # Native approval references submitted Attendance; corrupt links fail closed.
        for detail in details:
            reference = detail.reference_document
            if not reference:
                matches = frappe.get_list("Attendance", filters={"employee": slip.employee, "company": layout.company,
                    "docstatus": 1, "attendance_date": detail.date}, fields=["name"], limit_page_length=2)
                if len(matches) != 1:
                    frappe.throw("Approved overtime needs unambiguous submitted Attendance evidence for the printed day.")
                reference = matches[0].name
            att = frappe.get_doc("Attendance", reference)
            att.check_permission("read")
            if att.docstatus != 1 or att.employee != slip.employee or att.company != layout.company or getdate(att.attendance_date) != getdate(detail.date):
                frappe.throw("Approved overtime references inconsistent Attendance evidence.")
            duration = Decimal(str(detail.overtime_duration or 0))
            if duration < 0:
                frappe.throw("Negative approved overtime duration requires source correction.")
            row["hours"] += duration
        row["sources"].append(slip.name)
        if getdate(slip.start_date) < getdate(start) or getdate(slip.end_date) > getdate(end):
            row["complete"] = False
            findings.append({"code": "OVERTIME_PERIOD", "message": "Overtime Slip spans a different period; money and hourly rate require review."})
            continue
        if not frappe.has_permission("Additional Salary", "read"):
            row["complete"] = False
            findings.append({"code": "OVERTIME_MONEY_ACCESS", "message": "Native overtime amount is not accessible."})
            continue
        amounts = bounded(frappe.get_list("Additional Salary", filters={
            "employee": slip.employee, "company": layout.company, "docstatus": 1,
            "ref_doctype": "Overtime Slip", "ref_docname": slip.name,
        }, fields=["name", "amount", "salary_component"], limit_page_length=LIMIT + 1), "overtime amounts")
        if not amounts:
            row["complete"] = False
            findings.append({"code": "OVERTIME_MONEY_MISSING", "message": "Approved overtime has no submitted native Additional Salary amount."})
        components = [a.salary_component for a in amounts]
        if len(components) != len(set(components)):
            frappe.throw("Duplicate native overtime component amounts require payroll review.")
        row["amount"] += sum((Decimal(str(a.amount or 0)) for a in amounts), Decimal(0))
        # The prescribed single rate cannot describe mixed rates/components.
        if len(amounts) != 1 or len({d.overtime_type for d in details}) != 1:
            row["rate_unavailable"] = True
    if result:
        findings.append({"code": "OVERTIME_RATE_EVIDENCE", "message": "The historical per-rate breakdown is not stored on native Overtime Slip. A blended amount/hours quotient is not a prescribed hourly rate; review the original approved rate evidence."})
    return result, findings


def leave_balances(layout, employees, start, end):
    profile = checked_profile(layout, start, end)
    if not profile:
        return {}, [{"code": "LEAVE_MAPPING", "message": "Review an establishment profile and map its native annual, casual and sick Leave Types."}]
    for doctype in ("Leave Allocation", "Leave Ledger Entry"):
        if not frappe.has_permission(doctype, "read"):
            frappe.throw(f"Read access to {doctype} is required for authoritative leave balances.", frappe.PermissionError)
    from hrms.hr.doctype.leave_application.leave_application import get_leave_balance_on
    result, findings = {}, []
    categories = {"annual": profile.annual_leave_type, "casual": profile.casual_leave_type, "sick": profile.sick_leave_type}
    for employee in employees:
        row = result.setdefault(employee, {})
        for category, leave_type in categories.items():
            if not leave_type:
                findings.append({"code": "LEAVE_TYPE_MISSING", "message": f"Configure the {category} native Leave Type."})
                continue
            for key, at in [(category + "_balance", getdate(end)), (category + "_leave_opening", getdate(start) - timedelta(days=1))]:
                # Allocation absence is missing evidence, not a guessed zero.
                allocations = frappe.get_list("Leave Allocation", filters={
                    "employee": employee, "leave_type": leave_type, "docstatus": 1,
                    "from_date": ["<=", at], "to_date": [">=", at],
                }, fields=["name"], limit_page_length=2)
                if len(allocations) > 1:
                    frappe.throw("Overlapping native Leave Allocations require HR review.")
                if allocations:
                    row[key] = get_leave_balance_on(employee, leave_type, at, to_date=at)
                else:
                    findings.append({"code": "LEAVE_ALLOCATION_MISSING", "message": "A native allocation covering the balance date is missing."})
    return result, findings



def aggregate_periodic_return(layout, start, end):
    """Build a review-only Form 80/81 draft from native Attendance evidence.

    This intentionally returns observed averages only when submitted Attendance
    exists. It never treats current Employee headcount, missing days, or absent
    rows as a statutory zero or as a completed legal return.
    """
    if layout.form_code not in {"form_80", "form_81"}:
        return []
    if not frappe.has_permission("Employee", "read"):
        return [{"_findings": [{"code": "EMPLOYEE_ACCESS",
                                 "message": "Employee access is required to prepare a periodic return draft."}]}]
    employees = frappe.get_list(
        "Employee",
        filters={"company": layout.company, "status": "Active",
                 **({"branch": layout.branch} if layout.branch else {})},
        fields=["name", "gender", "date_of_birth", "date_of_joining", "relieving_date"],
        order_by="name asc",
        limit_page_length=LIMIT + 1,
    )
    employees = bounded(employees, "employees for periodic return")
    allowed = {row.name for row in employees}
    row = {"reporting_year": str(start)[:4]} if layout.form_code == "form_81" else {}
    findings = [{
        "code": "PERIODIC_REVIEW",
        "message": "Draft values are derived from submitted Attendance observations and require establishment review before use.",
    }]
    if not allowed:
        findings.append({"code": "NO_EMPLOYEES",
                         "message": "No active Employee records are available for this Company and establishment scope."})
        row["_findings"] = findings
        return [row]
    if not frappe.has_permission("Attendance", "read"):
        findings.append({"code": "ATTENDANCE_ACCESS",
                         "message": "Attendance access is required to calculate observed workforce averages."})
        row["_findings"] = findings
        return [row]
    attendance = frappe.get_list(
        "Attendance",
        filters={"company": layout.company, "employee": ["in", tuple(allowed)],
                 "attendance_date": ["between", [start, end]], "docstatus": 1},
        fields=["employee", "attendance_date", "status"],
        order_by="attendance_date asc",
        limit_page_length=LIMIT + 1,
    )
    attendance = bounded(attendance, "submitted Attendance observations")
    by_employee = {item.name: item for item in employees}
    period_end = getdate(end)
    leavers = [
        person for person in employees
        if getattr(person, "relieving_date", None)
        and getdate(person.relieving_date) >= getdate(start)
        and getdate(person.relieving_date) <= period_end
    ]
    if layout.form_code == "form_81":
        row["leavers_other"] = len(leavers)
        findings.append({
            "code": "LEAVER_CLASSIFICATION_REVIEW",
            "message": "Employees with a native relieving date are counted as leavers pending reviewed resignation, dismissal or discharge classification.",
        })
    by_day = {}
    for item in attendance:
        person = by_employee.get(item.employee)
        if not person or item.status not in {"Present", "Half Day", "Work From Home"}:
            continue
        by_day.setdefault(str(item.attendance_date), []).append(person)
    if not by_day:
        findings.append({"code": "ATTENDANCE_OBSERVATIONS_MISSING",
                         "message": "No submitted Attendance observations cover this period; averages and working days remain unfilled."})
    else:
        male = []
        female = []
        def adult(person, at):
            dob = getdate(person.date_of_birth) if person.date_of_birth else None
            return bool(dob and (at.year, at.month, at.day) >= (dob.year + 18, dob.month, dob.day))

        for day, people in by_day.items():
            at = getdate(day)
            male.append(sum(1 for person in people if person.gender == "Male" and adult(person, at)))
            female.append(sum(1 for person in people if person.gender == "Female" and adult(person, at)))
        row["adult_male"] = round(sum(male) / len(male), 2)
        row["adult_female"] = round(sum(female) / len(female), 2)
        findings.extend([
            {"code": "ADULT_CLASSIFICATION_REVIEW",
             "message": "Adult classification is based on native gender and birth-date evidence; verify the applicable legal category before submission."},
            {"code": "WORKING_DAYS_REVIEW",
             "message": "Observed Attendance dates do not establish the establishment's statutory working-day count; enter reviewed working days."},
        ])
    row["_findings"] = findings
    return [row]

def payment_evidence(slip, allowed):
    """Reuse the existing native reconciliation inspector without leaking its rows."""
    payroll_entry = slip.get("payroll_entry")
    if not payroll_entry or not frappe.has_permission("Payroll Entry", "read", payroll_entry):
        return "UNVERIFIED"
    if not all(frappe.has_permission(dt, "read") for dt in ("Journal Entry", "Bank Transaction")):
        return "UNVERIFIED"
    entry = frappe.get_doc("Payroll Entry", payroll_entry)
    if any(person.employee not in allowed for person in entry.employees):
        return "UNVERIFIED"
    from workforce_suite.workforce_suite.company_context import DEFAULT_EXPLICIT_SCOPE_ROLES
    if frappe.session.user != "Administrator" and not ({"System Manager"} | set(DEFAULT_EXPLICIT_SCOPE_ROLES)).intersection(frappe.get_roles()):
        return "UNVERIFIED"
    from workforce_suite.workforce_suite.payment_readiness import inspect_payroll_payment_readiness
    result = inspect_payroll_payment_readiness(entry)
    # Status alone is a reconciliation finding, never a forged worker receipt.
    return result["status"]
