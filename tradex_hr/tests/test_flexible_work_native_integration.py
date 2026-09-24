"""Disposable native HRMS v16 proof for flexible Daily Wage and shift selection."""
from datetime import date, datetime, timedelta
import os

import frappe
import pytest
from hrms.hr.doctype.shift_assignment.shift_assignment import get_employee_shift
from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip
from hrms.payroll.doctype.salary_structure.salary_structure import make_salary_slip

from tradex_hr.tradexcel_hr.daily_wage_input import _native_attendance_units

from tradex_hr.tradexcel_hr import daily_wage_input
from tradex_hr.tradexcel_hr.flexible_work_records import validate_operational_day_overrides


@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(
        site=os.environ.get("FRAPPE_TEST_SITE", "hrms-v16.localhost"),
        sites_path=os.environ.get("FRAPPE_TEST_SITES_PATH", "/home/sanchita/frappe-bench-v16/sites"),
        force=True,
    )
    frappe.connect()
    old_user = frappe.session.user
    frappe.set_user("Administrator")
    yield
    frappe.set_user(old_user)
    frappe.destroy()


def _active_tcl_employee_without_december_shift():
    assignments = frappe.get_all(
        "Shift Assignment",
        filters={"docstatus": 1, "status": "Active", "start_date": ["<=", "2026-12-10"]},
        fields=["employee", "end_date"],
    )
    occupied = {
        row.employee for row in assignments
        if not row.end_date or str(row.end_date) >= "2026-12-01"
    }
    employees = frappe.get_all(
        "Employee",
        filters={"company": "Tradexcel Ceramics Ltd.", "status": "Active"},
        fields=["name"],
        order_by="name",
    )
    for employee in employees:
        if employee.name not in occupied:
            return employee.name
    return None


def _safe_structure(employee, suffix):
    company = frappe.db.get_value("Employee", employee, "company")
    structure = frappe.get_doc({
        "doctype": "Salary Structure",
        "name": f"TEST Flexible Daily {suffix}",
        "company": company,
        "currency": "BDT",
        "payroll_frequency": "Monthly",
        "is_active": "Yes",
        "custom_tradex_pay_basis": "Daily Wage",
        "earnings": [{"salary_component": "Daily Wage", "amount": 0, "depends_on_payment_days": 0}],
    })
    structure.insert(ignore_permissions=True)
    structure.submit()
    assignment = frappe.get_doc({
        "doctype": "Salary Structure Assignment",
        "employee": employee,
        "company": company,
        "currency": "BDT",
        "salary_structure": structure.name,
        "from_date": "2026-12-01",
        "base": 350,
        "payroll_payable_account": frappe.db.get_value("Company", company, "default_payroll_payable_account"),
    })
    assignment.insert(ignore_permissions=True)
    assignment.submit()
    return structure, assignment


def _attendance(employee, day, status, hours, half_day_status=None):
    company = frappe.db.get_value("Employee", employee, "company")
    doc = frappe.get_doc({
        "doctype": "Attendance",
        "employee": employee,
        "company": company,
        "attendance_date": day,
        "status": status,
        "working_hours": hours,
        "half_day_status": half_day_status,
    })
    doc.insert(ignore_permissions=True)
    doc.submit()
    return doc


