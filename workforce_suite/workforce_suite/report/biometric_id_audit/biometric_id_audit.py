"""Device-scoped audit of biometric assignments and unmapped employees."""

from __future__ import annotations

from collections import Counter, defaultdict

import frappe
from frappe import _


SOURCE_FIELD = "workforce_source_employee_id"


def _clean(value):
    return str(value).strip() if value not in (None, "") else ""


def _filters(filters):
    filters = frappe._dict(filters or {})
    employee_filters = {}
    if filters.get("company"):
        employee_filters["company"] = filters.company
    if filters.get("employee_status") and filters.employee_status != "All":
        employee_filters["status"] = filters.employee_status
    return employee_filters, filters


def _assignment_rows(filters):
    conditions = ["a.enabled=1"]
    values = {}
    if filters.get("company"):
        conditions.append("e.company=%(company)s")
        values["company"] = filters.company
    if filters.get("employee_status") and filters.employee_status != "All":
        conditions.append("e.status=%(employee_status)s")
        values["employee_status"] = filters.employee_status
    if filters.get("device"):
        conditions.append("a.device=%(device)s")
        values["device"] = filters.device
    source_field = f"e.{SOURCE_FIELD}" if frappe.get_meta("Employee").has_field(SOURCE_FIELD) else "NULL"
    return frappe.db.sql(
        f"""SELECT a.name AS assignment, a.employee, a.biometric_id,
                   a.enrollment_status, a.source, a.device_serial,
                   d.name AS device, d.device_code, d.device_name,
                   e.employee_name, e.employee_number, e.company, e.branch,
                   e.department, {source_field} AS source_employee_id
              FROM `tabWorkforce Employee Biometric` a
              JOIN `tabWorkforce Biometric Device` d ON d.name=a.device
              JOIN `tabEmployee` e ON e.name=a.employee
             WHERE {' AND '.join(conditions)}""",
        values,
        as_dict=True,
    )


def _columns():
    return [
        {"label": _("Device"), "fieldname": "device", "fieldtype": "Link", "options": "Workforce Biometric Device", "width": 130},
        {"label": _("Device Serial"), "fieldname": "device_serial", "fieldtype": "Data", "width": 130},
        {"label": _("Biometric ID"), "fieldname": "biometric_id", "fieldtype": "Data", "width": 130},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 190},
        {"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 120},
        {"label": _("Employee ID"), "fieldname": "employee_id", "fieldtype": "Data", "width": 110},
        {"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 180},
        {"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 160},
        {"label": _("Home Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 140},
        {"label": _("Department"), "fieldname": "department", "fieldtype": "Link", "options": "Department", "width": 180},
        {"label": _("Selevo Employee ID"), "fieldname": "source_employee_id", "fieldtype": "Data", "width": 130},
        {"label": _("Assignment"), "fieldname": "assignment", "fieldtype": "Link", "options": "Workforce Employee Biometric", "width": 120},
    ]


def execute(filters=None):
    employee_filters, filters = _filters(filters)
    duplicates_only = filters.get("show_duplicates") == "Yes" or filters.get("assignment_status") == "Duplicate"
    wanted_status = filters.get("assignment_status") or "All"

    employee_fields = [
        "name", "employee_name", "employee_number", "company", "branch",
        "department", "attendance_device_id",
    ]
    has_source_field = frappe.get_meta("Employee").has_field(SOURCE_FIELD)
    if has_source_field:
        employee_fields.append(SOURCE_FIELD)
    employees = frappe.get_list(
        "Employee", filters=employee_filters, fields=employee_fields, limit_page_length=0
    )
    assignments = _assignment_rows(filters)
    assignments_by_employee = defaultdict(list)
    device_pin_counts = Counter()
    for row in assignments:
        key = (_clean(row.device_serial), _clean(row.biometric_id))
        assignments_by_employee[row.employee].append(row)
        device_pin_counts[key] += 1

    data = []
    for employee in employees:
        rows = assignments_by_employee.get(employee.name, [])
        if rows:
            for row in rows:
                key = (_clean(row.device_serial), _clean(row.biometric_id))
                status = row.enrollment_status or "Pending"
                if device_pin_counts[key] > 1:
                    status = "DUPLICATE DEVICE/PIN"
                elif status == "Enrolled":
                    status = "Unique / Enrolled"
                else:
                    status = f"Unique / {status}"
                data.append({
                    "device": row.device,
                    "device_serial": row.device_serial,
                    "biometric_id": row.biometric_id,
                    "status": status,
                    "employee": row.employee,
                    "employee_id": row.employee_number,
                    "employee_name": row.employee_name,
                    "company": row.company,
                    "branch": row.branch,
                    "department": row.department,
                    "source_employee_id": row.source_employee_id,
                    "assignment": row.assignment,
                })
        elif not filters.get("device") and _clean(employee.get("attendance_device_id")):
            data.append({
                "device": None,
                "device_serial": None,
                "biometric_id": employee.attendance_device_id,
                "status": "Legacy Global PIN - Assign Device",
                "employee": employee.name,
                "employee_id": employee.employee_number,
                "employee_name": employee.employee_name,
                "company": employee.company,
                "branch": employee.branch,
                "department": employee.department,
                "source_employee_id": employee.get(SOURCE_FIELD),
                "assignment": None,
            })
        else:
            data.append({
                "device": filters.get("device"),
                "device_serial": None,
                "biometric_id": None,
                "status": "Missing Biometric Assignment",
                "employee": employee.name,
                "employee_id": employee.employee_number,
                "employee_name": employee.employee_name,
                "company": employee.company,
                "branch": employee.branch,
                "department": employee.department,
                "source_employee_id": employee.get(SOURCE_FIELD),
                "assignment": None,
            })

    if wanted_status == "Assigned":
        data = [row for row in data if row["assignment"]]
    elif wanted_status == "Unassigned":
        data = [row for row in data if not row["assignment"]]
    elif wanted_status == "Duplicate" or duplicates_only:
        data = [row for row in data if row["status"] == "DUPLICATE DEVICE/PIN"]
    elif wanted_status == "Legacy":
        data = [row for row in data if row["status"].startswith("Legacy")]

    data.sort(key=lambda row: (
        _clean(row.get("device")), _clean(row.get("device_serial")),
        _clean(row.get("employee_name")), _clean(row.get("biometric_id")),
    ))
    return _columns(), data
