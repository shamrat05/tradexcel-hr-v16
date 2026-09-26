"""Older reports obey native scope and never infer pay from punches."""
from unittest.mock import patch

import frappe
import pytest
from frappe.desk.query_report import run

from tradex_hr.tests.persona_uat import PERSONA_ROLES, SyntheticPersonaHarness
from tradex_hr.tests.test_bulk_salary_authority_integration import _structure
from tradex_hr.tests.test_payroll_finalization_integration import _create_assignment


@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(site="hrms-v16.localhost", sites_path="/home/sanchita/frappe-bench-v16/sites", force=True)
    frappe.connect()
    frappe.set_user("Administrator")
    yield
    frappe.set_user("Administrator")
    frappe.destroy()


def test_legacy_reports_native_scope_status_and_salary_privacy():
    from hrms.payroll.doctype.salary_structure.salary_structure import make_salary_slip
    from tradex_hr.tradexcel_hr.report.daily_attendance_summary.daily_attendance_summary import execute as summary
    from tradex_hr.tradexcel_hr.report.workforce_anomaly_radar.workforce_anomaly_radar import execute as radar
    from tradex_hr.tradexcel_hr.report.tradexcel_payroll_register.tradexcel_payroll_register import execute as register

    company = "Tradexcel Ceramics Ltd."
    branches = frappe.get_all("Branch", filters={"company": company}, pluck="name", order_by="name")
    departments = frappe.get_all("Department", filters={"company": company}, pluck="name", order_by="name")
    token = "SOLRPT" + frappe.generate_hash(6).upper()[:6]
    personas = SyntheticPersonaHarness(token)
    tracked = []
    try:
        attendance = personas.create_user("attendance", [PERSONA_ROLES["attendance_officer"]],
            company=company, branch=branches[0], department=departments[0])
        payroll = personas.create_user("payroll", [PERSONA_ROLES["payroll_manager"]],
            company=company, branch=branches[0], department=departments[0])
        finance = personas.create_user("finance", [PERSONA_ROLES["finance"]],
            company=company, branch=branches[0], department=departments[0])
        worker = personas.create_user("worker", [PERSONA_ROLES["worker"]], company=company)
        employees = {key: personas.create_employee(key, company, branch, department)
            for key, branch, department in (
                ("punch", branches[0], departments[0]), ("absent", branches[0], departments[0]),
                ("draft", branches[0], departments[0]), ("branch", branches[1], departments[0]),
                ("department", branches[0], departments[1]))}
        for key in ("punch", "branch"):
            doc = frappe.get_doc({"doctype": "Employee Checkin", "employee": employees[key],
                "time": "2026-08-15 08:00:00", "log_type": "IN"}).insert(ignore_permissions=True)
            tracked.append((doc.doctype, doc.name))
        for key, status in (("absent", "Absent"), ("draft", "Present")):
            doc = frappe.get_doc({"doctype": "Attendance", "employee": employees[key],
                "company": company, "attendance_date": "2026-08-15", "status": status}).insert(ignore_permissions=True)
            tracked.append((doc.doctype, doc.name))
            if key == "absent":
                doc.submit()
        structure = _structure(company, "Monthly Salary")
        slips = {}
        for key in ("punch", "branch"):
            assignment = _create_assignment(employees[key], company, structure.currency,
                frappe.db.get_value("Company", company, "default_payroll_payable_account"),
                structure.name, 0, frappe.db.get_value("Company", company, "cost_center"))
            tracked.append((assignment.doctype, assignment.name))
            doc = make_salary_slip(structure.name, employee=employees[key], posting_date="2026-08-31")
            doc.start_date = "2026-08-01"
            doc.end_date = "2026-08-31"
            doc.insert(ignore_permissions=True)
            tracked.append((doc.doctype, doc.name))
            slips[key] = doc
        frappe.db.commit()
        daily = {"company": company, "from_date": "2026-08-15", "to_date": "2026-08-15"}
        monthly = {**daily, "from_date": "2026-08-01", "to_date": "2026-08-31"}
        frappe.set_user(attendance)
        for rows in (run("Daily Attendance Summary", filters=daily)["result"], summary(daily)[1]):
            indexed = {row["employee"]: row for row in rows}
            assert employees["branch"] not in indexed and employees["department"] not in indexed
            assert indexed[employees["punch"]]["status"] == "Not Marked"
            assert indexed[employees["punch"]]["total_hours"] is None
            assert indexed[employees["absent"]]["status"] == "Absent"
            assert indexed[employees["absent"]]["attendance_state"] == "Submitted Attendance"
            assert indexed[employees["draft"]]["attendance_state"] == "Draft Attendance"
            assert indexed[employees["draft"]]["total_hours"] is None
        missing = summary({**daily, "from_date": "2026-08-16", "to_date": "2026-08-16"})[1]
        assert next(row.status for row in missing if row.employee == employees["punch"]) == "Not Marked"
        for report, execute in (("Daily Attendance Summary", summary), ("Workforce Anomaly Radar", radar)):
            for field, value in (("branch", branches[1]), ("department", departments[1])):
                assert execute({**daily, field: value})[1] == []
            for rows in (run(report, filters=monthly)["result"], execute(monthly)[1]):
                assert not {employees["branch"], employees["department"]}.intersection(row.get("employee") for row in rows)
                assert not any(row.get("category") in {"Payroll", "Tax"} for row in rows)
        for execute in (summary, radar):
            with pytest.raises(frappe.PermissionError):
                execute({**monthly, "company": "Elegance Footwear Ltd."})
        with pytest.raises(frappe.PermissionError):
            radar({**monthly, "category": "Payroll"})
        with pytest.raises(frappe.PermissionError):
            register(monthly)
        frappe.set_user(payroll)
        assert not {slip.name for slip in slips.values()}.intersection(row.name for row in register(monthly)[1])
        frappe.set_user("Administrator")
        for slip in slips.values():
            slip.submit()
        frappe.db.commit()
        frappe.set_user(payroll)
        financial_findings = radar(monthly)[1]
        assert not {employees["branch"], employees["department"]}.intersection(row.get("employee") for row in financial_findings)
        frappe.set_user(finance)
        rows = run("Tradexcel Payroll Register", filters=monthly)["result"]
        assert slips["punch"].name in {row["name"] for row in rows}
        assert slips["branch"].name not in {row["name"] for row in rows}
        assert slips["branch"].name not in {row.name for row in register(monthly)[1]}
        with pytest.raises(frappe.PermissionError):
            register({**monthly, "company": "Elegance Footwear Ltd."})
        frappe.set_user("Administrator")
        slips["punch"].cancel()
        frappe.set_user(payroll)
        assert slips["punch"].name not in {row.name for row in register(monthly)[1]}
        frappe.set_user(worker)
        for report, execute in (("Daily Attendance Summary", summary), ("Workforce Anomaly Radar", radar), ("Tradexcel Payroll Register", register)):
            with pytest.raises(frappe.PermissionError):
                run(report, filters=monthly)
            with pytest.raises(frappe.PermissionError):
                execute(monthly)
    finally:
        frappe.set_user("Administrator")
        with patch.object(frappe, "in_test", True):
            for doctype, name in reversed(tracked):
                if frappe.db.exists(doctype, name):
                    doc = frappe.get_doc(doctype, name)
                    if doc.docstatus == 1:
                        doc.cancel()
                    frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
            personas.cleanup()
        frappe.db.commit()
        assert not any(frappe.db.exists(dt, name) for dt, name in tracked)


