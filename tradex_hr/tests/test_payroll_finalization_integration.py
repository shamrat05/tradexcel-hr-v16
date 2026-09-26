"""Synthetic native Payroll Entry finalization and accrual retry integration proof."""

from __future__ import annotations

import os
from datetime import date, timedelta

import frappe
import pytest
from frappe.model.workflow import apply_workflow


@pytest.fixture
def frappe_site():
    frappe.init(
        site=os.environ.get("FRAPPE_TEST_SITE", "hrms-v16.localhost"),
        sites_path=os.environ.get("FRAPPE_TEST_SITES_PATH", "/home/sanchita/frappe-bench-v16/sites"),
        force=True,
    )
    frappe.connect()
    yield
    frappe.destroy()


def _create_synthetic_company(token, monkeypatch):
    from erpnext.setup.doctype.company.company import Company
    import erpnext.setup.doctype.company.company as company_module
    import hrms.overrides.company as hrms_company

    company_name = f"Tradexcel Finalization Test {token}"
    abbreviation = f"TF{token[:3]}"
    company = frappe.new_doc("Company")
    company.company_name = company_name
    company.abbr = abbreviation
    company.default_currency = "BDT"
    company.country = "Bangladesh"
    company.create_chart_of_accounts_based_on = "Existing Company"
    company.existing_company = "Tradexcel Ceramics Ltd."
    company.set_mode_of_payment_account = lambda: None

    # Use the same isolated-company test setup as the native tax integration.
    monkeypatch.setattr(Company, "set_mode_of_payment_account", lambda _self: None)
    monkeypatch.setattr(Company, "create_default_departments", lambda _self: None)
    monkeypatch.setattr(company_module, "install_country_fixtures", lambda *_args: None)
    monkeypatch.setattr(hrms_company, "set_expense_claim_type_accounts", lambda *_args: None)
    monkeypatch.setattr(hrms_company, "set_default_hr_accounts", lambda *_args: None)
    company.save()

    payable = frappe.db.get_value(
        "Account", {"company": company.name, "is_group": 0, "root_type": "Liability"}, "name"
    )
    expense = frappe.db.get_value(
        "Account", {"company": company.name, "is_group": 0, "root_type": "Expense"}, "name"
    )
    assert payable and expense
    frappe.db.set_value("Account", payable, "account_type", "Payable")
    frappe.db.set_value("Company", company.name, "default_payroll_payable_account", payable)

    root = frappe.db.get_value("Cost Center", {"company": company.name, "is_group": 1}, "name")
    cost_center = frappe.get_doc({
        "doctype": "Cost Center",
        "cost_center_name": f"Payroll Test {token}",
        "company": company.name,
        "parent_cost_center": root,
        "is_group": 0,
    }).insert(ignore_permissions=True)
    frappe.db.set_value("Company", company.name, "cost_center", cost_center.name)
    frappe.clear_cache(doctype="Company")

    holiday_list = frappe.get_doc({
        "doctype": "Holiday List",
        "holiday_list_name": f"Payroll Test {token}",
        "from_date": "2026-01-01",
        "to_date": "2027-12-31",
        "holidays": [],
    }).insert(ignore_permissions=True)
    frappe.db.set_value("Company", company.name, "default_holiday_list", holiday_list.name)
    holiday_assignment = frappe.get_doc({
        "doctype": "Holiday List Assignment",
        "applicable_for": "Company",
        "assigned_to": company.name,
        "employee_company": company.name,
        "holiday_list": holiday_list.name,
        "from_date": "2026-01-01",
    }).insert(ignore_permissions=True)
    holiday_assignment.submit()

    frappe.get_doc({
        "doctype": "Fiscal Year",
        "year": f"Finalization Test FY {token}",
        "year_start_date": "2026-01-01",
        "year_end_date": "2026-12-31",
        "companies": [{"company": company.name}],
    }).insert(ignore_permissions=True)

    return company.name, abbreviation, payable, expense, cost_center.name, holiday_list.name


def _component(name, abbreviation, company, account, *, depends_on_payment_days=0):
    return frappe.get_doc({
        "doctype": "Salary Component",
        "salary_component": name,
        "salary_component_abbr": abbreviation,
        "type": "Earning",
        "depends_on_payment_days": depends_on_payment_days,
        "is_tax_applicable": 0,
        "accounts": [{"company": company, "account": account}],
    }).insert(ignore_permissions=True)


def _create_employee(label, company, holiday_list, salary_mode=None, branch=None, department=None):
    fields = {
        "doctype": "Employee",
        "first_name": label,
        "company": company,
        "date_of_birth": "1990-05-08",
        "date_of_joining": "2020-01-01",
        "gender": "Female",
        "employment_type": "Intern",
        "holiday_list": holiday_list,
        "status": "Active",
    }
    if branch:
        fields["branch"] = branch
    if department:
        fields["department"] = department
    if salary_mode == "Bank":
        fields.update({
            "salary_mode": "Bank",
            "bank_name": "Synthetic Test Bank",
            "bank_ac_no": f"EMP-{frappe.generate_hash(8)[:8]}",
        })
    return frappe.get_doc(fields).insert(ignore_permissions=True)


def _create_synthetic_company_bank_account(company, abbreviation, token):
    bank = frappe.get_doc({
        "doctype": "Bank",
        "bank_name": f"Codex Test Bank {token}",
    }).insert(ignore_permissions=True)
    parent = frappe.db.get_value(
        "Account",
        {"company": company, "root_type": "Asset", "is_group": 1},
        "name",
        order_by="lft asc",
    )
    account = frappe.get_doc({
        "doctype": "Account",
        "account_name": f"Payroll Test Bank {token}",
        "company": company,
        "parent_account": parent,
        "root_type": "Asset",
        "account_type": "Bank",
        "account_currency": "BDT",
        "is_group": 0,
    }).insert(ignore_permissions=True)
    bank_account = frappe.get_doc({
        "doctype": "Bank Account",
        "account_name": f"Payroll Test Bank Account {token}",
        "bank": bank.name,
        "account": account.name,
        "is_company_account": 1,
        "company": company,
        "bank_account_no": f"COMPANY-{token[:8]}",
    }).insert(ignore_permissions=True)
    frappe.db.set_value("Company", company, "default_bank_account", bank_account.name)
    frappe.clear_cache(doctype="Company")
    return bank.name, account.name, bank_account.name


def _create_synthetic_cash_account(company, token):
    parent = frappe.db.get_value(
        "Account",
        {"company": company, "root_type": "Asset", "is_group": 1},
        "name",
        order_by="lft asc",
    )
    return frappe.get_doc({
        "doctype": "Account",
        "account_name": f"Payroll Test Cash {token}",
        "company": company,
        "parent_account": parent,
        "root_type": "Asset",
        "account_type": "Cash",
        "account_currency": "BDT",
        "is_group": 0,
    }).insert(ignore_permissions=True).name


