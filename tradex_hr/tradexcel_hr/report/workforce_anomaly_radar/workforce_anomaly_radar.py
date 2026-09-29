"""Statistical and consistency anomaly radar across checkin, attendance, payroll and leave."""

from __future__ import annotations

from datetime import timedelta
from statistics import median

import frappe
from frappe import _
from frappe.utils import add_days, getdate, today

from tradex_hr.tradexcel_hr.company_context import assert_company_access, resolve_company

from tradex_hr.tradexcel_hr.report_scope import permitted_employee_names, permitted_salary_slips
from tradex_hr.tradexcel_hr.pay_basis import DAILY, MONTHLY, resolve_pay_basis

from tradex_hr.tradexcel_hr.anomaly_checks import SEVERITY_RANK, pair_punches, run_all


DEFAULT_Z_THRESHOLD = 3.5
DEFAULT_MIN_COHORT = 5
DEFAULT_MIN_PREVIOUS = 5
MIN_PAIRED_DAYS = 3
ARITHMETIC_TOLERANCE = 0.01
CATEGORIES = ("All", "Checkin", "Attendance", "Payroll", "Leave", "Tax")
SEVERITIES = ("All", "High", "Medium", "Low")


def normalize_filters(filters=None):
    values = frappe._dict(filters or {})
    values.company = resolve_company(values)
    values.branch = values.get("branch") or ""
    values.department = values.get("department") or ""
    values.category = values.get("category") or "All"
    values.severity = values.get("severity") or "All"
    values.from_date = getdate(values.get("from_date") or today()).replace(day=1)
    values.to_date = getdate(values.get("to_date") or today())
    values.z_threshold = float(values.get("z_threshold") or DEFAULT_Z_THRESHOLD)
    values.min_cohort = int(values.get("min_cohort") or DEFAULT_MIN_COHORT)
    if values.to_date < values.from_date:
        raise ValueError(_("To Date must not precede From Date"))
    if values.z_threshold <= 0:
        raise ValueError(_("Z threshold must be positive"))
    if values.min_cohort < 2:
        raise ValueError(_("Minimum cohort must be at least 2"))
    if values.category not in CATEGORIES:
        raise ValueError(_("Invalid category"))
    if values.severity not in SEVERITIES:
        raise ValueError(_("Invalid severity"))
    return values


