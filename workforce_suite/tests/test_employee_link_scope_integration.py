"""Native Employee permissions also bound linked correction/pay evidence."""
from unittest.mock import patch

import frappe
import pytest

from workforce_suite.tests.persona_uat import PERSONA_ROLES, SyntheticPersonaHarness
from workforce_suite.tests.test_bulk_salary_authority_integration import _structure


@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(site="hrms-v16.localhost", sites_path="/home/sanchita/frappe-bench-v16/sites", force=True)
    frappe.connect()
    frappe.set_user("Administrator")
    yield
    frappe.set_user("Administrator")
    frappe.destroy()


def test_native_employee_link_scope_lists_documents_and_identity_only_device_access():
    from frappe.client import get as client_get
    from workforce_suite.workforce_suite.report_scope import permitted_employee_query

    company = "Example Company A"
    other = "Example Company B"
    branches = frappe.get_all("Branch", filters={"company": company}, pluck="name", order_by="name")
    departments = frappe.get_all("Department", filters={"company": company}, pluck="name", order_by="name")
    h = SyntheticPersonaHarness("SOLLINK" + frappe.generate_hash(8).upper())
    tracked = []
    try:
        users = {}
        for key, role in (("hr", "hr_manager"), ("approver", "attendance_correction_approver"),
                          ("device", "device_admin"), ("payroll", "payroll_manager")):
            users[key] = h.create_user(key, [PERSONA_ROLES[role]], company=company,
                branch=branches[0], department=departments[0])
        users["native"] = h.create_user("native", ["HR User"], company=company,
            branch=branches[0], department=departments[0])
        users["worker"] = h.create_user("worker", [PERSONA_ROLES["worker"]], company=company)
        users["unlinked"] = h.create_user("unlinked", [PERSONA_ROLES["worker"]], company=company)
        rows = [
            ("in", company, branches[0], departments[0]),
            ("branch", company, branches[1], departments[0]),
            ("department", company, branches[0], departments[1]),
            ("blank", company, "", ""),
            ("company", other, frappe.db.get_value("Branch", {"company": other}, "name"),
             frappe.db.get_value("Department", {"company": other}, "name")),
        ]
        employees, documents = {}, {}
        structure = _structure(company, "Monthly Salary")
        for key, co, branch, department in rows:
            employee = h.create_employee(key, co, branch, department,
                user=users["worker"] if key == "in" else None)
            employees[key] = employee
            values = [
                {"doctype": "Employee Checkin", "employee": employee,
                 "time": "2026-09-01 08:00:00", "log_type": "IN"},
                {"doctype": "Attendance Request", "employee": employee, "company": co,
                 "from_date": "2026-09-01", "to_date": "2026-09-01", "reason": "On Duty",
                 "include_holidays": 1, "explanation": "Synthetic native permission boundary"},
            ]
            if co == company:
                values.append({"doctype": "Salary Structure Assignment", "employee": employee,
                    "company": co, "salary_structure": structure.name, "from_date": "2026-09-01",
                    "base": 0, "currency": structure.currency,
                    "payroll_payable_account": frappe.db.get_value("Company", co, "default_payroll_payable_account")})
            for payload in values:
                doc = frappe.get_doc(payload).insert(ignore_permissions=True)
                tracked.append((doc.doctype, doc.name))
                documents.setdefault(doc.doctype, {})[key] = doc.name
        frappe.db.commit()

        strict = bool(frappe.get_system_settings("apply_strict_user_permissions"))
        for key in ("hr", "approver", "payroll", "native", "device"):
            frappe.set_user(users[key])
            expected_keys = {"in"} | (set() if strict else {"blank"})
            scoped_employees = {row[0] for row in permitted_employee_query().run()}
            assert {employees[k] for k in expected_keys} <= scoped_employees
            assert not {employees[k] for k in ("branch", "department", "company")} & scoped_employees
            for doctype, names in documents.items():
                if not frappe.has_permission(doctype, "read"):
                    continue
                visible = set(frappe.get_list(doctype, filters={"name": ["in", list(names.values())]}, pluck="name"))
                expected = {names[k] for k in expected_keys if k in names}
                assert visible == expected, (key, doctype)
                for boundary, name in names.items():
                    doc = frappe.get_doc(doctype, name)
                    allowed = boundary in expected_keys
                    assert bool(frappe.has_permission(doctype, "read", doc)) == allowed
                    if allowed:
                        doc.check_permission("read")
                        assert client_get(doctype, name)["name"] == name
                    else:
                        with pytest.raises(frappe.PermissionError):
                            doc.check_permission("read")
                        with pytest.raises(frappe.PermissionError):
                            client_get(doctype, name)
                assert not frappe.get_list(doctype, filters={"employee": employees["branch"]}, pluck="name")

        # A known out-of-scope Employee must also fail a normal create/write
        # permission check, not merely disappear from lists.
        frappe.set_user(users["hr"])
        for doctype in ("Attendance Request", "Salary Structure Assignment"):
            outside = frappe.get_doc(doctype, documents[doctype]["branch"])
            with pytest.raises(frappe.PermissionError):
                outside.check_permission("write")
            candidate = frappe.copy_doc(outside)
            candidate.from_date = "2026-09-02"
            if doctype == "Attendance Request":
                candidate.to_date = "2026-09-02"
            with pytest.raises(frappe.PermissionError):
                candidate.insert()

        frappe.set_user(users["device"])
        assert frappe.has_permission("Employee", "select")
        assert not frappe.has_permission("Employee", "read")
        assert not frappe.has_permission("Salary Structure Assignment", "read")
        assert not frappe.has_permission("Salary Slip", "read")
        with pytest.raises(frappe.PermissionError):
            client_get("Employee", employees["in"])
        try:
            identity_rows = frappe.get_list("Employee", filters={"name": employees["in"]},
                fields=["name", "ctc", "bank_ac_no"])
        except frappe.PermissionError:
            pass
        else:
            assert identity_rows and all("ctc" not in row and "bank_ac_no" not in row for row in identity_rows)

        frappe.set_user(users["worker"])
        checkins = documents["Employee Checkin"]
        assert set(frappe.get_list("Employee Checkin", filters={"name": ["in", list(checkins.values())]}, pluck="name")) == {checkins["in"]}
        client_get("Employee Checkin", checkins["in"])
        with pytest.raises(frappe.PermissionError):
            client_get("Employee Checkin", checkins["branch"])
        frappe.set_user(users["unlinked"])
        with pytest.raises(frappe.PermissionError):
            frappe.get_list("Employee Checkin", pluck="name")

        # Direct document permission checks respect an explicitly supplied user,
        # not the Administrator session used by setup or an API caller.
        frappe.set_user("Administrator")
        assert not frappe.has_permission("Attendance Request", "read",
            documents["Attendance Request"]["branch"], user=users["approver"])
        assert frappe.has_permission("Attendance Request", "read", documents["Attendance Request"]["branch"])
        with patch.object(frappe, "in_test", True):
            disabled = frappe.get_doc("User", users["hr"])
            disabled.enabled = 0
            disabled.save(ignore_permissions=True)
        frappe.set_user(users["hr"])
        assert not frappe.get_list("Employee Checkin", filters={"name": ["in", list(checkins.values())]}, pluck="name")
        with pytest.raises(frappe.PermissionError):
            client_get("Employee Checkin", checkins["in"])
    finally:
        frappe.set_user("Administrator")
        with patch.object(frappe, "in_test", True):
            for doctype, name in reversed(tracked):
                if frappe.db.exists(doctype, name):
                    frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
            h.cleanup()
        frappe.db.commit()
        assert not any(frappe.db.exists(dt, name) for dt, name in tracked)


def test_empty_persona_harness_never_queries_unrelated_identity_records():
    h = SyntheticPersonaHarness("SOLLINKEMPTY" + frappe.generate_hash(8).upper())
    original = frappe.get_all

    def checked_get_all(doctype, *args, **kwargs):
        assert doctype not in {"User", "User Permission", "Contact", "Has Role", "Notification Settings"}, "An empty harness has no identity records to inspect"
        return original(doctype, *args, **kwargs)

    with patch.object(frappe, "get_all", side_effect=checked_get_all):
        h.cleanup()
