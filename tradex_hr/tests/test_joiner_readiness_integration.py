"""Synthetic native recruitment and direct-hire readiness integration tests."""
from __future__ import annotations

import os
from datetime import date, timedelta

import frappe
import pytest


@pytest.fixture(scope="module", autouse=True)
def frappe_site():
    frappe.init(
        site=os.environ.get("FRAPPE_TEST_SITE", "hrms-v16.localhost"),
        sites_path=os.environ.get("FRAPPE_TEST_SITES_PATH", "/home/sanchita/frappe-bench-v16/sites"),
        force=True,
    )
    frappe.connect()
    yield
    frappe.destroy()


def _designation(token, label):
    return frappe.get_doc({
        "doctype": "Designation",
        "designation_name": f"Joiner {label} {token}",
    }).insert(ignore_permissions=True).name


def _opening(company, designation, token, label):
    return frappe.get_doc({
        "doctype": "Job Opening",
        "job_title": f"Joiner {label} {token}",
        "company": company,
        "designation": designation,
        "status": "Open",
    }).insert()


def _applicant(opening, designation, token, label):
    return frappe.get_doc({
        "doctype": "Job Applicant",
        "applicant_name": f"Synthetic {label} {token}",
        "email_id": f"joiner-{label.lower()}-{token}@example.test",
        "status": "Shortlisted",
        "designation": designation,
        "job_title": opening.name if opening else None,
    }).insert()


def _offer(applicant, company, designation, status="Accepted", submit=True):
    offer = frappe.get_doc({
        "doctype": "Job Offer",
        "job_applicant": applicant.name,
        "offer_date": "2026-08-01",
        "designation": designation,
        "company": company,
        "status": status,
    }).insert()
    if submit:
        offer.submit()
    return offer


def _onboarding(applicant, offer, company, designation, token, label):
    return frappe.get_doc({
        "doctype": "Employee Onboarding",
        "job_applicant": applicant.name,
        "job_offer": offer.name,
        "company": company,
        "designation": designation,
        "employee_name": applicant.applicant_name,
        "date_of_joining": "2026-08-15",
        "boarding_begins_on": "2026-08-15",
    })