def _create_structure(name, company, currency, pay_basis, component, amount, *, depends_on_payment_days=0):
    structure = frappe.get_doc({
        "doctype": "Salary Structure",
        "name": name,
        "company": company,
        "currency": currency,
        "payroll_frequency": "Monthly",
        "is_active": "Yes",
        "custom_tradex_pay_basis": pay_basis,
        "earnings": [{
            "salary_component": component,
            "amount": amount,
            "depends_on_payment_days": depends_on_payment_days,
        }],
    }).insert(ignore_permissions=True)
    structure.submit()
    return structure


def _create_assignment(employee, company, currency, payable, structure, base, cost_center, *, from_date="2026-08-01", leave_encashment_amount_per_day=0):
    assignment = frappe.get_doc({
        "doctype": "Salary Structure Assignment",
        "employee": employee,
        "company": company,
        "currency": currency,
        "salary_structure": structure,
        "from_date": from_date,
        "base": base,
        "leave_encashment_amount_per_day": leave_encashment_amount_per_day,
        "payroll_payable_account": payable,
        "payroll_cost_centers": [{"cost_center": cost_center, "percentage": 100}],
    }).insert(ignore_permissions=True)
    assignment.submit()
    return assignment


def _create_scoped_user(role, company, token):
    user = frappe.get_doc({
        "doctype": "User",
        "email": f"codex-finalize-{role.lower().replace('/', '-').replace(' ', '-')}-{token}@example.test",
        "first_name": f"Synthetic {role}",
        "enabled": 1,
        "user_type": "System User",
        "send_welcome_email": 0,
        "roles": [{"role": role}],
    }).insert(ignore_permissions=True)
    frappe.get_doc({
        "doctype": "User Permission",
        "user": user.name,
        "allow": "Company",
        "for_value": company,
        "apply_to_all_doctypes": 1,
    }).insert(ignore_permissions=True)
    return user.name


def cleanup_synthetic_finalization_company(company_name):
    """Remove only this integration test's disposable company and cloned data."""
    prefix = "Tradexcel Finalization Test "
    if not company_name.startswith(prefix):
        frappe.throw("Refusing cleanup outside the synthetic finalization company scope.")

    token = company_name[len(prefix):]
    frappe.set_user("Administrator")
    frappe.in_test = True
    frappe.local.flags.in_test = True

    def delete_doc(doctype, name):
        if not name or not frappe.db.exists(doctype, name):
            return
        doc = frappe.get_doc(doctype, name)
        if doc.docstatus == 1:
            if doctype in ("Payroll Correction", "Arrear"):
                doc.workflow_state = "Tradexcel Adjustment Cancelled"
            doc.cancel()
        frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)

    # Bank Transaction has no Company link; remove it through the disposable
    # company's Bank Account before deleting its payment Journal Entry.
    bank_account_names = frappe.get_all(
        "Bank Account", filters={"company": company_name}, pluck="name"
    )
    if bank_account_names:
        for name in frappe.get_all(
            "Bank Transaction",
            filters={"bank_account": ["in", bank_account_names]},
            pluck="name",
        ):
            delete_doc("Bank Transaction", name)

    # A correction/arrear links historical source slips while its Additional
    # Salary may be consumed by later slips. Cancel those later slips first,
    # then the adjustments, then their historical source slips.
    adjustment_sources = set()
    for doctype in ("Payroll Correction", "Arrear"):
        if not frappe.db.exists("DocType", doctype):
            continue
        for name in frappe.get_all(doctype, filters={"company": company_name}, pluck="name"):
            doc = frappe.get_doc(doctype, name)
            for field in doc.meta.fields:
                if field.fieldtype == "Link" and field.options == "Salary Slip" and doc.get(field.fieldname):
                    adjustment_sources.add(doc.get(field.fieldname))
                elif field.fieldtype == "Table" and doc.get(field.fieldname):
                    child_meta = frappe.get_meta(field.options)
                    for row in doc.get(field.fieldname):
                        for child_field in child_meta.fields:
                            if (
                                child_field.fieldtype == "Link"
                                and child_field.options == "Salary Slip"
                                and row.get(child_field.fieldname)
                            ):
                                adjustment_sources.add(row.get(child_field.fieldname))

    for name in frappe.get_all("Salary Slip", filters={"company": company_name}, pluck="name"):
        if name not in adjustment_sources:
            delete_doc("Salary Slip", name)

    # Transactions and employee data must go before their account/tree masters.
    company_linked = (
        "Payroll Entry", "Journal Entry", "Bank Account", "Gratuity",
        "Payroll Correction", "Arrear", "Additional Salary", "Overtime Slip", "Payroll Period", "Salary Slip",
        "Salary Structure Assignment", "Salary Structure",
        "Attendance", "Leave Application", "Employee Checkin", "Tradexcel Attendance Period",
        "Tradexcel Working Time Classification", "Tradexcel Working Time Rule Set",
        "Employee Transfer", "Employee Promotion", "Employee",
        "Payment Ledger Entry",
    )
    for doctype in company_linked:
        if not frappe.db.exists("DocType", doctype):
            continue
        meta = frappe.get_meta(doctype)
        employee_names = frappe.get_all("Employee", filters={"company": company_name}, pluck="name")
        if doctype in ("Employee Transfer", "Employee Promotion"):
            filters = {"employee": ["in", employee_names]} if employee_names else None
        elif meta.has_field("company"):
            filters = {"company": company_name}
        elif doctype == "Employee Checkin":
            filters = {"employee": ["in", employee_names]} if employee_names else None
        else:
            continue
        if filters is None:
            continue
        for name in frappe.get_all(doctype, filters=filters, pluck="name"):
            delete_doc(doctype, name)

    for name in frappe.get_all(
        "Department", filters={"company": company_name}, fields=["name", "rgt"], order_by="rgt desc"
    ):
        delete_doc("Department", name.name)

    overtime_type = f"Test Overtime Type {token}"
    if frappe.db.exists("Overtime Type", overtime_type):
        delete_doc("Overtime Type", overtime_type)
    # Salary Component has no Company link. Remove only the three names this
    # fixture creates, after Salary Structures and Salary Slips are gone.
    for name in (f"Test Basic {token}", f"Test Daily {token}", f"Test Overtime {token}"):
        delete_doc("Salary Component", name)

    # Cancelling a synthetic native Journal Entry writes reversal GL Entries.
    # They have no value after the disposable company is torn down, and ERPNext
    # correctly prevents deleting an Account while any GL Entry still refers to it.
    if frappe.db.exists("DocType", "GL Entry"):
        frappe.db.delete("GL Entry", {"company": company_name})

    for name in frappe.get_all(
        "User", filters={"email": ["like", f"codex-finalize-%-{token}%@example.test"]}, pluck="name"
    ):
        for permission in frappe.get_all("User Permission", filters={"user": name}, pluck="name"):
            delete_doc("User Permission", permission)
        delete_doc("User", name)

    for name in frappe.get_all(
        "Holiday List Assignment",
        filters={"assigned_to": company_name},
        pluck="name",
    ):
        delete_doc("Holiday List Assignment", name)
    for name in frappe.get_all(
        "Holiday List", filters={"holiday_list_name": f"Payroll Test {token}"}, pluck="name"
    ):
        delete_doc("Holiday List", name)
    for name in frappe.get_all(
        "Leave Type", filters={"name": f"Codex Adjustment Test LWP {token}"}, pluck="name"
    ):
        delete_doc("Leave Type", name)

    for name in frappe.get_all(
        "Fiscal Year", filters={"year": ["like", f"Finalization Test FY {token}%"]}, pluck="name"
    ):
        delete_doc("Fiscal Year", name)

    for name in frappe.get_all(
        "Bank", filters={"bank_name": f"Codex Test Bank {token}"}, pluck="name"
    ):
        delete_doc("Bank", name)

    # Company setup clones nested-set masters; remove deepest nodes first so a
    # failed/early test run cannot leave cloned account trees after Company deletion.
    for doctype in ("Warehouse", "Account", "Cost Center"):
        names = frappe.get_all(
            doctype,
            filters={"company": company_name},
            fields=["name", "rgt"],
            order_by="rgt asc",
        )
        for row in names:
            delete_doc(doctype, row.name)

    if frappe.db.exists("Company", company_name):
        frappe.delete_doc("Company", company_name, force=True, ignore_permissions=True)

    leftovers = {}
    for doctype in company_linked + ("Warehouse", "Account", "Cost Center", "GL Entry"):
        if frappe.db.exists("DocType", doctype) and frappe.get_meta(doctype).has_field("company"):
            count = frappe.db.count(doctype, {"company": company_name})
            if count:
                leftovers[doctype] = count
    if frappe.db.exists("Company", company_name) or leftovers:
        frappe.throw(f"Synthetic payroll fixture cleanup incomplete: {leftovers}")

    frappe.db.commit()


