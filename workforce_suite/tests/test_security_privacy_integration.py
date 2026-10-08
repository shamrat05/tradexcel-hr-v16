"""Reproduced native API privacy boundaries; synthetic records only."""
import os

import frappe
import pytest
from unittest.mock import patch
from frappe.client import get
from workforce_suite.tests.persona_uat import SyntheticPersonaHarness, PERSONA_ROLES


@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(
        site=os.environ.get("FRAPPE_TEST_SITE", "test_workforce.localhost"),
        sites_path=os.environ.get("FRAPPE_TEST_SITES_PATH", "./sites"),
        force=True,
    )
    frappe.connect()
    frappe.set_user("Administrator")
    yield
    frappe.set_user("Administrator")
    frappe.destroy()


def test_employee_financial_fields_use_native_field_permissions():
    h = SyntheticPersonaHarness("SOLPRIV" + frappe.generate_hash(8).upper())
    try:
        company = "Example Company A"
        branch = frappe.db.get_value("Branch", {"company": company}, "name")
        department = frappe.db.get_value("Department", {"company": company}, "name")
        for key in (
            "hr_manager",
            "attendance_officer",
            "branch_manager",
            "department_manager",
            "factory_supervisor",
            "payroll_manager",
            "device_admin",
        ):
            h.create_user(
                key,
                [PERSONA_ROLES[key]],
                company=company,
                branch=branch,
                department=department,
            )
        h.create_user(
            "mixed_worker",
            [PERSONA_ROLES["attendance_officer"], "Employee"],
            company=company,
            branch=branch,
            department=department,
        )
        doc = frappe.get_doc(
            {
                "doctype": "Employee",
                "first_name": h.employee_marker,
                "employee_name": h.employee_marker,
                "company": company,
                "branch": branch,
                "department": department,
                "date_of_birth": "1990-01-01",
                "date_of_joining": "2020-01-01",
                "status": "Active",
                "gender": frappe.db.get_value("Gender", {}, "name"),
                "ctc": 123.45,
                "bank_ac_no": "SYNTHETIC-NOT-A-BANK",
            }
        ).insert(ignore_permissions=True)
        h.employees.append(doc.name)
        frappe.db.commit()
        for key, user in h.users.items():
            frappe.set_user(user)
            try:
                result = get("Employee", doc.name)
                assert (result.get("ctc") == 123.45) == (
                    key in ("hr_manager", "payroll_manager")
                )
                assert (result.get("bank_ac_no") == "SYNTHETIC-NOT-A-BANK") == (
                    key in ("hr_manager", "payroll_manager")
                )
                if key not in ("hr_manager", "payroll_manager"):
                    rows = frappe.get_list(
                        "Employee",
                        filters={"name": doc.name},
                        fields=["name", "ctc", "bank_ac_no"],
                    )
                    assert all(
                        "ctc" not in row and "bank_ac_no" not in row for row in rows
                    )
            except frappe.PermissionError:
                assert key == "device_admin"
    finally:
        frappe.set_user("Administrator")
        h.cleanup()


