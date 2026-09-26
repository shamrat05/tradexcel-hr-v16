"""Daily attendance report with safe defaults for optional filters."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate

from tradex_hr.tradexcel_hr.company_context import assert_company_access, resolve_company
from tradex_hr.tradexcel_hr.report_scope import permitted_employee_names

OPTIONAL_FILTERS = ("department", "branch", "status")
REQUIRED_FILTERS = ("company",)


def normalize_filters(filters: dict | None = None) -> frappe._dict:
    """Normalize legacy single-day and new date-range report requests."""
    values = frappe._dict(filters or {})
    values.company = resolve_company(values)

    from_date = values.get("from_date") or values.get("attendance_date")
    to_date = values.get("to_date") or values.get("attendance_date")
    if not from_date and not to_date:
        raise ValueError(_("Missing required filter: attendance_date or from_date/to_date"))
    from_date = from_date or to_date
    to_date = to_date or from_date
    try:
        from_date = getdate(from_date)
        to_date = getdate(to_date)
    except (TypeError, ValueError) as exc:
        raise ValueError(_("Attendance dates must be valid YYYY-MM-DD values")) from exc
    if from_date > to_date:
        raise ValueError(_("from_date cannot be later than to_date"))
    if (to_date - from_date).days > 366:
        raise ValueError(_("Attendance date range cannot exceed 366 days"))

    values.from_date = from_date.isoformat()
    values.to_date = to_date.isoformat()
    values.attendance_date = values.from_date

    for fieldname in OPTIONAL_FILTERS:
        values.setdefault(fieldname, "")

    return values


def execute(filters: dict | None = None) -> tuple[list[dict], list[dict]]:
    from frappe.desk.query_report import get_report_doc

    get_report_doc("Daily Attendance Summary")
    filters = normalize_filters(filters)
    assert_company_access(filters.company)
    columns = [
        {"label": _("Attendance Date"), "fieldname": "attendance_date", "fieldtype": "Date", "width": 105},
        {"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 120},
        {"label": _("Employee ID"), "fieldname": "employee_id", "fieldtype": "Data", "width": 100},
        {"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 180},
        {"label": _("Department"), "fieldname": "department", "fieldtype": "Link", "options": "Department", "width": 160},
        {"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 130},
        {"label": _("Designation"), "fieldname": "designation", "fieldtype": "Link", "options": "Designation", "width": 150},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 90},
        {"label": _("In Time"), "fieldname": "in_time", "fieldtype": "Time", "width": 90},
        {"label": _("Out Time"), "fieldname": "out_time", "fieldtype": "Time", "width": 90},
        {"label": _("Approved Working Hours"), "fieldname": "total_hours", "fieldtype": "Float", "width": 100},
        {"label": _("Late Entry"), "fieldname": "late_entry", "fieldtype": "Data", "width": 90},
        {"label": _("Early Exit"), "fieldname": "early_exit", "fieldtype": "Data", "width": 90},
        {"label": _("Punches"), "fieldname": "punch_count", "fieldtype": "Int", "width": 70},
    ]
    columns.append({"label": _("Attendance State"), "fieldname": "attendance_state", "fieldtype": "Data", "width": 160})
    columns.append({"label": _("Attendance"), "fieldname": "attendance", "fieldtype": "Link", "options": "Attendance", "width": 150})
    filters.employee_names = permitted_employee_names(filters.company, branch=filters.branch, department=filters.department)
    if not filters.employee_names:
        return columns, []
    query = """
        WITH RECURSIVE dates AS (
            SELECT CAST(%(from_date)s AS DATE) AS attendance_date
            UNION ALL
            SELECT DATE_ADD(attendance_date, INTERVAL 1 DAY)
            FROM dates
            WHERE attendance_date < CAST(%(to_date)s AS DATE)
        ), checkins AS (
            SELECT employee, DATE(time) AS attendance_date,
                   MIN(time) AS first_checkin, MAX(time) AS last_checkin,
                   COUNT(name) AS punch_count
            FROM `tabEmployee Checkin`
            WHERE time >= CONCAT(%(from_date)s, ' 00:00:00')
              AND time < DATE_ADD(CONCAT(%(to_date)s, ' 00:00:00'), INTERVAL 1 DAY)
            GROUP BY employee, DATE(time)
        ), attendance_grid AS (
            SELECT
                d.attendance_date,
                e.name AS employee,
                e.employee_number AS employee_id,
                e.employee_name,
                e.department,
                e.branch,
                e.designation,
                CASE
                    WHEN a.status IS NOT NULL THEN a.status
                    WHEN h.holiday_date IS NOT NULL THEN 'Holiday'
                    WHEN d.attendance_date > CURDATE() THEN 'Not Started'
                    ELSE 'Not Marked'
                END AS status,
                a.name AS attendance,
                CASE WHEN a.docstatus=1 THEN 'Submitted Attendance'
                     WHEN a.docstatus=0 THEN 'Draft Attendance'
                     ELSE 'Not Marked' END AS attendance_state,
                TIME(a.in_time) AS in_time,
                TIME(a.out_time) AS out_time,
                CASE WHEN a.docstatus=1 THEN a.working_hours ELSE NULL END AS total_hours,
                IF(COALESCE(a.late_entry, 0) = 1, 'Yes', 'No') AS late_entry,
                IF(COALESCE(a.early_exit, 0) = 1, 'Yes', 'No') AS early_exit,
                COALESCE(c.punch_count, 0) AS punch_count
            FROM dates d
            CROSS JOIN `tabEmployee` e
            LEFT JOIN `tabAttendance` a
                ON a.employee = e.name
                AND a.attendance_date = d.attendance_date
                AND a.docstatus < 2
            LEFT JOIN checkins c
                ON c.employee = e.name
                AND c.attendance_date = d.attendance_date
            LEFT JOIN `tabHoliday` h
                ON h.parent = e.holiday_list
                AND h.holiday_date = d.attendance_date
            WHERE e.company = %(company)s
              AND e.name IN %(employee_names)s
              AND (e.status = 'Active' OR e.relieving_date >= %(to_date)s)
              AND (%(department)s = '' OR e.department = %(department)s)
              AND (%(branch)s = '' OR e.branch = %(branch)s)
        )
        SELECT * FROM attendance_grid
        WHERE %(status)s = '' OR status = %(status)s
        ORDER BY attendance_date, branch, department, employee
    """
    data = frappe.db.sql(query, filters, as_dict=True)
    return columns, data
