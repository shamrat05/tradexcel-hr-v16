from datetime import date
from inspect import signature
from types import SimpleNamespace

import pytest

from tradex_hr.tradexcel_hr import run_payroll


def _row(employee, *, assignment=None, base=0, from_date="2026-01-01"):
    return {
        "employee_name": employee,
        "employee_full_name": employee,
        "company": "Tradexcel Ceramics Ltd.",
        "department": "Operations",
        "branch": "Tradexcel Factory",
        "employment_type": "Worker",
        "employee_number": employee,
        "tradex_source_employee_id": None,
        "date_of_joining": date(2025, 1, 1),
        "assignment_name": assignment,
        "salary_structure": "TCL Daily Wage" if assignment else None,
        "base": base,
        "from_date": from_date if assignment else None,
    }


def test_preflight_blocks_missing_assignment_and_zero_base():
    result = run_payroll.preflight_payroll_assignments(
        [_row("EMP-MISSING"), _row("EMP-ZERO", assignment="SSA-ZERO")],
        "2026-09-01",
        "2026-09-30",
    )
    by_employee = {item["employee"]: item for item in result}

    assert by_employee["EMP-MISSING"]["status"] == "BLOCKED_MISSING_ASSIGNMENT"
    assert by_employee["EMP-ZERO"]["status"] == "BLOCKED_MISSING_BASE"


def test_preflight_blocks_overlapping_assignments_without_guessing():
    result = run_payroll.preflight_payroll_assignments(
        [
            _row("EMP-OVERLAP", assignment="SSA-OLD", base=1000),
            _row("EMP-OVERLAP", assignment="SSA-NEW", base=1200),
        ],
        "2026-09-01",
        "2026-09-30",
    )

    assert result[0]["status"] == "BLOCKED_ASSIGNMENT_OVERLAP"
    assert "SSA-OLD" in result[0]["reason"]
    assert "SSA-NEW" in result[0]["reason"]


def test_preflight_blocks_mid_period_assignment_boundary():
    result = run_payroll.preflight_payroll_assignments(
        [_row("EMP-MID", assignment="SSA-MID", base=1200, from_date="2026-09-15")],
        "2026-09-01",
        "2026-09-30",
    )

    assert result[0]["status"] == "BLOCKED_MID_PERIOD_CHANGE"


def test_payroll_runner_has_no_legacy_manual_or_external_salary_inputs():
    params = signature(run_payroll.run_payroll_for_month).parameters
    assert "allow_manual_staff_payroll" not in params
    assert "source_compensation_file" not in params


def test_payroll_runner_refuses_implicit_site_selection(monkeypatch):
    monkeypatch.setattr(run_payroll, "frappe", SimpleNamespace(local=SimpleNamespace(site=None)))

    with pytest.raises(ValueError, match="explicit site and sites_path"):
        run_payroll.run_payroll_for_month(2026, 9)


def test_run_payroll_orchestration_is_fail_closed_and_preserves_prior_work(monkeypatch):
    rows = [
        _row("EMP-EXIST-DRAFT", assignment="SSA-DRAFT", base=1000),
        _row("EMP-EXIST-SUBMITTED", assignment="SSA-SUBMITTED", base=1000),
        _row("EMP-MISSING-BASE", assignment="SSA-ZERO", base=0),
        _row("EMP-OK", assignment="SSA-OK", base=1000),
        _row("EMP-FAIL", assignment="SSA-FAIL", base=1000),
    ]

    committed = []
    rolled_back = []
    created = []

    class DB:
        def sql(self, *_args, **_kwargs):
            return rows

        def get_value(self, _doctype, filters, *_args, **_kwargs):
            existing = {
                "EMP-EXIST-DRAFT": SimpleNamespace(name="SLIP-DRAFT", docstatus=0),
                "EMP-EXIST-SUBMITTED": SimpleNamespace(name="SLIP-SUBMITTED", docstatus=1),
            }
            return existing.get(filters["employee"])

        def savepoint(self, name):
            return name

        def commit(self):
            committed.append(True)

        def rollback(self, **kwargs):
            rolled_back.append(kwargs)

    fake_frappe = SimpleNamespace(local=SimpleNamespace(site="hrms-v16.localhost"), db=DB())
    monkeypatch.setattr(run_payroll, "frappe", fake_frappe)
    monkeypatch.setattr(run_payroll, "structure_earnings", lambda _structure, base: [
        {"salary_component": "Basic", "abbr": "B", "amount": base}
    ])
    monkeypatch.setattr(run_payroll, "employee_joins_after_period", lambda *_args: False)
    monkeypatch.setattr(run_payroll, "_load_source_salary", lambda *_args: pytest.fail("audit JSON used for payroll"))
    monkeypatch.setattr(run_payroll, "_create_manual_slip", lambda data: (
        (_ for _ in ()).throw(RuntimeError("synthetic row failure"))
        if data["employee"] == "EMP-FAIL"
        else (created.append(data["employee"]) or SimpleNamespace(gross_pay=data["gross_pay"]))
    ))

    component_exceptions = __import__(
        "tradex_hr.tradexcel_hr.component_exceptions", fromlist=["load_component_rules"]
    )
    payroll_policy = __import__(
        "tradex_hr.tradexcel_hr.payroll_policy", fromlist=["resolve_policy"]
    )
    monkeypatch.setattr(component_exceptions, "load_component_rules", lambda _company: [])
    monkeypatch.setattr(component_exceptions, "apply_component_rules", lambda earnings, *_args: earnings)
    monkeypatch.setattr(payroll_policy, "resolve_policy", lambda *_args: SimpleNamespace(pay_basis="Monthly"))

    result = run_payroll.run_payroll_for_month(2026, 9, site="hrms-v16.localhost", sites_path="/unused")

    assert result is False
    assert created == ["EMP-OK"]
    assert len(committed) == 1
    assert rolled_back == [{"save_point": "payroll_row"}]