def test_native_employee_linked_records_reject_outside_branch():
    h = SyntheticPersonaHarness("SOLSEC" + frappe.generate_hash(8).upper())
    tracked = []
    docs = {}

    def add(dt, **values):
        doc = frappe.get_doc({"doctype": dt, **values}).insert(ignore_permissions=True)
        tracked.append((dt, doc.name))
        return doc

    try:
        company = "Example Company A"
        branches = frappe.get_all(
            "Branch", filters={"company": company}, pluck="name", order_by="name"
        )
        department = frappe.db.get_value("Department", {"company": company}, "name")
        for key in (
            "hr_manager",
            "attendance_officer",
            "payroll_manager",
            "device_admin",
        ):
            h.create_user(
                key,
                [PERSONA_ROLES[key]],
                company=company,
                branch=branches[0],
                department=department,
            )
        employee = h.create_employee("outside-branch", company, branches[1], department)
        own = h.create_employee("own", company, branches[0], department)
        shift = add(
            "Shift Type", name=h.token, start_time="08:00:00", end_time="16:00:00"
        )
        component = add("Salary Component", salary_component=h.token, type="Earning")
        leave = add("Leave Type", leave_type_name=h.token)
        overtime = add(
            "Overtime Type",
            name=h.token,
            overtime_salary_component=component.name,
            standard_multiplier=1,
            applicable_salary_component=[{"salary_component": component.name}],
        )
        device = add(
            "Workforce Biometric Device",
            device_code=h.token,
            device_serial=h.token,
            bridge_url="http://127.0.0.1:1",
        )
        structure = frappe.db.get_value(
            "Salary Structure",
            {
                "company": company,
                "docstatus": 1,
                "custom_workforce_pay_basis": "Monthly Salary",
            },
            "name",
        )
        assignment = add(
            "Salary Structure Assignment",
            employee=employee,
            company=company,
            salary_structure=structure,
            from_date="2026-09-01",
            base=100,
        )
        assignment.submit()
        payloads = [
            (
                "Attendance",
                dict(
                    employee=employee,
                    company=company,
                    status="Present",
                    attendance_date="2026-09-01",
                ),
            ),
            (
                "Shift Assignment",
                dict(
                    employee=employee,
                    company=company,
                    shift_type=shift.name,
                    start_date="2026-09-01",
                    end_date="2026-09-01",
                ),
            ),
            (
                "Leave Allocation",
                dict(
                    employee=employee,
                    company=company,
                    leave_type=leave.name,
                    from_date="2026-09-01",
                    to_date="2026-09-30",
                    new_leaves_allocated=1,
                ),
            ),
            (
                "Additional Salary",
                dict(
                    employee=employee,
                    company=company,
                    salary_component=component.name,
                    amount=1,
                    currency=frappe.db.get_value(
                        "Company", company, "default_currency"
                    ),
                    payroll_date="2026-09-01",
                ),
            ),
            (
                "Overtime Slip",
                dict(
                    employee=employee,
                    company=company,
                    posting_date="2026-09-01",
                    start_date="2026-09-01",
                    end_date="2026-09-01",
                    overtime_details=[
                        {
                            "date": "2026-09-01",
                            "overtime_type": overtime.name,
                            "overtime_duration": 1,
                            "standard_working_hours": 8,
                        }
                    ],
                ),
            ),
            (
                "Workforce Employee Biometric",
                dict(employee=employee, device=device.name, biometric_id="SYNTHETIC"),
            ),
        ]
        for dt, payload in payloads:
            doc = add(dt, **payload)
            docs[dt] = doc.name
        frappe.db.commit()
        from frappe.client import get

        for key, user in h.users.items():
            frappe.set_user(user)
            for dt, name in docs.items():
                if not frappe.has_permission(dt, "read"):
                    continue
                visible = bool(
                    frappe.get_list(dt, filters={"name": name}, pluck="name")
                )
                try:
                    get(dt, name)
                    direct = True
                except frappe.PermissionError:
                    direct = False
                assert not visible and not direct, (key, dt)
        # Select-only Device Admin can maintain an in-scope mapping without Employee financial read.
        frappe.set_user(h.users["device_admin"])
        from workforce_suite.api import assign_employee_biometric

        with patch("workforce_suite.api._require_post"):
            with pytest.raises(frappe.PermissionError):
                assign_employee_biometric(employee, device.name, "FORGED")
            result = assign_employee_biometric(own, device.name, "OWN")
            tracked.append(("Workforce Employee Biometric", result["assignment"]))
            assert (
                get("Workforce Employee Biometric", result["assignment"])["employee"]
                == own
            )
    finally:
        frappe.set_user("Administrator")
        for dt, name in reversed(tracked):
            if frappe.db.exists(dt, name):
                doc = frappe.get_doc(dt, name)
                if doc.docstatus == 1:
                    doc.cancel()
                frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
        h.cleanup()