def test_synthetic_managed_payroll_native_partial_failure_retry_and_accrual(frappe_site, monkeypatch):
    from frappe.model.base_document import get_controller
    from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip
    from tradex_hr import role_setup
    from tradex_hr.tradexcel_hr import daily_wage_input, native_payroll, payroll_finalization

    token = frappe.generate_hash(7).upper()[:8]
    company_name = f"Tradexcel Finalization Test {token}"
    tracked = {
        "company": company_name,
        "attendance": [],
        "assignments": [],
        "structures": [],
        "components": [],
        "employees": [],
        "users": [],
        "permissions": [],
        "attendance_period": None,
        "payroll_entry": None,
        "salary_slips": [],
        "journal_entries": [],
        "daily_inputs": [],
        "holiday_list": None,
        "holiday_assignment": None,
        "fiscal_year": None,
        "overtime_slip": None,
        "overtime_type": None,
        "overtime_additional": None,
    }
    synthetic_branches = []
    original_in_test = frappe.in_test
    original_user = frappe.session.user
    component_names = (f"Test Basic {token}", f"Test Daily {token}", f"Test Overtime {token}")
    workflow_users = {}

    try:
        company, abbreviation, payable, expense, cost_center, holiday_list = _create_synthetic_company(token, monkeypatch)
        tracked["company"] = company
        tracked["holiday_list"] = holiday_list
        tracked["holiday_assignment"] = frappe.db.get_value(
            "Holiday List Assignment", {"assigned_to": company, "holiday_list": holiday_list}, "name"
        )
        tracked["fiscal_year"] = frappe.db.get_value("Fiscal Year Company", {"company": company}, "parent")
        test_bank, payment_account, company_bank_account = _create_synthetic_company_bank_account(
            company, abbreviation, token
        )

        branch_a = frappe.get_doc({
            "doctype": "Branch",
            "branch": f"Payroll Report Branch A {token}",
        }).insert(ignore_permissions=True)
        branch_b = frappe.get_doc({
            "doctype": "Branch",
            "branch": f"Payroll Report Branch B {token}",
        }).insert(ignore_permissions=True)
        synthetic_branches.extend([branch_a.name, branch_b.name])
        department_a = frappe.get_doc({
            "doctype": "Department",
            "department_name": f"Payroll Report Department A {token}",
            "company": company,
        }).insert(ignore_permissions=True)
        department_b = frappe.get_doc({
            "doctype": "Department",
            "department_name": f"Payroll Report Department B {token}",
            "company": company,
        }).insert(ignore_permissions=True)

        basic_component = _component(
            component_names[0], f"B{token[:3]}", company, expense, depends_on_payment_days=1
        )
        daily_component = _component(
            component_names[1], f"D{token[:3]}", company, expense
        )
        overtime_component = _component(component_names[2], f"O{token[:3]}", company, expense)
        tracked["components"] = [basic_component.name, daily_component.name, overtime_component.name]
        overtime_type = frappe.get_doc({
            "doctype": "Overtime Type",
            "name": f"Test Overtime Type {token}",
            "maximum_overtime_hours_allowed": 2,
            "overtime_salary_component": overtime_component.name,
            "overtime_calculation_method": "Salary Component Based",
            "applicable_salary_component": [{"salary_component": basic_component.name}],
            "standard_multiplier": 2,
            "applicable_for_weekend": 0,
            "weekend_multiplier": 2,
            "applicable_for_public_holiday": 0,
            "public_holiday_multiplier": 2,
        }).insert(ignore_permissions=True)
        tracked["overtime_type"] = overtime_type.name

        monthly_structure = _create_structure(
            f"Test Monthly {token}", company, "BDT", "Monthly Salary", basic_component.name, 30000,
            depends_on_payment_days=1,
        )
        daily_structure = _create_structure(
            f"Test Daily {token}", company, "BDT", "Daily Wage", daily_component.name, 0
        )
        tracked["structures"] = [monthly_structure.name, daily_structure.name]

        employees = [
            _create_employee(
                f"Payroll A {token}", company, holiday_list, salary_mode="Bank",
                branch=branch_a.name, department=department_a.name,
            ),
            _create_employee(
                f"Payroll B {token}", company, holiday_list, salary_mode="Bank",
                branch=branch_b.name, department=department_b.name,
            ),
            _create_employee(
                f"Payroll C {token}", company, holiday_list, salary_mode="Bank",
                branch=branch_b.name, department=department_b.name,
            ),
        ]
        tracked["employees"] = [employee.name for employee in employees]
        employees[0].date_of_joining = date(2026, 8, 15)
        employees[0].save(ignore_permissions=True)
        employees[1].relieving_date = date(2026, 8, 20)
        employees[1].status = "Left"
        employees[1].save(ignore_permissions=True)
        employees[2].relieving_date = date(2026, 8, 20)
        employees[2].status = "Left"
        employees[2].save(ignore_permissions=True)
        for index, employee in enumerate(employees):
            structure = daily_structure if index == 1 else monthly_structure
            _create_assignment(
                employee.name, company, "BDT", payable, structure.name,
                400 if index == 1 else 30000, cost_center,
                from_date=employee.date_of_joining if index == 0 else "2026-08-01",
            )
            tracked["assignments"].append(frappe.db.get_value(
                "Salary Structure Assignment",
                {"employee": employee.name, "salary_structure": structure.name, "docstatus": 1},
                "name",
            ))

        start, end = date(2026, 8, 1), date(2026, 8, 31)
        attendance_hash = None
        for employee in employees:
            employee_start = max(start, frappe.utils.getdate(employee.date_of_joining))
            employee_end = min(end, frappe.utils.getdate(employee.relieving_date)) if employee.relieving_date else end
            for offset in range((employee_end - employee_start).days + 1):
                day = employee_start + timedelta(days=offset)
                # Leave the final payroll-period day without Attendance for
                # Employee A. Its Salary Slip still closes Aug 31, allowing
                # the lifecycle test to isolate Salary Slip consumption from
                # the separate Attendance guard at the same effective date.
                if employee.name == employees[0].name and day == date(2026, 8, 31):
                    continue
                attendance_fields = {
                    "doctype": "Attendance",
                    "employee": employee.name,
                    "attendance_date": day,
                    "status": "Present",
                    "company": company,
                }
                if employee.name == employees[0].name and day == date(2026, 8, 17):
                    attendance_fields.update({
                        "working_hours": 10,
                        "standard_working_hours": 8,
                        "actual_overtime_duration": 2,
                        "overtime_type": overtime_type.name,
                    })
                attendance = frappe.get_doc(attendance_fields).insert(ignore_permissions=True)
                attendance.submit()
                tracked["attendance"].append(attendance.name)

        from tradex_hr.tradexcel_hr.attendance_payroll_boundary import current_attendance_period_hash
        attendance_hash = current_attendance_period_hash(company, start, end)
        period = frappe.get_doc({
            "doctype": "Tradexcel Attendance Period",
            "company": company,
            "from_date": start,
            "to_date": end,
            "status": "Finalized",
            "revision": 1,
            "attendance_hash": attendance_hash,
        })
        period._finalize_context = True
        period.insert(ignore_permissions=True)
        tracked["attendance_period"] = period.name

        # Refresh the app-owned custom permission set as migrate would, so the
        # Payroll Manager's authorized native batch submission is realistic.
        role_setup.ensure_tradex_roles()
        manager = _create_scoped_user("Tradexcel Payroll Manager", company, token)
        approver = _create_scoped_user("Tradexcel Payroll Approver", company, token)
        hr_manager = _create_scoped_user("Tradexcel HR Manager", company, token)
        director = _create_scoped_user("Tradexcel Owner/Director", company, token)
        finance = _create_scoped_user("Accounts User", company, token)
        report_reader = _create_scoped_user("Tradexcel Finance/Accounts Officer", company, token)
        report_worker = _create_scoped_user("Tradexcel Employee/Worker", company, token)
        report_compliance = _create_scoped_user("Tradexcel Compliance Auditor", company, token)
        report_supervisor = _create_scoped_user("Tradexcel Factory Supervisor", company, token)
        report_branch_manager = _create_scoped_user("Tradexcel Branch Manager", company, token)
        report_department_manager = _create_scoped_user("Tradexcel Department Manager", company, token)
        report_attendance_officer = _create_scoped_user("Tradexcel HR/Attendance Officer", company, token)
        report_branch_scoped_payroll = _create_scoped_user(
            "Tradexcel Payroll Manager", company, f"{token}-branch"
        )
        for allow, value in (("Branch", branch_a.name), ("Department", department_a.name)):
            frappe.get_doc({
                "doctype": "User Permission",
                "user": report_branch_scoped_payroll,
                "allow": allow,
                "for_value": value,
                "apply_to_all_doctypes": 1,
            }).insert(ignore_permissions=True)
        tracked["users"] = [
            manager, approver, hr_manager, director, finance, report_reader, report_worker,
            report_compliance, report_supervisor, report_branch_manager,
            report_department_manager, report_attendance_officer, report_branch_scoped_payroll,
        ]
        tracked["permissions"] = frappe.get_all(
            "User Permission", filters={"user": ["in", tracked["users"]]}, pluck="name"
        )
        workflow_users.update(manager=manager, approver=approver, director=director, finance=finance)
        frappe.clear_cache()
        frappe.set_user(approver)
        assert not frappe.has_permission("Salary Slip", "submit")
        frappe.set_user(manager)
        overtime_day = next(
            row for row in frappe.get_all(
                "Attendance",
                filters={"employee": employees[0].name, "attendance_date": date(2026, 8, 17), "docstatus": 1},
                fields=["name", "attendance_date", "actual_overtime_duration", "overtime_type", "standard_working_hours"],
            )
        )
        frappe.set_user(hr_manager)
        overtime_slip = frappe.get_doc({
            "doctype": "Overtime Slip",
            "employee": employees[0].name,
            "company": company,
            "posting_date": end,
            "start_date": overtime_day.attendance_date,
            "end_date": end,
            "overtime_details": [{
                "reference_document": overtime_day.name,
                "date": overtime_day.attendance_date,
                "overtime_type": overtime_type.name,
                "overtime_duration": overtime_day.actual_overtime_duration,
                "standard_working_hours": overtime_day.standard_working_hours,
            }],
        }).insert()
        tracked["overtime_slip"] = overtime_slip.name
        # Even a user temporarily holding both maker and approver roles cannot
        # submit their own money-bearing Overtime Slip.
        maker = frappe.get_doc("User", hr_manager)
        maker.append("roles", {"role": "Tradexcel Payroll Approver"})
        maker.save(ignore_permissions=True)
        frappe.clear_cache()
        frappe.set_user(hr_manager)
        with pytest.raises(frappe.PermissionError, match="maker cannot approve"):
            overtime_slip.submit()
        maker = frappe.get_doc("User", hr_manager)
        maker.roles = [row for row in maker.roles if row.role != "Tradexcel Payroll Approver"]
        maker.save(ignore_permissions=True)
        frappe.clear_cache()
        overtime_slip = frappe.get_doc("Overtime Slip", overtime_slip.name)
        frappe.set_user(approver)
        overtime_slip.submit()
        native_ot_input = frappe.get_value(
            "Additional Salary",
            {"ref_doctype": "Overtime Slip", "ref_docname": overtime_slip.name, "docstatus": 1},
            ["name", "amount", "salary_component"],
            as_dict=True,
        )
        assert native_ot_input and native_ot_input.amount > 0
        tracked["overtime_additional"] = native_ot_input.name
        assert native_ot_input.salary_component == overtime_component.name
        unauthorized_adjustment = frappe.get_doc({
            "doctype": "Additional Salary",
            "company": company,
            "employee": employees[0].name,
            "salary_component": overtime_component.name,
            "amount": 1,
            "payroll_date": end,
        })
        with pytest.raises(frappe.PermissionError):
            unauthorized_adjustment.insert()
            unauthorized_adjustment.submit()
        frappe.set_user(manager)

        # Prove the real Company User Permission denies finalization for another
        # company before reconciliation or readiness reads payroll records.
        other_companies = frappe.get_all(
            "Company", filters={"name": ["!=", company]}, pluck="name", limit=1
        )
        assert other_companies
        out_of_scope_entry = get_controller("Payroll Entry")({"doctype": "Payroll Entry"})
        out_of_scope_entry.company = other_companies[0]
        out_of_scope_entry.custom_tradex_run_key = "TRAD-OUT-OF-SCOPE-TEST"
        out_of_scope_entry.check_permission = lambda *_args, **_kwargs: None
        frappe.set_user(manager)
        with pytest.raises(frappe.PermissionError, match="explicit Company User Permission"):
            out_of_scope_entry.submit_salary_slips()
        from tradex_hr.tradexcel_hr.payment_readiness import inspect_payroll_payment_readiness
        with pytest.raises(frappe.PermissionError, match="explicit Company User Permission"):
            inspect_payroll_payment_readiness(out_of_scope_entry)

        # Inject only the synthetic component for the daily input adapter.
        original_create_daily_input = daily_wage_input.create_daily_wage_input
        monkeypatch.setattr(daily_wage_input, "DEFAULT_COMPONENT", daily_component.name)
        monkeypatch.setattr(native_payroll, "DEFAULT_COMPONENT", daily_component.name)
        monkeypatch.setattr(
            native_payroll,
            "create_daily_wage_input",
            lambda employee, period_name: original_create_daily_input(
                employee, period_name, salary_component=daily_component.name
            ),
        )

        frappe.set_user(manager)
        prepared = native_payroll.prepare_native_payroll(company, start, end)
        assert prepared["status"] == "PREPARED", prepared
        tracked["daily_inputs"] = [
            row.get("additional_salary") for row in prepared.get("daily_inputs", [])
            if row.get("additional_salary")
        ]
        tracked["payroll_entry"] = prepared["payroll_entry"]
        entry = frappe.get_doc("Payroll Entry", tracked["payroll_entry"])
        entry.db_set({"bank_account": company_bank_account, "payment_account": payment_account})
        assert entry.get_payroll_cost_centers_for_employee(
            employees[0].name, monthly_structure.name
        ) == {cost_center: 100}
        assert entry.cost_center == cost_center
        assert entry.docstatus == 0
        assert frappe.db.count("Salary Slip", {"payroll_entry": entry.name}) == 0
        planned, daily_blockers = native_payroll._daily_inputs_for_readiness(
            company, start, end, native_payroll.inspect_native_payroll_readiness(company, start, end)
        )
        if daily_blockers:
            employee_name = next(row["employee"] for row in daily_blockers)
            key = f"DAILY-WAGE:{period.name}:r{period.revision}:{employee_name}:{daily_component.name}"
            actual_input = daily_wage_input._get_existing_input(key)
            calculated = daily_wage_input.calculate_daily_wage_input(employee_name, start, end)
            checks = {
                "docstatus": actual_input.docstatus == 2,
                "disabled": actual_input.disabled,
                "employee": actual_input.employee == employee_name,
                "company": actual_input.company == company,
                "component": actual_input.salary_component == daily_component.name,
                "ref_doctype": actual_input.ref_doctype == "Tradexcel Attendance Period",
                "ref_docname": actual_input.ref_docname == period.name,
                "date": frappe.utils.getdate(actual_input.payroll_date) == frappe.utils.getdate(period.to_date),
                "amount": frappe.utils.flt(actual_input.amount) == frappe.utils.flt(calculated["amount"]),
                "module_component": (native_payroll.DEFAULT_COMPONENT, daily_component.name),
            }
            pytest.fail(f"{daily_blockers}; checks={checks}; existing={actual_input}; calculated={calculated}")
        assert len(planned) == 1 and planned[0]["existing_docstatus"] == 1, planned

        # Native Payroll Entry submit creates the three native draft Salary Slips.
        frappe.in_test = True
        frappe.local.flags.in_test = True
        try:
            apply_workflow({"doctype": "Payroll Entry", "name": entry.name}, "Submit for Review")
        finally:
            frappe.in_test = original_in_test
            frappe.local.flags.in_test = original_in_test
        frappe.set_user("Administrator")
        entry.reload()
        assert entry.docstatus == 1
        assert entry.workflow_state == "Tradexcel Payroll Pending Review"
        assert entry.salary_slips_created == 1
        slips = frappe.get_all(
            "Salary Slip",
            filters={"payroll_entry": entry.name, "docstatus": 0},
            fields=["name", "employee", "gross_pay", "net_pay", "payment_days", "total_working_days", "docstatus"],
            order_by="employee",
        )
        assert len(slips) == 3
        tracked["salary_slips"] = [row.name for row in slips]
        assert {row.employee for row in slips} == set(tracked["employees"])
        assert any(row.gross_pay > 0 for row in slips)

        # Financial reports deliberately exclude unapproved draft payroll.
        # This is checked through the real Desk endpoint as a scoped Finance
        # persona while the native Payroll Entry has created draft slips.
        from frappe.desk.query_report import run as run_report

        frappe.set_user(report_reader)
        report_filters = {
            "company": company,
            "from_date": start.isoformat(),
            "to_date": end.isoformat(),
            "branch": "",
            "department": "",
        }
        draft_components = run_report(
            "Tradexcel Pay Component Register",
            filters={**report_filters, "component_type": "All", "component": ""},
        )
        draft_variance = run_report("Tradexcel Payroll Variance", filters=report_filters)
        assert not ({row.salary_slip for row in draft_components["result"]} & set(tracked["salary_slips"]))
        assert not ({row.employee for row in draft_variance["result"]} & set(tracked["employees"]))
        frappe.set_user(manager)

        slips_by_employee = {row.employee: frappe.get_doc("Salary Slip", row.name) for row in slips}
        joiner_slip = slips_by_employee[employees[0].name]
        assert frappe.utils.getdate(joiner_slip.actual_start_date) == date(2026, 8, 15)
        assert frappe.utils.getdate(joiner_slip.actual_end_date) == end
        assert 0 < joiner_slip.payment_days < joiner_slip.total_working_days
        assert frappe.db.get_value("Salary Structure Assignment", tracked["assignments"][0], "base") == 30000
        assert joiner_slip.earnings[0].depends_on_payment_days
        assert joiner_slip.earnings[0].amount < joiner_slip.earnings[0].default_amount
        assert joiner_slip.gross_pay == joiner_slip.get_component_totals("earnings", depends_on_payment_days=1)
        assert 0 < joiner_slip.gross_pay < 30000
        assert frappe.db.get_value("Additional Salary", native_ot_input.name, "ref_docname") == overtime_slip.name
        assert joiner_slip.net_pay == joiner_slip.gross_pay

        monthly_leaver_slip = slips_by_employee[employees[2].name]
        assert any(row.salary_component == overtime_component.name for row in joiner_slip.earnings)
        assert employees[2].status == "Left"
        assert frappe.utils.getdate(monthly_leaver_slip.actual_start_date) == start
        assert frappe.utils.getdate(monthly_leaver_slip.actual_end_date) == date(2026, 8, 20)
        assert 0 < monthly_leaver_slip.payment_days < monthly_leaver_slip.total_working_days
        assert frappe.db.get_value("Salary Structure Assignment", tracked["assignments"][2], "base") == 30000
        assert monthly_leaver_slip.earnings[0].depends_on_payment_days
        assert monthly_leaver_slip.earnings[0].amount < monthly_leaver_slip.earnings[0].default_amount
        assert monthly_leaver_slip.gross_pay == monthly_leaver_slip.get_component_totals("earnings", depends_on_payment_days=1)
        assert 0 < monthly_leaver_slip.gross_pay < 30000
        assert monthly_leaver_slip.net_pay == monthly_leaver_slip.gross_pay

        daily_leaver_slip = slips_by_employee[employees[1].name]
        daily_input = frappe.get_all(
            "Additional Salary",
            filters={"employee": employees[1].name, "ref_doctype": "Tradexcel Attendance Period",
                     "ref_docname": period.name, "docstatus": 1},
            fields=["name", "amount"],
            limit=1,
        )[0]
        assert employees[1].status == "Left"
        assert frappe.utils.getdate(daily_leaver_slip.actual_end_date) == date(2026, 8, 20)
        assert daily_input.amount == 400 * 20
        assert daily_leaver_slip.gross_pay == daily_input.amount
        assert daily_leaver_slip.net_pay == daily_leaver_slip.gross_pay

        post_exit_attendance = frappe.get_doc({
            "doctype": "Attendance",
            "employee": employees[1].name,
            "attendance_date": "2026-08-21",
            "status": "Present",
            "company": company,
        }).insert(ignore_permissions=True)
        with pytest.raises(frappe.ValidationError, match="relieving date"):
            post_exit_attendance.submit()
        post_exit_attendance.delete(ignore_permissions=True)

        from tradex_hr.tradexcel_hr.financial_readiness import inspect_payroll_financial_readiness
        readiness = inspect_payroll_financial_readiness(entry)
        assert readiness["status"] == "READY", readiness

        frappe.set_user(approver)
        apply_workflow({"doctype": "Payroll Entry", "name": entry.name}, "Review Complete")
        frappe.set_user(director)
        apply_workflow({"doctype": "Payroll Entry", "name": entry.name}, "Approve")
        entry.reload()
        assert entry.workflow_state == payroll_finalization.APPROVED_STATE

        # The role has the native submit permission required by HRMS, but a
        # direct document/API submission remains blocked even after approval.
        frappe.set_user(manager)
        direct_slip = frappe.get_doc("Salary Slip", slips[0].name)
        with pytest.raises(frappe.ValidationError, match="Submit managed Salary Slips from the approved Payroll Entry"):
            direct_slip.submit()

        # Fail only employee B once; HRMS continues with A/C and makes its
        # native accrual JE for the successful subset.
        failing_employee = employees[1].name
        native_submit = SalarySlip.submit
        failed_once = {"value": False}

        def fail_one_once(slip):
            if slip.employee == failing_employee and not failed_once["value"]:
                failed_once["value"] = True
                raise frappe.ValidationError("Synthetic retryable salary-slip validation")
            return native_submit(slip)

        monkeypatch.setattr(SalarySlip, "submit", fail_one_once)
        frappe.set_user(manager)
        frappe.in_test = True
        frappe.local.flags.in_test = True
        try:
            entry = frappe.get_doc("Payroll Entry", entry.name)
            entry.submit_salary_slips()
        finally:
            frappe.in_test = original_in_test
            frappe.local.flags.in_test = original_in_test
        frappe.set_user("Administrator")

        first = payroll_finalization.inspect_payroll_accrual_reconciliation(entry.name)
        if first["status"] != "PARTIAL_SUBMISSION":
            error_log = frappe.get_all("Error Log", fields=["name"], order_by="creation desc", limit=1)
            trace = frappe.db.get_value("Error Log", error_log[0].name, "error") if error_log else ""
            pytest.fail(f"{first}; trace={trace}")
        assert first["safe_to_retry"] is True
        assert first["submitted_slip_count"] == 2
        assert first["draft_slip_count"] == 1
        submitted_first = frappe.get_all(
            "Salary Slip",
            filters={"payroll_entry": entry.name, "docstatus": 1},
            fields=["name", "employee", "journal_entry"],
        )
        assert {row.employee for row in submitted_first} == set(tracked["employees"]) - {failing_employee}
        assert all(row.journal_entry for row in submitted_first)
        tracked["journal_entries"] = sorted({row.journal_entry for row in submitted_first})

        # Retry through the same native Payroll Entry batch method. HRMS must
        # submit only the remaining draft and create a second native accrual.
        entry.reload()
        frappe.in_test = True
        frappe.local.flags.in_test = True
        try:
            entry.submit_salary_slips()
        finally:
            frappe.in_test = original_in_test
            frappe.local.flags.in_test = original_in_test
        final = payroll_finalization.inspect_payroll_accrual_reconciliation(entry.name)
        assert final["status"] == "READY", final
        assert final["submitted_slip_count"] == 3
        assert final["draft_slip_count"] == 0
        assert final["cancelled_slip_count"] == 0
        slips_after_retry = frappe.get_all(
            "Salary Slip",
            filters={"payroll_entry": entry.name, "docstatus": 1},
            fields=["name", "employee", "journal_entry", "end_date"],
        )
        assert {row.employee for row in slips_after_retry} == set(tracked["employees"])
        assert all(row.journal_entry for row in slips_after_retry)
        tracked["journal_entries"] = sorted({row.journal_entry for row in slips_after_retry})
        assert len(tracked["journal_entries"]) == 2
        for name in tracked["journal_entries"]:
            assert frappe.db.get_value("Journal Entry", name, "docstatus") == 1
        assert final["journal_entry_count"] == 2
        # Guard before mutation: Frappe's later dynamic-link check also throws,
        # but only after it has set docstatus=2 inside the current transaction.
        frappe.set_user("Administrator")
        with pytest.raises(frappe.ValidationError, match="salary input"):
            frappe.get_doc("Overtime Slip", tracked["overtime_slip"]).cancel()
        assert frappe.db.get_value("Overtime Slip", tracked["overtime_slip"], "docstatus") == 1
        assert frappe.db.get_value("Additional Salary", tracked["overtime_additional"], "docstatus") == 1
        frappe.set_user(manager)

        # The same native report endpoint exposes only the submitted synthetic
        # payroll, and amounts come from Salary Detail and native Salary Slip
        # totals. Direct execute has the same server-side scope.
        for payroll_persona in (manager, approver, report_reader, hr_manager, director, report_compliance):
            frappe.set_user(payroll_persona)
            assert frappe.has_permission("Salary Slip", "read")
            assert frappe.has_permission("Salary Slip", "report")
            assert frappe.has_permission("Salary Slip", "export")
            component_persona_rows = run_report(
                "Tradexcel Pay Component Register",
                filters={**report_filters, "component_type": "All", "component": ""},
            )["result"]
            variance_persona_rows = run_report("Tradexcel Payroll Variance", filters=report_filters)["result"]
            assert {row.salary_slip for row in component_persona_rows} == {row.name for row in slips_after_retry}
            assert {row.employee for row in variance_persona_rows} == set(tracked["employees"])

        frappe.set_user(report_reader)
        component_result = component_persona_rows
        variance_result = variance_persona_rows
        submitted_names = {row.name for row in slips_after_retry}
        assert component_result
        assert {row.salary_slip for row in component_result} == submitted_names
        assert {row.slip_status for row in component_result} == {"Submitted"}
        native_details = frappe.get_all(
            "Salary Detail",
            filters={"parent": ["in", tuple(submitted_names)], "parenttype": "Salary Slip"},
            fields=["parent", "parentfield", "salary_component", "amount"],
            order_by="parent, idx",
        )
        report_details = {
            (row.salary_slip, row.component_type, row.salary_component, float(row.amount))
            for row in component_result
        }
        expected_details = {
            (row.parent, "Earning" if row.parentfield == "earnings" else "Deduction",
             row.salary_component, float(row.amount))
            for row in native_details if row.parentfield in ("earnings", "deductions")
        }
        assert report_details == expected_details
        native_slips = {
            row.name: row for row in frappe.get_all(
                "Salary Slip",
                filters={"name": ["in", tuple(submitted_names)]},
                fields=["name", "employee", "employee_name", "company", "branch", "department",
                        "gross_pay", "total_deduction", "net_pay", "docstatus"],
            )
        }
        assert {row.employee for row in variance_result} == set(tracked["employees"])
        for row in variance_result:
            employee_slips = [slip for slip in native_slips.values() if slip.employee == row.employee]
            assert row.current_net == sum(slip.net_pay for slip in employee_slips)
            assert row.gross == sum(slip.gross_pay for slip in employee_slips)
            assert row.deductions == sum(slip.total_deduction for slip in employee_slips)
            assert row.review == "No previous payroll"

        frappe.set_user(report_branch_scoped_payroll)
        branch_scoped_components = run_report(
            "Tradexcel Pay Component Register",
            filters={**report_filters, "component_type": "All", "component": ""},
        )["result"]
        branch_scoped_variance = run_report("Tradexcel Payroll Variance", filters=report_filters)["result"]
        assert {row.employee for row in branch_scoped_components} == {employees[0].name}
        assert {row.employee for row in branch_scoped_variance} == {employees[0].name}
        assert run_report(
            "Tradexcel Pay Component Register",
            filters={**report_filters, "branch": branch_b.name, "component_type": "All", "component": ""},
        )["result"] == []
        assert run_report(
            "Tradexcel Payroll Variance",
            filters={**report_filters, "department": department_b.name},
        )["result"] == []
        from tradex_hr.tradexcel_hr.report.tradexcel_pay_component_register.tradexcel_pay_component_register import execute as execute_components
        _, direct_components = execute_components({
            **report_filters, "component_type": "All", "component": "",
        })
        assert {row.employee for row in direct_components} == {employees[0].name}
        assert {row.salary_slip for row in direct_components} == {
            row.name for row in slips_after_retry if row.employee == employees[0].name
        }
        assert run_report(
            "Tradexcel Pay Component Register",
            filters={**report_filters, "branch": f"Outside {token}", "component_type": "All", "component": ""},
        )["result"] == []
        assert run_report(
            "Tradexcel Payroll Variance",
            filters={**report_filters, "department": f"Outside {token}"},
        )["result"] == []
        with pytest.raises(frappe.PermissionError):
            run_report(
                "Tradexcel Payroll Variance",
                filters={**report_filters, "company": "Tradexcel Ceramics Ltd."},
            )

        # Move the synthetic Employee after the August payroll period using
        # native Employee Transfer. Salary Slip must keep its August Branch A
        # snapshot even though Employee now says Branch B.
        frappe.set_user("Administrator")
        historical_transfer = frappe.get_doc({
            "doctype": "Employee Transfer",
            "employee": employees[0].name,
            "company": company,
            "transfer_date": "2026-09-01",
            "transfer_details": [{
                "property": "Branch",
                "current": branch_a.name,
                "new": branch_b.name,
                "fieldname": "branch",
            }],
        }).insert(ignore_permissions=True)
        historical_transfer.submit()
        assert frappe.db.get_value("Employee", employees[0].name, "branch") == branch_b.name
        frappe.set_user(report_reader)
        historical_rows = run_report(
            "Tradexcel Pay Component Register",
            filters={**report_filters, "branch": branch_a.name, "component_type": "All", "component": ""},
        )["result"]
        assert historical_rows
        assert {row.branch for row in historical_rows if row.employee == employees[0].name} == {branch_a.name}
        historical_variance = run_report(
            "Tradexcel Payroll Variance",
            filters={**report_filters, "branch": branch_a.name},
        )["result"]
        employee_a_variance = next(row for row in historical_variance if row.employee == employees[0].name)
        assert employee_a_variance.branch == branch_a.name
        assert frappe.db.get_value("Employee", employees[0].name, "branch") == branch_b.name
        frappe.set_user("Administrator")
        historical_transfer.cancel()
        assert frappe.db.get_value("Employee", employees[0].name, "branch") == branch_a.name

        for excluded_persona in (
            report_worker, report_supervisor, report_branch_manager,
            report_department_manager, report_attendance_officer,
        ):
            frappe.set_user(excluded_persona)
            for report_name, report_filters_for_call in (
            ("Tradexcel Pay Component Register", {**report_filters, "component_type": "All", "component": ""}),
            ("Tradexcel Payroll Variance", report_filters),
            ):
                with pytest.raises(frappe.PermissionError):
                    run_report(report_name, filters=report_filters_for_call)
        with pytest.raises(frappe.PermissionError):
            execute_components({**report_filters, "component_type": "All", "component": ""})
        from tradex_hr.tradexcel_hr.report.tradexcel_payroll_variance.tradexcel_payroll_variance import execute as execute_variance
        with pytest.raises(frappe.PermissionError):
            execute_variance(report_filters)
        frappe.set_user("Administrator")

        # Actual submitted native Salary Slips consume later lifecycle changes
        # and their submitted SSA. Aug 31 is after the assignment's Aug 15
        # effective date and equals the submitted Salary Slip end date.
        consumed_ssa = frappe.get_doc("Salary Structure Assignment", tracked["assignments"][0])
        assert consumed_ssa.docstatus == 1
        consuming_slip = next(row for row in slips_after_retry if row.employee == employees[0].name)
        assert frappe.utils.getdate(consuming_slip.end_date) == date(2026, 8, 31)
        assert not frappe.db.exists("Attendance", {
            "employee": employees[0].name,
            "attendance_date": [">=", "2026-08-31"],
            "docstatus": 1,
        })
        frappe.set_user(approver)
        assert "Tradexcel Payroll Approver" in frappe.get_roles()
        assert frappe.has_permission("Salary Structure Assignment", "cancel", doc=consumed_ssa)
        with pytest.raises(frappe.ValidationError, match="LIFECYCLE_CHANGE_ALREADY_CONSUMED"):
            consumed_ssa.cancel()
        assert frappe.db.get_value("Salary Structure Assignment", consumed_ssa.name, "docstatus") == 1

        frappe.set_user("Administrator")
        old_employment_type = frappe.db.get_value("Employee", employees[0].name, "employment_type")
        new_employment_type = next(
            name for name in frappe.get_all("Employment Type", pluck="name", order_by="name asc")
            if name != old_employment_type
        )
        promotion = frappe.get_doc({
            "doctype": "Employee Promotion",
            "employee": employees[0].name,
            "promotion_date": "2026-08-31",
            "promotion_details": [{
                "property": "Employment Type",
                "current": old_employment_type,
                "new": new_employment_type,
                "fieldname": "employment_type",
            }],
        }).insert(ignore_permissions=True)
        promotion.submit()
        assert frappe.db.get_value("Employee", employees[0].name, "employment_type") == new_employment_type
        frappe.set_user("Administrator")
        with pytest.raises(frappe.ValidationError, match="LIFECYCLE_CHANGE_ALREADY_CONSUMED"):
            promotion.cancel()
        assert frappe.db.get_value("Employee Promotion", promotion.name, "docstatus") == 1
        assert frappe.db.get_value("Employee", employees[0].name, "employment_type") == new_employment_type
        assert frappe.db.get_value("Salary Slip", consuming_slip.name, "docstatus") == 1

        # Payment readiness uses the submitted Salary Slip snapshots and native
        # Bank Account. HRMS creates the only payment Journal Entry.
        from tradex_hr.tradexcel_hr.payment_readiness import inspect_payroll_payment_readiness
        frappe.set_user(manager)
        payment_readiness = inspect_payroll_payment_readiness(entry)
        assert payment_readiness["status"] == "READY_TO_PREPARE_PAYMENT", payment_readiness
        payment_entry = entry.make_bank_entry()
        assert payment_entry and payment_entry.docstatus == 0
        assert payment_entry.voucher_type == "Bank Entry"
        tracked["payment_entry"] = payment_entry.name
        retry_entry = entry.make_bank_entry()
        assert retry_entry.name == payment_entry.name
        draft_payment_readiness = inspect_payroll_payment_readiness(entry)
        assert draft_payment_readiness["status"] == "PAYMENT_ENTRY_DRAFT", draft_payment_readiness
        assert frappe.db.count(
            "Journal Entry Account",
            {"reference_type": "Payroll Entry", "reference_name": entry.name},
        ) >= 3

        frappe.set_user("Administrator")
        payment_entry.cheque_no = f"PAY-{token}"
        payment_entry.cheque_date = end
        payment_entry.save(ignore_permissions=True)
        frappe.set_user(finance)
        payment_entry.submit()
        assert payment_entry.docstatus == 1
        assert payment_entry.total_debit == payment_entry.total_credit
        # A retry after submission returns the native entry instead of creating
        # another payment JE while the bank transaction is still unmatched.
        frappe.set_user(manager)
        posted_retry = entry.make_bank_entry()
        assert posted_retry.name == payment_entry.name
        frappe.set_user("Administrator")
        bank_transaction = frappe.get_doc({
            "doctype": "Bank Transaction",
            "date": end,
            "bank_account": company_bank_account,
            "currency": "BDT",
            "description": f"Synthetic payroll transfer {token}",
            "withdrawal": payment_entry.total_credit,
        }).insert(ignore_permissions=True)
        bank_transaction.submit()
        tracked["bank_transaction"] = bank_transaction.name

        import json
        from erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool import reconcile_vouchers
        reconcile_vouchers(
            bank_transaction.name,
            json.dumps([{
                "payment_doctype": "Journal Entry",
                "payment_name": payment_entry.name,
                "amount": bank_transaction.unallocated_amount,
            }]),
        )
        frappe.set_user(manager)
        reconciled_payment = inspect_payroll_payment_readiness(entry)
        assert reconciled_payment["status"] == "BANK_RECONCILED", reconciled_payment
        assert reconciled_payment["clearance_date"] == end
        assert reconciled_payment["bank_transactions"][0]["status"] == "Reconciled"
        assert frappe.db.get_value("Bank Account", company_bank_account, "bank_account_no") == f"COMPANY-{token[:8]}"

        # Exercise the native Cash path with the same disposable payroll after
        # removing its synthetic Bank settlement. No bank match is supplied.
        frappe.set_user("Administrator")
        frappe.get_doc("Bank Transaction", bank_transaction.name).cancel()
        frappe.delete_doc("Bank Transaction", bank_transaction.name, force=True, ignore_permissions=True)
        frappe.get_doc("Journal Entry", payment_entry.name).cancel()
        frappe.delete_doc("Journal Entry", payment_entry.name, force=True, ignore_permissions=True)
        for slip in slips_after_retry:
            frappe.db.set_value(
                "Salary Slip",
                slip.name,
                {"mode_of_payment": "Cash", "bank_name": None, "bank_account_no": None},
            )

        cash_account = _create_synthetic_cash_account(company, token)
        frappe.db.set_value(
            "Payroll Entry", entry.name,
            {"payment_account": cash_account, "bank_account": None},
        )
        cash_entry_source = frappe.get_doc("Payroll Entry", entry.name)
        frappe.set_user(manager)
        cash_readiness = inspect_payroll_payment_readiness(cash_entry_source)
        assert cash_readiness["status"] == "READY_TO_PREPARE_PAYMENT", cash_readiness
        cash_entry = cash_entry_source.make_bank_entry()
        assert cash_entry and cash_entry.docstatus == 0
        assert cash_entry.voucher_type == "Cash Entry"

        frappe.set_user(finance)
        cash_entry.submit()
        assert cash_entry.docstatus == 1
        assert cash_entry.total_debit == cash_entry.total_credit
        frappe.set_user(manager)
        cash_posted = inspect_payroll_payment_readiness(cash_entry_source)
        assert cash_posted["status"] == "CASH_PAYMENT_ACCOUNTING_POSTED", cash_posted
        assert cash_posted["bank_transactions"] == []
        assert cash_posted["clearance_date"] is None
    finally:
        frappe.set_user("Administrator")
        # The proof stays under three slips (synchronous HRMS path) and enables
        # Frappe test mode around each native submission, suppressing its
        # internal commits. Roll back first; explicitly delete any synthetic
        # records that an upstream helper committed independently.
        frappe.in_test = True
        frappe.local.flags.in_test = True
        frappe.db.rollback()

        cleanup_synthetic_finalization_company(tracked["company"])
        for branch_name in reversed(synthetic_branches):
            if frappe.db.exists("Branch", branch_name):
                frappe.delete_doc("Branch", branch_name, force=True, ignore_permissions=True)
        assert all(not frappe.db.exists("Branch", name) for name in synthetic_branches)

        frappe.in_test = original_in_test
        frappe.local.flags.in_test = original_in_test
        assert not frappe.db.exists("Company", tracked["company"])
        assert all(not frappe.db.exists("Salary Component", name) for name in tracked["components"])
        for doctype in ("Account", "Cost Center", "Warehouse", "GL Entry"):
            assert frappe.db.count(doctype, {"company": tracked["company"]}) == 0
        if tracked["payroll_entry"]:
            assert not frappe.db.exists("Payroll Entry", tracked["payroll_entry"])
        assert frappe.db.count("Salary Slip", {"payroll_entry": tracked["payroll_entry"]}) == 0
        assert not frappe.db.exists("User", workflow_users.get("manager") or "_____")
        frappe.set_user(original_user)
