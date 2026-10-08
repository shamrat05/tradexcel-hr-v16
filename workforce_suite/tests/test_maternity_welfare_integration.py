"""Synthetic native Leave workflow proof; all records are cleaned in finally."""
import os

import frappe
import pytest


@pytest.fixture(scope="module", autouse=True)
def frappe_site():
    frappe.init(
        site=os.environ.get("FRAPPE_TEST_SITE", "test_workforce.localhost"),
        sites_path=os.environ.get("FRAPPE_TEST_SITES_PATH", "./sites"),
        force=True,
    )
    frappe.connect()
    yield
    frappe.destroy()


def test_native_maternity_leave_application_creates_native_attendance_and_ledger(monkeypatch):
    from workforce_suite.tests.test_payroll_finalization_integration import (
        _create_employee,
        _create_synthetic_company,
        cleanup_synthetic_finalization_company,
    )

    try:
        old_user = frappe.session.user
    except RuntimeError:
        pytest.skip("Native Leave integration requires an initialized isolated Frappe site.")
    token = frappe.generate_hash(8).upper()[:8]
    company = employee = leave_type = leave_period = allocation = application = None
    try:
        frappe.set_user("Administrator")
        company, _abbr, _payable, _expense, _cost_center, holiday_list = _create_synthetic_company(token, monkeypatch)
        holiday = frappe.get_doc("Holiday List", holiday_list)
        holiday.append("holidays", {"holiday_date": "2026-09-22", "description": "TEST ONLY Maternity Parity"})
        holiday.save(ignore_permissions=True)

        employee = _create_employee(f"Synthetic Maternity Leave {token}", company, holiday_list)
        employee.date_of_joining = "2020-01-01"
        employee.save(ignore_permissions=True)

        leave_type = frappe.get_doc({
            "doctype": "Leave Type",
            "leave_type_name": f"TEST ONLY Maternity Leave {token}",
            "max_leaves_allowed": 120,
            "is_lwp": 0,
            "is_ppl": 0,
            "include_holiday": 1,
            "max_continuous_days_allowed": 120,
        }).insert(ignore_permissions=True).name
        leave_period = frappe.get_doc({
            "doctype": "Leave Period",
            "from_date": "2026-01-01",
            "to_date": "2026-12-31",
            "is_active": 1,
            "company": company,
        }).insert(ignore_permissions=True).name
        allocation = frappe.get_doc({
            "doctype": "Leave Allocation",
            "employee": employee.name,
            "company": company,
            "leave_type": leave_type,
            "leave_period": leave_period,
            "from_date": "2026-01-01",
            "to_date": "2026-12-31",
            "new_leaves_allocated": 120,
        }).insert(ignore_permissions=True)
        allocation.submit()

        application = frappe.get_doc({
            "doctype": "Leave Application",
            "employee": employee.name,
            "company": company,
            "leave_type": leave_type,
            "from_date": "2026-09-21",
            "to_date": "2026-09-23",
            "leave_approver": frappe.session.user,
            "status": "Approved",
        }).insert(ignore_permissions=True)
        application.submit()
        assert application.total_leave_days == 3

        attendance = frappe.get_all(
            "Attendance",
            filters={"employee": employee.name, "attendance_date": ["between", ["2026-09-21", "2026-09-23"]]},
            fields=["attendance_date", "status", "docstatus"],
        )
        assert len(attendance) == 3
        assert all(row.status == "On Leave" and row.docstatus == 1 for row in attendance)
        assert frappe.db.exists("Leave Ledger Entry", {
            "employee": employee.name,
            "leave_type": leave_type,
            "transaction_type": "Leave Application",
            "transaction_name": application.name,
        })
    finally:
        frappe.set_user("Administrator")
        if application and frappe.db.exists("Leave Application", application.name):
            doc = frappe.get_doc("Leave Application", application.name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Leave Application", doc.name, force=True, ignore_permissions=True)
        if allocation and frappe.db.exists("Leave Allocation", allocation.name):
            doc = frappe.get_doc("Leave Allocation", allocation.name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Leave Allocation", doc.name, force=True, ignore_permissions=True)
        if employee:
            for name in frappe.get_all(
                "Attendance", filters={"employee": employee.name}, pluck="name"
            ):
                frappe.delete_doc("Attendance", name, force=True, ignore_permissions=True)
            for name in frappe.get_all(
                "Leave Ledger Entry", filters={"employee": employee.name, "leave_type": leave_type}, pluck="name"
            ):
                frappe.delete_doc("Leave Ledger Entry", name, force=True, ignore_permissions=True)
            frappe.delete_doc("Employee", employee.name, force=True, ignore_permissions=True)
        if leave_period and frappe.db.exists("Leave Period", leave_period):
            frappe.delete_doc("Leave Period", leave_period, force=True, ignore_permissions=True)
        if leave_type and frappe.db.exists("Leave Type", leave_type):
            frappe.delete_doc("Leave Type", leave_type, force=True, ignore_permissions=True)
        if company:
            cleanup_synthetic_finalization_company(company)
        frappe.set_user(old_user)


def test_migrated_maternity_doctypes_enforce_permissions_and_native_workflows(monkeypatch):
    from workforce_suite.tests.test_payroll_finalization_integration import (
        _create_employee, _create_scoped_user, _create_synthetic_company,
        cleanup_synthetic_finalization_company,
    )

    required = (
        "Workforce Maternity Rule Set", "Workforce Maternity Review",
        "Workforce Maternity Separation Review", "Workforce Workplace Welfare Review",
    )
    if not all(frappe.db.table_exists(name) and frappe.db.exists("DocType", name) for name in required):
        pytest.skip("Requires the standard migration that installs maternity DocTypes.")

    old_user = frappe.session.user
    original_in_test = frappe.in_test
    token = frappe.generate_hash(8).upper()[:8]
    company = employee = leave_period = allocation = leave_application = separation = None
    branch_a = branch_b = None
    leave_types = []
    users = {}
    user_permissions = []
    records = []
    try:
        frappe.set_user("Administrator")
        company, _abbr, _payable, _expense, _cost_center, holiday_list = _create_synthetic_company(token, monkeypatch)
        branch_a = frappe.get_doc({"doctype": "Branch", "branch": f"Maternity Test A {token}", "company": company}).insert(ignore_permissions=True).name
        branch_b = frappe.get_doc({"doctype": "Branch", "branch": f"Maternity Test B {token}", "company": company}).insert(ignore_permissions=True).name
        # Seed this synthetic historical Employee in its initial insert. After
        # creation, lifecycle-controlled Branch/history edits must use native
        # Employee Transfer rather than direct Employee.save().
        employee = frappe.get_doc({
            "doctype": "Employee",
            "first_name": f"Maternity Test {token}",
            "company": company,
            "date_of_birth": "1990-05-08",
            "date_of_joining": "2020-01-01",
            "gender": "Female",
            "employment_type": "Intern",
            "holiday_list": holiday_list,
            "status": "Active",
            "branch": branch_a,
            "internal_work_history": [
                {"branch": branch_b, "from_date": "2020-01-01", "to_date": "2026-08-31"},
                {"branch": branch_a, "from_date": "2026-09-01"},
            ],
        }).insert(ignore_permissions=True)

        for key, role, scoped_company in (
            ("hr", "Workforce Suite Manager", company),
            ("owner", "Workforce Owner/Director", company),
            ("auditor", "Workforce Compliance Auditor", company),
            ("payroll", "Workforce Payroll Manager", company),
            ("supervisor", "Workforce Factory Supervisor", company),
            ("efl_hr", "Workforce Suite Manager", "Example Company B"),
        ):
            users[key] = _create_scoped_user(role, scoped_company, f"{token}-{key}")
            user_permissions.extend(frappe.get_all(
                "User Permission", filters={"user": users[key]}, pluck="name"
            ))
        frappe.clear_cache()

        def make_leave_type(label, **overrides):
            doc = frappe.get_doc({
                "doctype": "Leave Type", "leave_type_name": f"TEST Maternity {label} {token}",
                "max_leaves_allowed": 120, "is_lwp": 0, "is_ppl": 0,
                "include_holiday": 1, "max_continuous_days_allowed": 120, **overrides,
            }).insert(ignore_permissions=True)
            leave_types.append(doc.name)
            return doc.name

        def new_rule(title, leave_type):
            return frappe.get_doc({
                "doctype": "Workforce Maternity Rule Set", "title": title,
                "company": company, "legal_regime": "Bangladesh Labour Act",
                "effective_from": "2026-01-01", "effective_to": "2026-12-31",
                "minimum_service_months": 6, "pre_delivery_days": 60,
                "post_delivery_days": 60, "post_delivery_work_protection_days": 60,
                "separation_protection_before_months": 6, "separation_protection_after_days": 60,
                "benefit_rate_method": "Monthly Gross / Divisor", "benefit_daily_rate_divisor": 26,
                "maternity_leave_type": leave_type, "leave_is_lwp": 0, "leave_is_ppl": 0,
                "leave_include_holidays": 1, "leave_max_continuous_days": 120,
                "legal_review_notes": "SYNTHETIC TEST ONLY",
                "sources": [{
                    "source_title": "Synthetic maternity authority", "source_type": "Act",
                    "section_reference": "TEST", "effective_date": "2020-01-01",
                    "official_reference": "SYNTHETIC TEST REFERENCE",
                }],
            })

        def insert_as_hr(doc):
            frappe.set_user(users["hr"])
            doc.insert()
            records.append((doc.doctype, doc.name))
            return doc

        # MAT-RULE-001 through 004: mismatched native configuration cannot be approved.
        for label, overrides in (
            ("LWP", {"is_lwp": 1}), ("PPL", {"is_ppl": 1, "fraction_of_daily_salary_per_leave": 0.5}),
            ("Holiday", {"include_holiday": 0}), ("Maximum", {"max_continuous_days_allowed": 60}),
        ):
            bad_type = make_leave_type(label, **overrides)
            bad_rule = insert_as_hr(new_rule(f"Bad native Leave {label} {token}", bad_type))
            frappe.set_user(users["owner"])
            with pytest.raises(frappe.ValidationError) as error:
                bad_rule.submit()
            assert "does not match the reviewed rule" in str(error.value)

        native_leave_type = make_leave_type("Matching")
        rule = insert_as_hr(new_rule(f"Matching maternity rule {token}", native_leave_type))
        frappe.set_user(users["hr"])
        assert frappe.has_permission(rule.doctype, "read", rule)
        assert frappe.has_permission(rule.doctype, "create")
        assert frappe.has_permission(rule.doctype, "write", rule)
        assert not frappe.has_permission(rule.doctype, "submit", rule)
        assert not frappe.has_permission(rule.doctype, "cancel", rule)
        assert not frappe.has_permission(rule.doctype, "delete", rule)
        frappe.set_user(users["owner"])
        assert frappe.has_permission(rule.doctype, "submit", rule)
        rule.submit()
        assert rule.docstatus == 1 and rule.reviewed_by == users["owner"]
        assert rule.sources[0].source_title == "Synthetic maternity authority"
        with pytest.raises((frappe.ValidationError, frappe.PermissionError)):
            rule.cancel()

        leave_period = frappe.get_doc({
            "doctype": "Leave Period", "from_date": "2026-01-01", "to_date": "2026-12-31",
            "is_active": 1, "company": company,
        }).insert(ignore_permissions=True).name
        allocation = frappe.get_doc({
            "doctype": "Leave Allocation", "employee": employee.name, "company": company,
            "leave_type": native_leave_type, "leave_period": leave_period,
            "from_date": "2026-01-01", "to_date": "2026-12-31", "new_leaves_allocated": 120,
        }).insert(ignore_permissions=True)
        allocation.submit()
        leave_application = frappe.get_doc({
            "doctype": "Leave Application", "employee": employee.name, "company": company,
            "leave_type": native_leave_type, "from_date": "2026-09-21", "to_date": "2026-09-23",
            "leave_approver": "Administrator", "status": "Approved",
        }).insert(ignore_permissions=True)
        leave_application.submit()

        maternity_review = insert_as_hr(frappe.get_doc({
            "doctype": "Workforce Maternity Review", "employee": employee.name,
            "company": company, "branch": branch_a, "rule_set": rule.name,
            "expected_delivery_date": "2026-10-01", "benefit_eligibility": "Pending Review",
            "eligibility_reason": "Pending", "review_notes": "SYNTHETIC TEST ONLY",
            "native_leave_applications": [{"leave_application": leave_application.name}],
        }))
        frappe.set_user(users["owner"])
        assert frappe.has_permission(maternity_review.doctype, "read", maternity_review)
        assert frappe.has_permission(maternity_review.doctype, "submit", maternity_review)
        maternity_review.submit()
        assert maternity_review.docstatus == 1
        assert maternity_review.native_leave_applications[0].leave_application == leave_application.name

        # Native Internal Work History supports a different historical establishment.
        historical_review = insert_as_hr(frappe.get_doc({
            "doctype": "Workforce Maternity Review", "employee": employee.name,
            "company": company, "branch": branch_b, "rule_set": rule.name,
            "expected_delivery_date": "2026-03-01", "benefit_eligibility": "Pending Review",
            "eligibility_reason": "Pending", "review_notes": "SYNTHETIC HISTORICAL TEST ONLY",
        }))
        frappe.set_user(users["owner"])
        historical_review.submit()
        assert historical_review.docstatus == 1

        duplicate = frappe.get_doc({
            "doctype": "Workforce Maternity Review", "employee": employee.name,
            "company": company, "branch": branch_a, "rule_set": rule.name,
            "expected_delivery_date": "2026-10-15", "benefit_eligibility": "Pending Review",
            "eligibility_reason": "Pending", "review_notes": "SYNTHETIC OVERLAP TEST ONLY",
        })
        frappe.set_user(users["hr"])
        with pytest.raises(frappe.ValidationError, match="Another submitted maternity review overlaps"):
            duplicate.insert()

        from workforce_suite.workforce_suite.maternity_welfare import _validate_maternity_establishment
        with pytest.raises(frappe.ValidationError, match="does not match native Employee work history"):
            _validate_maternity_establishment(employee.name, branch_b, "2026-10-01")
        with pytest.raises(frappe.ValidationError, match="does not establish the reviewed historical Branch"):
            _validate_maternity_establishment(employee.name, branch_b, "2019-01-01")

        welfare = insert_as_hr(frappe.get_doc({
            "doctype": "Workforce Workplace Welfare Review", "company": company,
            "branch": branch_a, "legal_regime": "Bangladesh Labour Act",
            "effective_from": "2026-01-01", "effective_to": "2026-12-31",
            "first_aid_applicability": "Not Applicable", "child_room_applicability": "Not Applicable",
            "child_room_status": "Not Applicable", "review_notes": "SYNTHETIC TEST ONLY",
            "sources": [{
                "source_title": "Synthetic welfare authority", "source_type": "Act",
                "section_reference": "TEST", "effective_date": "2020-01-01",
                "official_reference": "SYNTHETIC TEST REFERENCE",
            }],
        }))
        frappe.set_user(users["owner"])
        assert frappe.has_permission(welfare.doctype, "submit", welfare)
        welfare.submit()
        assert welfare.docstatus == 1 and welfare.reviewed_by == users["owner"]

        # Link a synthetic native Employee Separation and submit its protected decision.
        frappe.set_user("Administrator")
        employee.reload()
        employee.relieving_date = "2026-09-30"
        employee.status = "Left"
        employee.save(ignore_permissions=True)
        separation = frappe.get_doc({
            "doctype": "Employee Separation", "employee": employee.name, "company": company,
            "boarding_begins_on": "2026-09-30", "custom_workforce_separation_type": "Resignation",
        }).insert(ignore_permissions=True).name
        separation_review = insert_as_hr(frappe.get_doc({
            "doctype": "Workforce Maternity Separation Review", "employee_separation": separation,
            "employee": employee.name, "company": company, "maternity_review": maternity_review.name,
            "decision": "Hold", "evidence_reference": "SYNTHETIC TEST ONLY",
            "review_notes": "SYNTHETIC TEST ONLY",
        }))
        frappe.set_user(users["owner"])
        separation_review.submit()
        assert separation_review.docstatus == 1

        # Test actual permission hooks, query filters, and get_doc checks as each role.
        docs = (rule, maternity_review, historical_review, separation_review, welfare)
        for user in (users["hr"], users["owner"]):
            frappe.set_user(user)
            for doc in docs:
                frappe.get_doc(doc.doctype, doc.name).check_permission("read")
                assert doc.name in {row.name for row in frappe.get_list(doc.doctype, filters={"name": doc.name}, fields=["name"])}

        frappe.set_user(users["auditor"])
        for doc in (rule, welfare):
            assert frappe.has_permission(doc.doctype, "read", doc)
            frappe.get_doc(doc.doctype, doc.name).check_permission("read")
            assert frappe.get_list(doc.doctype, filters={"name": doc.name}, fields=["name"])

        sensitive = (maternity_review, historical_review, separation_review)
        for user in (users["auditor"], users["payroll"], users["supervisor"], users["efl_hr"]):
            frappe.set_user(user)
            for doc in sensitive:
                assert not frappe.has_permission(doc.doctype, "read", doc)
                try:
                    rows = frappe.get_list(doc.doctype, filters={"name": doc.name}, fields=["name"])
                except frappe.PermissionError:
                    rows = []
                assert not rows
                with pytest.raises(frappe.PermissionError):
                    frappe.get_doc(doc.doctype, doc.name).check_permission("read")

        frappe.set_user(users["owner"])
        saved_rule = frappe.get_doc(rule.doctype, rule.name)
        saved_rule.minimum_service_months = 7
        with pytest.raises((frappe.ValidationError, frappe.PermissionError)):
            saved_rule.save()
        saved_maternity_review = frappe.get_doc(maternity_review.doctype, maternity_review.name)
        saved_maternity_review.review_notes = "CHANGED AFTER SUBMIT"
        with pytest.raises((frappe.ValidationError, frappe.PermissionError)):
            saved_maternity_review.save()
        saved_welfare = frappe.get_doc(welfare.doctype, welfare.name)
        saved_welfare.review_notes = "CHANGED AFTER SUBMIT"
        with pytest.raises((frappe.ValidationError, frappe.PermissionError)):
            saved_welfare.save()
        with pytest.raises((frappe.ValidationError, frappe.PermissionError)):
            welfare.cancel()
        assert "Workforce Compliance Auditor" in {row.role for row in frappe.get_meta(rule.doctype).permissions}
        assert "Workforce Compliance Auditor" not in {row.role for row in frappe.get_meta(maternity_review.doctype).permissions}

        # Assert the migrated DocPerm rows directly, including forbidden rights.
        expected = {
            rule.doctype: {
                "Workforce Suite Manager": {"read": 1, "write": 1, "create": 1, "submit": 0, "cancel": 0, "delete": 0},
                "Workforce Owner/Director": {"read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 0, "delete": 0},
                "Workforce Compliance Auditor": {"read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0},
            },
            maternity_review.doctype: {
                "Workforce Suite Manager": {"read": 1, "write": 1, "create": 1, "submit": 0, "cancel": 0, "delete": 0},
                "Workforce Owner/Director": {"read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 0, "delete": 0},
            },
            separation_review.doctype: {
                "Workforce Suite Manager": {"read": 1, "write": 1, "create": 1, "submit": 0, "cancel": 0, "delete": 0},
                "Workforce Owner/Director": {"read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 0, "delete": 0},
            },
            welfare.doctype: {
                "Workforce Suite Manager": {"read": 1, "write": 1, "create": 1, "submit": 0, "cancel": 0, "delete": 0},
                "Workforce Owner/Director": {"read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 0, "delete": 0},
                "Workforce Compliance Auditor": {"read": 1, "write": 0, "create": 0, "submit": 0, "cancel": 0, "delete": 0},
            },
        }
        for doctype, role_rights in expected.items():
            for role, rights in role_rights.items():
                row = frappe.db.get_value("DocPerm", {"parent": doctype, "role": role, "permlevel": 0}, list(rights), as_dict=True)
                assert row, f"Missing DocPerm for {doctype} / {role}"
                assert {right: int(row[right] or 0) for right in rights} == rights

        # A valid role with a different explicit Company permission cannot see
        # another company's rule or establishment-level welfare review.
        frappe.set_user(users["efl_hr"])
        for doc in (rule, welfare):
            assert not frappe.has_permission(doc.doctype, "read", doc)
            assert not frappe.get_list(doc.doctype, filters={"name": doc.name}, fields=["name"])
            with pytest.raises(frappe.PermissionError):
                frappe.get_doc(doc.doctype, doc.name).check_permission("read")

        # Submitted employee-specific and separation reviews are immutable.
        frappe.set_user(users["owner"])
        saved_separation_review = frappe.get_doc(separation_review.doctype, separation_review.name)
        saved_separation_review.review_notes = "CHANGED AFTER SUBMIT"
        with pytest.raises((frappe.ValidationError, frappe.PermissionError)):
            saved_separation_review.save()
        with pytest.raises((frappe.ValidationError, frappe.PermissionError)):
            separation_review.cancel()
    finally:
        frappe.set_user("Administrator")
        frappe.in_test = True
        frappe.local.flags.in_test = True
        for doctype, name in reversed(records):
            if frappe.db.exists(doctype, name):
                if frappe.db.get_value(doctype, name, "docstatus") == 1:
                    # These documents were created solely by this integration
                    # test. Reset submission state only for exact tracked names
                    # because their production lifecycle intentionally forbids
                    # cancellation.
                    frappe.db.set_value(doctype, name, "docstatus", 0, update_modified=False)
                frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
        if separation and frappe.db.exists("Employee Separation", separation):
            frappe.delete_doc("Employee Separation", separation, force=True, ignore_permissions=True)
        if leave_application and frappe.db.exists("Leave Application", leave_application.name):
            doc = frappe.get_doc("Leave Application", leave_application.name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Leave Application", doc.name, force=True, ignore_permissions=True)
        if allocation and frappe.db.exists("Leave Allocation", allocation.name):
            doc = frappe.get_doc("Leave Allocation", allocation.name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Leave Allocation", doc.name, force=True, ignore_permissions=True)
        if employee:
            for name in frappe.get_all("Attendance", filters={"employee": employee.name}, pluck="name"):
                frappe.delete_doc("Attendance", name, force=True, ignore_permissions=True)
            for name in frappe.get_all(
                "Leave Ledger Entry", filters={"employee": employee.name, "leave_type": ["in", leave_types]}, pluck="name"
            ):
                frappe.delete_doc("Leave Ledger Entry", name, force=True, ignore_permissions=True)
        if leave_period and frappe.db.exists("Leave Period", leave_period):
            frappe.delete_doc("Leave Period", leave_period, force=True, ignore_permissions=True)
        for name in leave_types:
            if frappe.db.exists("Leave Type", name):
                frappe.delete_doc("Leave Type", name, force=True, ignore_permissions=True)
        for name in user_permissions:
            if frappe.db.exists("User Permission", name):
                frappe.delete_doc("User Permission", name, force=True, ignore_permissions=True)
        for user in users.values():
            if frappe.db.exists("User", user):
                frappe.delete_doc("User", user, force=True, ignore_permissions=True)
        if employee:
            frappe.delete_doc("Employee", employee.name, force=True, ignore_permissions=True)
        for branch in (branch_a, branch_b):
            if branch and frappe.db.exists("Branch", branch):
                frappe.delete_doc("Branch", branch, force=True, ignore_permissions=True)
        if company:
            cleanup_synthetic_finalization_company(company)
            assert not frappe.db.exists("Company", company)
        assert all(not frappe.db.exists(doctype, name) for doctype, name in records)
        assert all(not frappe.db.exists("Leave Type", name) for name in leave_types)
        assert all(not frappe.db.exists("User Permission", name) for name in user_permissions)
        assert all(not frappe.db.exists("User", user) for user in users.values())
        assert all(not frappe.db.exists("Branch", name) for name in (branch_a, branch_b) if name)
        if leave_period:
            assert not frappe.db.exists("Leave Period", leave_period)
        if allocation:
            assert not frappe.db.exists("Leave Allocation", allocation.name)
        if leave_application:
            assert not frappe.db.exists("Leave Application", leave_application.name)
        if employee:
            assert not frappe.db.exists("Employee", employee.name)
            assert not frappe.get_all("Attendance", filters={"employee": employee.name}, pluck="name")
            assert not frappe.get_all(
                "Leave Ledger Entry", filters={"employee": employee.name, "leave_type": ["in", leave_types]}, pluck="name"
            )
        if separation:
            assert not frappe.db.exists("Employee Separation", separation)
        frappe.in_test = original_in_test
        frappe.set_user(old_user)
