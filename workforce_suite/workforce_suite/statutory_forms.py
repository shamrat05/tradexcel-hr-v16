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
from workforce_suite.workforce_suite.company_context import assert_company_access
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
    assert_company_access(company, require_explicit_scope=True)
    if not frappe.has_permission("Workforce Statutory Print Layout", "read"):
        frappe.throw(_("You are not allowed to print statutory layouts."), frappe.PermissionError)
    records = frappe.get_list(
        "Workforce Statutory Print Layout",
        filters={"form_code": form_code, "company": company},
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
        if employee or department or employment_type or branch:
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
                "gender", "employment_type"],
        order_by="name asc", limit_page_length=MAX_PRINT_ROWS + 1,
    )
    return [dict(
        employee=x.name, employee_name=x.employee_name,
        employee_number=x.employee_number, designation=x.designation,
        department=x.department, branch=x.branch, status=x.status,
        date_of_birth=x.date_of_birth, date_of_joining=x.date_of_joining,
        gender=x.gender, employment_type=x.employment_type,
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
            "total_work_hours": 0,
        })
        key = days[getdate(r.attendance_date).weekday()]
        row[key] = r.working_hours if r.working_hours is not None else ""
        if r.working_hours is not None:
            row["total_work_hours"] += float(r.working_hours)
    # These are actual native worker identifiers, not assumed legal register
    # numbers. Never substitute an Employee ID for a statutory register ID.
    identities = frappe.get_list(
        "Employee",
        filters={"company": layout.company, "name": ["in", list(groups)]},
        fields=["name", "employee_number", "branch"],
        limit_page_length=MAX_PRINT_ROWS + 1,
    ) if groups else []
    person_index = {person.name: person for person in identities}
    output = []
    for serial, employee_id in enumerate(sorted(groups), 1):
        row = groups[employee_id]
        person = person_index.get(employee_id)
        row["serial_no"] = serial
        if person:
            row["employee_number"] = person.employee_number
            row["branch"] = person.branch
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
    # Form 9 draft fields use native submitted leave history only. Annual
    # opening/balances, approval date, and legal classifications still require
    # independent evidence: never invent them from total_leave_days.
    output = []
    for record in rows:
        row = dict(record)
        row["leave_requested"] = record.leave_type
        if record.status == "Approved":
            row["granted_days"] = record.total_leave_days
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
    mapped = {
        col.field_key: col.salary_component
        for col in layout.columns
        if col.field_key in COMPONENT_KEYS and col.salary_component
    }
    output = []
    for index, r in enumerate(slips, 1):
        # Parent passed the native permission-aware list query.
        slip = frappe.get_doc("Salary Slip", r.name)
        slip.check_permission("read")
        row = dict(
            serial_no=index, employee=r.employee, employee_name=r.employee_name,
            salary_slip=r.name, gross_pay=r.gross_pay,
            total_deduction=r.total_deduction, net_pay=r.net_pay,
            start_date=r.start_date, end_date=r.end_date,
        )
        details = list(slip.get("earnings", [])) + list(slip.get("deductions", []))
        for key, component in mapped.items():
            row[key] = sum(float(x.amount or 0) for x in details if x.salary_component == component)
        output.append(row)
    return output


def _read_manual(layout, from_date: str, to_date: str):
    names = frappe.get_list(
        "Workforce Statutory Record",
        filters={
            "company": layout.company, "layout": layout.name,
            "entry_date": ["between", [from_date, to_date]],
            "docstatus": ["in", [0, 1]] if not layout.docstatus else 1,
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
    assert_company_access(layout.company, require_explicit_scope=True)
    try:
        start, end = normalize_period(layout.form_code, layout.data_source, from_date, to_date)
        language = validate_language(layout, language)
    except ValueError as exc:
        frappe.throw(str(exc))
    if start and layout.effective_from and end < str(layout.effective_from):
        frappe.throw(_("This template version is not effective during the selected period."))
    if start and layout.effective_to and start > str(layout.effective_to):
        frappe.throw(_("This template has expired for the selected period."))

    spec = spec_for(layout.form_code)
    if spec["kind"] == "Evidence Only":
        frappe.throw(_("Upload the real externally issued approval; do not generate it."))
    if layout.form_family != spec["kind"] or layout.data_source != spec["data_source"]:
        frappe.throw(_("This layout does not match its DIFE source type and data source."))
    if layout.docstatus and not spec["legal_approved"]:
        frappe.throw(_("A government-reviewed template is required before official printing."))

    allowed = _scope_employees(
        layout, employee=employee, branch=branch,
        department=department, employment_type=employment_type,
        include_all=include_all,
    )
    rows = _source_rows(layout, start, end, allowed)
    if len(rows) > MAX_PRINT_ROWS:
        frappe.throw(_("Too many records for a single printable document."))
    columns = list(layout.columns)
    if layout.docstatus:
        if not rows:
            frappe.throw(_("No confirmed records are available for the official print."))
        for i, row in enumerate(rows, 1):
            for col in columns:
                if col.required_value and row.get(col.field_key) in (None, ""):
                    frappe.throw(_("Missing {0} on row {1}.").format(col.label_en, i))

    company_name = frappe.db.get_value("Company", layout.company, "company_name")
    html = render_html(
        layout, rows, company_name=company_name or layout.company,
        from_date=start, to_date=end, is_draft=layout.docstatus != 1,
        language=language,
    )
    return layout, html, {
        "rows": rows, "company_name": company_name or layout.company,
        "from_date": start, "to_date": end, "language": language,
    }


@frappe.whitelist()
def export_options(layout_name: str):
    """Only render controls applicable to this saved layout."""
    layout = frappe.get_doc("Workforce Statutory Print Layout", layout_name)
    layout.check_permission("read")
    assert_company_access(layout.company, require_explicit_scope=True)
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
    _, html, _ = _print_context(
        layout_name, from_date, to_date, language=language,
        employee=employee, branch=branch, department=department,
        employment_type=employment_type, include_all=bool(int(include_all)),
    )
    return {"html": html}


@frappe.whitelist()
def download_a4(
    layout_name: str, from_date: str = "", to_date: str = "",
    language: str = "en", employee: str = "", branch: str = "",
    department: str = "", employment_type: str = "", include_all: int = 0,
):
    """Always render on A4 with orientation selected by reviewed layout."""
    from frappe.utils.pdf import get_pdf

    layout, html, _ = _print_context(
        layout_name, from_date, to_date, language=language,
        employee=employee, branch=branch, department=department,
        employment_type=employment_type, include_all=bool(int(include_all)),
    )
    options = {
        "page-size": "A4", "orientation": layout.orientation,
        "margin-top": "9mm", "margin-bottom": "12mm",
        "margin-left": "8mm", "margin-right": "8mm",
        "print-media-type": "",
    }
    payload = get_pdf(html, options)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", layout.form_code)
    frappe.local.response.filename = (
        f"{safe_name}_{language}_{from_date or 'employee'}_{to_date or 'document'}.pdf"
    )
    frappe.local.response.filecontent = payload
    frappe.local.response.type = "pdf"



@frappe.whitelist()
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
    )
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", layout.form_code)
    frappe.local.response.filename = f"{safe_name}_{language}_working_copy.docx"
    frappe.local.response.filecontent = payload
    frappe.local.response.type = "download"