def _columns():
    return [
        {"label": _("Category"), "fieldname": "category", "fieldtype": "Data", "width": 100},
        {"label": _("Severity"), "fieldname": "severity", "fieldtype": "Data", "width": 80},
        {"label": _("Scope"), "fieldname": "scope", "fieldtype": "Data", "width": 80},
        {"label": _("Subject"), "fieldname": "subject", "fieldtype": "Data", "width": 180},
        {"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 110},
        {"label": _("Metric"), "fieldname": "metric", "fieldtype": "Data", "width": 220},
        {"label": _("Observed"), "fieldname": "observed", "fieldtype": "Data", "width": 220},
        {"label": _("Baseline"), "fieldname": "baseline", "fieldtype": "Data", "width": 200},
        {"label": _("Deviation"), "fieldname": "deviation", "fieldtype": "Data", "width": 140},
        {"label": _("Detail"), "fieldname": "detail", "fieldtype": "Data", "width": 320},
        {"label": _("Suggested Action"), "fieldname": "suggested_action", "fieldtype": "Data", "width": 320},
    ]


def _employee_rows(filters):
    names = permitted_employee_names(filters.company, branch=filters.branch, department=filters.department)
    if not names:
        return []
    return frappe.get_list(
        "Employee", filters={"name": ["in", names], "status": "Active"},
        fields=["name", "employee_name", "branch", "department", "date_of_joining"],
        order_by="name", limit_page_length=0,
    )


def execute(filters=None):
    from frappe.desk.query_report import get_report_doc

    get_report_doc("Workforce Anomaly Radar")
    filters = normalize_filters(filters)
    assert_company_access(filters.company)
    columns = _columns()
    employees = _employee_rows(filters)
    names = [row.name for row in employees]
    if not names:
        return columns, []
    employee_by_name = {row.name: row for row in employees}

    start = f"{filters.from_date} 00:00:00"
    end = f"{add_days(filters.to_date, 1)} 00:00:00"
    period_days = (filters.to_date - filters.from_date).days + 1
    previous_start = f"{add_days(filters.from_date, -period_days)} 00:00:00"
    previous_end = start

    salary_allowed = frappe.has_permission("Salary Slip", "read") and frappe.has_permission("Salary Slip", "report")
    if filters.category in {"Payroll", "Tax"} and not salary_allowed:
        frappe.throw(_("You do not have permission to view payroll findings."), frappe.PermissionError)
    slips = permitted_salary_slips(
        filters.company, tuple(names), from_date=filters.from_date, to_date=filters.to_date,
        overlapping_period=True,
    ) if salary_allowed else []
    pair_start = min([filters.from_date] + [getdate(slip.start_date) for slip in slips]) - timedelta(days=1)
    pair_end = max([filters.to_date] + [getdate(slip.end_date) for slip in slips]) + timedelta(days=2)

    events_by_employee = {}
    for row in frappe.db.sql(
        """
        SELECT employee, time, log_type FROM `tabEmployee Checkin`
        WHERE employee IN %(names)s AND time >= %(start)s AND time < %(end)s
        ORDER BY employee, time
        """,
        {"names": names, "start": f"{pair_start} 00:00:00", "end": f"{pair_end} 00:00:00"}, as_dict=True,
    ):
        events_by_employee.setdefault(row.employee, []).append((row.time, row.log_type))

    checkin_dates = [moment.date() for events in events_by_employee.values() for moment, _lt in events]
    checkin_span = (
        f"{min(checkin_dates)} to {max(checkin_dates)}" if checkin_dates else "no device data"
    )

    pairs_by_employee, punch_issues = {}, []
    for employee, events in events_by_employee.items():
        pairs, issues = pair_punches(events)
        pairs_by_employee[employee] = pairs
        if issues["extra_ins"] or issues["orphan_outs"] or issues["unclosed"]:
            punch_issues.append({
                "employee": employee,
                "employee_name": employee_by_name[employee].employee_name,
                **issues,
            })

    duration_observations = []
    for employee, pairs in pairs_by_employee.items():
        if len(pairs) < MIN_PAIRED_DAYS:
            continue
        minutes = [(out - inn).total_seconds() / 60.0 for inn, out in pairs]
        duration_observations.append({
            "key": employee,
            "cohort": employee_by_name[employee].department or "",
            "value": float(median(minutes)),
            "employee": employee,
            "employee_name": employee_by_name[employee].employee_name,
            "days": len(minutes),
        })

    previous_counts = {
        row.employee: int(row.n)
        for row in frappe.db.sql(
            """
            SELECT employee, COUNT(*) AS n FROM `tabEmployee Checkin`
            WHERE employee IN %(names)s AND time >= %(start)s AND time < %(end)s
            GROUP BY employee
            """,
            {"names": names, "start": previous_start, "end": previous_end}, as_dict=True,
        )
    }
    current_counts = {
        employee: sum(1 for moment, _log_type in events
                      if filters.from_date <= moment.date() <= filters.to_date)
        for employee, events in events_by_employee.items()
    }
    punch_trend_observations = [
        {
            "key": employee,
            "cohort": employee_by_name[employee].department or "",
            "current": current_counts.get(employee, 0),
            "previous": previous_counts.get(employee, 0),
            "employee": employee,
            "employee_name": employee_by_name[employee].employee_name,
        }
        for employee in names
        if current_counts.get(employee, 0) or previous_counts.get(employee, 0)
    ]

    attendance_rows = frappe.db.sql(
        """
        SELECT a.employee, a.employee_name, a.attendance_date, a.status
        FROM `tabAttendance` a
        WHERE a.docstatus < 2 AND a.attendance_date BETWEEN %(from)s AND %(to)s
          AND a.employee IN %(names)s
        """,
        {"from": filters.from_date, "to": filters.to_date, "names": names}, as_dict=True,
    )

    approved_leave = frappe.get_all(
        "Leave Application", filters={"docstatus": 1, "employee": ["in", names]},
        fields=["employee", "employee_name", "leave_type", "from_date", "to_date", "total_leave_days"],
    )
    leave_cover = set()
    for row in approved_leave:
        day = getdate(row.from_date)
        last = min(getdate(row.to_date), filters.to_date)
        while day <= last:
            if day >= filters.from_date:
                leave_cover.add(f"{row.employee}|{day.isoformat()}")
            day += timedelta(days=1)

    paired_days = {
        employee: {inn.date().isoformat() for inn, _out in pairs
                   if filters.from_date <= inn.date() <= filters.to_date}
        for employee, pairs in pairs_by_employee.items()
    }
    allocations_all = frappe.get_all(
        "Leave Allocation", filters={"docstatus": 1, "employee": ["in", names]},
        fields=["name", "employee", "leave_type", "from_date", "to_date", "total_leaves_allocated"],
    )
    used_by_key = {}
    for application in approved_leave:
        for allocation in allocations_all:
            if (application.employee == allocation.employee
                    and application.leave_type == allocation.leave_type
                    and getdate(application.from_date) <= getdate(allocation.to_date)
                    and getdate(application.to_date) >= getdate(allocation.from_date)):
                used_by_key[allocation.name] = used_by_key.get(allocation.name, 0.0) + float(
                    application.total_leave_days or 0
                )
    leave_balances = [
        {
            "employee": row.employee,
            "employee_name": employee_by_name[row.employee].employee_name,
            "leave_type": row.leave_type,
            "allocated": float(row.total_leaves_allocated or 0),
            "used": used_by_key.get(row.name, 0.0),
        }
        for row in allocations_all
        if getdate(row.from_date) <= filters.to_date and getdate(row.to_date) >= filters.from_date
    ]
    leave_without_allocation = []
    for application in approved_leave:
        if not (getdate(application.from_date) <= filters.to_date
                and getdate(application.to_date) >= filters.from_date):
            continue
        covered = any(
            application.employee == allocation.employee
            and application.leave_type == allocation.leave_type
            and getdate(application.from_date) <= getdate(allocation.to_date)
            and getdate(application.to_date) >= getdate(allocation.from_date)
            for allocation in allocations_all
        )
        if not covered:
            leave_without_allocation.append({
                "employee": application.employee,
                "employee_name": application.employee_name,
                "leave_type": application.leave_type,
                "days": application.total_leave_days,
                "from_date": str(application.from_date),
            })

    slip_names = [slip.name for slip in slips]
    earning_totals, deduction_totals = {}, {}
    if slip_names:
        for parentfield, target in (("earnings", earning_totals), ("deductions", deduction_totals)):
            target.update({
                row.parent: float(row.total or 0)
                for row in frappe.db.sql(
                    """
                    SELECT parent, SUM(amount) AS total FROM `tabSalary Detail`
                    WHERE parenttype = 'Salary Slip' AND parentfield = %(field)s
                      AND parent IN %(names)s AND IFNULL(do_not_include_in_total, 0)=0
                    GROUP BY parent
                    """,
                    {"field": parentfield, "names": slip_names}, as_dict=True,
                )
            })

    base_observations = []
    if salary_allowed and frappe.has_permission("Salary Structure Assignment", "read"):
        visible_assignments = set(frappe.get_list(
            "Salary Structure Assignment",
            filters={"company": filters.company, "employee": ["in", names], "docstatus": 1,
                     "from_date": ["<=", filters.to_date]},
            pluck="name", limit_page_length=0,
        ))
        for employee in names:
            authority = resolve_pay_basis(employee, filters.to_date)
            if (authority.get("status") in {MONTHLY, DAILY}
                    and authority.get("assignment") in visible_assignments
                    and float(authority.get("base") or 0) > 0):
                base_observations.append({
                    "key": employee, "cohort": authority["salary_structure"],
                    "value": float(authority["base"]), "employee": employee,
                    "employee_name": employee_by_name[employee].employee_name,
                })
    tax_allowed = salary_allowed and frappe.has_permission("Income Tax Slab", "read")
    tax_slab_count = len(frappe.get_list(
        "Income Tax Slab", filters={"company": filters.company, "docstatus": 1},
        pluck="name", limit_page_length=0,
    )) if tax_allowed else 0

    assigned_employees = {
        row["employee"]
        for row in frappe.get_all(
            "Shift Assignment",
            filters={"docstatus": 1, "employee": ["in", names]},
            fields=["employee"],
            distinct=True,
        )
    }
    no_shift_assignment = [
        {"employee": row.name, "employee_name": row.employee_name}
        for row in employees
        if row.name not in assigned_employees
    ]
    attendance_scope = frappe.db.sql(
        """
        SELECT COUNT(*) total, SUM(IFNULL(shift, '') = '') no_shift
        FROM `tabAttendance`
        WHERE employee IN %(names)s AND attendance_date BETWEEN %(from_date)s AND %(to_date)s
        """,
        {"names": names, "from_date": filters.from_date, "to_date": filters.to_date},
        as_dict=True,
    )[0]
    attendance_no_shift = {
        "rows": int(attendance_scope.no_shift or 0),
        "total": int(attendance_scope.total or 0),
    }

    context = {
        "z_threshold": filters.z_threshold,
        "min_cohort": filters.min_cohort,
        "min_previous": DEFAULT_MIN_PREVIOUS,
        "tolerance": ARITHMETIC_TOLERANCE,
        "punch_issues": punch_issues,
        "duration_observations": duration_observations,
        "punch_trend_observations": punch_trend_observations,
        "attendance_rows": attendance_rows,
        "paired_days": paired_days,
        "leave_cover": leave_cover,
        "slips": slips,
        "earning_totals": earning_totals,
        "deduction_totals": deduction_totals,
        "base_observations": base_observations,
        "leave_balances": leave_balances,
        "leave_without_allocation": leave_without_allocation,
        "active_slip_count": len(slips) if tax_allowed else 0,
        "tax_slab_count": tax_slab_count,
        "company_name": filters.company,
        "period_to_date": filters.to_date,
        "checkin_span": checkin_span,
        "no_shift_assignment": no_shift_assignment,
        "attendance_no_shift": attendance_no_shift,
    }

    rows = []
    for finding in run_all(context):
        if filters.category != "All" and finding["category"] != filters.category:
            continue
        if filters.severity != "All" and finding["severity"] != filters.severity:
            continue
        rows.append({
            "category": finding["category"],
            "severity": finding["severity"],
            "scope": finding["scope"],
            "subject": finding["subject"],
            "employee": finding["employee"] or "",
            "metric": finding["metric"],
            "observed": finding["observed"],
            "baseline": finding["baseline"],
            "deviation": finding["deviation"],
            "detail": finding["detail"],
            "suggested_action": finding["action"],
        })
    rows.sort(key=lambda row: (
        SEVERITY_RANK[row["severity"]], row["category"], row["subject"], row["metric"],
    ))
    return columns, rows
