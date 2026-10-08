"""Versioned source catalog and permission-scoped dataset adapters for DIFE drafts.

No hardcoded employer, wage rate, income tax, branch, salary percentage,
work shift or medical evidence is shipped in this module.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import json
import re

import frappe
from frappe import _
from frappe.utils import getdate

from workforce_suite.workforce_suite.statutory_export_policy import (
    available_languages, normalize_period, period_mode, validate_language,
)
from workforce_suite.workforce_suite.statutory_access import check_company, checked_profile
from workforce_suite.workforce_suite.statutory_schema import validate_schema, missing_findings, reconcile_wages, money
from workforce_suite.workforce_suite.statutory_native_data import supplemental, approved_overtime, leave_balances, payment_evidence
from workforce_suite.workforce_suite.report_scope import (
    permitted_employee_names, permitted_salary_slips,
)
from workforce_suite.workforce_suite.statutory_print_html import render_html

SPECS_PATH = Path(__file__).with_name("statutory_form_specs.json")
MAX_PRINT_ROWS = 2000
FIELD_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

# Company-specific Salary Components MUST be mapped by the human editor.
COMPONENT_KEYS = frozenset({
    "basic_wage", "house_rent", "transport", "medical", "food_allowance",
    "attendance_bonus", "overtime_payment", "other_pay",
})


@lru_cache(maxsize=1)
def catalog():
    data = json.loads(SPECS_PATH.read_text(encoding="utf-8"))
    return {row["id"]: row for row in data["entries"]}


def spec_for(form_code: str):
    row = catalog().get(form_code)
    if not row:
        frappe.throw(_("Unknown statutory reference code: {0}").format(form_code))
    return row


@frappe.whitelist()
def available_print_layouts(form_code: str, company: str, branch: str = ""):
    """List only readable layouts in the requested Company/establishment.

    Contextual buttons never guess which tenant or saved legal draft to use.
    A site-wide report cannot silently select a layout restricted to one Branch.
    """
    spec_for(form_code)
    if not company:
        frappe.throw(_("Select a Company in the current report first."))
    check_company(company)
    if not frappe.has_permission("Workforce Statutory Print Layout", "read"):
        frappe.throw(_("You are not allowed to print statutory layouts."), frappe.PermissionError)
    records = frappe.get_list(
        "Workforce Statutory Print Layout",
        filters={"form_code": form_code, "company": company, "docstatus": ["!=", 2]},
        fields=["name", "title", "branch", "docstatus", "orientation", "template_version"],
        order_by="modified desc",
        limit_page_length=100,
    )
    return [
        {
            "name": item.name, "title": item.title,
            "branch": item.branch or "",
            "status": "Reviewed" if item.docstatus == 1 else "Draft",
            "orientation": item.orientation,
            "version": item.template_version,
        }
        for item in records if not item.branch or (branch and item.branch == branch)
    ]


@frappe.whitelist()
def get_form_spec(form_code: str):
    if not frappe.has_permission("Workforce Statutory Print Layout", "create"):
        frappe.throw(_("You cannot configure statutory form layouts."), frappe.PermissionError)
    spec = spec_for(form_code)
    return {
        "id": spec["id"], "title": spec["ui_title"],
        "orientation": spec["orientation"], "form_family": spec["kind"],
        "data_source": spec["data_source"],
        "source_url": spec["source_pdf_url"],
        "source_sha256": spec["source_sha256"],
        "source_issue": spec["source_issue"],
        "field_audit": spec["field_audit"],
        "columns": spec["columns"],
    }


def _scope_employees(
    layout, employee: str = "", branch: str = "",
    department: str = "", employment_type: str = "",
    include_all: bool = False,
) -> tuple[str, ...]:
    """Enforce company, establishment and native Employee visibility.

    A personal document defaults to one worker; bulk needs an explicit choice.
    Branch, department and worker category filters are optional, never
    repeated when already supplied by the current report.
    """
    if employee and include_all:
        frappe.throw(_("Choose either one employee or all matching employees."))
    if layout.data_source == "Manual":
        from frappe.permissions import get_user_permissions
        scopes = get_user_permissions(frappe.session.user)
        if scopes.get("Employee") or scopes.get("Department") or (scopes.get("Branch") and not layout.branch):
            frappe.throw(_("Manual establishment returns need a permitted establishment layout; whole-company evidence is not available to a narrowed scope."), frappe.PermissionError)
        if branch and branch != layout.branch:
            frappe.throw(_("Manual evidence Branch must match its establishment layout."), frappe.PermissionError)
        if employee or department or employment_type:
            frappe.throw(_("These worker filters do not apply to manually entered evidence."))
        return ()
    if layout.branch and branch and layout.branch != branch:
        frappe.throw(_("Selected branch is outside the saved print layout."))
    effective_branch = layout.branch or branch
    if effective_branch and frappe.db.get_value("Branch", effective_branch, "company") != layout.company:
        frappe.throw(_("Selected Branch is not in the layout Company."))
    if department:
        owner = frappe.db.get_value("Department", department, "company")
        if owner and owner != layout.company:
            frappe.throw(_("Department is outside the layout Company."))
    allowed = permitted_employee_names(
        layout.company, branch=effective_branch or None,
        department=department or None,
    )
    if employment_type:
        # Filter only the already-permitted Employee IDs.
        scoped = frappe.get_list(
            "Employee", filters={"name": ["in", allowed],
                                 "employment_type": employment_type,
                                 "company": layout.company},
            fields=["name"], limit_page_length=0,
        ) if allowed else []
        permitted = {row.name for row in scoped}
        allowed = tuple(name for name in allowed if name in permitted)
    if employee:
        if employee not in allowed:
            frappe.throw(_("Employee is outside your authorized scope."),
                         frappe.PermissionError)
        allowed = (employee,)
    elif layout.form_family == "Document" and layout.data_source == "Employee":
        if not include_all:
            frappe.throw(_("Select an Employee or explicitly choose all matching employees."))
        if len(allowed) > 50:
            frappe.throw(_("For personal documents, export at most 50 workers at a time. Narrow the filters."))
    if len(allowed) > MAX_PRINT_ROWS:
        frappe.throw(_("Limit exports to 2000 workers by selecting branch or department."))
    return allowed


def _read_employees(company: str, from_date: str, to_date: str, allowed: tuple[str, ...]):
    if not allowed:
        return []
    if len(allowed) > MAX_PRINT_ROWS:
        frappe.throw(_("Too many employee rows. Narrow the branch or reporting period."))
    records = frappe.get_list(
        "Employee",
        filters={"company": company, "name": ["in", allowed]},
        fields=["name", "employee_name", "employee_number", "designation",
                "department", "branch", "status", "date_of_birth", "date_of_joining",
                "gender", "employment_type", "permanent_address"],
        order_by="name asc", limit_page_length=MAX_PRINT_ROWS + 1,
    )
    return [dict(
        employee=x.name, employee_name=x.employee_name,
        employee_number=x.employee_number, designation=x.designation,
        department=x.department, branch=x.branch, status=x.status,
        date_of_birth=x.date_of_birth, date_of_joining=x.date_of_joining,
        gender=x.gender, employment_type=x.employment_type, permanent_address=x.permanent_address,
    ) for x in records]


def _read_attendance(layout, from_date: str, to_date: str, allowed: tuple[str, ...]):
    if not allowed:
        return []
    records = frappe.get_list(
        "Attendance",
        filters={"company": layout.company, "employee": ["in", allowed],
                 "attendance_date": ["between", [from_date, to_date]],
                 "docstatus": 1},
        fields=["name", "employee", "employee_name", "attendance_date",
                "status", "working_hours", "shift"],
        order_by="employee asc, attendance_date asc",
        limit_page_length=MAX_PRINT_ROWS + 1,
    )
    if len(records) > MAX_PRINT_ROWS:
        frappe.throw(_("Too many attendance records for one printable register. Narrow the scope."))
    if layout.form_code != "form_34":
        return [dict(r) for r in records]

    # Weekly per-worker pivot. Native Attendance working_hours is
    # informational; it is NOT proof of approved overtime or its rate.
    if (getdate(to_date) - getdate(from_date)).days != 6:
        frappe.throw(_("Form 34 needs exactly seven consecutive days."))
    days = ["day_mon", "day_tue", "day_wed", "day_thu",
            "day_fri", "day_sat", "day_sun"]
    groups = {}
    for r in records:
        row = groups.setdefault(r.employee, {
            "employee": r.employee, "employee_name": r.employee_name,
            "total_work_hours": money(0), "_attendance": [],
        })
        row["_attendance"].append(r.name)
        key = days[getdate(r.attendance_date).weekday()]
        if float(r.working_hours or 0) < 0:
            frappe.throw(_("Negative submitted work hours require correction before printing."))
        if float(r.working_hours or 0) > 0 and r.status not in {"Present", "Half Day", "Work From Home"}:
            frappe.throw(_("Positive work hours on non-work Attendance require correction before printing."))
        if key in row:
            frappe.throw(_("Multiple Attendance records for one day require an explicit shift-aware legal review."))
        row[key] = r.working_hours if r.working_hours is not None else ""
        if r.working_hours is not None and r.status in {"Present", "Half Day", "Work From Home"}:
            row["total_work_hours"] += money(r.working_hours)
    # These are actual native worker identifiers, not assumed legal register
    # numbers. Never substitute an Employee ID for a statutory register ID.
    identities = frappe.get_list(
        "Employee",
        filters={"company": layout.company, "name": ["in", list(groups)]},
        fields=["name", "designation"],
        limit_page_length=MAX_PRINT_ROWS + 1,
    ) if groups else []
    person_index = {person.name: person for person in identities}
    overtime, ot_findings = approved_overtime(layout, tuple(groups), from_date, to_date)
    output = []
    for serial, employee_id in enumerate(sorted(groups), 1):
        row = groups[employee_id]
        person = person_index.get(employee_id)
        row["serial_no"] = serial
        if person:
            row["designation"] = person.designation
        ot = overtime.get(employee_id)
        row["_findings"] = list(ot_findings)
        if ot:
            row["approved_overtime_hours"] = ot["hours"]
            row["_overtime"] = ot["sources"]
            if ot["complete"]:
                row["overtime_pay"] = ot["amount"]

        output.append(row)
    return output


def _read_leave(layout, from_date: str, to_date: str, allowed: tuple[str, ...]):
    if not allowed:
        return []
    rows = frappe.get_list(
        "Leave Application",
        filters={"company": layout.company, "employee": ["in", allowed],
                 "from_date": ["<=", to_date], "to_date": [">=", from_date],
                 "docstatus": 1},
        fields=["name", "employee", "employee_name", "leave_type",
                "from_date", "to_date", "total_leave_days", "status"],
        order_by="from_date asc, employee asc",
        limit_page_length=MAX_PRINT_ROWS + 1,
    )
    if len(rows) > MAX_PRINT_ROWS:
        frappe.throw(_("Too many leave records for one PDF. Narrow the reporting period."))
    balance_cache = {}
    profile = checked_profile(layout, from_date, to_date)
    types = ({"annual_requested": profile.annual_leave_type,
              "casual_requested": profile.casual_leave_type,
              "sick_requested": profile.sick_leave_type} if profile else {})
    from hrms.hr.doctype.leave_application.leave_application import get_number_of_leave_days
    output = []
    for record in rows:
        if record.status != "Approved":
            continue
        doc = frappe.get_doc("Leave Application", record.name)
        doc.check_permission("read")
        first = max(getdate(from_date), getdate(doc.from_date))
        last = min(getdate(to_date), getdate(doc.to_date))
        days = get_number_of_leave_days(doc.employee, doc.leave_type, first, last,
                                       doc.half_day, doc.half_day_date)
        cache_key = (record.employee, str(last))
        if cache_key not in balance_cache:
            balance_cache[cache_key] = leave_balances(layout, (record.employee,), from_date, str(last))
        balances, findings = balance_cache[cache_key]
        row = dict(record)
        row.update(balances.get(record.employee, {}))
        row["_findings"] = list(findings)
        row["_leave_application"] = record.name
        row["granted_days"] = days
        for key, leave_type in types.items():
            if record.leave_type == leave_type:
                row[key] = f"{first} — {last} ({days})"
        output.append(row)
    return output


def _read_salary_slips(layout, from_date: str, to_date: str, allowed: tuple[str, ...]):
    if not allowed:
        return []
    slips = permitted_salary_slips(
        layout.company, allowed, from_date=from_date, to_date=to_date,
        overlapping_period=True,
    )
    if len(slips) > MAX_PRINT_ROWS:
        frappe.throw(_("Too many salary slips for one printable register."))
    mapped = {}
    for col in list(layout.columns) + list(layout.get("salary_mappings") or []):
        if col.field_key in COMPONENT_KEYS and col.salary_component:
            mapped.setdefault(col.field_key, []).append(col.salary_component)
    components = [component for values in mapped.values() for component in values]
    if len(components) != len(set(components)):
        frappe.throw(_("Duplicate earning mappings would double-count native wages."))
    output = []
    for index, r in enumerate(slips, 1):
        if getdate(r.start_date) < getdate(from_date) or getdate(r.end_date) > getdate(to_date):
            frappe.throw(_("The selected period cuts a submitted Salary Slip. Use its complete payroll period; wages are never prorated by this export."))
        # Parent passed the native permission-aware list query.
        slip = frappe.get_doc("Salary Slip", r.name)
        slip.check_permission("read")
        row = dict(
            serial_no=index, employee=r.employee, employee_name=r.employee_name,
            salary_slip=r.name, gross_pay=r.gross_pay,
            total_deduction=r.total_deduction, net_pay=r.net_pay,
            start_date=r.start_date, end_date=r.end_date,
        )
        details = list(slip.get("earnings", []))
        included = [x for x in details if not x.get("do_not_include_in_total")]
        try:
            reconcile_wages([x.amount for x in included], slip.gross_pay, slip.total_deduction, slip.net_pay,
                            precision=slip.precision("gross_pay") or 2, loan_repayment=slip.get("total_loan_repayment"))
        except ValueError as exc:
            frappe.throw(str(exc))
        unknown = {x.salary_component for x in included if money(x.amount) != 0} - set(components)
        if unknown:
            frappe.throw(_("Map every included earning component before producing the wage register: {0}").format(", ".join(sorted(unknown))))
        for key, group in mapped.items():
            row[key] = sum((money(x.amount) for x in included if x.salary_component in group), money(0))
        row["total_deduction"] = money(slip.total_deduction) + money(slip.get("total_loan_repayment"))
        if abs(sum((money(x.amount) for x in slip.deductions if not x.get("do_not_include_in_total")), money(0)) - money(slip.total_deduction)) > money(1).scaleb(-(slip.precision("gross_pay") or 2)):
            frappe.throw(_("Salary Slip deduction rows do not reconcile with their native total."))
        row["_payment_status"] = payment_evidence(slip, allowed)
        row["_findings"] = [{"code": "PAYMENT_EVIDENCE", "message": "Submitted wages are not proof of payment or worker acknowledgement. Review native Finance reconciliation and receipt evidence."}]
        overtime, ot_findings = approved_overtime(layout, (r.employee,), str(r.start_date), str(r.end_date))
        row["_findings"].extend(ot_findings)
        ot = overtime.get(r.employee)
        if ot:
            row["overtime_hours"] = ot["hours"]
            row["_overtime"] = ot["sources"]
            if ot["complete"] and "overtime_payment" in mapped:
                if abs(money(row["overtime_payment"]) - ot["amount"]) > money(1).scaleb(-(slip.precision("gross_pay") or 2)):
                    frappe.throw(_("Salary Slip overtime does not reconcile with submitted native overtime amounts."))

        output.append(row)
    return output


def _read_manual(layout, from_date: str, to_date: str):
    names = frappe.get_list(
        "Workforce Statutory Record",
        filters={
            "company": layout.company, "layout": layout.name,
            "entry_date": ["between", [from_date, to_date]],
            "docstatus": 1,
        },
        fields=["name"], order_by="entry_date asc, name asc",
        limit_page_length=MAX_PRINT_ROWS + 1,
    )
    if len(names) > MAX_PRINT_ROWS:
        frappe.throw(_("Too many manual statutory records for one PDF."))
    rows = []
    for name in names:
        record = frappe.get_doc("Workforce Statutory Record", name.name)
        record.check_permission("read")
        row = {cell.field_key: cell.field_value for cell in record.get("entries", [])}
        row["_manual_record"] = record.name
        row["reference_no"] = row.get("reference_no") or record.reference_id
        row["record_date"] = row.get("record_date") or record.entry_date
        rows.append(row)
    return rows


def _source_rows(layout, start, end, allowed):
    if layout.data_source == "Manual":
        return _read_manual(layout, start, end)
    if layout.data_source == "Employee":
        return _read_employees(layout.company, start, end, allowed)
    if layout.data_source == "Attendance":
        return _read_attendance(layout, start, end, allowed)
    if layout.data_source == "Leave Application":
        return _read_leave(layout, start, end, allowed)
    if layout.data_source == "Salary Slip":
        return _read_salary_slips(layout, start, end, allowed)
    frappe.throw(_("This print data source is not supported."))


def _print_context(
    layout_name: str, from_date: str = "", to_date: str = "",
    *, employee: str = "", branch: str = "", department: str = "",
    employment_type: str = "", include_all: bool = False,
    language: str = "en",
):
    layout = frappe.get_doc("Workforce Statutory Print Layout", layout_name)
    layout.check_permission("read")
    check_company(layout.company)
    try:
        start, end = normalize_period(layout.form_code, layout.data_source, from_date, to_date)
        language = validate_language(layout, language)
    except ValueError as exc:
        frappe.throw(str(exc))
    if layout.docstatus == 2:
        frappe.throw(_("Cancelled templates cannot be exported."))
    if start and layout.effective_from and start < str(layout.effective_from):
        frappe.throw(_("This template version is not effective during the selected period."))
    if start and layout.effective_to and end > str(layout.effective_to):
        frappe.throw(_("This template has expired for the selected period."))

    spec = spec_for(layout.form_code)
    if spec["kind"] == "Evidence Only":
        frappe.throw(_("Upload the real externally issued approval; do not generate it."))
    if layout.form_family != spec["kind"] or layout.data_source != spec["data_source"]:
        frappe.throw(_("This layout does not match its DIFE source type and data source."))
    if layout.docstatus and not spec["legal_approved"]:
        frappe.throw(_("A government-reviewed template is required before official printing."))

    try:
        validate_schema(spec, layout.columns)
    except ValueError as exc:
        frappe.throw(str(exc))
    profile = checked_profile(layout, start, end, language)

    allowed = _scope_employees(
        layout, employee=employee, branch=branch,
        department=department, employment_type=employment_type,
        include_all=include_all,
    )
    rows = _source_rows(layout, start, end, allowed)
    if len(rows) > MAX_PRINT_ROWS:
        frappe.throw(_("Too many records for a single printable document."))
    evidence = supplemental(layout, allowed, start, end) if layout.data_source != "Manual" else {}
    persons = {r["employee"]: r for r in _read_employees(layout.company, start, end, allowed)} if layout.form_code == "form_9" else {}
    for index, row in enumerate(rows, 1):
        row["serial_no"] = row.get("serial_no") or index
        facts = evidence.get(row.get("employee"), {})
        row.update(facts)
        if layout.form_code == "form_34":
            row["designation_card"] = " / ".join(str(x) for x in (row.get("designation"), facts.get("card_no")) if x)
        if layout.form_code == "form_9":
            for key in ("employee_name", "designation", "department", "date_of_joining"):
                row[key] = persons.get(row.get("employee"), {}).get(key)
            for key in ("worker_register_no", "card_no"):
                if not row.get(key):
                    row.setdefault("_findings", []).append({"code": "WORKER_ID_MISSING", "message": "Review the worker register and card identifiers; Employee ID was not substituted."})
        if layout.data_source == "Employee":
            row["worker_name"] = row.get("employee_name")
            row["worker_name_and_nid"] = (row.get("employee_name", "") + " / " + facts["national_id"]) if facts.get("national_id") else ""
            row["sex_dob_age"] = " / ".join(str(row.get(k) or "") for k in ("gender", "date_of_birth"))
            row["designation_grade"] = " / ".join(str(x) for x in (row.get("designation"), facts.get("grade")) if x)
            row["appointment_date"] = row.get("date_of_joining")
            row["job_title"] = row.get("designation")
            row["place_of_work"] = row.get("branch")
        if profile and layout.data_source == "Manual":
            for key, value in {"establishment": profile.establishment_bn if language == "bn" else profile.establishment_en,
                               "registration_no": profile.registration_no, "licence_no": profile.licence_no,
                               "mailing_address": profile.address_bn if language == "bn" else profile.address_en,
                               "industry": profile.industry_bn if language == "bn" else profile.industry_en}.items():
                row.setdefault(key, value)
    findings = missing_findings(spec, rows)
    for row in rows:
        findings.extend(row.get("_findings", []))
    if not profile:
        findings.append({"code": "PROFILE_MISSING", "message": "Configure a reviewed establishment profile; Company name alone does not establish registration, address or legal applicability."})
    columns = list(layout.columns)
    if layout.docstatus:
        if not rows:
            frappe.throw(_("No confirmed records are available for the official print."))
        for i, row in enumerate(rows, 1):
            for col in columns:
                if col.required_value and row.get(col.field_key) in (None, ""):
                    frappe.throw(_("Missing {0} on row {1}.").format(col.label_en, i))

    company_name = ((profile.establishment_bn if language == "bn" else profile.establishment_en)
                    if profile else frappe.db.get_value("Company", layout.company, "company_name"))
    company_address = (profile.address_bn if language == "bn" else profile.address_en) if profile else ""
    signatory = ((profile.signatory_bn if language == "bn" else profile.signatory_en) or "") if profile else ""
    html = render_html(
        layout, rows, company_name=company_name or layout.company,
        company_address=company_address, signatory=signatory,
        from_date=start, to_date=end, is_draft=layout.docstatus != 1,
        language=language,
    )
    return layout, html, {
        "rows": rows, "company_name": company_name or layout.company,
        "from_date": start, "to_date": end, "language": language, "findings": findings,
        "company_address": company_address, "signatory": signatory,
        "scope": {"employee": employee, "branch": branch or layout.branch, "department": department,
                  "employment_type": employment_type, "include_all": include_all},
    }


@frappe.whitelist()
def export_options(layout_name: str):
    """Only render controls applicable to this saved layout."""
    layout = frappe.get_doc("Workforce Statutory Print Layout", layout_name)
    layout.check_permission("read")
    check_company(layout.company)
    return {
        "company": layout.company,
        "branch": layout.branch or "",
        "data_source": layout.data_source,
        "form_family": layout.form_family,
        "form_code": layout.form_code,
        "period_mode": period_mode(layout.form_code, layout.data_source),
        "languages": list(available_languages(layout)),
        "allow_worker_filters": layout.data_source != "Manual",
        "employee_required": layout.form_family == "Document" and layout.data_source == "Employee",
        "docx_working_copy": True,
    }


@frappe.whitelist()
def preview_a4(
    layout_name: str, from_date: str = "", to_date: str = "",
    language: str = "en", employee: str = "", branch: str = "",
    department: str = "", employment_type: str = "", include_all: int = 0,
):
    """Render the selected authorization-scoped draft or approved layout."""
    _, html, data = _print_context(
        layout_name, from_date, to_date, language=language,
        employee=employee, branch=branch, department=department,
        employment_type=employment_type, include_all=bool(int(include_all)),
    )
    return {"html": html, "findings": data["findings"], "status": "Draft", "row_count": len(data["rows"])}


@frappe.whitelist(methods=["POST"])
def download_a4(
    layout_name: str, from_date: str = "", to_date: str = "",
    language: str = "en", employee: str = "", branch: str = "",
    department: str = "", employment_type: str = "", include_all: int = 0,
):
    """Always render on A4 with orientation selected by reviewed layout."""
    from frappe.utils.pdf import get_pdf

    layout, html, data = _print_context(
        layout_name, from_date, to_date, language=language,
        employee=employee, branch=branch, department=department,
        employment_type=employment_type, include_all=bool(int(include_all)),
    )
    options = {
        "page-size": "A4", "orientation": layout.orientation,
        "margin-top": "9mm", "margin-bottom": "12mm",
        "margin-left": "8mm", "margin-right": "8mm",
        "print-media-type": "",
        "footer-right": "[page] / [topage]", "footer-font-size": "8",
    }
    payload = get_pdf(html, options)
    _audit_generation(layout, data, "PDF", payload)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", layout.form_code)
    frappe.local.response.filename = (
        f"{safe_name}_{data['language']}_{data['from_date'] or 'employee'}_{data['to_date'] or 'document'}.pdf"
    )
    frappe.local.response.filecontent = payload
    frappe.local.response.type = "pdf"



@frappe.whitelist(methods=["POST"])
def download_docx(
    layout_name: str, from_date: str = "", to_date: str = "",
    language: str = "en", employee: str = "", branch: str = "",
    department: str = "", employment_type: str = "", include_all: int = 0,
):
    """Editable A4 working copy. Never identified as a government-issued form."""
    from workforce_suite.workforce_suite.statutory_print_docx import render_docx

    layout, _html, data = _print_context(
        layout_name, from_date, to_date, language=language,
        employee=employee, branch=branch, department=department,
        employment_type=employment_type, include_all=bool(int(include_all)),
    )
    payload = render_docx(
        layout, data["rows"], company_name=data["company_name"],
        from_date=data["from_date"], to_date=data["to_date"], language=data["language"],
        company_address=data["company_address"], signatory=data["signatory"],
    )
    _audit_generation(layout, data, "DOCX", payload)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", layout.form_code)
    frappe.local.response.filename = f"{safe_name}_{language}_working_copy.docx"
    frappe.local.response.filecontent = payload
    frappe.local.response.type = "download"


def _audit_generation(layout, data, output_format, payload):
    """Record provenance, not sensitive cells or a false filing/payment status."""
    import hashlib
    from frappe.utils import now_datetime
    references = []
    for row in data["rows"]:
        references.append({key: row[key] for key in (
            "employee", "salary_slip", "_attendance", "_overtime", "_evidence", "_leave_application", "_manual_record"
        ) if key in row})
    previous = getattr(frappe.flags, "statutory_generation", False)
    frappe.flags.statutory_generation = True
    try:
        audit = frappe.get_doc({
            "doctype": "Workforce Statutory Export", "company": layout.company, "branch": layout.branch,
            "layout": layout.name, "template_version": layout.template_version, "source_sha256": layout.source_sha256,
            "scope_json": json.dumps({**data["scope"], "from_date": data["from_date"], "to_date": data["to_date"],
                                      "references": references}, default=str),
            "language": data["language"], "output_format": output_format,
            "payload_sha256": hashlib.sha256(payload).hexdigest(), "generated_by": frappe.session.user,
            "generated_at": now_datetime(), "status": "Draft Generated",
        })
        # The exporter already authorized layout, Company and every source.
        # Clients cannot insert audit documents through REST or modify them.
        audit.insert(ignore_permissions=True)
    finally:
        frappe.flags.statutory_generation = previous