def test_payroll_entry_requires_scope_for_every_employee_child():
    h = SyntheticPersonaHarness("SOLPRIV" + frappe.generate_hash(8).upper())
    entry = None
    try:
        company = "Example Company A"
        branches = frappe.get_all(
            "Branch", filters={"company": company}, pluck="name", order_by="name"
        )
        department = frappe.db.get_value("Department", {"company": company}, "name")
        user = h.create_user(
            "payroll",
            [PERSONA_ROLES["payroll_manager"]],
            company=company,
            branch=branches[0],
            department=department,
        )
        employee = h.create_employee("outside", company, branches[1], department)
        co = frappe.get_doc("Company", company)
        entry = frappe.get_doc(
            {
                "doctype": "Payroll Entry",
                "company": company,
                "start_date": "2026-09-01",
                "end_date": "2026-09-30",
                "posting_date": "2026-09-30",
                "currency": co.default_currency,
                "exchange_rate": 1,
                "cost_center": co.cost_center,
                "payroll_payable_account": co.default_payroll_payable_account,
                "payroll_frequency": "Monthly",
                "custom_workforce_run_key": h.token,
                "employees": [{"employee": employee}],
            }
        ).insert(ignore_permissions=True)
        frappe.db.commit()
        frappe.set_user(user)
        from workforce_suite.workforce_suite.payroll_finalization import (
            inspect_payroll_accrual_reconciliation,
        )

        assert not frappe.get_list(
            "Payroll Entry", filters={"name": entry.name}, pluck="name"
        )
        with pytest.raises(frappe.PermissionError):
            get("Payroll Entry", entry.name)
        with pytest.raises(frappe.PermissionError):
            inspect_payroll_accrual_reconciliation(entry.name)
        frappe.set_user("Administrator")
        own = h.create_employee("own", company, branches[0], department)
        entry.employees = []
        entry.append("employees", {"employee": own})
        entry.save(ignore_permissions=True)
        frappe.set_user(user)
        assert get("Payroll Entry", entry.name)["employees"][0]["employee"] == own
        assert frappe.get_list(
            "Payroll Entry", filters={"name": entry.name}, pluck="name"
        ) == [entry.name]

    finally:
        frappe.set_user("Administrator")
        if entry and frappe.db.exists("Payroll Entry", entry.name):
            frappe.delete_doc(
                "Payroll Entry", entry.name, force=True, ignore_permissions=True
            )
        h.cleanup()


def test_native_shift_schedule_and_request_tampering_and_mixed_roles():
    h = SyntheticPersonaHarness("SOLSHIFT" + frappe.generate_hash(8).upper())
    tracked = []

    def add(dt, **v):
        d = frappe.get_doc({"doctype": dt, **v}).insert(ignore_permissions=True)
        tracked.append((dt, d.name))
        return d

    try:
        co = "Example Company A"
        bs = frappe.get_all(
            "Branch", filters={"company": co}, pluck="name", order_by="name"
        )
        dep = frappe.db.get_value("Department", {"company": co}, "name")
        u = h.create_user(
            "native", ["HR User"], company=co, branch=bs[0], department=dep
        )
        mixed = h.create_user(
            "mixed",
            ["HR User", PERSONA_ROLES["hr_manager"]],
            company=co,
            branch=bs[0],
            department=dep,
        )
        own = h.create_employee("own", co, bs[0], dep)
        outside = h.create_employee("outside", co, bs[1], dep)
        shift = add(
            "Shift Type", name=h.token, start_time="08:00:00", end_time="16:00:00"
        )
        schedule = add(
            "Shift Schedule",
            name=h.token,
            frequency="Every Week",
            repeat_on_days=[{"day": "Monday"}],
            shift_type=shift.name,
        )
        employee_doc = frappe.get_doc("Employee", outside)
        employee_doc.shift_request_approver = u
        employee_doc.save(ignore_permissions=True)
        request = add(
            "Shift Request",
            employee=outside,
            company=co,
            shift_type=shift.name,
            from_date="2026-09-08",
            to_date="2026-09-08",
            approver=u,
        )
        frappe.db.commit()
        frappe.set_user(u)
        tool = frappe.get_doc("Shift Assignment Tool")
        tool.update(
            {
                "action": "Assign Shift Schedule",
                "company": co,
                "start_date": "2026-09-07",
                "end_date": "2026-09-07",
                "shift_schedule": schedule.name,
                "status": "Active",
            }
        )
        visible = {r.employee for r in tool.get_employees()}
        assert own in visible and outside not in visible
        with pytest.raises(frappe.PermissionError):
            tool.bulk_assign([outside])
        with pytest.raises(frappe.PermissionError):
            tool._bulk_assign([outside])
        tool.action = "Process Shift Requests"
        tool.from_date = "2026-09-08"
        tool.to_date = "2026-09-08"
        forged = [{"shift_request": request.name, "employee": own}]
        with pytest.raises(frappe.PermissionError):
            tool.bulk_process_shift_requests(forged, "Approved")
        with pytest.raises(frappe.PermissionError):
            tool._bulk_process_shift_requests(forged, "Approved")
        assert frappe.db.get_value("Shift Request", request.name, "docstatus") == 0
        frappe.set_user(mixed)
        tool.action = "Assign Shift Schedule"
        assert own in {r.employee for r in tool.get_employees()}
        calls = []
        with patch(
            "frappe.enqueue", side_effect=lambda fn, **kw: calls.append((fn, kw))
        ):
            tool.bulk_assign([own])
        assert len(calls) == 1
        for fn, kw in calls:
            fn(employees=kw["employees"])
        assert frappe.get_all(
            "Shift Schedule Assignment", filters={"employee": own}, pluck="name"
        )
        assert not frappe.get_all(
            "Shift Schedule Assignment", filters={"employee": outside}, pluck="name"
        )

    finally:
        frappe.set_user("Administrator")
        for dt in ("Shift Assignment", "Shift Request", "Shift Schedule Assignment"):
            for n in (
                frappe.get_all(
                    dt, filters={"employee": ["in", h.employees]}, pluck="name"
                )
                if h.employees
                else []
            ):
                d = frappe.get_doc(dt, n)
                if d.docstatus == 1:
                    d.cancel()
                frappe.delete_doc(dt, n, force=True, ignore_permissions=True)
        for dt, n in reversed(tracked):
            if frappe.db.exists(dt, n):
                frappe.delete_doc(dt, n, force=True, ignore_permissions=True)
        h.cleanup()


