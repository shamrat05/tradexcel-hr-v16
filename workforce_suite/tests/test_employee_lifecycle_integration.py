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


def _scoped_user(role, company, label):
	user = frappe.get_doc({
		"doctype": "User",
		"email": f"codex-lifecycle-{label[:16]}-{frappe.generate_hash()[:10]}@example.test",
		"first_name": f"Synthetic lifecycle {label[:24]}",
		"enabled": 1,
		"user_type": "System User",
		"send_welcome_email": 0,
		"roles": [{"role": role}],
	}).insert(ignore_permissions=True)
	try:
		permission = frappe.get_doc({
			"doctype": "User Permission",
			"user": user.name,
			"allow": "Company",
			"for_value": company,
			"apply_to_all_doctypes": 1,
		}).insert(ignore_permissions=True)
	except Exception:
		for name in frappe.get_all("User Permission", filters={"user": user.name}, pluck="name"):
			frappe.delete_doc("User Permission", name, force=True, ignore_permissions=True)
		if frappe.db.exists("User", user.name):
			frappe.delete_doc("User", user.name, force=True, ignore_permissions=True)
		frappe.clear_cache()
		raise
	return user.name, permission.name


def _movement_row(fieldname, current, new, property_name):
	return {"property": property_name, "current": current or "", "new": new, "fieldname": fieldname}


def _cancel_and_delete(doctype, names):
	for name in reversed(names):
		if not name or not frappe.db.exists(doctype, name):
			continue
		doc = frappe.get_doc(doctype, name)
		if doc.docstatus == 1:
			doc.cancel()
		frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)


def test_native_transfer_and_rehire_employment_spell_boundaries():
	from workforce_suite.workforce_suite.employee_lifecycle import validate_employee_employment_spell

	company = "Example Company A"
	other_company = "Example Company B"
	assert frappe.db.exists("Company", company)
	assert frappe.db.exists("Company", other_company)

	old_user = frappe.session.user
	employee_name = None
	transfer_names = []
	attendance_names = []
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

		# A submitted record on the generated employment spell consumes this
		# cross-company Transfer and must block reversal.
		attendance = frappe.get_doc({
			"doctype": "Attendance",
			"employee": new_employee_name,
			"employee_name": frappe.db.get_value("Employee", new_employee_name, "employee_name"),
			"company": other_company,
			"attendance_date": "2026-09-25",
			"status": "Present",
		}).insert(ignore_permissions=True)
		attendance_names.append(attendance.name)
		attendance.submit()
		with pytest.raises(frappe.ValidationError, match="LIFECYCLE_CHANGE_ALREADY_CONSUMED"):
			valid.cancel()
		attendance.cancel()
		frappe.delete_doc("Attendance", attendance.name, force=True, ignore_permissions=True)
		attendance_names.remove(attendance.name)

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
		for name in attendance_names:
			if frappe.db.exists("Attendance", name):
				doc = frappe.get_doc("Attendance", name)
				if doc.docstatus == 1:
					doc.cancel()
				frappe.delete_doc("Attendance", name, force=True, ignore_permissions=True)
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


