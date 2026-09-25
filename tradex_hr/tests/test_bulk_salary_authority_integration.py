"""Site-backed tests for native bulk SSA preparation and approval boundaries."""

from __future__ import annotations

import json

import frappe
import pytest
from frappe.utils import add_days, getdate

from tradex_hr.tests.persona_uat import PERSONA_ROLES, SyntheticPersonaHarness, assert_only_tradexcel_roles


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


def _run_tool_method(method, payload, *, args=None):
	from frappe.handler import run_doc_method

	acting_user = frappe.session.user
	# The native tool is a singleton. Set its filters through an Administrator
	# fixture update, then exercise Frappe's actual dt/dn document-method route as
	# the persona. Sending an ad hoc unsaved singleton JSON document makes
	# check_if_latest compare a missing modified timestamp with the stored row.
	frappe.set_user("Administrator")
	doc = frappe.get_single("Bulk Salary Structure Assignment")
	for key, value in payload.items():
		if key not in {"doctype", "name", "modified"}:
			doc.set(key, value)
	for key in ("employment_type", "branch", "department", "designation", "grade"):
		if key not in payload:
			doc.set(key, None)
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	frappe.set_user(acting_user)
	frappe.local.request = frappe._dict(method="POST")
	frappe.local.response.docs = []
	result = run_doc_method(
		method=method,
		dt="Bulk Salary Structure Assignment",
		dn="Bulk Salary Structure Assignment",
		args=json.dumps(args, default=str) if args is not None else None,
	)
	return result if result is not None else frappe.response.get("message")


def _workspace_shortcuts(user):
	from frappe.desk.desktop import get_desktop_page, get_workspaces

	frappe.set_user(user)
	page = next((row for row in get_workspaces()["pages"] if row.get("name") == "tradexcel-hr"), None)
	if not page:
		return set()
	payload = get_desktop_page(json.dumps(page))
	return {row.get("label") for row in payload.get("shortcuts", {}).get("items", [])}


def _structure(company, basis):
	from hrms.payroll.doctype.salary_structure_assignment.salary_structure_assignment import get_tax_component

	for row in frappe.get_all(
		"Salary Structure",
		filters={"company": company, "docstatus": 1, "is_active": "Yes", "custom_tradex_pay_basis": basis},
		fields=["name", "custom_tradex_pay_basis", "currency"],
		order_by="name asc",
	):
		if not get_tax_component(row.name):
			return row
	return None


def _tool_payload(company, structure, from_date=None):
	return {
		"doctype": "Bulk Salary Structure Assignment",
		"salary_structure": structure.name,
		"from_date": from_date or add_days(getdate(), 2),
		"company": company,
		"currency": structure.currency,
		"payroll_payable_account": frappe.db.get_value(
			"Company", company, "default_payroll_payable_account"
		),
	}


def _new_employee(personas, key, company, branch, department):
	name = personas.create_employee(key, company, branch, department)
	# Contradictory HR categorization is deliberate: only the Structure's
	# explicit pay-basis metadata determines whether Base is monthly or daily.
	worker_type = "Worker" if frappe.db.exists("Employment Type", "Worker") else None
	if worker_type:
		frappe.db.set_value("Employee", name, "employment_type", worker_type)
	return name