def test_daily_wage_native_attendance_unit_parity_across_holiday_settings():
    """Compare the adapter with native Salary Slip semantics using disposable site records."""
    savepoint = "daily_wage_native_holiday_parity"
    frappe.db.savepoint(savepoint)
    suffix = frappe.generate_hash(7)
    company = "Tradexcel Ceramics Ltd."
    employee = None
    holiday_list = None
    leave_types = []
    settings_fields = (
        "payroll_based_on",
        "include_holidays_in_total_working_days",
        "consider_marked_attendance_on_holidays",
        "daily_wages_fraction_for_half_day",
        "consider_unmarked_attendance_as",
    )
    original_settings = {
        field: frappe.db.get_single_value("Payroll Settings", field)
        for field in settings_fields
    }
    try:
        holiday_list = frappe.get_doc({
            "doctype": "Holiday List",
            "holiday_list_name": f"TEST Native Parity {suffix}",
            "from_date": "2026-09-01",
            "to_date": "2026-09-06",
            "holidays": [{"holiday_date": "2026-09-03", "description": "Synthetic holiday"}],
        })
        holiday_list.insert(ignore_permissions=True)

        employee_doc = frappe.get_doc({
            "doctype": "Employee",
            "employee_name": f"TEST Native Parity {suffix}",
            "first_name": f"TEST Native Parity {suffix}",
            "company": company,
            "date_of_birth": "1990-01-01",
            "date_of_joining": "2020-01-01",
            "gender": "Female",
            "employment_type": "Intern",
            "holiday_list": holiday_list.name,
            "status": "Active",
        })
        employee_doc.insert(ignore_permissions=True)
        employee = employee_doc.name

        for title, flags in (
            (f"TEST LWP {suffix}", {"is_lwp": 1}),
            (f"TEST PPL {suffix}", {"is_ppl": 1, "fraction_of_daily_salary_per_leave": 0.5}),
        ):
            leave_type = frappe.get_doc({
                "doctype": "Leave Type",
                "leave_type_name": title,
                "include_holiday": 0,
                **flags,
            })
            leave_type.insert(ignore_permissions=True)
            leave_types.append(leave_type.name)
        frappe.clear_cache(doctype="Leave Type")

        attendance_rows = [
            ("2026-09-01", "Present", None, None),
            ("2026-09-02", "Half Day", None, "Absent"),
            ("2026-09-03", "Present", None, None),
            ("2026-09-04", "On Leave", leave_types[0], None),
            ("2026-09-05", "On Leave", leave_types[1], None),
            ("2026-09-06", "Absent", None, None),
        ]
        for day, status, leave_type, half_day_status in attendance_rows:
            _attendance(employee, day, status, 4 if status in {"Present", "Half Day"} else 0,
                        half_day_status=half_day_status)
            if leave_type:
                attendance_name = frappe.db.get_value(
                    "Attendance", {"employee": employee, "attendance_date": day, "docstatus": 1}, "name"
                )
                frappe.db.set_value("Attendance", attendance_name, "leave_type", leave_type)
        frappe.clear_cache(doctype="Payroll Settings")

        for include_holidays in (0, 1):
            for consider_marked in (0, 1):
                frappe.db.set_single_value("Payroll Settings", "payroll_based_on", "Attendance")
                frappe.db.set_single_value(
                    "Payroll Settings", "include_holidays_in_total_working_days", include_holidays
                )
                frappe.db.set_single_value(
                    "Payroll Settings", "consider_marked_attendance_on_holidays", consider_marked
                )
                frappe.db.set_single_value("Payroll Settings", "daily_wages_fraction_for_half_day", 0.5)
                frappe.db.set_single_value("Payroll Settings", "consider_unmarked_attendance_as", "Present")
                frappe.clear_cache(doctype="Payroll Settings")

                native_slip = SalarySlip({
                    "doctype": "Salary Slip", "employee": employee,
                    "start_date": "2026-09-01", "end_date": "2026-09-06",
                })
                native_slip.employee = employee
                native_slip.start_date = date(2026, 9, 1)
                native_slip.end_date = date(2026, 9, 6)
                native_slip.get_working_days_details()

                adapter = _native_attendance_units(employee, date(2026, 9, 1), date(2026, 9, 6))
                assert adapter["payable_units"] == native_slip.payment_days
    finally:
        for field, value in original_settings.items():
            frappe.db.set_single_value("Payroll Settings", field, value)
        frappe.db.rollback(save_point=savepoint)
        frappe.clear_cache(doctype="Payroll Settings")
        frappe.clear_cache(doctype="Leave Type")
        assert employee is None or not frappe.db.exists("Employee", employee)
        assert holiday_list is None or not frappe.db.exists("Holiday List", holiday_list.name)
        assert all(not frappe.db.exists("Leave Type", name) for name in leave_types)


