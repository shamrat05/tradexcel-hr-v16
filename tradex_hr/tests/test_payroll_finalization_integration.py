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


def _component(name, abbreviation, company, account):
    return frappe.get_doc({
        "doctype": "Salary Component",
        "salary_component": name,
        "salary_component_abbr": abbreviation,
        "type": "Earning",
        "depends_on_payment_days": 0,
        "is_tax_applicable": 0,
        "accounts": [{"company": company, "account": account}],
    }).insert(ignore_permissions=True)


def _create_employee(label, company, holiday_list):
    return frappe.get_doc({
        "doctype": "Employee",
        "first_name": label,
        "company": company,
        "date_of_birth": "1990-05-08",
        "date_of_joining": "2020-01-01",
        "gender": "Female",
        "employment_type": "Intern",
        "holiday_list": holiday_list,
        "status": "Active",
    }).insert(ignore_permissions=True)


def _create_structure(name, company, currency, pay_basis, component, amount):
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
            "depends_on_payment_days": 0,
        }],
    }).insert(ignore_permissions=True)
    structure.submit()
    return structure


def _create_assignment(employee, company, currency, payable, structure, base, cost_center):
    assignment = frappe.get_doc({
        "doctype": "Salary Structure Assignment",
        "employee": employee,
        "company": company,
        "currency": currency,
        "salary_structure": structure,
        "from_date": "2026-08-01",
        "base": base,
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
            doc.cancel()
        frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)

    # Transactions and employee data must go before their account/tree masters.
    company_linked = (
        "Payroll Entry", "Salary Slip", "Journal Entry", "Additional Salary",
        "Salary Structure Assignment", "Salary Structure", "Salary Component",
        "Attendance", "Employee Checkin", "Tradexcel Attendance Period", "Employee",
        "Payment Ledger Entry",
    )
    for doctype in company_linked:
        if not frappe.db.exists("DocType", doctype):
            continue
        meta = frappe.get_meta(doctype)
        if meta.has_field("company"):
            filters = {"company": company_name}
        elif doctype == "Employee Checkin":
            employee_names = frappe.get_all("Employee", filters={"company": company_name}, pluck="name")
            filters = {"employee": ["in", employee_names]} if employee_names else None
        else:
            continue
        if filters is None:
            continue
        for name in frappe.get_all(doctype, filters=filters, pluck="name"):
            delete_doc(doctype, name)

    # Cancelling a synthetic native Journal Entry writes reversal GL Entries.
    # They have no value after the disposable company is torn down, and ERPNext
    # correctly prevents deleting an Account while any GL Entry still refers to it.
    if frappe.db.exists("DocType", "GL Entry"):
        frappe.db.delete("GL Entry", {"company": company_name})

    for name in frappe.get_all(
        "User", filters={"email": ["like", f"codex-finalize-%-{token}@example.test"]}, pluck="name"
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
        "Fiscal Year", filters={"year": f"Finalization Test FY {token}"}, pluck="name"
    ):
        delete_doc("Fiscal Year", name)

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

    token = frappe.generate_hash(7).upper()
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
    }
    original_in_test = frappe.in_test
    original_user = frappe.session.user
    component_names = (f"Test Basic {token}", f"Test Daily {token}")
    workflow_users = {}

    try:
        company, abbreviation, payable, expense, cost_center, holiday_list = _create_synthetic_company(token, monkeypatch)
        tracked["company"] = company
        tracked["holiday_list"] = holiday_list
        tracked["holiday_assignment"] = frappe.db.get_value(
            "Holiday List Assignment", {"assigned_to": company, "holiday_list": holiday_list}, "name"
        )
        tracked["fiscal_year"] = frappe.db.get_value("Fiscal Year Company", {"company": company}, "parent")

        basic_component = _component(
            component_names[0], f"B{token[:3]}", company, expense
        )
        daily_component = _component(
            component_names[1], f"D{token[:3]}", company, expense
        )
        tracked["components"] = [basic_component.name, daily_component.name]

        monthly_structure = _create_structure(
            f"Test Monthly {token}", company, "BDT", "Monthly Salary", basic_component.name, 30000
        )
        daily_structure = _create_structure(
            f"Test Daily {token}", company, "BDT", "Daily Wage", daily_component.name, 0
        )
        tracked["structures"] = [monthly_structure.name, daily_structure.name]

        employees = [
            _create_employee(f"Payroll A {token}", company, holiday_list),
            _create_employee(f"Payroll B {token}", company, holiday_list),
            _create_employee(f"Payroll C {token}", company, holiday_list),
        ]
        tracked["employees"] = [employee.name for employee in employees]
        for index, employee in enumerate(employees):
            structure = daily_structure if index == 1 else monthly_structure
            _create_assignment(
                employee.name, company, "BDT", payable, structure.name,
                400 if index == 1 else 30000, cost_center,
            )
            tracked["assignments"].append(frappe.db.get_value(
                "Salary Structure Assignment",
                {"employee": employee.name, "salary_structure": structure.name, "docstatus": 1},
                "name",
            ))

        start, end = date(2026, 8, 1), date(2026, 8, 31)
        attendance_hash = None
        for employee in employees:
            for offset in range(31):
                day = start + timedelta(days=offset)
                attendance = frappe.get_doc({
                    "doctype": "Attendance",
                    "employee": employee.name,
                    "attendance_date": day,
                    "status": "Present",
                    "company": company,
                }).insert(ignore_permissions=True)
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
        director = _create_scoped_user("Tradexcel Owner/Director", company, token)
        tracked["users"] = [manager, approver, director]
        tracked["permissions"] = frappe.get_all(
            "User Permission", filters={"user": ["in", tracked["users"]]}, pluck="name"
        )
        workflow_users.update(manager=manager, approver=approver, director=director)
        frappe.clear_cache()
        frappe.set_user(approver)
        assert not frappe.has_permission("Salary Slip", "submit")
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
            fields=["name", "employee", "gross_pay", "net_pay"],
            order_by="employee",
        )
        assert len(slips) == 3
        tracked["salary_slips"] = [row.name for row in slips]
        assert {row.employee for row in slips} == set(tracked["employees"])
        assert any(row.gross_pay > 0 for row in slips)

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
            fields=["name", "employee", "journal_entry"],
        )
        assert {row.employee for row in slips_after_retry} == set(tracked["employees"])
        assert all(row.journal_entry for row in slips_after_retry)
        tracked["journal_entries"] = sorted({row.journal_entry for row in slips_after_retry})
        assert len(tracked["journal_entries"]) == 2
        for name in tracked["journal_entries"]:
            assert frappe.db.get_value("Journal Entry", name, "docstatus") == 1
        assert final["journal_entry_count"] == 2
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

        frappe.in_test = original_in_test
        frappe.local.flags.in_test = original_in_test
        assert not frappe.db.exists("Company", tracked["company"])
        for doctype in ("Account", "Cost Center", "Warehouse", "GL Entry"):
            assert frappe.db.count(doctype, {"company": tracked["company"]}) == 0
        if tracked["payroll_entry"]:
            assert not frappe.db.exists("Payroll Entry", tracked["payroll_entry"])
        assert frappe.db.count("Salary Slip", {"payroll_entry": tracked["payroll_entry"]}) == 0
        assert not frappe.db.exists("User", workflow_users.get("manager") or "_____")
        frappe.set_user(original_user)
