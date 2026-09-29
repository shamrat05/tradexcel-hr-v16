from datetime import date
from inspect import signature
from types import SimpleNamespace

import pytest

from tradex_hr.tradexcel_hr import run_payroll


def _row(
    employee,
    *,
    assignment=None,
    base=0,
    from_date="2026-01-01",
    joining_date=date(2025, 1, 1),
    relieving_date=None,
    status="Active",
):
    return {
        "employee_name": employee,
        "employee_full_name": employee,
        "company": "Tradexcel Ceramics Ltd.",
        "department": "Operations",
        "branch": "Tradexcel Factory",
        "employment_type": "Worker",
        "employee_number": employee,
        "tradex_source_employee_id": None,
        "date_of_joining": joining_date,
        "relieving_date": relieving_date,
        "status": status,
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


def test_preflight_uses_latest_historical_assignment_at_period_start():
    result = run_payroll.preflight_payroll_assignments(
        [
            _row("EMP-HISTORY", assignment="SSA-JAN", base=20000, from_date="2026-01-01"),
            _row("EMP-HISTORY", assignment="SSA-JUN", base=25000, from_date="2026-06-01"),
        ],
        "2026-09-01",
        "2026-09-30",
    )

    assert result[0]["status"] == "READY"
    assert result[0]["assignment"]["assignment_name"] == "SSA-JUN"


def test_preflight_reports_employment_boundaries_and_unsupported_status():
    result = run_payroll.preflight_payroll_assignments(
        [
            _row("EMP-LEFT", assignment="SSA-LEFT", base=1000, relieving_date=date(2026, 9, 20), status="Left"),
            _row("EMP-JOINED", assignment="SSA-JOINED", base=1000, joining_date=date(2026, 9, 10)),
            _row("EMP-SUSPENDED", assignment="SSA-SUSPENDED", base=1000, status="Suspended"),
        ],
        "2026-09-01",
        "2026-09-30",
    )
    by_employee = {item["employee"]: item for item in result}

    assert by_employee["EMP-LEFT"]["status"] == "BLOCKED_RELIEVE_MID_PERIOD"
    assert by_employee["EMP-JOINED"]["status"] == "BLOCKED_JOIN_MID_PERIOD"
    assert by_employee["EMP-SUSPENDED"]["status"] == "BLOCKED_EMPLOYMENT_STATUS"


def test_payroll_runner_has_no_legacy_manual_or_external_salary_inputs():
    params = signature(run_payroll.run_payroll_for_month).parameters
    assert "allow_manual_staff_payroll" not in params
    assert "source_compensation_file" not in params


def test_legacy_manual_runner_is_disabled_without_site_context(monkeypatch):
    monkeypatch.setattr(run_payroll, "frappe", SimpleNamespace(local=SimpleNamespace(site=None)))

    with pytest.raises(RuntimeError, match="Tradexcel Payroll Readiness"):
        run_payroll.run_payroll_for_month(2026, 9, "Tradexcel Ceramics Ltd.")


def test_legacy_manual_payroll_runner_is_disabled_even_with_site_context(monkeypatch):
    monkeypatch.setattr(run_payroll, "frappe", SimpleNamespace(local=SimpleNamespace(site="hrms-v16.localhost")))

    with pytest.raises(RuntimeError, match="native Payroll Entry workflow"):
        run_payroll.run_payroll_for_month(
            2026, 9, "Tradexcel Ceramics Ltd.", site="hrms-v16.localhost", sites_path="/unused"
        )


def test_payroll_runner_requires_company(monkeypatch):
    params = signature(run_payroll.run_payroll_for_month).parameters
    assert params["company"].default is signature(run_payroll.run_payroll_for_month).empty


def test_cli_requires_explicit_period_company_and_site(monkeypatch):
    for name in ("TRADEX_PAYROLL_COMPANY", "FRAPPE_SITE", "FRAPPE_SITES_PATH"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(SystemExit) as error:
        run_payroll.main([])
    assert error.value.code == 2


def test_cli_reports_legacy_runner_shutdown_with_managed_recovery_path(capsys):
    with pytest.raises(SystemExit) as error:
        run_payroll.main([
            "--year", "2026",
            "--month", "9",
            "--company", "Tradexcel Ceramics Ltd.",
            "--site", "hrms-v16.localhost",
            "--sites-path", "/home/sanchita/frappe-bench-v16/sites",
        ])

    assert error.value.code == 2
    assert "Tradexcel Payroll Readiness" in capsys.readouterr().err


def test_cli_passes_explicit_payroll_target(monkeypatch):
    calls = []
    monkeypatch.setattr(
        run_payroll,
        "run_payroll_for_month",
        lambda *args, **kwargs: calls.append((args, kwargs)) or False,
    )

    assert run_payroll.main([
        "--year", "2026",
        "--month", "9",
        "--company", "Elegance Footwear Ltd.",
        "--site", "hrms-v16.localhost",
        "--sites-path", "/home/sanchita/frappe-bench-v16/sites",
    ]) == 1
    assert calls == [(
        (2026, 9),
        {
            "company": "Elegance Footwear Ltd.",
            "site": "hrms-v16.localhost",
            "sites_path": "/home/sanchita/frappe-bench-v16/sites",
        },
    )]
