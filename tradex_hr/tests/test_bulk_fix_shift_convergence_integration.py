"""Regression evidence that Employee Data Gaps delegates shift work to HRMS."""

from __future__ import annotations

import json
from pathlib import Path

import frappe
import pytest


@pytest.fixture(scope="module", autouse=True)
def site():
	frappe.init(
		site="hrms-v16.localhost",
		sites_path="/home/sanchita/frappe-bench-v16/sites",
		force=True,
	)
	frappe.connect()
	frappe.set_user("Administrator")
	yield
	frappe.set_user("Administrator")
	frappe.destroy()


def test_retired_employee_gap_shift_resolver_cannot_create_assignment():
	company = "Tradexcel Ceramics Ltd."
	branch = frappe.get_all("Branch", filters={"company": company}, pluck="name", limit=1)[0]
	department = frappe.get_all("Department", filters={"company": company}, pluck="name", limit=1)[0]
	shift_type = frappe.get_all("Shift Type", pluck="name", limit=1)[0]
	token = f"SYNTHETIC SHIFT GAP {frappe.generate_hash(8).upper()}"
	employee = frappe.get_doc(
		{
			"doctype": "Employee",
			"first_name": token,
			"employee_name": token,
			"company": company,
			"branch": branch,
			"department": department,
			"gender": frappe.db.get_value("Gender", {}, "name") or "Female",
			"date_of_birth": "1990-01-01",
			"date_of_joining": "2020-01-01",
			"status": "Active",
		}
	).insert(ignore_permissions=True)
	frappe.db.commit()
	assignment_names = []
	policy_exception_names = []
	try:
		from tradex_hr.tradexcel_hr.bulk_fix import resolve_gap

		with pytest.raises(frappe.ValidationError, match="Use Bulk Shift Assignment"):
			resolve_gap(
				"No Shift Assignment",
				[employee.name],
				{"shift_type": shift_type, "start_date": frappe.utils.today()},
			)
		assignment_names = frappe.get_all(
			"Shift Assignment", filters={"employee": employee.name}, pluck="name"
		)
		policy_exception_names = frappe.get_all(
			"Tradexcel Policy Exception", filters={"employee": employee.name}, pluck="name"
		)
		assert not assignment_names
		assert not policy_exception_names
	finally:
		frappe.set_user("Administrator")
		assignment_names = frappe.get_all(
			"Shift Assignment", filters={"employee": employee.name}, pluck="name"
		)
		policy_exception_names = frappe.get_all(
			"Tradexcel Policy Exception", filters={"employee": employee.name}, pluck="name"
		)
		for name in assignment_names:
			if not frappe.db.exists("Shift Assignment", name):
				continue
			doc = frappe.get_doc("Shift Assignment", name)
			if doc.docstatus == 1:
				doc.cancel()
			frappe.delete_doc("Shift Assignment", name, force=True, ignore_permissions=True)
		for name in policy_exception_names:
			if frappe.db.exists("Tradexcel Policy Exception", name):
				frappe.delete_doc("Tradexcel Policy Exception", name, force=True, ignore_permissions=True)
		if frappe.db.exists("Employee", employee.name):
			frappe.delete_doc("Employee", employee.name, force=True, ignore_permissions=True)
		frappe.db.commit()
	assert not frappe.db.exists("Employee", employee.name)
	assert not frappe.get_all("Shift Assignment", filters={"employee": employee.name})


def test_employee_gaps_uses_bundled_javascript_and_only_navigates_for_shift_gap():
	app_root = Path(__file__).resolve().parents[1]
	js_path = app_root / "tradexcel_hr/report/employee_data_gaps/employee_data_gaps.js"
	json_path = app_root / "tradexcel_hr/report/employee_data_gaps/employee_data_gaps.json"
	install_path = app_root / "install.py"
	javascript = js_path.read_text()
	report_json = json.loads(json_path.read_text())
	from tradex_hr.install import REPORTS
	from tradex_hr.tradexcel_hr import bulk_fix

	assert frappe.db.exists("DocType", "Shift Assignment Tool")
	assert frappe.get_meta("Shift Assignment Tool").issingle
	assert frappe.db.get_value(
		"Workspace Shortcut", {"label": "Bulk Shift Assignment"}, "link_to"
	) == "Shift Assignment Tool"
	assert "no_shift_assignment" in (app_root / "tradexcel_hr/report/employee_data_gaps/employee_data_gaps.py").read_text()
	assert '"No Shift Assignment"' not in javascript.split("const GAP_RESOLVERS =", 1)[1].split("};", 1)[0]
	assert 'frappe.set_route("Form", "Shift Assignment Tool")' in javascript
	assert "frappe.route_options = route_options" in javascript
	assert "employee" not in javascript.split("const route_options", 1)[1].split("frappe.set_route", 1)[0]
	# The endpoint remains for Department/Designation/Holiday List field fixes,
	# but the shift gap is no longer registered as an in-place resolver.
	assert javascript.count("tradex_hr.tradexcel_hr.bulk_fix.resolve_gap") == 1
	assert "tradex_hr.tradexcel_hr.bulk_fix.resolve_gap" not in report_json["javascript"]
	assert "tradex_hr.tradexcel_hr.bulk_fix.resolve_gap" not in install_path.read_text()
	assert "javascript" not in REPORTS["Employee Data Gaps"]
	assert not hasattr(bulk_fix, "_assign_shifts")
	assert not hasattr(bulk_fix, "_clone_exception")

	from frappe.desk.query_report import get_script

	active_script = get_script("Employee Data Gaps")["script"]
	assert 'frappe.set_route("Form", "Shift Assignment Tool")' in active_script
	assert active_script.count("tradex_hr.tradexcel_hr.bulk_fix.resolve_gap") == 1