def test_native_recruited_and_direct_hire_joiner_boundaries(monkeypatch):
    from tradex_hr.tests.test_payroll_finalization_integration import (
        _component,
        _create_employee,
        _create_scoped_user,
        _create_synthetic_company,
        _create_structure,
        _create_assignment,
        cleanup_synthetic_finalization_company,
    )
    from tradex_hr.tradexcel_hr.joiner_readiness import (
        interview_feedback_query_conditions,
        interview_query_conditions,
        inspect_joiner_readiness,
        job_applicant_query_conditions,
        recruitment_has_permission,
        validate_recruitment_company_scope,
    )

    token = frappe.generate_hash(8).upper()[:8]
    other_token = frappe.generate_hash(8).upper()[:8]
    company = other_company = None
    openings, applicants, offers, onboardings, employees, designations, users, tasks = ([] for _ in range(8))
    old_user = frappe.session.user
    old_in_test = frappe.in_test
    old_local_in_test = getattr(frappe.local.flags, "in_test", False)
    try:
        frappe.set_user("Administrator")
        company, _abbr, _payable, _expense, _cost, holiday_list = _create_synthetic_company(token, monkeypatch)
        other_company, _abbr2, _payable2, _expense2, _cost2, other_holiday_list = _create_synthetic_company(other_token, monkeypatch)
        from tradex_hr.role_setup import ensure_tradex_roles
        ensure_tradex_roles()
        role_user = _create_scoped_user("Tradexcel HR Manager", company, token)
        users.append(role_user)
        assert "HR User" not in frappe.get_roles(role_user)
        assert frappe.has_permission("Job Opening", "create", user=role_user)
        assert frappe.has_permission("Job Applicant", "create", user=role_user)
        assert frappe.has_permission("Interview", "create", user=role_user)
        assert frappe.has_permission("Job Offer", "submit", user=role_user)
        assert frappe.has_permission("Employee Onboarding", "submit", user=role_user)
        assert not frappe.has_permission("Job Offer", "cancel", user=role_user)
        assert not frappe.has_permission("Job Offer", "delete", user=role_user)
        assert not frappe.has_permission("Employee Onboarding", "cancel", user=role_user)
        assert not frappe.has_permission("Employee Onboarding", "delete", user=role_user)
        assert frappe.has_permission("Task", "read", user=role_user)
        assert frappe.has_permission("Task", "write", user=role_user)
        assert not frappe.has_permission("Task", "create", user=role_user)
        assert not frappe.has_permission("Task", "delete", user=role_user)
        assert not frappe.has_permission("Journal Entry", "submit", user=role_user)
        assert not frappe.has_permission("Salary Slip", "submit", user=role_user)
        assert not frappe.has_permission("Salary Structure Assignment", "submit", user=role_user)

        designation = _designation(token, "Operator")
        other_designation = _designation(token, "Clerk")
        designations.extend((designation, other_designation))
        foreign_opening = _opening(other_company, designation, other_token, "EFL")
        openings.append(foreign_opening.name)
        frappe.set_user(role_user)
        opening = _opening(company, designation, token, "TCL")
        openings.append(opening.name)

        accepted_applicant = _applicant(opening, designation, token, "Accepted")
        applicants.append(accepted_applicant.name)
        assert frappe.permissions.has_controller_permissions(
            accepted_applicant, "write", user=role_user
        ), "Applicant controller rejected the custom HR role"
        assert frappe.permissions.has_user_permission(
            accepted_applicant, user=role_user, ptype="write"
        ), "Company User Permission rejected the same-company applicant"
        assert frappe.has_permission("Job Applicant", "write", doc=accepted_applicant, user=role_user)
        accepted_offer = _offer(accepted_applicant, company, designation)
        offers.append(accepted_offer.name)
        accepted_onboarding = _onboarding(
            accepted_applicant, accepted_offer, company, designation, token, "Accepted"
        )
        accepted_onboarding.holiday_list = holiday_list
        accepted_onboarding.append("activities", {
            "activity_name": f"Synthetic onboarding activity {token}",
            "role": "Tradexcel HR Manager",
            "begin_on": 0,
            "duration": 1,
            "required_for_employee_creation": 1,
        })
        accepted_onboarding.insert()
        onboardings.append(accepted_onboarding.name)
        accepted_onboarding.submit()
        assert accepted_onboarding.job_offer == accepted_offer.name
        assert accepted_onboarding.project
        assert frappe.db.count("Task", {"project": accepted_onboarding.project}) == 1
        task_name = accepted_onboarding.activities[0].task
        assert frappe.db.get_value("Task", task_name, "status") != "Completed"
        from hrms.hr.doctype.job_applicant.job_applicant import make_employee as employee_from_applicant
        incomplete_mapper = employee_from_applicant(accepted_applicant.name)
        incomplete_mapper.first_name = incomplete_mapper.first_name or "Synthetic Incomplete"
        incomplete_mapper.company = company
        incomplete_mapper.date_of_birth = "1990-05-08"
        incomplete_mapper.date_of_joining = "2026-08-15"
        incomplete_mapper.gender = "Female"
        incomplete_mapper.employment_type = "Intern"
        with pytest.raises(frappe.ValidationError, match="mandatory tasks"):
            try:
                incomplete_mapper.insert(ignore_permissions=True)
            finally:
                if incomplete_mapper.name and frappe.db.exists("Employee", incomplete_mapper.name):
                    employees.append(incomplete_mapper.name)
        accepted_onboarding.reload()
        accepted_onboarding.mark_onboarding_as_completed()
        from hrms.hr.doctype.employee_onboarding.employee_onboarding import make_employee
        recruited_employee = make_employee(accepted_onboarding.name)
        recruited_employee.first_name = recruited_employee.employee_name
        recruited_employee.date_of_birth = date(1990, 5, 8)
        recruited_employee.date_of_joining = date(2026, 8, 15)
        recruited_employee.gender = "Female"
        recruited_employee.employment_type = "Intern"
        recruited_employee.holiday_list = holiday_list
        recruited_employee.salary_mode = "Cash"
        recruited_employee.insert()
        employees.append(recruited_employee.name)
        assert recruited_employee.job_applicant == accepted_applicant.name

        # Prove this native onboarding-created Employee can pass through the
        # existing managed first-payroll path and produce a native draft slip.
        from frappe.model.workflow import apply_workflow
        from tradex_hr import role_setup
        from tradex_hr.tradexcel_hr.attendance_payroll_boundary import current_attendance_period_hash
        from tradex_hr.tradexcel_hr.joiner_readiness import inspect_joiner_readiness
        from tradex_hr.tradexcel_hr.native_payroll import prepare_native_payroll

        payroll_start, payroll_end = date(2026, 8, 1), date(2026, 8, 31)
        component = _component(
            f"Joiner Basic {token}", f"JB{token[:2]}", company, _expense,
            depends_on_payment_days=1,
        )
        structure = _create_structure(
            f"Joiner Monthly {token}", company, "BDT", "Monthly Salary",
            component.name, 30000, depends_on_payment_days=1,
        )
        assignment = _create_assignment(
            recruited_employee.name, company, "BDT", _payable, structure.name,
            30000, _cost, from_date="2026-08-15",
        )
        for offset in range(17):
            attendance = frappe.get_doc({
                "doctype": "Attendance",
                "employee": recruited_employee.name,
                "attendance_date": date(2026, 8, 15) + timedelta(days=offset),
                "status": "Present",
                "company": company,
            }).insert(ignore_permissions=True)
            attendance.submit()
        period = frappe.get_doc({
            "doctype": "Tradexcel Attendance Period",
            "company": company,
            "from_date": payroll_start,
            "to_date": payroll_end,
            "status": "Finalized",
            "revision": 1,
            "attendance_hash": current_attendance_period_hash(company, payroll_start, payroll_end),
        })
        period._finalize_context = True
        period.insert(ignore_permissions=True)
        role_setup.ensure_tradex_roles()
        payroll_manager = _create_scoped_user("Tradexcel Payroll Manager", company, token)
        users.append(payroll_manager)
        frappe.clear_cache()
        frappe.set_user(payroll_manager)
        joiner_result = inspect_joiner_readiness(recruited_employee.name)
        assert joiner_result["hire_source"] == "Recruitment"
        assert "SALARY_ASSIGNMENT_REQUIRED" not in {
            finding["code"] for finding in joiner_result["sections"]["payroll"]["findings"]
        }, joiner_result["sections"]["payroll"]
        prepared = prepare_native_payroll(company, payroll_start, payroll_end)
        assert prepared["status"] == "PREPARED", prepared
        payroll_entry = frappe.get_doc("Payroll Entry", prepared["payroll_entry"])
        original_in_test = frappe.in_test
        frappe.in_test = True
        frappe.local.flags.in_test = True
        try:
            apply_workflow(
                {"doctype": "Payroll Entry", "name": payroll_entry.name},
                "Submit for Review",
            )
        finally:
            frappe.in_test = original_in_test
            frappe.local.flags.in_test = original_in_test
        draft_slips = frappe.get_all(
            "Salary Slip",
            filters={"payroll_entry": payroll_entry.name, "employee": recruited_employee.name, "docstatus": 0},
            fields=["name"],
        )
        assert len(draft_slips) == 1, draft_slips
        draft_slip = frappe.get_doc("Salary Slip", draft_slips[0].name)
        assert draft_slip.actual_start_date == date(2026, 8, 15)
        assert draft_slip.actual_end_date == payroll_end
        assert draft_slip.gross_pay > 0 and draft_slip.net_pay == draft_slip.gross_pay
        frappe.set_user("Administrator")

        draft_applicant = _applicant(opening, designation, token, "Draft")
        applicants.append(draft_applicant.name)
        draft_offer = _offer(draft_applicant, company, designation, submit=False)
        offers.append(draft_offer.name)
        assert draft_offer.docstatus == 0
        assert "tradex_hr.tradexcel_hr.joiner_readiness.validate_employee_onboarding" in \
            frappe.get_doc_hooks()["Employee Onboarding"]["validate"]
        with pytest.raises(frappe.ValidationError, match="submitted, accepted"):
            _onboarding(draft_applicant, draft_offer, company, designation, token, "Draft").insert(ignore_permissions=True)

        pending_applicant = _applicant(opening, designation, token, "Pending")
        applicants.append(pending_applicant.name)
        pending_offer = _offer(pending_applicant, company, designation, status="Awaiting Response")
        offers.append(pending_offer.name)
        with pytest.raises(frappe.ValidationError, match="submitted, accepted"):
            _onboarding(pending_applicant, pending_offer, company, designation, token, "Pending").insert(ignore_permissions=True)

        unscoped_applicant = _applicant(None, designation, token, "Unscoped")
        applicants.append(unscoped_applicant.name)
        unscoped_offer = _offer(unscoped_applicant, company, designation)
        offers.append(unscoped_offer.name)
        with pytest.raises(frappe.ValidationError, match="linked to a Job Opening"):
            _onboarding(unscoped_applicant, unscoped_offer, company, designation, token, "Unscoped").insert(ignore_permissions=True)

        wrong_applicant = _applicant(opening, designation, token, "WrongApplicant")
        applicants.append(wrong_applicant.name)
        with pytest.raises(frappe.ValidationError, match="same applicant"):
            _onboarding(wrong_applicant, accepted_offer, company, designation, token, "WrongApplicant").insert(ignore_permissions=True)

        scope_applicant = _applicant(opening, designation, token, "Scope")
        applicants.append(scope_applicant.name)
        scope_offer = _offer(scope_applicant, company, designation)
        offers.append(scope_offer.name)
        with pytest.raises(frappe.ValidationError, match="same company"):
            _onboarding(scope_applicant, scope_offer, other_company, designation, token, "WrongCompany").insert(ignore_permissions=True)
        wrong_opening_applicant = _applicant(opening, designation, token, "WrongOpening")
        applicants.append(wrong_opening_applicant.name)
        foreign_company_offer = _offer(wrong_opening_applicant, other_company, designation)
        offers.append(foreign_company_offer.name)
        with pytest.raises(frappe.ValidationError, match="Job Opening must belong"):
            _onboarding(wrong_opening_applicant, foreign_company_offer, other_company, designation, token, "ForeignOffer").insert(ignore_permissions=True)

        with pytest.raises(frappe.ValidationError, match="designation"):
            _onboarding(scope_applicant, scope_offer, company, other_designation, token, "WrongDesignation").insert(ignore_permissions=True)

        foreign_applicant = _applicant(foreign_opening, designation, other_token, "Foreign")
        applicants.append(foreign_applicant.name)
        foreign_offer = _offer(foreign_applicant, other_company, designation)
        offers.append(foreign_offer.name)
        foreign_onboarding = _onboarding(
            foreign_applicant, foreign_offer, other_company, designation, other_token, "Foreign"
        ).insert(ignore_permissions=True)
        onboardings.append(foreign_onboarding.name)
        foreign_employee = _create_employee(f"Foreign Joiner {other_token}", other_company, other_holiday_list, salary_mode="Cash")
        employees.append(foreign_employee.name)
        foreign_attempt_applicant = _applicant(foreign_opening, designation, other_token, "ForeignAttempt")
        applicants.append(foreign_attempt_applicant.name)
        foreign_attempt_offer = _offer(foreign_attempt_applicant, other_company, designation)
        offers.append(foreign_attempt_offer.name)
        foreign_draft_applicant = _applicant(foreign_opening, designation, other_token, "ForeignDraft")
        applicants.append(foreign_draft_applicant.name)
        foreign_draft_offer = _offer(
            foreign_draft_applicant, other_company, designation,
            status="Awaiting Response", submit=False,
        )
        offers.append(foreign_draft_offer.name)
        foreign_task = frappe.get_doc({
            "doctype": "Task",
            "subject": f"Synthetic foreign task {token}",
            "company": other_company,
        }).insert(ignore_permissions=True)
        tasks.append(foreign_task.name)
        company_condition = job_applicant_query_conditions(role_user)
        assert company in company_condition
        assert other_company not in company_condition
        for condition in (interview_query_conditions(role_user), interview_feedback_query_conditions(role_user)):
            assert company in condition
            assert other_company not in condition
        assert frappe.has_permission("Job Applicant", "read", doc=foreign_applicant, user=role_user) is False
        assert frappe.has_permission("Job Opening", "read", doc=foreign_opening, user=role_user) is False
        assert frappe.has_permission("Job Offer", "read", doc=foreign_offer, user=role_user) is False
        assert frappe.has_permission("Employee Onboarding", "read", doc=foreign_onboarding, user=role_user) is False
        assert frappe.has_permission("Task", "read", doc=foreign_task, user=role_user) is False
        assert frappe.has_permission("Task", "write", doc=foreign_task, user=role_user) is False
        foreign_interview = frappe._dict({
            "doctype": "Interview", "job_opening": foreign_opening.name,
            "job_applicant": foreign_applicant.name,
        })
        mismatched_interview = frappe._dict({
            "doctype": "Interview", "job_opening": opening.name,
            "job_applicant": foreign_applicant.name,
        })
        foreign_feedback = frappe._dict({
            "doctype": "Interview Feedback", "job_applicant": foreign_applicant.name,
        })
        unscoped_interview = frappe._dict({
            "doctype": "Interview", "job_opening": None, "job_applicant": None,
        })
        unscoped_feedback = frappe._dict({
            "doctype": "Interview Feedback", "interview": None, "job_applicant": None,
        })
        assert recruitment_has_permission(foreign_interview, "read", user=role_user) is False
        assert recruitment_has_permission(mismatched_interview, "read", user=role_user) is False
        assert recruitment_has_permission(foreign_feedback, "read", user=role_user) is False
        assert recruitment_has_permission(unscoped_interview, "read", user=role_user) is False
        assert recruitment_has_permission(unscoped_feedback, "read", user=role_user) is False
        frappe.set_user(role_user)
        from tradex_hr.tradexcel_hr.joiner_readiness import validate_recruitment_company_scope
        assert frappe.session.user == role_user
        assert "Tradexcel HR Manager" in frappe.get_roles(role_user)
        assert "tradex_hr.tradexcel_hr.joiner_readiness.validate_recruitment_company_scope" in \
            frappe.get_doc_hooks()["Job Opening"]["validate"]
        with pytest.raises(frappe.PermissionError):
            validate_recruitment_company_scope(frappe._dict({
                "doctype": "Job Opening", "company": other_company
            }))
        with pytest.raises(frappe.PermissionError):
            _opening(other_company, designation, token, "Unauthorized")
        with pytest.raises(frappe.PermissionError):
            _applicant(foreign_opening, designation, token, "Unauthorized")
        with pytest.raises(frappe.PermissionError):
            validate_recruitment_company_scope(foreign_interview)
        with pytest.raises(frappe.PermissionError):
            validate_recruitment_company_scope(foreign_feedback)
        with pytest.raises(frappe.PermissionError):
            validate_recruitment_company_scope(mismatched_interview)
        foreign_draft_offer.offer_date = "2026-09-24"
        with pytest.raises(frappe.PermissionError):
            foreign_draft_offer.save(ignore_permissions=True)
        own_visible = frappe.get_list(
            "Job Applicant", filters={"name": accepted_applicant.name}, pluck="name"
        )
        assert own_visible == [accepted_applicant.name]
        visible_foreign = frappe.get_list(
            "Job Applicant", filters={"name": foreign_applicant.name}, pluck="name"
        )
        assert not visible_foreign
        assert frappe.get_list("Interview", fields=["name"], limit=1) == []
        assert frappe.get_list("Interview Feedback", fields=["name"], limit=1) == []
        frappe.set_user("Administrator")

        foreign_before = frappe.db.count("Employee", {"company": other_company})
        frappe.set_user(role_user)
        with pytest.raises(frappe.PermissionError):
            _onboarding(foreign_attempt_applicant, foreign_attempt_offer, other_company, designation, other_token, "CrossCompany").insert(ignore_permissions=True)
        with pytest.raises(frappe.PermissionError):
            inspect_joiner_readiness(foreign_employee.name)
        assert frappe.db.count("Employee", {"company": other_company}) == foreign_before
        frappe.set_user("Administrator")

        second_employee = frappe.get_doc({
            "doctype": "Employee", "first_name": f"Duplicate Employee {token}",
            "company": company, "date_of_birth": "1990-05-08", "date_of_joining": "2026-10-01",
            "gender": "Female", "employment_type": "Intern", "status": "Active",
            "job_applicant": accepted_applicant.name,
        })
        with pytest.raises(frappe.ValidationError, match="already linked to Employee"):
            second_employee.insert(ignore_permissions=True)

        cash_employee = _create_employee(f"Direct Cash {token}", company, holiday_list, salary_mode="Cash")
        # The shared payroll fixture only populates Bank mode; establish the
        # intended native Cash choice explicitly for this onboarding scenario.
        cash_employee.db_set("salary_mode", "Cash")
        bank_employee = _create_employee(f"Direct Bank {token}", company, holiday_list, salary_mode="Bank")
        bank_secret = bank_employee.bank_ac_no
        bank_employee.db_set({"bank_name": None, "bank_ac_no": None})
        blank_employee = _create_employee(f"Direct Blank {token}", company, holiday_list)
        cheque_employee = _create_employee(f"Direct Cheque {token}", company, holiday_list)
        cheque_employee.db_set("salary_mode", "Cheque")
        employees.extend((cash_employee.name, bank_employee.name, blank_employee.name, cheque_employee.name))

        cash_result = inspect_joiner_readiness(cash_employee.name)
        bank_result = inspect_joiner_readiness(bank_employee.name)
        blank_result = inspect_joiner_readiness(blank_employee.name)
        cheque_result = inspect_joiner_readiness(cheque_employee.name)
        population_result = inspect_joiner_readiness(recruited_employee.name)
        assert cash_result["hire_source"] == "Direct Hire"
        assert cash_result["sections"]["payment"]["status"] == "READY"
        assert "BANK_NAME_REQUIRED" in {f["code"] for f in bank_result["sections"]["payment"]["findings"]}
        assert "BANK_ACCOUNT_REQUIRED" in {f["code"] for f in bank_result["sections"]["payment"]["findings"]}
        assert "PAYMENT_MODE_REQUIRED" in {f["code"] for f in blank_result["sections"]["payment"]["findings"]}
        assert "PAYMENT_MODE_REVIEW_REQUIRED" in {f["code"] for f in cheque_result["sections"]["payment"]["findings"]}
        assert "SALARY_ASSIGNMENT_REQUIRED" in {
            f["code"] for f in cash_result["sections"]["payroll"]["findings"]
        }
        assert population_result["sections"]["payroll"]["status"] == "READY"
        assert "FIRST_PAYROLL_COMPANY_POPULATION_REVIEW" not in {
            f["code"] for f in population_result["sections"]["payroll"]["findings"]
        }
        assert cash_result["sections"]["payroll"]["status"] == "NEEDS_ATTENTION"
        assert bank_secret not in repr(bank_result)
        assert bank_employee.personal_email in {None, ""}
        assert not bank_employee.job_applicant
        assert not bank_employee.user_id
        assert "BIOMETRIC_SETUP_REVIEW" in {f["code"] for f in cash_result["sections"]["attendance"]["findings"]}

    finally:
        frappe.set_user("Administrator")
        for name in reversed(onboardings):
            if frappe.db.exists("Employee Onboarding", name):
                doc = frappe.get_doc("Employee Onboarding", name)
                if doc.docstatus == 1:
                    doc.cancel()
                frappe.delete_doc("Employee Onboarding", name, force=True, ignore_permissions=True)
        for name in reversed(tasks):
            if frappe.db.exists("Task", name):
                frappe.delete_doc("Task", name, force=True, ignore_permissions=True)
        for name in reversed(offers):
            if frappe.db.exists("Job Offer", name):
                doc = frappe.get_doc("Job Offer", name)
                if doc.docstatus == 1:
                    doc.cancel()
                frappe.delete_doc("Job Offer", name, force=True, ignore_permissions=True)
        for name in reversed(employees):
            if frappe.db.exists("Employee", name):
                frappe.delete_doc("Employee", name, force=True, ignore_permissions=True)
        for name in reversed(applicants):
            if frappe.db.exists("Job Applicant", name):
                frappe.delete_doc("Job Applicant", name, force=True, ignore_permissions=True)
        for name in reversed(openings):
            if frappe.db.exists("Job Opening", name):
                frappe.delete_doc("Job Opening", name, force=True, ignore_permissions=True)
        for name in reversed(designations):
            if frappe.db.exists("Designation", name):
                frappe.delete_doc("Designation", name, force=True, ignore_permissions=True)
        for user in users:
            for permission in frappe.get_all("User Permission", filters={"user": user}, pluck="name"):
                frappe.delete_doc("User Permission", permission, force=True, ignore_permissions=True)
            if frappe.db.exists("User", user):
                frappe.delete_doc("User", user, force=True, ignore_permissions=True)
        for test_company in (company, other_company):
            if test_company:
                cleanup_synthetic_finalization_company(test_company)
        frappe.in_test = old_in_test
        frappe.local.flags.in_test = old_local_in_test
        frappe.set_user(old_user)


