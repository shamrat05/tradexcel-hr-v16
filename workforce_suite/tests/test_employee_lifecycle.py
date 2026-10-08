from types import SimpleNamespace

import pytest

from workforce_suite.workforce_suite import employee_lifecycle as lifecycle


class AttrDict(dict):
	__getattr__ = dict.__getitem__
	__setattr__ = dict.__setitem__


def _stub_db(monkeypatch, get_value, *, exists=None, get_all=None):
	monkeypatch.setattr(
		lifecycle.frappe,
		"db",
		SimpleNamespace(
			get_value=get_value,
			exists=exists or (lambda *args, **kwargs: False),
			get_all=get_all or (lambda *args, **kwargs: []),
		),
	)
	monkeypatch.setattr(lifecycle, "_", lambda message: message)
	monkeypatch.setattr(lifecycle.frappe, "session", SimpleNamespace(user="Administrator"), raising=False)
	monkeypatch.setattr(lifecycle.frappe, "has_permission", lambda *args, **kwargs: True)
	monkeypatch.setattr(lifecycle.frappe, "get_roles", lambda *args, **kwargs: ["Workforce Payroll Approver"])
	monkeypatch.setattr(
		lifecycle.frappe,
		"flags",
		SimpleNamespace(workforce_transfer_cancellation_employee=None),
	)
	monkeypatch.setattr(
		lifecycle.frappe,
		"throw",
		lambda message, exc=None, **kwargs: (_ for _ in ()).throw((exc or Exception)(message)),
	)


def test_cross_company_transfer_requires_native_new_employee_id(monkeypatch):
	_stub_db(monkeypatch, lambda *args, **kwargs: SimpleNamespace(company="COMPANY_A", name="EMP-1"))

	with pytest.raises(lifecycle.frappe.ValidationError):
		lifecycle.validate_employee_transfer(
			AttrDict(employee="EMP-1", new_company="COMPANY_B", create_new_employee_id=0)
		)

	lifecycle.validate_employee_transfer(
		AttrDict(employee="EMP-1", new_company="COMPANY_B", create_new_employee_id=1)
	)
	lifecycle.validate_employee_transfer(
		AttrDict(employee="EMP-1", new_company="COMPANY_A", create_new_employee_id=0)
	)


def test_promotion_salary_revision_requires_exact_date_submitted_assignment(monkeypatch):
	def get_value(doctype, *args, **kwargs):
		if doctype == "Employee":
			return SimpleNamespace(company="COMPANY_A", ctc=1000, name="EMP-1")
		return None
	_stub_db(monkeypatch, get_value)
	doc = AttrDict(employee="EMP-1", promotion_date="2026-09-25", current_ctc=1000, revised_ctc=1200)

	with pytest.raises(lifecycle.frappe.ValidationError):
		lifecycle.validate_employee_promotion(doc)


def test_promotion_salary_revision_requires_current_company_and_explicit_basis(monkeypatch):
	responses = iter(
		[
			SimpleNamespace(company="COMPANY_A", ctc=1000, name="EMP-1"),
			SimpleNamespace(name="SSA-1", company="COMPANY_B", salary_structure="Daily Wage"),
			"Daily Wage",
		]
	)
	_stub_db(monkeypatch, lambda *args, **kwargs: next(responses))
	doc = AttrDict(employee="EMP-1", promotion_date="2026-09-25", current_ctc=1000, revised_ctc=1200)

	with pytest.raises(lifecycle.frappe.ValidationError):
		lifecycle.validate_employee_promotion(doc)

	responses = iter(
		[
			SimpleNamespace(company="COMPANY_A", ctc=1000, name="EMP-1"),
			SimpleNamespace(name="SSA-1", company="COMPANY_A", salary_structure="Daily Wage"),
			None,
		]
	)
	_stub_db(monkeypatch, lambda *args, **kwargs: next(responses))
	with pytest.raises(lifecycle.frappe.ValidationError):
		lifecycle.validate_employee_promotion(doc)