def test_salary_scope_returns_complete_native_population():
    """Installed runtime, rather than generic documentation, defines pagination."""
    from erpnext.accounts.utils import get_fiscal_year
    from frappe.utils import add_months, get_first_day, get_last_day
    from hrms.payroll.doctype.salary_structure.salary_structure import make_salary_slip
    from tradex_hr.tradexcel_hr.report_scope import permitted_salary_slips

    company = "Tradexcel Ceramics Ltd."
    branch = frappe.db.get_value("Branch", {"company": company}, "name")
    department = frappe.db.get_value("Department", {"company": company}, "name")
    personas = SyntheticPersonaHarness("SOLPAGE" + frappe.generate_hash(6).upper()[:6])
    tracked = []
    try:
        payroll = personas.create_user("payroll", [PERSONA_ROLES["payroll_manager"]], company=company)
        structure = _structure(company, "Monthly Salary")
        _year, fiscal_start, fiscal_end = get_fiscal_year("2026-08-31", company=company)
        for index in range(3):
            employee = personas.create_employee(str(index), company, branch, department)
            assignment = _create_assignment(employee, company, structure.currency,
                frappe.db.get_value("Company", company, "default_payroll_payable_account"),
                structure.name, 0, frappe.db.get_value("Company", company, "cost_center"), from_date=fiscal_start)
            tracked.append((assignment.doctype, assignment.name))
            for month in range(7):
                start = get_first_day(add_months(fiscal_start, month))
                end = get_last_day(start)
                slip = make_salary_slip(structure.name, employee=employee, posting_date=end)
                slip.start_date = start
                slip.end_date = end
                slip.insert(ignore_permissions=True)
                tracked.append((slip.doctype, slip.name))
                slip.submit()
        frappe.db.commit()
        frappe.set_user(payroll)
        native_default = frappe.get_list("Salary Slip", filters={"employee": ["in", personas.employees], "docstatus": 1}, pluck="name")
        assert len(native_default) == 21
        scoped = permitted_salary_slips(company, tuple(personas.employees), from_date=fiscal_start, to_date=fiscal_end)
        assert len(scoped) == 21
        assert {row.name for row in scoped} == {name for dt, name in tracked if dt == "Salary Slip"}
    finally:
        frappe.set_user("Administrator")
        with patch.object(frappe, "in_test", True):
            for doctype, name in reversed(tracked):
                if frappe.db.exists(doctype, name):
                    doc = frappe.get_doc(doctype, name)
                    if doc.docstatus == 1:
                        doc.cancel()
                    frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
            personas.cleanup()
        frappe.db.commit()
        assert not any(frappe.db.exists(dt, name) for dt, name in tracked)
