"""Synthetic site-backed checks for native employee lifecycle guards."""

import os

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


def _department(company):
	return frappe.db.get_value("Department", {"company": company}, "name") or frappe.db.get_value(
		"Department", {}, "name"
	)


def _employee(company, label):
	doc = frappe.get_doc(
		{
			"doctype": "Employee",
			"naming_series": "HR-EMP-",
			"first_name": f"Synthetic lifecycle {label} {frappe.generate_hash(6)}",
			"company": company,
			"status": "Active",
			"gender": frappe.db.get_value("Gender", {}, "name"),
			"date_of_birth": "1990-05-08",
			"date_of_joining": "2020-01-01",
			"department": _department(company),
		}
	).insert(ignore_permissions=True)
	return doc.name


def test_native_transfer_and_rehire_employment_spell_boundaries():
	from tradex_hr.tradexcel_hr.employee_lifecycle import validate_employee_employment_spell

	company = "Tradexcel Ceramics Ltd."
	other_company = "Elegance Footwear Ltd."
	assert frappe.db.exists("Company", company)
	assert frappe.db.exists("Company", other_company)

	old_user = frappe.session.user
	employee_name = None
	transfer_names = []
	new_employee_name = None
	try:
		frappe.set_user("Administrator")
		employee_name = _employee(company, "transfer")
		salary_change = frappe.get_doc(
			{
				"doctype": "Employee Promotion",
				"employee": employee_name,
				"promotion_date": "2026-09-25",
				"current_ctc": 1000,
				"revised_ctc": 1200,
			}
		)
		with pytest.raises(frappe.ValidationError):
			salary_change.insert(ignore_permissions=True)

		invalid = frappe.get_doc(
			{
				"doctype": "Employee Transfer",
				"employee": employee_name,
				"transfer_date": "2026-09-25",
				"company": company,
				"new_company": other_company,
				"transfer_details": [
					{"property": "Designation", "current": "", "new": "Manager", "fieldname": "designation"}
				],
			}
		)
		with pytest.raises(frappe.ValidationError):
			invalid.insert(ignore_permissions=True)

		valid = frappe.get_doc(
			{
				"doctype": "Employee Transfer",
				"employee": employee_name,
				"transfer_date": "2026-09-25",
				"company": company,
				"new_company": other_company,
				"create_new_employee_id": 1,
				"transfer_details": [
					{
						"property": "Department",
						"current": _department(company),
						"new": _department(other_company),
						"fieldname": "department",
					}
				],
			}
		).insert(ignore_permissions=True)
		transfer_names.append(valid.name)
		valid.submit()
		new_employee_name = valid.new_employee_id
		assert new_employee_name and frappe.db.exists("Employee", new_employee_name)
		assert frappe.db.get_value("Employee", new_employee_name, "company") == other_company
		assert (
			str(frappe.db.get_value("Employee", new_employee_name, "date_of_joining"))
			== "2026-09-25"
		)
		assert frappe.db.get_value("Employee", employee_name, "status") == "Left"
		assert str(frappe.db.get_value("Employee", employee_name, "date_of_joining")) == "2020-01-01"
		assert str(frappe.db.get_value("Employee", employee_name, "relieving_date")) == "2026-09-25"

		# HRMS requires its generated Employee to be removed before reversal.
		frappe.delete_doc("Employee", new_employee_name, force=True, ignore_permissions=True)
		frappe.db.set_value("Employee Transfer", valid.name, "new_employee_id", None)
		valid.reload()
		valid.cancel()
		new_employee_name = None
		assert frappe.db.get_value("Employee", employee_name, "status") == "Active"
		assert not frappe.db.get_value("Employee", employee_name, "relieving_date")
		assert frappe.db.get_value("Employee", employee_name, "company") == company

		frappe.db.set_value("Employee", employee_name, {
			"status": "Left",
			"relieving_date": "2026-09-24",
		})
		left_employee = frappe.get_doc("Employee", employee_name)
		left_employee.status = "Active"
		left_employee.relieving_date = None
		with pytest.raises(frappe.ValidationError):
			left_employee.save(ignore_permissions=True)

		# The untouched completed spell remains acceptable to the guard.
		left_employee.reload()
		assert left_employee.status == "Left"
		assert str(left_employee.relieving_date) == "2026-09-24"
		validate_employee_employment_spell(left_employee)
	finally:
		frappe.set_user("Administrator")
		if new_employee_name and frappe.db.exists("Employee", new_employee_name):
			frappe.delete_doc("Employee", new_employee_name, force=True, ignore_permissions=True)
			if transfer_names and frappe.db.exists("Employee Transfer", transfer_names[-1]):
				frappe.db.set_value("Employee Transfer", transfer_names[-1], "new_employee_id", None)
		for name in reversed(transfer_names):
			if frappe.db.exists("Employee Transfer", name):
				doc = frappe.get_doc("Employee Transfer", name)
				if doc.docstatus == 1:
					try:
						doc.cancel()
					except Exception:
						if employee_name and frappe.db.exists("Employee", employee_name):
							frappe.db.set_value(
								"Employee",
								employee_name,
								{"status": "Active", "relieving_date": None, "company": company},
							)
				frappe.delete_doc("Employee Transfer", name, force=True, ignore_permissions=True)
		if employee_name and frappe.db.exists("Employee", employee_name):
			frappe.delete_doc("Employee", employee_name, force=True, ignore_permissions=True)
		frappe.set_user(old_user)

	assert not frappe.db.exists("Employee", employee_name)
	if transfer_names:
		assert not frappe.db.exists("Employee Transfer", {"name": ["in", transfer_names]})
