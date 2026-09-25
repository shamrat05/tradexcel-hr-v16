from types import SimpleNamespace

import pytest

from tradex_hr.tradexcel_hr import employee_lifecycle as lifecycle


class AttrDict(dict):
	__getattr__ = dict.__getitem__
	__setattr__ = dict.__setitem__


def _stub_db(monkeypatch, get_value):
	monkeypatch.setattr(lifecycle.frappe, "db", SimpleNamespace(get_value=get_value))
	monkeypatch.setattr(lifecycle, "_", lambda message: message)
	monkeypatch.setattr(
		lifecycle.frappe,
		"flags",
		SimpleNamespace(tradex_transfer_cancellation_employee=None),
	)
	monkeypatch.setattr(
		lifecycle.frappe,
		"throw",
		lambda message, exc=None, **kwargs: (_ for _ in ()).throw((exc or Exception)(message)),
	)


def test_cross_company_transfer_requires_native_new_employee_id(monkeypatch):
	_stub_db(monkeypatch, lambda *args, **kwargs: "TCL")

	with pytest.raises(lifecycle.frappe.ValidationError):
		lifecycle.validate_employee_transfer(
			AttrDict(employee="EMP-1", new_company="EFL", create_new_employee_id=0)
		)

	lifecycle.validate_employee_transfer(
		AttrDict(employee="EMP-1", new_company="EFL", create_new_employee_id=1)
	)
	lifecycle.validate_employee_transfer(
		AttrDict(employee="EMP-1", new_company="TCL", create_new_employee_id=0)
	)


def test_promotion_salary_revision_requires_exact_date_submitted_assignment(monkeypatch):
	values = iter([None])
	_stub_db(monkeypatch, lambda *args, **kwargs: next(values))
	doc = AttrDict(employee="EMP-1", promotion_date="2026-09-25", current_ctc=1000, revised_ctc=1200)

	with pytest.raises(lifecycle.frappe.ValidationError):
		lifecycle.validate_employee_promotion(doc)


def test_promotion_salary_revision_requires_current_company_and_explicit_basis(monkeypatch):
	responses = iter(
		[
			SimpleNamespace(name="SSA-1", company="EFL", salary_structure="Daily Wage"),
			"TCL",
			"Daily Wage",
		]
	)
	_stub_db(monkeypatch, lambda *args, **kwargs: next(responses))
	doc = AttrDict(employee="EMP-1", promotion_date="2026-09-25", current_ctc=1000, revised_ctc=1200)

	with pytest.raises(lifecycle.frappe.ValidationError):
		lifecycle.validate_employee_promotion(doc)

	responses = iter(
		[
			SimpleNamespace(name="SSA-1", company="TCL", salary_structure="Daily Wage"),
			"TCL",
			None,
		]
	)
	_stub_db(monkeypatch, lambda *args, **kwargs: next(responses))
	with pytest.raises(lifecycle.frappe.ValidationError):
		lifecycle.validate_employee_promotion(doc)


def test_promotion_salary_revision_accepts_exact_date_assignment_with_explicit_basis(monkeypatch):
	responses = iter(
		[
			SimpleNamespace(name="SSA-1", company="TCL", salary_structure="Daily Wage"),
			"TCL",
			"Daily Wage",
		]
	)

	def get_value(doctype, filters=None, fields=None, **kwargs):
		if doctype == "Salary Structure Assignment":
			assert filters["from_date"] == lifecycle.getdate("2026-09-25")
			assert filters["docstatus"] == 1
		return next(responses)

	_stub_db(monkeypatch, get_value)
	doc = AttrDict(employee="EMP-1", promotion_date="2026-09-25", current_ctc=1000, revised_ctc=1200)

	lifecycle.validate_employee_promotion(doc)


def test_promotion_without_salary_change_does_not_require_assignment(monkeypatch):
	_stub_db(monkeypatch, lambda *args, **kwargs: pytest.fail("No salary assignment lookup expected"))
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
	transfer.employee = "EMP-1"
	transfer.create_new_employee_id = 1
	transfer.on_cancel()
	assert lifecycle.frappe.flags.tradex_transfer_cancellation_employee is None
