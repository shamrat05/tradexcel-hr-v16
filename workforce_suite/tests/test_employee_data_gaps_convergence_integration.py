"""Employee Data Gaps must scope rows and navigate to canonical native records."""

from __future__ import annotations
import os

import json
from pathlib import Path

import frappe
import pytest

from workforce_suite.tests.persona_uat import PERSONA_ROLES, SyntheticPersonaHarness
from workforce_suite.workforce_suite.report.employee_data_gaps.employee_data_gaps import execute
from workforce_suite.workforce_suite.report_scope import permitted_employee_names


@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(site=os.environ.get("FRAPPE_TEST_SITE", "test_workforce.localhost"), sites_path=os.environ.get("FRAPPE_TEST_SITES_PATH", "./sites"), force=True)
    frappe.connect()
    frappe.set_user("Administrator")
    yield
    frappe.set_user("Administrator")
    frappe.destroy()


def test_report_routes_only_to_native_mutation_and_has_one_js_source():
    from frappe.desk.query_report import get_script
    from workforce_suite.install import REPORTS

    app_root = Path(__file__).resolve().parents[1]
    js = (app_root / "workforce_suite/report/employee_data_gaps/employee_data_gaps.js").read_text()
    report_json = json.loads((app_root / "workforce_suite/report/employee_data_gaps/employee_data_gaps.json").read_text())
    assert not (app_root / "workforce_suite/bulk_fix.py").exists()
    with pytest.raises(ModuleNotFoundError):
        frappe.get_attr("workforce_suite.workforce_suite.bulk_fix.resolve_gap")
    assert "bulk_fix.resolve_gap" not in js
    assert report_json["javascript"] == ""
    assert "javascript" not in REPORTS["Employee Data Gaps"]
    for native in ("Shift Assignment Tool", "Bulk Salary Structure Assignment", "Employee Transfer", "Employee Promotion"):
        assert native in js and frappe.db.exists("DocType", native)
    assert frappe.get_meta("Shift Assignment Tool").issingle
    assert frappe.db.get_value(
        "Workspace Shortcut", {"label": "Bulk Shift Assignment"}, "link_to"
    ) == "Shift Assignment Tool"
    assert 'frappe.set_route("Form", "Shift Assignment Tool")' in js
    assert 'employee' not in js.split("const route_options", 1)[1].split("frappe.set_route", 1)[0]
    active = get_script("Employee Data Gaps")["script"]
    assert "bulk_fix.resolve_gap" not in active
    assert 'frappe.set_route("Form", "Shift Assignment Tool")' in active


def test_report_endpoint_company_branch_department_and_manual_filter_scope():
    from frappe.desk.query_report import run

    company_a = "Example Company A"
    company_b = "Example Company B"
    branches = frappe.get_all("Branch", filters={"company": company_a}, pluck="name", order_by="name")
    departments = frappe.get_all("Department", filters={"company": company_a}, pluck="name", order_by="name")
    other_branch = frappe.db.get_value("Branch", {"company": company_b}, "name")
    other_department = frappe.db.get_value("Department", {"company": company_b}, "name")
    assert len(branches) > 1 and len(departments) > 1 and other_branch and other_department
    token = "SOLDG" + frappe.generate_hash(6).upper()[:6]
    personas = SyntheticPersonaHarness(token)
    try:
        frappe.set_user("Administrator")
        scoped = personas.create_user("scoped", [PERSONA_ROLES["attendance_officer"]],
            company=company_a, branch=branches[0], department=departments[0])
        allowed = personas.create_employee("allowed", company_a, branches[0], departments[0])
        wrong_branch = personas.create_employee("wrong-branch", company_a, branches[1], departments[0])
        wrong_department = personas.create_employee("wrong-department", company_a, branches[0], departments[1])
        other = personas.create_employee("other-company", company_b, other_branch, other_department)
        frappe.db.commit()
        frappe.set_user(scoped)
        rows = run("Employee Data Gaps", filters={"company": company_a})["result"]
        names = {row["employee"] for row in rows}
        assert allowed in names
        assert not {wrong_branch, wrong_department, other}.intersection(names)
        assert not {wrong_branch, wrong_department, other}.intersection(
            row["employee"] for row in execute({"company": company_a})[1]
        )
        assert run("Employee Data Gaps", filters={"company": company_a, "branch": branches[1]})["result"] == []
        assert run("Employee Data Gaps", filters={"company": company_a, "department": departments[1]})["result"] == []
        assert run("Employee Data Gaps", filters={"company": company_a, "employee": wrong_branch})["result"] == []
        assert {row["employee"] for row in run("Employee Data Gaps", filters={"company": company_a, "employee": allowed})["result"]} == {allowed}
        with pytest.raises(frappe.PermissionError):
            run("Employee Data Gaps", filters={"company": company_b})
        # The shared native Employee scope must not silently truncate a large
        # authorized population at Frappe's default get_list page length.
        frappe.set_user("Administrator")
        assert len(permitted_employee_names(company_a)) == frappe.db.count("Employee", {"company": company_a})
    finally:
        personas.cleanup()
        frappe.set_user("Administrator")
        assert not frappe.get_all("Employee", filters={"employee_name": ["like", f"TEST PERSONA {token}%"]})


def test_native_data_import_update_uses_employee_validation():
    from frappe.core.doctype.data_import.importer import Importer

    company = "Example Company A"
    branch = frappe.db.get_value("Branch", {"company": company}, "name")
    departments = frappe.get_all("Department", filters={"company": company}, pluck="name", limit=2)
    assert branch and len(departments) == 2
    token = "SOLDI" + frappe.generate_hash(6).upper()[:6]
    personas = SyntheticPersonaHarness(token)
    try:
        frappe.set_user("Administrator")
        hr = personas.create_user("hr", [PERSONA_ROLES["hr_manager"]], company=company)
        employee = personas.create_employee("employee", company, branch, departments[0])
        frappe.db.commit()
        assert not frappe.has_permission("Employee", "import", user=hr)
        assert not frappe.has_permission("Data Import", "create", user=hr)
        # Native Importer.update_record loads Employee and calls save(); the
        # lifecycle guard still rejects protected direct field changes even
        # under Administrator, without creating another import engine.
        importer = object.__new__(Importer)
        importer.doctype = "Employee"
        importer.data_import = frappe._dict(doctype="Data Import", name="SYNTHETIC IMPORT")
        with pytest.raises(frappe.ValidationError, match="native Employee Transfer or Employee Promotion"):
            importer.update_record(frappe._dict(name=employee, department=departments[1]))
        assert frappe.db.get_value("Employee", employee, "department") == departments[0]
    finally:
        personas.cleanup()
