"""Explicit synthetic integration fixtures; never called by app installation.

Run with bench execute only on a disposable site marked workforce_rehearsal.
The legacy salary fixture deliberately simulates an imported unsafe structure.
"""
from datetime import date, timedelta
import frappe


def seed():
    if not frappe.conf.get("workforce_rehearsal"):
        raise RuntimeError("Synthetic integration seeding requires an explicit disposable rehearsal site")
    frappe.set_user("Administrator")
    if frappe.db.exists("Company", "Example Company A"):
        raise RuntimeError("Refusing to overwrite an existing fixture population")
    if not frappe.db.exists("Gender", "Female"):
        frappe.get_doc({"doctype": "Gender", "gender": "Female"}).insert(ignore_permissions=True)
    if not frappe.db.exists("Warehouse Type", "Transit"):
        frappe.get_doc({"doctype": "Warehouse Type", "name": "Transit"}).insert(ignore_permissions=True)
    if not frappe.db.exists("Fiscal Year", "2026"):
        frappe.get_doc({"doctype": "Fiscal Year", "year": "2026", "year_start_date": "2026-01-01",
                        "year_end_date": "2026-12-31"}).insert(ignore_permissions=True)
    for suffix in ("A", "B"):
        company = frappe.get_doc({"doctype": "Company", "company_name": f"Example Company {suffix}",
            "abbr": f"COMPANY_{suffix}", "default_currency": "BDT", "country": "Bangladesh"}).insert(ignore_permissions=True)
        for index in (1, 2):
            frappe.get_doc({"doctype": "Branch", "branch": f"TEST-WORKFORCE-{suffix}-{index}", "company": company.name}).insert(ignore_permissions=True)
            frappe.get_doc({"doctype": "Department", "department_name": f"TEST-WORKFORCE-{suffix}-{index}", "company": company.name}).insert(ignore_permissions=True)
        payable = frappe.db.get_value("Account", {"company": company.name, "account_name": "Creditors"}, "name")
        frappe.db.set_value("Company", company.name, "default_payroll_payable_account", payable)
    holiday = frappe.get_doc({"doctype": "Holiday List", "holiday_list_name": "TEST-WORKFORCE-HOLIDAYS",
        "from_date": "2026-01-01", "to_date": "2026-12-31"})
    for offset in range(365):
        day = date(2026, 1, 1) + timedelta(days=offset)
        if day.weekday() == 6:
            holiday.append("holidays", {"holiday_date": day, "description": "Synthetic weekly holiday", "weekly_off": 1})
    holiday.insert(ignore_permissions=True)
    for company in ("Example Company A", "Example Company B"):
        frappe.db.set_value("Company", company, "default_holiday_list", holiday.name)
    for key, joined in (("DAILY", "2020-01-01"), ("JOINER", "2026-09-15")):
        employee = frappe.get_doc({"doctype": "Employee", "first_name": f"TEST WORKFORCE {key}",
            "gender": "Female", "date_of_birth": "1990-01-01", "date_of_joining": joined,
            "company": "Example Company A", "status": "Active", "holiday_list": holiday.name,
            "branch": "TEST-WORKFORCE-A-1", "department": frappe.db.get_value("Department", {"company": "Example Company A", "department_name": "TEST-WORKFORCE-A-1"}, "name")})
        employee.insert(ignore_permissions=True)
        frappe.rename_doc("Employee", employee.name, f"TEST-WORKFORCE-{key}", force=True)
    component = frappe.get_doc({"doctype": "Salary Component", "salary_component": "TEST WORKFORCE Day Rate",
        "salary_component_abbr": "TWDR", "type": "Earning", "depends_on_payment_days": 0}).insert(ignore_permissions=True)
    structure = frappe.get_doc({"doctype": "Salary Structure", "name": "Example Daily Wage",
        "company": "Example Company A", "currency": "BDT", "payroll_frequency": "Monthly", "is_active": "Yes",
        "custom_workforce_pay_basis": "Daily Wage", "custom_workforce_daily_wage_component": component.name,
        "earnings": [{"salary_component": component.name, "amount": 0, "depends_on_payment_days": 0}]}).insert(ignore_permissions=True)
    structure.submit()
    assignment = frappe.get_doc({"doctype": "Salary Structure Assignment", "employee": "TEST-WORKFORCE-DAILY",
        "company": structure.company, "currency": "BDT", "salary_structure": structure.name, "from_date": "2026-09-01",
        "base": 425, "payroll_payable_account": frappe.db.get_value("Company", structure.company, "default_payroll_payable_account")}).insert(ignore_permissions=True)
    assignment.submit()
    # Simulate historical imported metadata only in this explicitly disposable fixture.
    frappe.db.set_value("Salary Structure", structure.name, "custom_workforce_daily_wage_component", None)
    frappe.db.set_value("Salary Detail", structure.earnings[0].name,
                        {"formula": "base * payment_days", "amount_based_on_formula": 1, "depends_on_payment_days": 1})
    device = frappe.get_doc({"doctype": "Workforce Biometric Device", "device_code": "TEST-WORKFORCE-DEVICE",
        "device_serial": "TEST-WORKFORCE-SERIAL", "bridge_url": "https://synthetic.example.test", "enabled": 1,
        "company": structure.company}).insert(ignore_permissions=True)
    frappe.get_doc({"doctype": "Workforce Employee Biometric", "employee": "TEST-WORKFORCE-DAILY",
        "device": device.name, "biometric_id": "SYNTHETIC-1", "enabled": 1}).insert(ignore_permissions=True)
    frappe.db.set_single_value("Payroll Settings", "payroll_based_on", "Leave")
    frappe.db.commit()
    return {"status": "SYNTHETIC_FIXTURES_READY", "companies": 2, "employees": 2}