def test_promotion_salary_revision_accepts_exact_date_assignment_with_explicit_basis(monkeypatch):
	responses = iter(
		[
			"Daily Wage",
		]
	)

	def get_value(doctype, filters=None, fields=None, **kwargs):
		if doctype == "Employee":
			return SimpleNamespace(company="COMPANY_A", ctc=1000, name="EMP-1")
		if doctype == "Salary Structure Assignment":
			assert filters["from_date"] == lifecycle.getdate("2026-09-25")
			assert filters["docstatus"] == 1
			return SimpleNamespace(name="SSA-1", company="COMPANY_A", salary_structure="Daily Wage")
		return next(responses)

	_stub_db(monkeypatch, get_value)
	doc = AttrDict(employee="EMP-1", promotion_date="2026-09-25", current_ctc=1000, revised_ctc=1200)

	lifecycle.validate_employee_promotion(doc)


def test_promotion_without_salary_change_does_not_require_assignment(monkeypatch):
	_stub_db(
		monkeypatch,
		lambda doctype, *args, **kwargs: SimpleNamespace(company="COMPANY_A", ctc=1000, name="EMP-1")
		if doctype == "Employee"
		else pytest.fail("No salary assignment lookup expected"),
	)
	doc = AttrDict(employee="EMP-1", promotion_date="2026-09-25", current_ctc=1000, revised_ctc=1000)

	lifecycle.validate_employee_promotion(doc)


def test_rehire_must_preserve_completed_employment_spell(monkeypatch):
	previous = SimpleNamespace(date_of_joining="2020-01-01", relieving_date="2026-09-01", status="Left")
	_stub_db(monkeypatch, lambda *args, **kwargs: previous)
	doc = AttrDict(
		name="EMP-1",
		date_of_joining="2020-01-01",
		relieving_date=None,
		status="Active",
		is_new=lambda: False,
	)

	with pytest.raises(lifecycle.frappe.ValidationError):
		lifecycle.validate_employee_employment_spell(doc)

	doc.relieving_date = "2026-09-01"
	doc.status = "Left"
	lifecycle.validate_employee_employment_spell(doc)

	# Administrative identity metadata may still be maintained after exit.
	doc.user_id = "employee@example.test"
	lifecycle.validate_employee_employment_spell(doc)


def test_preexisting_relieving_date_allows_exit_metadata_until_native_left_status(monkeypatch):
	previous = SimpleNamespace(date_of_joining="2020-01-01", relieving_date="2026-09-01", status="Active")
	_stub_db(monkeypatch, lambda *args, **kwargs: previous)
	doc = AttrDict(
		name="EMP-1",
		date_of_joining="2020-01-01",
		relieving_date="2026-09-01",
		status="Active",
		user_id="employee@example.test",
		is_new=lambda: False,
	)
	lifecycle.validate_employee_employment_spell(doc)


def test_native_transfer_cancellation_restores_only_its_own_employment_spell(monkeypatch):
	previous = SimpleNamespace(date_of_joining="2020-01-01", relieving_date="2026-09-01", status="Left")
	_stub_db(monkeypatch, lambda *args, **kwargs: previous)

	class NativeEmployeeTransfer:
		def get(self, key, default=None):
			return getattr(self, key, default)

		def on_cancel(self):
			employee = AttrDict(
				name="EMP-1",
				date_of_joining="2020-01-01",
				relieving_date=None,
				status="Active",
				is_new=lambda: False,
			)
			lifecycle.validate_employee_employment_spell(employee)

	class EmployeeTransfer(lifecycle.EmployeeTransferLifecycleMixin, NativeEmployeeTransfer):
		pass

	transfer = EmployeeTransfer()
	transfer.doctype = "Employee Transfer"
	transfer.employee = "EMP-1"
	transfer.create_new_employee_id = 1
	transfer.on_cancel()
	assert lifecycle.frappe.flags.workforce_transfer_cancellation_employee is None