def test_native_bulk_salary_structure_assignment_maker_checker_and_scope(monkeypatch):
	from hrms.payroll.doctype.bulk_salary_structure_assignment.bulk_salary_structure_assignment import (
		BulkSalaryStructureAssignment as NativeBulkSalaryStructureAssignment,
	)
	from frappe.desk.doctype.bulk_update.bulk_update import submit_cancel_or_update_docs
	from tradex_hr.tradexcel_hr.bulk_salary_structure_assignment import TradexcelBulkSalaryStructureAssignmentMixin
	from tradex_hr.tradexcel_hr.bulk_salary_structure_assignment import _tool_mode
	from tradex_hr.tradexcel_hr.pay_basis import DAILY, MONTHLY, resolve_pay_basis

	company_a = "Tradexcel Ceramics Ltd."
	company_b = "Elegance Footwear Ltd."
	branches_a = frappe.get_all("Branch", filters={"company": company_a}, pluck="name", order_by="name")
	branches_b = frappe.get_all("Branch", filters={"company": company_b}, pluck="name", order_by="name")
	departments_a = frappe.get_all("Department", filters={"company": company_a}, pluck="name", order_by="name")
	departments_b = frappe.get_all("Department", filters={"company": company_b}, pluck="name", order_by="name")
	assert len(branches_a) >= 2 and len(departments_a) >= 2 and branches_b and departments_b

	monthly = _structure(company_a, MONTHLY)
	daily = _structure(company_a, DAILY)
	assert monthly and daily, "Site-backed test requires explicit submitted monthly and daily structures"
	assert frappe.db.get_value("Company", company_a, "default_payroll_payable_account")
	date = add_days(getdate(), 2)
	frappe.clear_cache(doctype="Bulk Salary Structure Assignment")
	tool_state = frappe.get_single("Bulk Salary Structure Assignment")
	tool_fields = (
		"salary_structure", "from_date", "income_tax_slab", "company",
		"payroll_payable_account", "currency", "branch", "department",
		"designation", "grade", "employment_type",
	)
	tool_state_before = {field: tool_state.get(field) for field in tool_fields}
	side_effect_counts = {
		doctype: frappe.db.count(doctype)
		for doctype in ("Attendance", "Employee Checkin", "Salary Slip", "Payroll Entry", "Additional Salary", "Arrear")
	}
	token = f"BULKSSA{frappe.generate_hash(9).upper()}"
	personas = SyntheticPersonaHarness(token)
	tracked_ssas: list[str] = []
	error_log_before = set(frappe.get_all("Error Log", pluck="name"))
	logs = []
	events = []
	original_log_error = frappe.log_error
	original_publish = frappe.publish_realtime
	original_enqueue = frappe.enqueue

	try:
		frappe.set_user("Administrator")
		users = {
			"hr_manager": personas.create_user(
				"hr-manager", [PERSONA_ROLES["hr_manager"]], company=company_a,
				branch=branches_a[0], department=departments_a[0],
			),
			"payroll_manager": personas.create_user(
				"payroll-manager", [PERSONA_ROLES["payroll_manager"]], company=company_a,
				branch=branches_a[0], department=departments_a[0],
			),
			"approver": personas.create_user(
				"payroll-approver", [PERSONA_ROLES["payroll_approver"]], company=company_a,
			),
			"finance": personas.create_user(
				"finance", [PERSONA_ROLES["finance"]], company=company_a,
			),
			"branch_manager": personas.create_user(
				"branch-manager", [PERSONA_ROLES["branch_manager"]], company=company_a,
				branch=branches_a[0],
			),
			"worker": personas.create_user("worker", [PERSONA_ROLES["worker"]], company=company_a),
			"native_mixed": personas.create_user(
				"native-hr-mixed", ["HR User", PERSONA_ROLES["payroll_manager"]],
				company=company_a, branch=branches_a[0], department=departments_a[0],
			),
			"dual_maker_approver": personas.create_user(
				"dual-maker-approver", [PERSONA_ROLES["hr_manager"], PERSONA_ROLES["payroll_approver"]],
				company=company_a, branch=branches_a[0], department=departments_a[0],
			),
		}
		for key in ("hr_manager", "payroll_manager", "approver", "finance", "branch_manager", "worker", "dual_maker_approver"):
			assert_only_tradexcel_roles(users[key])
		assert "HR User" in frappe.get_roles(users["native_mixed"])

		employees = {
			"monthly": _new_employee(personas, "monthly", company_a, branches_a[0], departments_a[0]),
			"daily": _new_employee(personas, "daily", company_a, branches_a[0], departments_a[0]),
			"zero_daily": _new_employee(personas, "zero-daily", company_a, branches_a[0], departments_a[0]),
			"other_branch": _new_employee(personas, "other-branch", company_a, branches_a[1], departments_a[0]),
			"other_department": _new_employee(personas, "other-department", company_a, branches_a[0], departments_a[1]),
			"cross_company": _new_employee(personas, "cross-company", company_b, branches_b[0], departments_b[0]),
			"inactive": _new_employee(personas, "inactive", company_a, branches_a[0], departments_a[0]),
			"future": _new_employee(personas, "future", company_a, branches_a[0], departments_a[0]),
			"relieved": _new_employee(personas, "relieved", company_a, branches_a[0], departments_a[0]),
			"partial_a": _new_employee(personas, "partial-a", company_a, branches_a[0], departments_a[0]),
			"partial_bad": _new_employee(personas, "partial-bad", company_a, branches_a[0], departments_a[0]),
			"partial_c": _new_employee(personas, "partial-c", company_a, branches_a[0], departments_a[0]),
			"tamper_company": _new_employee(personas, "tamper-company", company_a, branches_a[0], departments_a[0]),
			"tamper_currency": _new_employee(personas, "tamper-currency", company_a, branches_a[0], departments_a[0]),
			"payroll_maker": _new_employee(personas, "payroll-maker", company_a, branches_a[0], departments_a[0]),
		}
		frappe.db.set_value("Employee", employees["inactive"], "status", "Inactive")
		non_worker_type = next(
			(name for name in frappe.get_all("Employment Type", pluck="name") if name != "Worker"), None
		)
		if non_worker_type:
			frappe.db.set_value("Employee", employees["monthly"], "employment_type", non_worker_type)
		frappe.db.set_value("Employee", employees["future"], "date_of_joining", add_days(date, 1))
		frappe.db.set_value("Employee", employees["relieved"], {
			"status": "Left", "relieving_date": add_days(date, -1),
		})
		tool_single = frappe.get_single("Bulk Salary Structure Assignment")
		tool_single.update(_tool_payload(company_a, monthly, date))
		tool_single.branch = branches_a[0]
		tool_single.department = departments_a[0]
		tool_single.save(ignore_permissions=True)
		frappe.db.commit()

		# The unextended installed native controller's preview is not permission
		# aware: Query Builder defaults ignore_permissions=True. This synthetic
		# control records the pre-fix rows without exposing real Employee data.
		frappe.clear_cache()
		frappe.set_user(users["native_mixed"])
		assert frappe.has_permission("Bulk Salary Structure Assignment", "read")
		native_preview_doc = NativeBulkSalaryStructureAssignment({
			"doctype": "Bulk Salary Structure Assignment", "from_date": date,
		})
		raw_native_preview = native_preview_doc.get_employees([])
		raw_native_names = {row.get("employee") or row.get("name") for row in raw_native_preview}
		assert employees["other_branch"] in raw_native_names
		assert employees["other_department"] in raw_native_names
		assert employees["cross_company"] in raw_native_names

		# Before the extension, native apply accepts the client-selected rows,
		# calls the ignore-permissions helper, and asks it to submit. The existing
		# Tradexcel Employee Company/permission validators and SSA maker-checker
		# then fail closed in this app, so no authority survives these attacks.
		frappe.log_error = lambda *args, **kwargs: logs.append((args, kwargs))
		for employee in (employees["other_branch"], employees["cross_company"]):
			native_apply_doc = NativeBulkSalaryStructureAssignment(_tool_payload(company_a, monthly, date))
			native_apply_doc.bulk_assign_structure([{"employee": employee, "base": 1250, "variable": 0}])
			assert not frappe.db.exists(
				"Salary Structure Assignment", {"employee": employee, "from_date": date}
			)
		frappe.log_error = original_log_error

		# Native HRMS picker uses a Query Builder call with ignore_permissions by
		# default. The installed extension must intersect it with Employee get_list.
		frappe.set_user(users["hr_manager"])
		assert frappe.has_permission("Bulk Salary Structure Assignment", "read")
		original_get_doc = frappe.get_doc
		class MissingBasisStructure:
			company = company_a
			currency = monthly.currency
			custom_tradex_pay_basis = None
			docstatus = 1
			is_active = "Yes"
			def check_permission(self, _ptype):
				return None
		frappe.get_doc = lambda doctype, *args, **kwargs: (
			MissingBasisStructure() if doctype == "Salary Structure" else original_get_doc(doctype, *args, **kwargs)
		)
		try:
			with pytest.raises(frappe.ValidationError, match="explicit Monthly Salary or Daily Wage"):
				TradexcelBulkSalaryStructureAssignmentMixin._validate_structure_context(
					frappe._dict(salary_structure="SYNTHETIC-MISSING-BASIS", from_date=date, company=company_a)
				)
		finally:
			frappe.get_doc = original_get_doc
		payload = _tool_payload(company_a, monthly)
		rows = _run_tool_method("get_employees", payload, args={"advanced_filters": []})
		preview_names = {row.get("name") or row.get("employee") for row in rows}
		assert employees["monthly"] in preview_names
		assert not preview_names.intersection({employees["other_branch"], employees["other_department"], employees["cross_company"]})
		assert not preview_names.intersection({employees["inactive"], employees["future"], employees["relieved"]})
		for manual_filters in (
			{"branch": branches_a[1]},
			{"department": departments_a[1]},
		):
			manual_payload = {**payload, **manual_filters}
			try:
				manual_rows = _run_tool_method("get_employees", manual_payload, args={"advanced_filters": []})
			except frappe.PermissionError:
				# Frappe can reject opening the singleton itself when its linked
				# Branch/Department User Permission is outside the acting user.
				manual_rows = []
			assert not {row.get("name") or row.get("employee") for row in manual_rows}.intersection(
				{employees["other_branch"], employees["other_department"]}
			)
		frappe.set_user("Administrator")
		tool_single = frappe.get_single("Bulk Salary Structure Assignment")
		tool_single.update(_tool_payload(company_a, monthly, date))
		tool_single.branch = branches_a[0]
		tool_single.department = departments_a[0]
		tool_single.save(ignore_permissions=True)
		frappe.db.commit()
		manager_shortcuts = _workspace_shortcuts(users["hr_manager"])
		frappe.set_user(users["hr_manager"])
		manager_user = frappe.get_user()
		manager_user.build_permissions()
		assert "Bulk Salary Structure Assignment" in manager_shortcuts, {
			"has_permission": frappe.has_permission("Bulk Salary Structure Assignment", "read", user=users["hr_manager"]),
			"can_read": "Bulk Salary Structure Assignment" in (manager_user.can_read or []),
			"allow_modules": manager_user.allow_modules,
			"workspace_shortcuts": sorted(manager_shortcuts),
		}
		assert "Bulk Salary Structure Assignment" in _workspace_shortcuts(users["payroll_manager"])
		for key in ("approver", "finance", "branch_manager", "worker"):
			assert not frappe.has_permission("Bulk Salary Structure Assignment", "read", user=users[key])
			assert "Bulk Salary Structure Assignment" not in _workspace_shortcuts(users[key])
			frappe.set_user(users[key])
			with pytest.raises(frappe.PermissionError):
				_run_tool_method("get_employees", _tool_payload(company_a, monthly, date), args={"advanced_filters": []})

		# Two explicit bases override the synthetic Employees' matching Worker
		# employment type. HR Manager may create drafts but cannot submit.
		frappe.set_user(users["hr_manager"])
		for key, structure in (("monthly", monthly), ("daily", daily)):
			payload = _tool_payload(company_a, structure, date)
			_run_tool_method(
				"bulk_assign_structure", payload,
				args={"employees": [{"employee": employees[key], "base": 1750, "variable": 0}]},
			)
			ssa = frappe.get_value(
				"Salary Structure Assignment", {"employee": employees[key], "from_date": date}, "name"
			)
			assert ssa
			tracked_ssas.append(ssa)
			assert frappe.db.get_value("Salary Structure Assignment", ssa, "docstatus") == 0
			assert not frappe.has_permission("Salary Structure Assignment", "submit", doc=frappe.get_doc("Salary Structure Assignment", ssa))
			resolved = resolve_pay_basis(employees[key], date)
			assert resolved["status"] == "UNRESOLVED"
			assert frappe.db.get_value("Salary Structure Assignment", ssa, "salary_structure") == structure.name

		# Zero remains an explicit draft value, never silently converted. The
		# canonical Daily Wage readiness resolver treats it as a blocker.
		_run_tool_method(
			"bulk_assign_structure", _tool_payload(company_a, daily, date),
			args={"employees": [{"employee": employees["zero_daily"], "base": 0, "variable": 0}]},
		)
		zero_ssa = frappe.get_value(
			"Salary Structure Assignment", {"employee": employees["zero_daily"], "from_date": date}, "name"
		)
		assert zero_ssa and frappe.db.get_value("Salary Structure Assignment", zero_ssa, "base") == 0
		tracked_ssas.append(zero_ssa)
		assert resolve_pay_basis(employees["zero_daily"], date)["status"] == "UNRESOLVED"

		# Payroll Manager is also a maker, but cannot submit the draft it created.
		frappe.set_user(users["payroll_manager"])
		_run_tool_method(
			"bulk_assign_structure", _tool_payload(company_a, daily, date),
			args={"employees": [{"employee": employees["payroll_maker"], "base": 1350, "variable": 0}]},
		)
		payroll_maker_ssa = frappe.get_value(
			"Salary Structure Assignment", {"employee": employees["payroll_maker"], "from_date": date}, "name"
		)
		assert payroll_maker_ssa and frappe.db.get_value("Salary Structure Assignment", payroll_maker_ssa, "docstatus") == 0
		tracked_ssas.append(payroll_maker_ssa)
		with pytest.raises(frappe.PermissionError):
			frappe.get_doc("Salary Structure Assignment", payroll_maker_ssa).submit()

		# The draft itself hides duplicate same-date entries from preview and
		# prevents a repeated apply with a forged row.
		rows = _run_tool_method("get_employees", _tool_payload(company_a, monthly, date), args={"advanced_filters": []})
		assert employees["monthly"] not in {row.get("name") or row.get("employee") for row in rows}
		for employee in (employees["other_branch"], employees["other_department"], employees["cross_company"]):
			with pytest.raises((frappe.ValidationError, frappe.PermissionError), match="permitted|eligible|scope"):
				_run_tool_method(
					"bulk_assign_structure", _tool_payload(company_a, monthly, date),
					args={"employees": [{"employee": employee, "base": 900, "variable": 0}]},
				)

		# Manual field tampering cannot select another Company/currency/account or
		# tax slab. Structural values are derived from the submitted Structure and
		# Company's configured payable account.
		for field, value, employee in (
			("company", company_b, employees["tamper_company"]),
			("currency", "USD" if monthly.currency != "USD" else "BDT", employees["tamper_currency"]),
			("payroll_payable_account", frappe.db.get_value("Company", company_b, "default_payroll_payable_account") or "forged-account", employees["partial_a"]),
			("income_tax_slab", "forged-synthetic-tax-slab", employees["partial_a"]),
		):
			bad = _tool_payload(company_a, monthly, date)
			bad[field] = value
			try:
				_run_tool_method(
					"bulk_assign_structure", bad,
					args={"employees": [{"employee": employee, "base": 900, "variable": 0}]},
				)
			except (frappe.ValidationError, frappe.PermissionError, frappe.DoesNotExistError):
				pass
			ssa_name = frappe.get_value(
				"Salary Structure Assignment", {"employee": employee, "from_date": date}, "name"
			)
			if ssa_name:
				ssa = frappe.get_doc("Salary Structure Assignment", ssa_name)
				assert ssa.company == company_a
				assert ssa.salary_structure == monthly.name
				assert ssa.currency == monthly.currency
				assert ssa.payroll_payable_account == frappe.db.get_value(
					"Company", company_a, "default_payroll_payable_account"
				)
				tracked_ssas.append(ssa_name)

		# Foreign structure selection is denied by native permission scope before
		# it can be used to construct an SSA.
		foreign_structure = _structure(company_b, MONTHLY)
		if foreign_structure:
			bad = _tool_payload(company_a, monthly, date)
			bad["salary_structure"] = foreign_structure.name
			with pytest.raises((frappe.ValidationError, frappe.PermissionError)):
				_run_tool_method(
					"bulk_assign_structure", bad,
					args={"employees": [{"employee": employees["partial_a"], "base": 900, "variable": 0}]},
				)

		# Row-level numeric errors are partial failures: two native drafts survive
		# and one forged negative row is reported failed without an SSA.
		frappe.set_user(users["hr_manager"])
		frappe.log_error = lambda *args, **kwargs: logs.append((args, kwargs))
		frappe.publish_realtime = lambda *args, **kwargs: events.append((args, kwargs))
		logs.clear()
		rows = [
			{"employee": employees["partial_a"], "base": "1250", "variable": "25"},
			{"employee": employees["partial_bad"], "base": "-1", "variable": 0},
			{"employee": employees["partial_c"], "base": "1450", "variable": 0},
		]
		assert set(frappe.get_list("Employee", filters={"name": ["in", [r["employee"] for r in rows]]}, pluck="name")) == {
			employees["partial_a"], employees["partial_bad"], employees["partial_c"]
		}
		# Isolate the per-row savepoint/result behavior from HRMS' independent
		# native preview filters; all selected Employees have already passed the
		# same real get_list scope check above.
		original_eligible_rows = TradexcelBulkSalaryStructureAssignmentMixin._eligible_rows
		monkeypatch.setattr(
			TradexcelBulkSalaryStructureAssignmentMixin,
			"_eligible_rows",
			lambda self, advanced_filters=None: [{"employee": name} for name in [r["employee"] for r in rows]],
		)
		_run_tool_method("bulk_assign_structure", _tool_payload(company_a, monthly, date), args={"employees": rows})
		for key in ("partial_a", "partial_c"):
			ssa = frappe.get_value("Salary Structure Assignment", {"employee": employees[key], "from_date": date}, "name")
			assert ssa and frappe.db.get_value("Salary Structure Assignment", ssa, "docstatus") == 0
			tracked_ssas.append(ssa)
		assert not frappe.db.exists("Salary Structure Assignment", {"employee": employees["partial_bad"], "from_date": date})
		assert events[-1][1]["message"]["failure"] == [employees["partial_bad"]], logs
		assert {r["employee"] for r in events[-1][1]["message"]["success"]} == {employees["partial_a"], employees["partial_c"]}
		monkeypatch.setattr(TradexcelBulkSalaryStructureAssignmentMixin, "_eligible_rows", original_eligible_rows)
		for forged in (
			{"employee": employees["partial_bad"], "base": 1200, "variable": "-4"},
			{"employee": employees["partial_bad"], "base": "NaN", "variable": 0},
			{"employee": employees["partial_bad"], "base": "1e9999", "variable": 0},
		):
			_run_tool_method(
				"bulk_assign_structure", _tool_payload(company_a, monthly, date), args={"employees": [forged]}
			)
			assert not frappe.db.exists(
				"Salary Structure Assignment", {"employee": employees["partial_bad"], "from_date": date}
			)
			assert events[-1][1]["message"]["failure"] == [employees["partial_bad"]]

		# A submitted payroll consumption blocks a retroactive draft. This is a
		# controlled synthetic boundary: no Salary Slip is created or changed.
		original_exists = frappe.db.exists
		def consumed_exists(doctype, filters=None, *args, **kwargs):
			if doctype == "Salary Slip" and isinstance(filters, dict) and filters.get("employee") == employees["partial_bad"]:
				return "SYNTHETIC-CONSUMED-SLIP"
			return original_exists(doctype, filters, *args, **kwargs)
		monkeypatch.setattr(frappe.db, "exists", consumed_exists)
		frappe.publish_realtime = lambda *args, **kwargs: events.append((args, kwargs))
		_run_tool_method(
			"bulk_assign_structure", _tool_payload(company_a, monthly, date),
			args={"employees": [{"employee": employees["partial_bad"], "base": 1000, "variable": 0}]},
		)
		assert not frappe.db.exists(
			"Salary Structure Assignment", {"employee": employees["partial_bad"], "from_date": date}
		)
		assert events[-1][1]["message"]["failure"] == [employees["partial_bad"]]
		monkeypatch.setattr(frappe.db, "exists", original_exists)

		# Independent approver uses Frappe's native Salary Structure Assignment
		# List View bulk submit API. Maker self-approval remains blocked by the
		# existing SSA before_submit guard, including dual Tradexcel roles.
		frappe.set_user(users["dual_maker_approver"])
		dual_payload = _tool_payload(company_a, monthly, add_days(date, 1))
		_run_tool_method(
			"bulk_assign_structure", dual_payload,
			args={"employees": [{"employee": employees["monthly"], "base": 1900, "variable": 0}]},
		)
		dual_ssa = frappe.get_value(
			"Salary Structure Assignment", {"employee": employees["monthly"], "from_date": add_days(date, 1)}, "name"
		)
		assert dual_ssa
		tracked_ssas.append(dual_ssa)
		with pytest.raises(frappe.ValidationError, match="SSA_MAKER_CHECKER"):
			frappe.get_doc("Salary Structure Assignment", dual_ssa).submit()

		frappe.set_user(users["approver"])
		assert not frappe.has_permission("Salary Structure Assignment", "create")
		draft_names = [
			frappe.get_value("Salary Structure Assignment", {"employee": employees[key], "from_date": date}, "name")
			for key in ("monthly", "daily", "zero_daily", "partial_a", "partial_c", "payroll_maker")
		]
		submit_cancel_or_update_docs("Salary Structure Assignment", draft_names, action="submit")
		for key, structure, expected in (("monthly", monthly, MONTHLY), ("daily", daily, DAILY)):
			ssa_name = frappe.get_value(
				"Salary Structure Assignment", {"employee": employees[key], "from_date": date}, "name"
			)
			ssa = frappe.get_doc("Salary Structure Assignment", ssa_name)
			assert ssa.docstatus == 1
			resolved = resolve_pay_basis(employees[key], date)
			assert resolved["status"] == expected
			assert resolved["salary_structure"] == structure.name
			assert resolved["assignment"] == ssa.name
			assert resolved["base"] == 1750
		zero_result = resolve_pay_basis(employees["zero_daily"], date)
		assert zero_result["status"] == DAILY and zero_result["base"] == 0
		from tradex_hr.tradexcel_hr.pay_basis import resolve_daily_rate
		assert resolve_daily_rate(zero_result)["status"] == "BLOCKED_MISSING_BASE"
		frappe.set_user(users["hr_manager"])
		submitted_preview = _run_tool_method(
			"get_employees", _tool_payload(company_a, monthly, date), args={"advanced_filters": []}
		)
		assert employees["monthly"] not in {
			row.get("name") or row.get("employee") for row in submitted_preview
		}

		# The combined native/custom role follows the native one-step HRMS action;
		# scope/payload checks remain active and the SSA is submitted as before.
		frappe.set_user(users["native_mixed"])
		assert _tool_mode() == "native"
		native_employee = _new_employee(personas, "native-control", company_a, branches_a[0], departments_a[0])
		payload = _tool_payload(company_a, monthly, add_days(date, 3))
		eligible = _run_tool_method("get_employees", payload, args={"advanced_filters": []})
		assert native_employee in {row.get("name") or row.get("employee") for row in eligible}
		_run_tool_method(
			"bulk_assign_structure", payload,
			args={"employees": [{"employee": native_employee, "base": 2000, "variable": 0}]},
		)
		native_ssa = frappe.get_value(
			"Salary Structure Assignment", {"employee": native_employee, "from_date": add_days(date, 3)}, "name"
		)
		assert native_ssa and frappe.db.get_value("Salary Structure Assignment", native_ssa, "docstatus") == 1
		tracked_ssas.append(native_ssa)

		# >30 rows retain native queue dispatch; execution revalidates the current
		# Employee permission population rather than trusting the queued snapshot.
		frappe.set_user(users["payroll_manager"])
		queue_employees = [
			_new_employee(personas, f"queue-{idx}", company_a, branches_a[0], departments_a[0])
			for idx in range(31)
		]
		queued = []
		frappe.enqueue = lambda method, **kwargs: queued.append((method, kwargs))
		queue_rows = [{"employee": name, "base": 1100, "variable": 0} for name in queue_employees]
		_run_tool_method("bulk_assign_structure", _tool_payload(company_a, daily, add_days(date, 4)), args={"employees": queue_rows})
		assert len(queued) == 1
		assert not any(frappe.db.exists("Salary Structure Assignment", {"employee": name}) for name in queue_employees)
		for permission_name in frappe.get_all(
			"User Permission",
			filters={"user": users["payroll_manager"], "allow": "Branch", "for_value": branches_a[0]},
			pluck="name",
		):
			frappe.delete_doc("User Permission", permission_name, force=True, ignore_permissions=True)
		late_permission = frappe.get_doc({
			"doctype": "User Permission", "user": users["payroll_manager"],
			"allow": "Branch", "for_value": branches_a[1], "apply_to_all_doctypes": 1,
		}).insert(ignore_permissions=True)
		personas.permissions.append(late_permission.name)
		frappe.clear_cache(user=users["payroll_manager"])
		with pytest.raises(frappe.PermissionError):
			queued_args = {key: value for key, value in queued[0][1].items() if key != "timeout"}
			queued[0][0](**queued_args)

		# No operation generated attendance, checkin, payroll or adjustment rows.
		for doctype, count in side_effect_counts.items():
			assert frappe.db.count(doctype) == count

	finally:
		frappe.log_error = original_log_error
		frappe.publish_realtime = original_publish
		frappe.enqueue = original_enqueue
		frappe.set_user("Administrator")
		frappe.db.set_single_value("Bulk Salary Structure Assignment", tool_state_before)
		frappe.db.commit()
		frappe.clear_cache(doctype="Bulk Salary Structure Assignment")
		for name in list(dict.fromkeys(tracked_ssas)):
			if not frappe.db.exists("Salary Structure Assignment", name):
				continue
			doc = frappe.get_doc("Salary Structure Assignment", name)
			if doc.docstatus == 1:
				doc.cancel()
			frappe.delete_doc("Salary Structure Assignment", name, force=True, ignore_permissions=True)
		personas.cleanup()
		created_error_logs = set(frappe.get_all("Error Log", pluck="name")) - error_log_before
		# Only test-owned Error Logs may be removed; these were created while the
		# synthetic operation ran and are captured by the per-test marker in their
		# error/message fields.
		for name in created_error_logs:
			message = frappe.db.get_value("Error Log", name, ["error", "method"], as_dict=True)
			if message and token in (message.error or ""):
				frappe.delete_doc("Error Log", name, force=True, ignore_permissions=True)
		frappe.clear_cache()

	assert not any(frappe.db.exists("Salary Structure Assignment", name) for name in tracked_ssas)
	assert not frappe.get_all("Employee", filters={"employee_name": ["like", f"{personas.employee_marker}%"]}, pluck="name")