def extend():
    """Complete explicit native setup needed by the pre-existing integration suite."""
    if not frappe.conf.get("workforce_rehearsal"):
        raise RuntimeError("Integration setup requires a disposable rehearsal site")
    frappe.set_user("Administrator")
    assert frappe.db.exists("Employee", "TEST-WORKFORCE-DAILY")
    for year in (2027,):
        if not frappe.db.exists("Fiscal Year", str(year)):
            frappe.get_doc({"doctype": "Fiscal Year", "year": str(year), "year_start_date": f"{year}-01-01",
                            "year_end_date": f"{year}-12-31"}).insert(ignore_permissions=True)
    for name in ("Worker", "Staff"):
        if not frappe.db.exists("Employment Type", name):
            frappe.get_doc({"doctype": "Employment Type", "employee_type_name": name}).insert(ignore_permissions=True)
    for name in ("TEST WORKFORCE Operator", "TEST WORKFORCE Manager"):
        if not frappe.db.exists("Designation", name):
            frappe.get_doc({"doctype": "Designation", "designation_name": name}).insert(ignore_permissions=True)
    if not frappe.db.exists("Leave Type", "TEST WORKFORCE Paid Leave"):
        frappe.get_doc({"doctype": "Leave Type", "leave_type_name": "TEST WORKFORCE Paid Leave",
                        "is_lwp": 0, "include_holiday": 1}).insert(ignore_permissions=True)
    if not frappe.db.exists("Mode of Payment", "Cash"):
        frappe.get_doc({"doctype": "Mode of Payment", "mode_of_payment": "Cash", "type": "Cash"}).insert(ignore_permissions=True)
    if not frappe.db.exists("Shift Type", "TEST WORKFORCE Shift"):
        frappe.get_doc({"doctype": "Shift Type", "name": "TEST WORKFORCE Shift", "start_time": "08:00:00",
                        "end_time": "16:00:00", "enable_auto_attendance": 0}).insert(ignore_permissions=True)
    component = None
    for company in ("Example Company A", "Example Company B"):
        center = frappe.db.get_value("Cost Center", {"company": company, "is_group": 0}, "name")
        if not center:
            center = frappe.get_doc({"doctype": "Cost Center", "cost_center_name": "TEST WORKFORCE Operations",
                "company": company, "parent_cost_center": frappe.db.get_value("Cost Center", {"company": company, "is_group": 1}, "name"), "is_group": 0}).insert(ignore_permissions=True).name
        frappe.db.set_value("Company", company, "cost_center", center)
        if not frappe.db.exists("Holiday List Assignment", {"applicable_for": "Company", "assigned_to": company, "docstatus": 1}):
            assignment = frappe.get_doc({"doctype": "Holiday List Assignment", "applicable_for": "Company",
                "assigned_to": company, "holiday_list": "TEST-WORKFORCE-HOLIDAYS", "from_date": "2026-01-01"}).insert(ignore_permissions=True)
            assignment.submit()
        name = "TEST WORKFORCE Monthly " + company[-1]
        if not frappe.db.exists("Salary Structure", name):
            if not component:
                component = frappe.get_doc({"doctype": "Salary Component", "salary_component": "TEST WORKFORCE Monthly Base",
                    "salary_component_abbr": "TWMB", "type": "Earning"}).insert(ignore_permissions=True)
            structure = frappe.get_doc({"doctype": "Salary Structure", "name": name, "company": company,
                "currency": "BDT", "payroll_frequency": "Monthly", "is_active": "Yes", "custom_workforce_pay_basis": "Monthly Salary",
                "earnings": [{"salary_component": component.name, "amount_based_on_formula": 1, "formula": "base"}]}).insert(ignore_permissions=True)
            structure.submit()
    for company in ("Example Company A", "Example Company B"):
        name = "AAA TEST WORKFORCE Daily " + company[-1]
        if not frappe.db.exists("Salary Structure", name):
            component_name = "TEST WORKFORCE Regular Day " + company[-1]
            component = frappe.get_doc({"doctype": "Salary Component", "salary_component": component_name,
                "salary_component_abbr": "TWRD" + company[-1], "type": "Earning", "depends_on_payment_days": 0}).insert(ignore_permissions=True)
            structure = frappe.get_doc({"doctype": "Salary Structure", "name": name, "company": company,
                "currency": "BDT", "payroll_frequency": "Monthly", "is_active": "Yes", "custom_workforce_pay_basis": "Daily Wage",
                "custom_workforce_daily_wage_component": component.name,
                "earnings": [{"salary_component": component.name, "amount": 0, "depends_on_payment_days": 0}]}).insert(ignore_permissions=True)
            structure.submit()
    if not frappe.db.exists("Employee", "TEST-WORKFORCE-OTHER"):
        employee = frappe.get_doc({"doctype": "Employee", "first_name": "TEST WORKFORCE OTHER", "company": "Example Company B",
            "gender": "Female", "date_of_birth": "1990-01-01", "date_of_joining": "2020-01-01", "status": "Active",
            "branch": "TEST-WORKFORCE-B-1", "department": frappe.db.get_value("Department", {"company": "Example Company B"}, "name")}).insert(ignore_permissions=True)
        frappe.rename_doc("Employee", employee.name, "TEST-WORKFORCE-OTHER", force=True)
    frappe.defaults.set_global_default("company", "Example Company A")
    frappe.db.set_single_value("Global Defaults", "default_company", "Example Company A")
    frappe.db.set_single_value("Global Defaults", "default_currency", "BDT")
    frappe.db.commit()
    return {"status": "EXPLICIT_NATIVE_FIXTURES_COMPLETE"}

