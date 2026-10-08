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


def _check_dates(from_date: str, to_date: str):
    a, b = getdate(from_date), getdate(to_date)
    if a > b or (b - a).days > 370:
        frappe.throw(_("Choose a valid date range of at most 371 days."))
    return a.isoformat(), b.isoformat()


def _read_employees(company: str, from_date: str, to_date: str):
    allowed = permitted_employee_names(company)
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


def _read_attendance(layout, from_date: str, to_date: str):
    allowed = permitted_employee_names(layout.company)
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
    return list(groups.values())


def _read_leave(layout, from_date: str, to_date: str):
    allowed = permitted_employee_names(layout.company)
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
    return [dict(r) for r in rows]


def _read_salary_slips(layout, from_date: str, to_date: str):
    allowed = permitted_employee_names(layout.company)
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


def _source_rows(layout, start, end):
    if layout.data_source == "Manual":
        return _read_manual(layout, start, end)
    if layout.data_source == "Employee":
        return _read_employees(layout.company, start, end)
    if layout.data_source == "Attendance":
        return _read_attendance(layout, start, end)
    if layout.data_source == "Leave Application":
        return _read_leave(layout, start, end)
    if layout.data_source == "Salary Slip":
        return _read_salary_slips(layout, start, end)
    frappe.throw(_("This print data source is not supported."))


def _print_context(layout_name: str, from_date: str, to_date: str):
    layout = frappe.get_doc("Workforce Statutory Print Layout", layout_name)
    layout.check_permission("read")
    assert_company_access(layout.company, require_explicit_scope=True)
    start, end = _check_dates(from_date, to_date)
    if layout.effective_from and end < layout.effective_from:
        frappe.throw(_("This template version is not effective during the selected period."))
    if layout.effective_to and start > layout.effective_to:
        frappe.throw(_("This template has expired for the selected period."))

    spec = spec_for(layout.form_code)
    if spec["kind"] == "Evidence Only":
        frappe.throw(_("Upload the real externally issued approval; do not generate it."))
    if layout.docstatus and not spec["legal_approved"]:
        frappe.throw(_("A government-reviewed template is required before official printing."))

    rows = _source_rows(layout, start, end)
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
    )
    return layout, html


@frappe.whitelist()
def preview_a4(layout_name: str, from_date: str, to_date: str):
    """Return escaped company-scoped HTML for app-owned browser preview."""
    _, html = _print_context(layout_name, from_date, to_date)
    return {"html": html}


@frappe.whitelist()
def download_a4(layout_name: str, from_date: str, to_date: str):
    """Native Frappe PDF converter receives explicit A4 + orientation."""
    from frappe.utils.pdf import get_pdf

    layout, html = _print_context(layout_name, from_date, to_date)
    options = {
        "page-size": "A4", "orientation": layout.orientation,
        "margin-top": "9mm", "margin-bottom": "12mm",
        "margin-left": "8mm", "margin-right": "8mm",
        "print-media-type": "",
    }
    payload = get_pdf(html, options)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", layout.form_code)
    frappe.local.response.filename = f"{safe_name}_{from_date}_{to_date}.pdf"
    frappe.local.response.filecontent = payload
    frappe.local.response.type = "pdf"
