"""Active-employee data quality radar with evidence and drill-down for correction."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate, today

from workforce_suite.workforce_suite.company_context import assert_company_access, resolve_company
from workforce_suite.workforce_suite.pay_basis import CONFLICT, DAILY, MONTHLY, resolve_pay_basis
from workforce_suite.workforce_suite.report_scope import permitted_employee_names


GAP_DEFINITIONS = (
    ("no_department", "Missing Department", "High", "Use native Employee Transfer to set Department"),
    ("no_employee_number", "Missing Employee Number", "High", "Verify and update Employee Number"),
    ("no_active_assignment", "No Active Salary Assignment", "High", "Prepare a native Salary Structure Assignment"),
    ("no_shift_assignment", "No Shift Assignment", "High", "Open native Shift Assignment Tool"),
    ("conflicting_assignments", "Conflicting Salary Assignments", "High", "Review same-date submitted Salary Structure Assignments"),
    ("pay_basis_unresolved", "Pay Basis Needs Review", "High", "Review the explicit pay basis on the assigned Salary Structure"),
    ("future_doj_with_punches", "Future Joining Date With Punches", "High", "Review Date of Joining against Employee Checkin evidence"),
    ("no_designation", "Missing Designation", "Medium", "Use native Employee Promotion to set Designation"),
    ("no_date_of_birth", "Missing Date of Birth", "Low", "Verify Date of Birth in Employee"),
    ("no_holiday_list", "Missing Holiday List", "Low", "Review the Employee Holiday List"),
)
GAP_ORDER = {key: index for index, (key, *_rest) in enumerate(GAP_DEFINITIONS)}
GAP_BY_LABEL = {label: key for key, label, *_rest in GAP_DEFINITIONS}
PRIORITY_RANK = {"High": 0, "Medium": 1, "Low": 2}


def normalize_filters(filters=None):
    values = frappe._dict(filters or {})
    values.company = resolve_company(values)
    values.status = values.get("status") or "Active"
    values.branch = values.get("branch") or ""
    values.department = values.get("department") or ""
    values.employment_type = values.get("employment_type") or ""
    values.employee = values.get("employee") or ""
    values.gap_type = values.get("gap_type") or "All"
    values.priority = values.get("priority") or "All"
    if values.status not in {"Active", "Inactive", "Left", "All"}:
        raise ValueError(_("Invalid employee status"))
    if values.gap_type != "All" and values.gap_type not in GAP_BY_LABEL:
        raise ValueError(_("Invalid gap"))
    if values.priority not in {"All", "High", "Medium", "Low"}:
        raise ValueError(_("Invalid priority"))
    return values


def employee_gaps(employee, latest_structure, pay_basis_status, punches_total, as_of=None, has_shift_assignment=True):
    """Return gap keys for one employee; pure and testable via explicit as_of."""
    gaps = []
    if not employee.get("department"):
        gaps.append("no_department")
    if not employee.get("employee_number"):
        gaps.append("no_employee_number")
    if not has_shift_assignment:
        gaps.append("no_shift_assignment")
    if not latest_structure:
        gaps.append("no_active_assignment")
    elif pay_basis_status == CONFLICT:
        gaps.append("conflicting_assignments")
    elif pay_basis_status not in {MONTHLY, DAILY}:
        gaps.append("pay_basis_unresolved")
    date_of_joining = employee.get("date_of_joining")
    reference_day = getdate(as_of) if as_of else getdate(today())
    if date_of_joining and getdate(date_of_joining) > reference_day and punches_total:
        gaps.append("future_doj_with_punches")
    if not employee.get("designation"):
        gaps.append("no_designation")
    if not employee.get("date_of_birth"):
        gaps.append("no_date_of_birth")
    if not employee.get("holiday_list"):
        gaps.append("no_holiday_list")
    return sorted(set(gaps), key=lambda key: GAP_ORDER[key])


def _columns():
    return [
        {"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 120},
        {"label": _("Employee ID"), "fieldname": "employee_number", "fieldtype": "Data", "width": 100},
        {"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 180},
        {"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 130},
        {"label": _("Department"), "fieldname": "department", "fieldtype": "Link", "options": "Department", "width": 150},
        {"label": _("Designation"), "fieldname": "designation", "fieldtype": "Link", "options": "Designation", "width": 140},
        {"label": _("Employment Type"), "fieldname": "employment_type", "fieldtype": "Data", "width": 110},
        {"label": _("Date of Joining"), "fieldname": "date_of_joining", "fieldtype": "Date", "width": 100},
        {"label": _("Latest Assignment"), "fieldname": "latest_assignment", "fieldtype": "Data", "width": 230},
        {"label": _("Assignment From"), "fieldname": "assignment_from", "fieldtype": "Date", "width": 100},
        {"label": _("Submitted Assignments"), "fieldname": "assignment_count", "fieldtype": "Int", "width": 120},
        {"label": _("First Punch"), "fieldname": "first_punch", "fieldtype": "Date", "width": 90},
        {"label": _("Last Punch"), "fieldname": "last_punch", "fieldtype": "Date", "width": 90},
        {"label": _("Punches"), "fieldname": "punches_total", "fieldtype": "Int", "width": 80},
        {"label": _("Gaps"), "fieldname": "gaps", "fieldtype": "Data", "width": 280},
        {"label": _("Priority"), "fieldname": "priority", "fieldtype": "Data", "width": 80},
        {"label": _("Suggested Action"), "fieldname": "suggested_action", "fieldtype": "Data", "width": 330},
    ]


def execute(filters=None):
    filters = normalize_filters(filters)
    assert_company_access(filters.company)
    employee_names = permitted_employee_names(
        filters.company, branch=filters.branch, department=filters.department,
    )
    if not employee_names:
        return _columns(), []
    conditions = ["e.company = %(company)s", "e.name IN %(employee_names)s"]
    if filters.status != "All":
        conditions.append("e.status = %(status)s")
    if filters.branch:
        conditions.append("e.branch = %(branch)s")
    if filters.department:
        conditions.append("e.department = %(department)s")
    if filters.employment_type:
        conditions.append("e.employment_type = %(employment_type)s")
    if filters.employee:
        conditions.append("e.name = %(employee)s")

    employees = frappe.db.sql(
        f"""
        SELECT e.name, e.employee_number, e.employee_name, e.branch, e.department,
               e.designation, e.employment_type, e.status, e.date_of_joining,
               e.date_of_birth, e.holiday_list
        FROM `tabEmployee` e
        WHERE {' AND '.join(conditions)}
        ORDER BY e.branch, e.department, e.name
        """,
        {**filters, "employee_names": employee_names}, as_dict=True,
    )
    if not employees:
        return _columns(), []
    names = [row.name for row in employees]

    latest = {
        row.employee: row
        for row in frappe.db.sql(
            """
            WITH ranked AS (
                SELECT employee, salary_structure, from_date,
                       ROW_NUMBER() OVER (
                           PARTITION BY employee
                           ORDER BY from_date DESC, creation DESC
                       ) AS rn
                FROM `tabSalary Structure Assignment`
                WHERE docstatus = 1 AND from_date <= %(today)s AND employee IN %(names)s
            )
            SELECT employee, salary_structure, from_date FROM ranked WHERE rn = 1
            """,
            {"names": names, "today": today()}, as_dict=True,
        )
    }
    assignment_counts = {
        row.employee: int(row.n)
        for row in frappe.db.sql(
            """
            SELECT employee, COUNT(*) AS n FROM `tabSalary Structure Assignment`
            WHERE docstatus = 1 AND employee IN %(names)s
            GROUP BY employee
            """,
            {"names": names}, as_dict=True,
        )
    }
    as_of_date = today()
    shift_assigned = set(frappe.db.sql(
        """SELECT DISTINCT employee FROM `tabShift Assignment`
           WHERE docstatus=1 AND employee IN %(names)s
             AND start_date<=%(as_of)s
             AND (end_date IS NULL OR end_date>=%(as_of)s)""",
        {"names": names, "as_of": as_of_date}, pluck=True,
    ))
    punches = {
        row.employee: row
        for row in frappe.db.sql(
            """
            SELECT employee, COUNT(*) AS punches, MIN(time) AS first_punch, MAX(time) AS last_punch
            FROM `tabEmployee Checkin`
            WHERE employee IN %(names)s
            GROUP BY employee
            """,
            {"names": names}, as_dict=True,
        )
    }

    rows = []
    for employee in employees:
        assignment = latest.get(employee.name)
        punch = punches.get(employee.name)
        punch_total = int(punch.punches) if punch else 0
        gaps = employee_gaps(
            employee,
            assignment.salary_structure if assignment else None,
            resolve_pay_basis(employee.name, as_of_date).get("status"),
            punch_total,
            has_shift_assignment=employee.name in shift_assigned,
        )
        if not gaps:
            continue
        if filters.gap_type != "All" and GAP_BY_LABEL[filters.gap_type] not in gaps:
            continue
        labels = []
        actions = []
        severities = []
        for key, label, severity, action in GAP_DEFINITIONS:
            if key not in gaps:
                continue
            labels.append(label)
            severities.append(severity)
            if action not in actions:
                actions.append(action)
        priority = sorted(severities, key=lambda value: PRIORITY_RANK[value])[0]
        if filters.priority != "All" and priority != filters.priority:
            continue
        rows.append({
            "employee": employee.name,
            "employee_number": employee.employee_number,
            "employee_name": employee.employee_name,
            "branch": employee.branch,
            "department": employee.department,
            "designation": employee.designation,
            "employment_type": employee.employment_type,
            "date_of_joining": employee.date_of_joining,
            "latest_assignment": assignment.salary_structure if assignment else "",
            "assignment_from": assignment.from_date if assignment else None,
            "assignment_count": int(assignment_counts.get(employee.name, 0)),
            "first_punch": str(punch.first_punch)[:10] if punch and punch.first_punch else None,
            "last_punch": str(punch.last_punch)[:10] if punch and punch.last_punch else None,
            "punches_total": punch_total,
            "gaps": ", ".join(labels),
            "priority": priority,
            "suggested_action": " | ".join(actions),
        })

    rows.sort(key=lambda row: (
        PRIORITY_RANK[row["priority"]], row["branch"] or "",
        row["department"] or "", row["employee"],
    ))
    return _columns(), rows
