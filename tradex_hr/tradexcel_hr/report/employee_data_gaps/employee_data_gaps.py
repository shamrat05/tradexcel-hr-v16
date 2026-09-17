"""Active-employee data quality radar with evidence and drill-down for correction."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate, today


GAP_DEFINITIONS = (
    ("no_department", "Missing Department", "High", "Set the employee's Department"),
    ("no_employee_number", "Missing Employee Number", "High", "Assign an Employee Number"),
    ("no_active_assignment", "No Active Salary Assignment", "High", "Create a Salary Structure Assignment effective on or before today"),
    ("duplicate_active_assignments", "Multiple Active Salary Assignments", "Medium", "Cancel the superseded assignment so one active structure remains"),
    ("wage_structure_not_worker", "Latest Structure Is a Wage Structure", "High", "Confirm the employment type and pay basis"),
    ("worker_without_wage_structure", "Worker Without Wage Structure", "High", "Assign a wage Salary Structure or confirm the employment type"),
    ("future_doj_with_punches", "Future Joining Date With Punches", "High", "Verify Date of Joining and assignment date against device punches"),
    ("no_designation", "Missing Designation", "Medium", "Set the Designation"),
    ("no_date_of_birth", "Missing Date of Birth", "Low", "Complete Date of Birth from HR documents"),
    ("no_holiday_list", "Missing Holiday List", "Low", "Assign a Holiday List"),
)
GAP_ORDER = {key: index for index, (key, *_rest) in enumerate(GAP_DEFINITIONS)}
GAP_BY_LABEL = {label: key for key, label, *_rest in GAP_DEFINITIONS}
PRIORITY_RANK = {"High": 0, "Medium": 1, "Low": 2}


def normalize_filters(filters=None):
    values = frappe._dict(filters or {})
    values.company = values.get("company") or "Tradexcel Ceramics Ltd."
    values.status = values.get("status") or "Active"
    values.branch = values.get("branch") or ""
    values.department = values.get("department") or ""
    values.employment_type = values.get("employment_type") or "All"
    values.gap_type = values.get("gap_type") or "All"
    values.priority = values.get("priority") or "All"
    if values.status not in {"Active", "Inactive", "Left", "All"}:
        raise ValueError(_("Invalid employee status"))
    if values.employment_type not in {"All", "Worker", "Non Worker"}:
        raise ValueError(_("Invalid employment type"))
    if values.gap_type != "All" and values.gap_type not in GAP_BY_LABEL:
        raise ValueError(_("Invalid gap"))
    if values.priority not in {"All", "High", "Medium", "Low"}:
        raise ValueError(_("Invalid priority"))
    return values


def employee_gaps(employee, latest_structure, wage_structures, punches_total, assignment_count=1, as_of=None):
    """Return gap keys for one employee; pure and testable via explicit as_of."""
    gaps = []
    if not employee.get("department"):
        gaps.append("no_department")
    if not employee.get("employee_number"):
        gaps.append("no_employee_number")
    if not latest_structure:
        gaps.append("no_active_assignment")
    if int(assignment_count or 0) > 1:
        gaps.append("duplicate_active_assignments")
    is_worker = employee.get("employment_type") == "Worker"
    has_wage = bool(latest_structure) and latest_structure in wage_structures
    if not is_worker and has_wage:
        gaps.append("wage_structure_not_worker")
    if is_worker and not has_wage:
        gaps.append("worker_without_wage_structure")
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
        {"label": _("Assignments"), "fieldname": "assignment_count", "fieldtype": "Int", "width": 90},
        {"label": _("First Punch"), "fieldname": "first_punch", "fieldtype": "Date", "width": 90},
        {"label": _("Last Punch"), "fieldname": "last_punch", "fieldtype": "Date", "width": 90},
        {"label": _("Punches"), "fieldname": "punches_total", "fieldtype": "Int", "width": 80},
        {"label": _("Gaps"), "fieldname": "gaps", "fieldtype": "Data", "width": 280},
        {"label": _("Priority"), "fieldname": "priority", "fieldtype": "Data", "width": 80},
        {"label": _("Suggested Action"), "fieldname": "suggested_action", "fieldtype": "Data", "width": 330},
    ]


def execute(filters=None):
    filters = normalize_filters(filters)
    conditions = ["e.company = %(company)s"]
    if filters.status != "All":
        conditions.append("e.status = %(status)s")
    if filters.branch:
        conditions.append("e.branch = %(branch)s")
    if filters.department:
        conditions.append("e.department = %(department)s")
    if filters.employment_type == "Worker":
        conditions.append("e.employment_type = 'Worker'")
    elif filters.employment_type == "Non Worker":
        conditions.append("e.employment_type != 'Worker'")

    employees = frappe.db.sql(
        f"""
        SELECT e.name, e.employee_number, e.employee_name, e.branch, e.department,
               e.designation, e.employment_type, e.status, e.date_of_joining,
               e.date_of_birth, e.holiday_list
        FROM `tabEmployee` e
        WHERE {' AND '.join(conditions)}
        ORDER BY e.branch, e.department, e.name
        """,
        filters, as_dict=True,
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
    wage_structures = set(frappe.get_all(
        "Salary Structure", filters={"name": ["like", "%Wage%"]}, pluck="name"
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
            wage_structures,
            punch_total,
            int(assignment_counts.get(employee.name, 0)),
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