def test_native_daily_wage_policy_changes_only_work_day_units():
    employee = "HR-EMP-00225"
    if not frappe.db.exists("Employee", {"name": employee, "company": "Tradexcel Ceramics Ltd.", "status": "Active"}):
        pytest.skip("Synthetic fixture employee is unavailable")
    savepoint = "flex_work_native_daily_wage"
    frappe.db.savepoint(savepoint)
    created = []
    try:
        structure, assignment = _safe_structure(employee, frappe.generate_hash(6))
        created.extend([("Salary Structure", structure.name),
                        ("Salary Structure Assignment", assignment.name)])
        slip = SalarySlip({"doctype": "Salary Slip"})
        slip.employee = employee
        slip.start_date = date(2026, 12, 1)
        slip.end_date = date(2026, 12, 31)
        holidays = set(slip.get_holidays_for_employee(slip.start_date, slip.end_date))
        workdays = [slip.start_date + timedelta(days=i) for i in range(31)
                    if slip.start_date + timedelta(days=i) not in holidays]
        holiday_day = next(iter(holidays), None)
        if holiday_day:
            holiday_attendance = _attendance(employee, holiday_day, "Present", 4)
            created.append(("Attendance", holiday_attendance.name))
            from tradex_hr.tradexcel_hr.flexible_work_records import build_operational_day_override_preview
            holiday_preview = build_operational_day_override_preview(frappe._dict({
                "company": "Tradexcel Ceramics Ltd.", "operational_date": holiday_day,
                "branch": None, "department": None,
            }))
            assert holiday_preview["status"] == "READY"
            assert holiday_preview["affected_count"] == 0
            assert holiday_preview["normal_units"] == 0
            assert holiday_preview["override_units"] == 0
            assert holiday_preview["amount_impact"] == 0
        if len(workdays) < 3:
            pytest.skip("TCL Holiday List has fewer than three working days in test month")

        work_attendance = None
        for index, day in enumerate(workdays):
            if index == 0:
                work_attendance = _attendance(employee, day, "Present", 6)
                attendance = work_attendance
            elif index == 1:
                attendance = _attendance(employee, day, "Present", 7)
            elif index == 2:
                attendance = _attendance(employee, day, "Half Day", 4, half_day_status="Absent")
            else:
                attendance = _attendance(employee, day, "Absent", 0)
            created.append(("Attendance", attendance.name))

        policy = frappe.get_doc({
            "doctype": "Tradexcel Flexible Work Policy",
            "title": f"Synthetic flexible work {frappe.generate_hash(6)}",
            "company": "Tradexcel Ceramics Ltd.",
            "effective_from": "2026-12-01",
            "effective_to": "2026-12-31",
            "standard_paid_hours": 8,
            "full_day_minimum_hours": 7,
            "flexible_shift_enabled": 0,
            "policy_notes": "Synthetic native mechanics proof only; not an approved company policy.",
        })
        policy.insert(ignore_permissions=True)
        created.append(("Tradexcel Flexible Work Policy", policy.name))
        policy.submit()

        override = frappe.get_doc({
            "doctype": "Tradexcel Operational Day Override",
            "company": "Tradexcel Ceramics Ltd.",
            "operational_date": workdays[0],
            "reason_category": "No Work / Production Stop",
            "reason": "Synthetic native mechanics proof only.",
        })
        override.insert(ignore_permissions=True)
        created.append(("Tradexcel Operational Day Override", override.name))
        assert override.preview_status == "READY"
        assert override.preview_affected_count == 1
        assert override.preview_normal_units == 0.75
        assert override.preview_override_units == 1
        assert override.preview_amount_impact == 87.5
        override.submit()

        frappe.db.set_value("Attendance", work_attendance.name, "working_hours", 5)
        assert frappe.db.get_value("Attendance", work_attendance.name, "working_hours") == 5
        from tradex_hr.tradexcel_hr.flexible_work_records import build_operational_day_override_preview
        fresh_preview = build_operational_day_override_preview(override)
        assert fresh_preview["attendance_hash"] != override.preview_hash
        stale = validate_operational_day_overrides(
            "Tradexcel Ceramics Ltd.", "2026-12-01", "2026-12-31"
        )
        assert stale == [{"code": "OPERATIONAL_DAY_OVERRIDE_PREVIEW_STALE", "record": override.name}]
        frappe.db.set_value("Attendance", work_attendance.name, "working_hours", 6)
        assert validate_operational_day_overrides(
            "Tradexcel Ceramics Ltd.", "2026-12-01", "2026-12-31"
        ) == []

        result = daily_wage_input.calculate_daily_wage_input(employee, "2026-12-01", "2026-12-31")
        assert result["status"] == "READY"
        assert result["payable_units"] == 2.5
        assert result["rate"] == 350
        assert result["amount"] == 875

        period = frappe.get_doc({
            "doctype": "Tradexcel Attendance Period",
            "company": "Tradexcel Ceramics Ltd.",
            "from_date": "2026-12-01",
            "to_date": "2026-12-31",
            "status": "Finalized",
            "revision": 1,
            "attendance_hash": "synthetic-flex-work-period",
        })
        period._finalize_context = True
        period.insert(ignore_permissions=True)
        created.append(("Tradexcel Attendance Period", period.name))
        original = daily_wage_input.require_finalized_attendance
        daily_wage_input.require_finalized_attendance = lambda *_args: period
        try:
            additional = daily_wage_input.create_daily_wage_input(employee, period.name)
            if additional.get("name"):
                created.append(("Additional Salary", additional["name"]))
        finally:
            daily_wage_input.require_finalized_attendance = original
        assert additional["status"] == "CREATED"
        native_slip = make_salary_slip(structure.name, employee=employee, posting_date="2026-12-31")
        wage_rows = [row for row in native_slip.earnings if row.salary_component == "Daily Wage"]
        assert sum(row.amount for row in wage_rows) == 875
    finally:
        frappe.db.rollback(save_point=savepoint)
        for doctype, name in created:
            assert not frappe.db.exists(doctype, name), f"Synthetic {doctype} {name} remained after rollback"