def test_scoped_workforce_roles_can_operate_native_lifecycle_and_ssa_maker_checker():
	"""Prove native lifecycle/SSA permissions using scoped custom-role users."""
	company = "Example Company A"
	other_company = "Example Company B"
	token = frappe.generate_hash().upper()[:8]
	old_user = frappe.session.user
	tracked = {"users": [], "permissions": [], "employees": [], "transfers": [], "promotions": [], "ssas": []}
	manager = approver = None
	try:
		frappe.set_user("Administrator")
		manager, permission = _scoped_user("Workforce Suite Manager", company, f"manager-{token}")
		tracked["users"].append(manager)
		tracked["permissions"].append(permission)
		approver, permission = _scoped_user("Workforce Payroll Approver", company, f"approver-{token}")
		tracked["users"].append(approver)
		tracked["permissions"].append(permission)
		employee = _employee(company, f"roles-{token}")
		tracked["employees"].append(employee)
		foreign_employee = _employee(other_company, f"foreign-{token}")
		tracked["employees"].append(foreign_employee)
		foreign_department = frappe.db.get_value("Employee", foreign_employee, "department")
		new_foreign_department = next(
			(
				name
				for name in frappe.get_all("Department", filters={"company": other_company}, pluck="name")
				if name != foreign_department
			),
			None,
		)
		assert new_foreign_department
		foreign_transfer = frappe.get_doc({
			"doctype": "Employee Transfer",
			"employee": foreign_employee,
			"company": other_company,
			"transfer_date": frappe.utils.today(),
			"transfer_details": [
				_movement_row("department", foreign_department, new_foreign_department, "Department")
			],
		}).insert(ignore_permissions=True)
		tracked.setdefault("foreign_transfers", []).append(foreign_transfer.name)
		foreign_promotion = frappe.get_doc({
			"doctype": "Employee Promotion",
			"employee": foreign_employee,
			"company": other_company,
			"promotion_date": frappe.utils.today(),
		}).insert(ignore_permissions=True)
		tracked.setdefault("foreign_promotions", []).append(foreign_promotion.name)
		department = frappe.db.get_value("Employee", employee, "department")
		departments = frappe.get_all("Department", filters={"company": company}, pluck="name", order_by="name asc")
		new_department = next((name for name in departments if name != department), None)
		assert new_department, "Synthetic same-company transfer needs two native Departments"
		old_department = department
		old_branch = frappe.db.get_value("Employee", employee, "branch")
		old_designation = frappe.db.get_value("Employee", employee, "designation")
		old_employment_type = frappe.db.get_value("Employee", employee, "employment_type")
		new_employment_type = next(
			(name for name in frappe.get_all("Employment Type", pluck="name", order_by="name asc")
			 if name != old_employment_type),
			None,
		)
		new_branch = next(
			(name for name in frappe.get_all("Branch", pluck="name", order_by="name asc") if name != old_branch),
			None,
		)
		new_designation = next(
			(name for name in frappe.get_all("Designation", pluck="name", order_by="name asc") if name != old_designation),
			None,
		)
		assert new_branch and new_designation and new_employment_type, (
			"Native movement checks need alternative Branch, Designation, and Employment Type values"
		)

		frappe.clear_cache()
		frappe.set_user(manager)
		roles = set(frappe.get_roles())
		assert "Workforce Suite Manager" in roles
		assert "HR User" not in roles and "HR Manager" not in roles
		assert frappe.has_permission("Employee Transfer", "create")
		assert frappe.has_permission("Employee Transfer", "submit")
		assert frappe.has_permission("Employee Promotion", "create")
		assert frappe.has_permission("Employee Promotion", "submit")
		assert not frappe.has_permission("Employee Transfer", "read", foreign_transfer)
		assert not frappe.has_permission("Employee Promotion", "read", foreign_promotion)
		assert foreign_transfer.name not in frappe.get_list(
			"Employee Transfer", filters={"name": foreign_transfer.name}, pluck="name"
		)
		assert foreign_promotion.name not in frappe.get_list(
			"Employee Promotion", filters={"name": foreign_promotion.name}, pluck="name"
		)
		with pytest.raises(frappe.PermissionError):
			frappe.get_doc("Employee Transfer", foreign_transfer.name).check_permission("read")
		with pytest.raises(frappe.PermissionError):
			frappe.get_doc("Employee Promotion", foreign_promotion.name).check_permission("read")
		assert frappe.has_permission("Employee", "read", employee)
		assert not frappe.has_permission("Employee", "read", foreign_employee)
		listed = set(frappe.get_list("Employee", filters={"name": ["in", [employee, foreign_employee]]}, pluck="name"))
		assert employee in listed and foreign_employee not in listed
		with pytest.raises(frappe.PermissionError):
			frappe.get_doc("Employee", foreign_employee).check_permission("read")

		# Existing Employee movement cannot be saved directly, even by Administrator.
		for fieldname, value in (
			("branch", new_branch),
			("department", new_department),
			("designation", new_designation),
			("company", other_company),
		):
			frappe.set_user("Administrator")
			doc = frappe.get_doc("Employee", employee)
			setattr(doc, fieldname, value)
			with pytest.raises(frappe.ValidationError, match="must be changed through native Employee Transfer"):
				doc.save(ignore_permissions=True)
			frappe.set_user(manager)

		transfer = frappe.get_doc(
			{
				"doctype": "Employee Transfer",
				"employee": employee,
				"company": company,
				"transfer_date": frappe.utils.today(),
				"transfer_details": [
					_movement_row("branch", old_branch, new_branch, "Branch"),
					_movement_row("department", old_department, new_department, "Department"),
					_movement_row("designation", old_designation, new_designation, "Designation"),
					_movement_row("employment_type", old_employment_type, new_employment_type, "Employment Type"),
				],
			}
		).insert()
		tracked["transfers"].append(transfer.name)
		transfer.submit()
		assert frappe.db.get_value("Employee", employee, "branch") == new_branch
		assert frappe.db.get_value("Employee", employee, "department") == new_department
		assert frappe.db.get_value("Employee", employee, "designation") == new_designation
		assert frappe.db.get_value("Employee", employee, "employment_type") == new_employment_type
		history = frappe.get_all(
			"Employee Internal Work History",
			filters={"parent": employee, "parenttype": "Employee", "parentfield": "internal_work_history"},
			fields=["branch", "department", "designation", "from_date"],
		)
		assert any(row.branch == new_branch for row in history)
		assert any(row.department == new_department for row in history)
		assert any(row.designation == new_designation for row in history)
		transfer.cancel()
		assert frappe.db.get_value("Employee", employee, "branch") == old_branch
		assert frappe.db.get_value("Employee", employee, "department") == old_department
		assert frappe.db.get_value("Employee", employee, "designation") == old_designation
		assert frappe.db.get_value("Employee", employee, "employment_type") == old_employment_type

		# The Promotion path also performs its Employee update inside native context.
		designations = frappe.get_all("Designation", pluck="name", order_by="name asc")
		new_designation = next((name for name in designations if name != old_designation), None)
		assert new_designation, "Synthetic Promotion needs a second native Designation"
		promotion = frappe.get_doc(
			{
				"doctype": "Employee Promotion",
				"employee": employee,
				"promotion_date": frappe.utils.today(),
				"promotion_details": [_movement_row("designation", old_designation, new_designation, "Designation")],
			}
		).insert()
		tracked["promotions"].append(promotion.name)
		promotion.submit()
		assert frappe.db.get_value("Employee", employee, "designation") == new_designation
		promotion.cancel()
		assert frappe.db.get_value("Employee", employee, "designation") == old_designation

		# Employment Type is supported by the native Promotion detail table.
		employment_promotion = frappe.get_doc({
			"doctype": "Employee Promotion",
			"employee": employee,
			"promotion_date": frappe.utils.today(),
			"promotion_details": [
				_movement_row("employment_type", old_employment_type, new_employment_type, "Employment Type")
			],
		}).insert()
		tracked["promotions"].append(employment_promotion.name)
		employment_promotion.submit()
		assert frappe.db.get_value("Employee", employee, "employment_type") == new_employment_type
		employment_promotion.cancel()
		assert frappe.db.get_value("Employee", employee, "employment_type") == old_employment_type

		# Maker can save but cannot submit; an independent Payroll Approver can submit.
		structure = frappe.db.get_value(
			"Salary Structure",
			{"company": company, "docstatus": 1, "is_active": "Yes"},
			["name", "custom_workforce_pay_basis"],
			as_dict=True,
		)
		if not structure:
			structure = frappe.db.get_value(
				"Salary Structure",
			{"company": company, "docstatus": 1},
			["name", "custom_workforce_pay_basis"],
			as_dict=True,
			order_by="name asc",
			)
		assert structure and structure.custom_workforce_pay_basis, "Need an existing submitted structure with explicit pay basis"
		frappe.set_user(manager)
		ssa = frappe.get_doc(
			{
				"doctype": "Salary Structure Assignment",
				"employee": employee,
				"company": company,
				"salary_structure": structure.name,
				"from_date": frappe.utils.today(),
				"base": 1000,
			}
		).insert()
		tracked["ssas"].append(ssa.name)
		assert ssa.docstatus == 0
		with pytest.raises(frappe.PermissionError):
			ssa.submit()
		# HRMS bulk-creation paths may call submit() after an internal
		# ignore-permissions save. The server-side role gate must still reject it.
		ssa.reload()
		ssa.flags.ignore_permissions = True
		with pytest.raises(frappe.PermissionError, match="Only a Workforce Payroll Approver"):
			ssa.submit()
		ssa.flags.ignore_permissions = False
		frappe.set_user(approver)
		assert "Workforce Payroll Approver" in frappe.get_roles()
		assert "HR User" not in frappe.get_roles() and "HR Manager" not in frappe.get_roles()
		assert not frappe.has_permission("Salary Structure Assignment", "create")
		assert frappe.has_permission("Salary Structure Assignment", "submit")
		ssa.reload()
		ssa.submit()
		assert ssa.docstatus == 1

		# A salary-changing Promotion consumes the exact-date native SSA; safe
		# cancellation requires reversing the unconsumed SSA first.
		frappe.set_user(manager)
		financial_promotion = frappe.get_doc(
			{
				"doctype": "Employee Promotion",
				"employee": employee,
				"promotion_date": frappe.utils.today(),
				"current_ctc": 1000,
				"revised_ctc": 1200,
			}
		).insert()
		tracked["promotions"].append(financial_promotion.name)
		financial_promotion.submit()
		assert frappe.db.get_value("Employee", employee, "ctc") == 1200
		with pytest.raises(frappe.ValidationError, match="Cancel the exact effective submitted Salary Structure Assignment first"):
			financial_promotion.cancel()
		frappe.set_user(approver)
		ssa.reload()
		ssa.cancel()
		frappe.set_user(manager)
		financial_promotion.reload()
		financial_promotion.cancel()
		assert frappe.db.get_value("Employee", employee, "ctc") == 1000

		# A dual-role maker/approver still cannot approve their own SSA.
		frappe.set_user("Administrator")
		dual, permission = _scoped_user("Workforce Suite Manager", company, f"dual-{token}")
		tracked["users"].append(dual)
		tracked["permissions"].append(permission)
		user_doc = frappe.get_doc("User", dual)
		user_doc.append("roles", {"role": "Workforce Payroll Approver"})
		user_doc.save(ignore_permissions=True)
		frappe.clear_cache()
		frappe.set_user(dual)
		dual_ssa = frappe.get_doc(
			{
				"doctype": "Salary Structure Assignment",
				"employee": employee,
				"company": company,
				"salary_structure": structure.name,
				"from_date": frappe.utils.add_days(frappe.utils.today(), 1),
				"base": 1000,
			}
		).insert()
		tracked["ssas"].append(dual_ssa.name)
		with pytest.raises(frappe.ValidationError, match="SSA_MAKER_CHECKER"):
			dual_ssa.submit()

		# A submitted later effective assignment also consumes its predecessor.
		frappe.set_user(manager)
		older_ssa = frappe.get_doc({
			"doctype": "Salary Structure Assignment",
			"employee": employee,
			"company": company,
			"salary_structure": structure.name,
			"from_date": frappe.utils.add_days(frappe.utils.today(), 2),
			"base": 1000,
		}).insert()
		tracked["ssas"].append(older_ssa.name)
		frappe.set_user(approver)
		older_ssa.submit()
		frappe.set_user(manager)
		newer_ssa = frappe.get_doc({
			"doctype": "Salary Structure Assignment",
			"employee": employee,
			"company": company,
			"salary_structure": structure.name,
			"from_date": frappe.utils.add_days(frappe.utils.today(), 3),
			"base": 1100,
		}).insert()
		tracked["ssas"].append(newer_ssa.name)
		frappe.set_user(approver)
		newer_ssa.submit()
		with pytest.raises(frappe.ValidationError, match="LIFECYCLE_CHANGE_ALREADY_CONSUMED"):
			older_ssa.cancel()
		assert frappe.db.get_value("Salary Structure Assignment", older_ssa.name, "docstatus") == 1

		# A COMPANY_A manager cannot write an COMPANY_B assignment, even with direct insertion.
		frappe.set_user("Administrator")
		tcl_manager = manager
		frappe.set_user(tcl_manager)
		foreign_structure = frappe.db.get_value(
			"Salary Structure", {"company": other_company, "docstatus": 1}, "name", order_by="name asc"
		)
		if foreign_structure:
			with pytest.raises(frappe.PermissionError):
				frappe.get_doc(
					{
						"doctype": "Salary Structure Assignment",
						"employee": foreign_employee,
						"company": other_company,
						"salary_structure": foreign_structure,
						"from_date": frappe.utils.today(),
						"base": 1000,
					}
				).insert()
			# An in-scope Payroll Approver may cancel unconsumed SSA drafts, but
			# Company User Permission must also protect cancellation of a submitted
			# foreign-company assignment.
			frappe.set_user("Administrator")
			foreign_ssa = frappe.get_doc({
				"doctype": "Salary Structure Assignment",
				"employee": foreign_employee,
				"company": other_company,
				"salary_structure": foreign_structure,
				"from_date": frappe.utils.today(),
				"base": 1000,
			}).insert(ignore_permissions=True)
			tracked.setdefault("foreign_ssas", []).append(foreign_ssa.name)
			foreign_ssa.submit()
			frappe.set_user(approver)
			with pytest.raises(frappe.PermissionError):
				foreign_ssa.cancel()
		else:
			assert not frappe.has_permission("Employee", "read", foreign_employee)
	finally:
		frappe.set_user("Administrator")
		for name in tracked["users"]:
			for permission_name in frappe.get_all("User Permission", filters={"user": name}, pluck="name"):
				frappe.delete_doc("User Permission", permission_name, force=True, ignore_permissions=True)
		_cancel_and_delete("Salary Structure Assignment", tracked["ssas"])
		_cancel_and_delete("Salary Structure Assignment", tracked.get("foreign_ssas", []))
		_cancel_and_delete("Employee Promotion", tracked["promotions"])
		_cancel_and_delete("Employee Transfer", tracked["transfers"])
		_cancel_and_delete("Employee Promotion", tracked.get("foreign_promotions", []))
		_cancel_and_delete("Employee Transfer", tracked.get("foreign_transfers", []))
		for name in tracked["employees"]:
			if frappe.db.exists("Employee", name):
				frappe.delete_doc("Employee", name, force=True, ignore_permissions=True)
		for name in tracked["users"]:
			if frappe.db.exists("User", name):
				frappe.delete_doc("User", name, force=True, ignore_permissions=True)
		frappe.clear_cache()
		frappe.set_user(old_user)
	assert all(not frappe.db.exists("User", name) for name in tracked["users"])
	assert all(not frappe.db.exists("User Permission", name) for name in tracked["permissions"])
	assert all(not frappe.db.exists("Employee", name) for name in tracked["employees"])
	assert all(not frappe.db.exists("Salary Structure Assignment", name) for name in tracked["ssas"])
	assert all(not frappe.db.exists("Salary Structure Assignment", name) for name in tracked.get("foreign_ssas", []))
	assert all(not frappe.db.exists("Employee Transfer", name) for name in tracked["transfers"])
	assert all(not frappe.db.exists("Employee Promotion", name) for name in tracked["promotions"])
	assert all(not frappe.db.exists("Employee Transfer", name) for name in tracked.get("foreign_transfers", []))
	assert all(not frappe.db.exists("Employee Promotion", name) for name in tracked.get("foreign_promotions", []))