def test_existing_employee_movement_field_requires_native_lifecycle_context(monkeypatch):
	previous = AttrDict(company="COMPANY_A", branch="Old Branch", department="Old Department", designation="Old Role", grade=None, employment_type=None, ctc=1000)
	_stub_db(monkeypatch, lambda *args, **kwargs: previous)
	doc = AttrDict(
		name="EMP-1",
		company="COMPANY_A",
		branch="New Branch",
		department="Old Department",
		designation="Old Role",
		grade=None,
		employment_type=None,
		ctc=1000,
		internal_work_history=[],
		is_new=lambda: False,
	)
	with pytest.raises(lifecycle.frappe.ValidationError, match="must be changed through native Employee Transfer"):
		lifecycle.validate_employee_lifecycle_fields(doc)

	lifecycle.frappe.flags.workforce_employee_lifecycle_context = {
		"employee": "EMP-1",
		"fields": {"branch"},
		"history": False,
	}
	lifecycle.validate_employee_lifecycle_fields(doc)


def test_consumed_salary_slip_blocks_lifecycle_cancellation(monkeypatch):
	_stub_db(
		monkeypatch,
		lambda *args, **kwargs: None,
		exists=lambda doctype, filters=None: doctype in {"Salary Slip", "DocType"},
	)
	monkeypatch.setattr(lifecycle.frappe, "get_all", lambda *args, **kwargs: [])
	doc = AttrDict(
		doctype="Employee Transfer",
		name="TRANSFER-1",
		employee="EMP-1",
		new_employee_id=None,
		transfer_date="2026-09-25",
	)
	with pytest.raises(lifecycle.frappe.ValidationError, match="LIFECYCLE_CHANGE_ALREADY_CONSUMED"):
		lifecycle._assert_lifecycle_change_unconsumed(doc)


@pytest.mark.parametrize(
	("doctype", "date_field"),
	[
		(doctype, date_field)
		for doctype, date_fields in lifecycle.EMPLOYEE_REVIEW_SNAPSHOTS.items()
		for date_field in date_fields
	],
)
def test_effective_review_snapshot_blocks_movement_cancellation(monkeypatch, doctype, date_field):
	"""Exercise installed review-boundary mechanics without inventing legal data."""
	def exists(candidate, filters=None):
		if candidate == "DocType":
			return True
		return candidate == doctype and filters.get(date_field) == [">=", lifecycle.getdate("2026-09-01")]

	_stub_db(monkeypatch, lambda *args, **kwargs: None, exists=exists)
	monkeypatch.setattr(
		lifecycle.frappe,
		"get_meta",
		lambda candidate: SimpleNamespace(has_field=lambda field: field in {"employee", "docstatus", date_field}),
	)
	monkeypatch.setattr(lifecycle.frappe, "get_all", lambda *args, **kwargs: [])
	doc = AttrDict(
		doctype="Employee Transfer",
		name="TRANSFER-1",
		employee="EMP-1",
		new_employee_id=None,
		transfer_date="2026-09-01",
		creation="2026-08-01 00:00:00",
	)
	with pytest.raises(lifecycle.frappe.ValidationError, match="LIFECYCLE_CHANGE_ALREADY_CONSUMED"):
		lifecycle._assert_lifecycle_change_unconsumed(doc)


@pytest.mark.parametrize("consumed_doctype", ["Salary Slip", "later Salary Structure Assignment"])
def test_consumed_ssa_cannot_be_cancelled(monkeypatch, consumed_doctype):
	def exists(doctype, filters=None):
		if doctype == "DocType":
			return True
		if consumed_doctype == "Salary Slip":
			return doctype == "Salary Slip"
		return doctype == "Salary Structure Assignment" and filters.get("from_date") == [">", lifecycle.getdate("2026-09-01")]

	_stub_db(monkeypatch, lambda *args, **kwargs: None, exists=exists)
	doc = AttrDict(employee="EMP-1", from_date="2026-09-01", name="SSA-1")
	with pytest.raises(lifecycle.frappe.ValidationError, match="LIFECYCLE_CHANGE_ALREADY_CONSUMED"):
		lifecycle.validate_salary_structure_assignment_before_cancel(doc)