def test_leave_exit_location_and_mobile_identity_scope():
    h = SyntheticPersonaHarness("SOLSEC" + frappe.generate_hash(8).upper())
    tracked = []
    docs = {}

    def add(dt, **values):
        doc = frappe.get_doc({"doctype": dt, **values}).insert(ignore_permissions=True)
        tracked.append((dt, doc.name))
        return doc

    try:
        company = "Example Company A"
        branches = frappe.get_all(
            "Branch", filters={"company": company}, pluck="name", order_by="name"
        )
        department = frappe.db.get_value("Department", {"company": company}, "name")
        for key in (
            "hr_manager",
            "attendance_officer",
            "payroll_manager",
            "device_admin",
            "compliance",
        ):
            h.create_user(
                key,
                [PERSONA_ROLES[key]],
                company=company,
                branch=branches[0],
                department=department,
            )
        employee = h.create_employee("outside-branch", company, branches[1], department)
        shift = add(
            "Shift Type", name=h.token, start_time="08:00:00", end_time="16:00:00"
        )
        component = add("Salary Component", salary_component=h.token, type="Earning")
        leave = add("Leave Type", leave_type_name=h.token)
        overtime = add(
            "Overtime Type",
            name=h.token,
            overtime_salary_component=component.name,
            standard_multiplier=1,
            applicable_salary_component=[{"salary_component": component.name}],
        )
        device = add(
            "Workforce Biometric Device",
            device_code=h.token,
            device_serial=h.token,
            bridge_url="http://127.0.0.1:1",
        )
        structure = frappe.db.get_value(
            "Salary Structure",
            {
                "company": company,
                "docstatus": 1,
                "custom_workforce_pay_basis": "Monthly Salary",
            },
            "name",
        )
        assignment = add(
            "Salary Structure Assignment",
            employee=employee,
            company=company,
            salary_structure=structure,
            from_date="2026-09-01",
            base=100,
        )
        assignment.submit()
        ed = frappe.get_doc("Employee", employee)
        ed.leave_approver = "Administrator"
        ed.relieving_date = "2026-09-30"
        ed.save(ignore_permissions=True)
        policy = add(
            "Leave Policy",
            title=h.token,
            leave_policy_details=[{"leave_type": leave.name, "annual_allocation": 1}],
        )
        lwp = add("Leave Type", leave_type_name=h.token + "LWP", is_lwp=1)
        duty = add(
            "Workforce Field Duty",
            duty_id=h.token,
            employee=employee,
            company=company,
            duty_date="2026-09-01",
            duty_type="Field Work",
            purpose="Synthetic permission test",
        )
        ping = add(
            "Workforce Location Ping",
            sync_id=h.token,
            employee=employee,
            company=company,
            field_duty=duty.name,
            ping_time="2026-09-01 09:00:00",
            latitude=1,
            longitude=1,
        )
        payloads = [
            (
                "Workforce Mobile Event",
                dict(
                    sync_id=h.token,
                    event_type="Checkin",
                    employee=employee,
                    company=company,
                    received_at="2026-09-01 09:00:00",
                ),
            ),
            (
                "Leave Policy Assignment",
                dict(
                    employee=employee,
                    company=company,
                    leave_policy=policy.name,
                    assignment_based_on="Joining Date",
                ),
            ),
            (
                "Leave Application",
                dict(
                    employee=employee,
                    company=company,
                    leave_type=lwp.name,
                    from_date="2026-09-02",
                    to_date="2026-09-02",
                    status="Open",
                    leave_approver="Administrator",
                ),
            ),
            (
                "Full and Final Statement",
                dict(
                    employee=employee,
                    company=company,
                    relieving_date="2026-09-30",
                    transaction_date="2026-09-30",
                ),
            ),
            (
                "Attendance",
                dict(
                    employee=employee,
                    company=company,
                    status="Present",
                    attendance_date="2026-09-01",
                ),
            ),
            (
                "Shift Assignment",
                dict(
                    employee=employee,
                    company=company,
                    shift_type=shift.name,
                    start_date="2026-09-01",
                    end_date="2026-09-01",
                ),
            ),
            (
                "Leave Allocation",
                dict(
                    employee=employee,
                    company=company,
                    leave_type=leave.name,
                    from_date="2026-09-01",
                    to_date="2026-09-30",
                    new_leaves_allocated=1,
                ),
            ),
            (
                "Additional Salary",
                dict(
                    employee=employee,
                    company=company,
                    salary_component=component.name,
                    amount=1,
                    currency=frappe.db.get_value(
                        "Company", company, "default_currency"
                    ),
                    payroll_date="2026-09-01",
                ),
            ),
            (
                "Overtime Slip",
                dict(
                    employee=employee,
                    company=company,
                    posting_date="2026-09-01",
                    start_date="2026-09-01",
                    end_date="2026-09-01",
                    overtime_details=[
                        {
                            "date": "2026-09-01",
                            "overtime_type": overtime.name,
                            "overtime_duration": 1,
                            "standard_working_hours": 8,
                        }
                    ],
                ),
            ),
            (
                "Workforce Employee Biometric",
                dict(employee=employee, device=device.name, biometric_id="SYNTHETIC"),
            ),
        ]
        for dt, payload in payloads:
            doc = add(dt, **payload)
            docs[dt] = doc.name
        docs["Workforce Field Duty"] = duty.name
        docs["Workforce Location Ping"] = ping.name
        frappe.db.commit()
        from frappe.client import get

        for key, user in h.users.items():
            frappe.set_user(user)
            for dt, name in docs.items():
                if not frappe.has_permission(dt, "read"):
                    continue
                visible = bool(
                    frappe.get_list(dt, filters={"name": name}, pluck="name")
                )
                try:
                    get(dt, name)
                    direct = True
                except frappe.PermissionError:
                    direct = False
                assert not visible and not direct, (key, dt)
        frappe.set_user(h.users["hr_manager"])
        from workforce_suite.workforce_suite.field_attendance_service import (
            get_live_locations,
            _assert_employee_self,
            _employee,
        )

        assert not any(
            r.employee == employee for r in get_live_locations(company=company)
        )
        with pytest.raises(frappe.PermissionError):
            _assert_employee_self(_employee(employee))
    finally:
        frappe.set_user("Administrator")
        for dt, name in reversed(tracked):
            if frappe.db.exists(dt, name):
                doc = frappe.get_doc(dt, name)
                if doc.docstatus == 1:
                    doc.cancel()
                frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
        h.cleanup()