def test_lifecycle_cancellation_blocks_consumed_attendance_and_later_movement():
	company = "Example Company A"
	old_user = frappe.session.user
	tracked = {"users": [], "permissions": [], "employees": [], "transfers": [], "promotions": [], "attendance": []}
	token = frappe.generate_hash().upper()[:8]
	try:
		frappe.set_user("Administrator")
		manager, permission = _scoped_user("Workforce Suite Manager", company, f"cancel-{token}")
		tracked["users"].append(manager)
		tracked["permissions"].append(permission)
		employee = _employee(company, f"cancel-{token}")
		tracked["employees"].append(employee)
		department = frappe.db.get_value("Employee", employee, "department")
		new_department = next(
			(name for name in frappe.get_all("Department", filters={"company": company}, pluck="name") if name != department),
			None,
		)
		old_designation = frappe.db.get_value("Employee", employee, "designation")
		new_designation = next(
			(name for name in frappe.get_all("Designation", pluck="name") if name != old_designation),
			None,
		)
		assert new_department and new_designation
		frappe.clear_cache()
		frappe.set_user(manager)
		transfer = frappe.get_doc(
			{
				"doctype": "Employee Transfer",
				"employee": employee,
				"company": company,
				"transfer_date": frappe.utils.today(),
				"transfer_details": [_movement_row("department", department, new_department, "Department")],
			}
		).insert()
		tracked["transfers"].append(transfer.name)
		transfer.submit()

		frappe.set_user("Administrator")
		attendance = frappe.get_doc(
			{
				"doctype": "Attendance",
				"employee": employee,
				"employee_name": frappe.db.get_value("Employee", employee, "employee_name"),
				"company": company,
				"attendance_date": frappe.utils.today(),
				"status": "Present",
			}
		).insert(ignore_permissions=True)
		tracked["attendance"].append(attendance.name)
		attendance.submit()
		frappe.set_user(manager)
		transfer.reload()
		with pytest.raises(frappe.ValidationError, match="LIFECYCLE_CHANGE_ALREADY_CONSUMED"):
			transfer.cancel()

		frappe.set_user("Administrator")
		attendance.reload()
		attendance.cancel()
		frappe.delete_doc("Attendance", attendance.name, force=True, ignore_permissions=True)
		tracked["attendance"].remove(attendance.name)

		promotion = frappe.get_doc(
			{
				"doctype": "Employee Promotion",
				"employee": employee,
				"promotion_date": frappe.utils.today(),
				"promotion_details": [_movement_row("designation", old_designation, new_designation, "Designation")],
			}
		).insert(ignore_permissions=True)
		tracked["promotions"].append(promotion.name)
		promotion.submit()
		frappe.set_user(manager)
		transfer.reload()
		with pytest.raises(frappe.ValidationError, match="LIFECYCLE_CHANGE_ALREADY_CONSUMED"):
			transfer.cancel()
		frappe.set_user("Administrator")
		promotion.reload()
		promotion.cancel()
		frappe.set_user(manager)
		transfer.reload()
		transfer.cancel()
		assert frappe.db.get_value("Employee", employee, "department") == department
	finally:
		frappe.set_user("Administrator")
		for name in tracked["attendance"]:
			if frappe.db.exists("Attendance", name):
				doc = frappe.get_doc("Attendance", name)
				if doc.docstatus == 1:
					doc.cancel()
				frappe.delete_doc("Attendance", name, force=True, ignore_permissions=True)
		_cancel_and_delete("Employee Promotion", tracked["promotions"])
		_cancel_and_delete("Employee Transfer", tracked["transfers"])
		for name in tracked["permissions"]:
			if frappe.db.exists("User Permission", name):
				frappe.delete_doc("User Permission", name, force=True, ignore_permissions=True)
		for name in tracked["employees"]:
			if frappe.db.exists("Employee", name):
				frappe.delete_doc("Employee", name, force=True, ignore_permissions=True)
		for name in tracked["users"]:
			if frappe.db.exists("User", name):
				frappe.delete_doc("User", name, force=True, ignore_permissions=True)
		frappe.clear_cache()
		frappe.set_user(old_user)
	assert all(not frappe.db.exists("Employee", name) for name in tracked["employees"])
	assert all(not frappe.db.exists("User Permission", name) for name in tracked["permissions"])