def test_native_multiple_shift_assignments_resolve_non_overlapping_shifts():
    employee = _active_tcl_employee_without_december_shift()
    if not employee:
        pytest.skip("No Active TCL employee is free of Shift Assignment during the synthetic window")
    savepoint = "flex_native_shift_selection"
    frappe.db.savepoint(savepoint)
    original = frappe.db.get_single_value("HR Settings", "allow_multiple_shift_assignments")
    shift_names = []
    assignment_names = []
    try:
        frappe.db.set_single_value("HR Settings", "allow_multiple_shift_assignments", 1)
        suffix = frappe.generate_hash(5)
        shifts = [
            (f"TEST AM {suffix}", "06:00:00", "14:00:00"),
            (f"TEST PM {suffix}", "14:00:00", "22:00:00"),
            (f"TEST Night {suffix}", "22:00:00", "06:00:00"),
        ]
        for name, start, end in shifts:
            doc = frappe.get_doc({
                "doctype": "Shift Type",
                "name": name,
                "start_time": start,
                "end_time": end,
                "begin_check_in_before_shift_start_time": 0,
                "allow_check_out_after_shift_end_time": 0,
                "enable_auto_attendance": 0,
            })
            doc.insert(ignore_permissions=True)
            shift_names.append(name)

        for name, _, _ in shifts:
            assignment = frappe.get_doc({
                "doctype": "Shift Assignment",
                "employee": employee,
                "shift_type": name,
                "start_date": "2026-12-01",
                "end_date": "2026-12-10",
                "status": "Active",
            })
            assignment.insert(ignore_permissions=True)
            assignment_names.append(assignment.name)
            assignment.submit()

        morning = get_employee_shift(employee, datetime(2026, 12, 2, 8, 0))
        evening = get_employee_shift(employee, datetime(2026, 12, 3, 16, 0))
        night_start = get_employee_shift(employee, datetime(2026, 12, 4, 23, 30))
        night_after_midnight = get_employee_shift(employee, datetime(2026, 12, 5, 3, 0))
        assert morning.shift_type.name == shifts[0][0]
        assert evening.shift_type.name == shifts[1][0]
        assert night_start.shift_type.name == shifts[2][0]
        assert night_after_midnight.shift_type.name == shifts[2][0]
    finally:
        frappe.db.set_single_value("HR Settings", "allow_multiple_shift_assignments", original)
        frappe.db.rollback(save_point=savepoint)
        assert frappe.db.get_single_value("HR Settings", "allow_multiple_shift_assignments") == original
        assert all(not frappe.db.exists("Shift Type", name) for name in shift_names)
        assert all(not frappe.db.exists("Shift Assignment", name) for name in assignment_names)