def test_native_recruitment_mappers_cannot_bypass_employee_onboarding(monkeypatch):
    from tradex_hr.tests.test_payroll_finalization_integration import (
        _create_synthetic_company,
        cleanup_synthetic_finalization_company,
    )
    token = frappe.generate_hash(8).upper()[:8]
    company = None
    openings, applicants, offers, employees, designations = [], [], [], [], []
    old_user = frappe.session.user
    try:
        frappe.set_user("Administrator")
        company, _abbr, *_ = _create_synthetic_company(token, monkeypatch)
        designation = _designation(token, "Mapper Bypass")
        designations.append(designation)
        opening = _opening(company, designation, token, "Mapper")
        openings.append(opening.name)

        applicant_only = _applicant(opening, designation, token, "ApplicantOnly")
        applicants.append(applicant_only.name)
        from hrms.hr.doctype.job_applicant.job_applicant import make_employee as employee_from_applicant
        from hrms.hr.doctype.job_offer.job_offer import make_employee as employee_from_offer

        def fill_employee(employee):
            employee.first_name = employee.first_name or employee.employee_name or "Synthetic Mapper"
            employee.company = company
            employee.date_of_birth = "1990-05-08"
            employee.date_of_joining = "2026-09-01"
            employee.gender = "Female"
            employee.employment_type = "Intern"
            employee.status = "Active"
            return employee

        mapped_applicant = fill_employee(employee_from_applicant(applicant_only.name))
        with pytest.raises(frappe.ValidationError, match="Employee Onboarding"):
            try:
                mapped_applicant.insert(ignore_permissions=True)
            finally:
                if mapped_applicant.name and frappe.db.exists("Employee", mapped_applicant.name):
                    employees.append(mapped_applicant.name)

        offer_applicant = _applicant(opening, designation, token, "OfferOnly")
        applicants.append(offer_applicant.name)
        accepted_offer = _offer(offer_applicant, company, designation)
        offers.append(accepted_offer.name)
        mapped_offer = fill_employee(employee_from_offer(accepted_offer.name))
        with pytest.raises(frappe.ValidationError, match="Employee Onboarding"):
            try:
                mapped_offer.insert(ignore_permissions=True)
            finally:
                if mapped_offer.name and frappe.db.exists("Employee", mapped_offer.name):
                    employees.append(mapped_offer.name)
    finally:
        frappe.set_user("Administrator")
        for name in reversed(employees):
            if frappe.db.exists("Employee", name):
                frappe.delete_doc("Employee", name, force=True, ignore_permissions=True)
        for name in reversed(offers):
            if frappe.db.exists("Job Offer", name):
                doc = frappe.get_doc("Job Offer", name)
                if doc.docstatus == 1:
                    doc.cancel()
                frappe.delete_doc("Job Offer", name, force=True, ignore_permissions=True)
        for name in reversed(applicants):
            if frappe.db.exists("Job Applicant", name):
                frappe.delete_doc("Job Applicant", name, force=True, ignore_permissions=True)
        for name in reversed(openings):
            if frappe.db.exists("Job Opening", name):
                frappe.delete_doc("Job Opening", name, force=True, ignore_permissions=True)
        for name in reversed(designations):
            if frappe.db.exists("Designation", name):
                frappe.delete_doc("Designation", name, force=True, ignore_permissions=True)
        if company:
            cleanup_synthetic_finalization_company(company)
        frappe.set_user(old_user)
