from datetime import date
import os

import frappe
import pytest

from tradex_hr import install
from tradex_hr.tradexcel_hr.report.tradexcel_payroll_readiness import tradexcel_payroll_readiness as report


@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(
        site=os.environ.get("FRAPPE_TEST_SITE", "hrms-v16.localhost"),
        sites_path=os.environ.get("FRAPPE_TEST_SITES_PATH", "/home/sanchita/frappe-bench-v16/sites"),
        force=True,
    )
    frappe.connect()
    yield
    frappe.destroy()


def test_report_contains_each_readiness_employee_once(monkeypatch):
    outcomes = [
        {"employee": "EMP-1", "employee_data": {"employee_name": "One"}, "status": "READY",
         "pay_basis": {"status": "Monthly Salary"}, "findings": []},
        {"employee": "EMP-2", "employee_data": {"employee_name": "Two"}, "status": "ATTENDANCE_UNMARKED",
         "pay_basis": {"status": "Daily Wage"},
         "findings": [{"code": "ATTENDANCE_UNMARKED", "reason": "Native Payroll Entry found 6 unmarked day(s)."}]},
        {"employee": "EMP-3", "employee_data": {"employee_name": "Three"}, "status": "BLOCKED_PAY_BASIS",
         "pay_basis": {"status": "UNRESOLVED", "reason": "No submitted Salary Structure Assignment applies on 2026-09-01"},
         "findings": [{"code": "BLOCKED_PAY_BASIS", "reason": "No submitted Salary Structure Assignment applies on 2026-09-01"}]},
    ]
    monkeypatch.setattr(report, "_report_period", lambda *_args: (
        "Company A", date(2026, 9, 1), date(2026, 9, 30)
    ))
    monkeypatch.setattr(report, "inspect_native_payroll_readiness", lambda *_args: {
        "employee_count": 3, "ready_count": 1, "blocked_count": 2, "outcomes": outcomes,
    })
    monkeypatch.setattr(report, "_existing_payroll_entry", lambda *_args: [])

    columns, rows, message, _chart, summary = report.execute({"company": "Company A"})

    assert len(rows) == 3
    assert {row["employee"] for row in rows} == {"EMP-1", "EMP-2", "EMP-3"}
    assert len({row["employee"] for row in rows}) == len(rows)
    assert rows[1]["problem"] == "6 attendance day(s) need review"
    assert rows[1]["action_kinds"] == "attendance|attendance_requests"
    assert "No salary assignment applies" in rows[2]["problem"]
    assert rows[2]["action_kinds"] == "salary_assignments"
    assert summary[1]["value"] == 1
    assert summary[2]["value"] == 2
    assert message == "September 2026 Payroll"


def test_unsafe_daily_wage_structure_offers_migration_review(monkeypatch):
    monkeypatch.setattr(report, "_report_period", lambda *_args: (
        "Company A", date(2026, 9, 1), date(2026, 9, 30)
    ))
    monkeypatch.setattr(report, "inspect_native_payroll_readiness", lambda *_args: {
        "employee_count": 1, "ready_count": 0, "blocked_count": 1,
        "outcomes": [{
            "employee": "EMP-1",
            "employee_data": {"employee_name": "One"},
            "status": "ATTENDANCE_UNMARKED",
            "pay_basis": {"status": "Daily Wage"},
            "findings": [
                {"code": "ATTENDANCE_UNMARKED", "reason": "Native Payroll Entry found 2 unmarked day(s)."},
                {"code": "BLOCKED_UNSAFE_STRUCTURE", "reason": "Legacy structure is unsafe."},
            ],
        }],
    })

    monkeypatch.setattr(report, "_existing_payroll_entry", lambda *_args: [])
    _columns, rows, _message, _chart, summary = report.execute({"company": "Company A"})

    assert rows[0]["problem"].startswith("2 attendance day(s) need review")
    assert "(+ 1 more issue)" in rows[0]["problem"]
    assert "migration" in rows[0]["action_kinds"]
    assert summary[1]["value"] == 0


def test_prepare_endpoint_uses_server_result_and_has_no_client_ready_argument(monkeypatch):
    called = {}
    monkeypatch.setattr(report, "_require_payroll_manager", lambda _company: None)
    monkeypatch.setattr(report, "_report_period", lambda _filters: (
        "Company A", date(2026, 9, 1), date(2026, 9, 30)
    ))
    monkeypatch.setattr(report, "prepare_native_payroll", lambda company, start, end: (
        called.update(company=company, start=start, end=end)
        or {"status": "BLOCKED", "ready_count": 0, "blocked_count": 1, "blockers": []}
    ))

    result = report.prepare_payroll("Company A", "2026-09-01")

    assert result["status"] == "BLOCKED"
    assert called == {
        "company": "Company A",
        "start": date(2026, 9, 1),
        "end": date(2026, 9, 30),
    }


def test_structure_migration_preview_requires_an_explicit_effective_date(monkeypatch):
    monkeypatch.setattr(report, "_require_payroll_manager", lambda _company: None)
    monkeypatch.setattr(report, "_report_period", lambda _filters: (
        "Company A", date(2026, 9, 1), date(2026, 9, 30)
    ))
    monkeypatch.setattr(report, "_employees_for_period", lambda *_args: [
        {"name": "EMP-1", "employee_name": "One"}
    ])
    monkeypatch.setattr(report, "resolve_pay_basis", lambda *_args: {
        "status": report.DAILY, "assignment": "SSA-1",
        "salary_structure": "Legacy Daily", "base": 350,
    })
    monkeypatch.setattr(report, "inspect_attendance_integrity", lambda *_args: {
        "blockers": [{"employee": "EMP-1", "reason": "3 attendance days need review."}]
    })
    monkeypatch.setattr(report, "inspect_daily_wage_structure", lambda *_args: {
        "status": "BLOCKED_UNSAFE_STRUCTURE", "reason": "Legacy structure is unsafe."
    })
    monkeypatch.setattr(report.frappe, "get_all", lambda *_args, **_kwargs: pytest.fail(
        "No future assignment conflict query is needed without a requested effective date"
    ))

    before_structures = frappe.db.count("Salary Structure")
    before_assignments = frappe.db.count("Salary Structure Assignment")
    result = report.get_daily_wage_migration_preview("Company A", "2026-09-01")

    assert frappe.db.count("Salary Structure") == before_structures
    assert frappe.db.count("Salary Structure Assignment") == before_assignments
    assert result["status"] == "DECISION_REQUIRED"
    assert result["effective_date"] is None
    assert result["rows"][0]["current_assignment"] == "SSA-1"
    assert "3 attendance days need review" in result["rows"][0]["conflicts"]
    assert result["proposed_structure"]["components"] == [
        {"component": "Daily Wage", "amount": 0, "depends_on_payment_days": 0},
        {"component": "Overtime Pay", "amount": 0, "depends_on_payment_days": 0},
    ]


def test_workspace_primary_shortcut_routes_to_readiness_and_keeps_native_entries():
    shortcuts = {label: (target, kind) for label, target, kind in install.WORKSPACE_SHORTCUTS}
    assert shortcuts["Run Monthly Payroll"] == ("Tradexcel Payroll Readiness", "Report")
    assert shortcuts["Payroll Entries (Advanced)"] == ("Payroll Entry", "DocType")


def test_report_exposes_native_queue_and_failure_state(monkeypatch):
    monkeypatch.setattr(report, "_report_period", lambda *_args: (
        "Company A", date(2026, 9, 1), date(2026, 9, 30)
    ))
    monkeypatch.setattr(report, "inspect_native_payroll_readiness", lambda *_args: {
        "employee_count": 1, "ready_count": 1, "blocked_count": 0,
        "outcomes": [{
            "employee": "EMP-1", "employee_data": {"employee_name": "One"},
            "status": "READY", "pay_basis": {"status": "Monthly Salary"}, "findings": [],
        }],
    })
    monkeypatch.setattr(report, "_existing_payroll_entry", lambda *_args: [{
        "name": "PAY-1", "docstatus": 1, "status": "Failed", "salary_slips_created": 0,
        "custom_tradex_run_key": report._managed_run_key("Company A", date(2026, 9, 1), date(2026, 9, 30)),
    }])

    _columns, _rows, message, _chart, summary = report.execute({"company": "Company A"})

    assert summary[3]["value"] == "Failed"
    assert summary[4]["value"] == "PAY-1"
    assert "native retry" in message


def test_financial_blockers_route_to_native_fix_records():
    assert report._financial_action_kinds([
        {"code": "TAX_SLAB_MISSING"},
        {"code": "COMPONENT_ACCOUNT_MISSING"},
        {"code": "NEGATIVE_NET_PAY"},
    ]) == "tax_slabs|salary_components|salary_slip"
    assert report._financial_action_kinds([{"code": "TAX_PERIOD_MISSING"}]) == "payroll_periods"
    assert report._financial_action_kinds([{"code": "TAX_ASSIGNMENT_MISSING"}]) == "salary_assignments"
    assert report._financial_action_kinds([
        {"code": "TAX_EXCEPTION_REVIEW_REQUIRED"},
    ]) == "policy_exceptions"
    assert report._financial_action_kinds([
        {"code": "PAYROLL_PAYABLE_INVALID"},
        {"code": "ACCOUNTING_DIMENSION_MISSING", "reference": "Cost Center"},
        {"code": "ACCOUNTING_DIMENSION_MISSING", "reference": "project"},
    ]) == "payroll_payable|cost_centers|accounting_dimensions"


def test_financial_report_shows_component_override_source_and_fix_action(monkeypatch):
    from tradex_hr.tradexcel_hr import financial_readiness

    start, end = date(2026, 9, 1), date(2026, 9, 30)
    monkeypatch.setattr(report, "_report_period", lambda *_args: ("Company A", start, end))
    monkeypatch.setattr(report, "_assert_employee_scope", lambda *_args: None)
    monkeypatch.setattr(report, "inspect_native_payroll_readiness", lambda *_args: {
        "employee_count": 1, "ready_count": 1, "blocked_count": 0,
        "outcomes": [{"employee": "EMP-1", "employee_data": {"employee_name": "One"},
                      "status": "READY", "pay_basis": {"status": "Monthly Salary"}, "findings": []}],
    })
    run_key = report._managed_run_key("Company A", start, end)
    monkeypatch.setattr(report, "_existing_payroll_entry", lambda *_args: [{
        "name": "PE-1", "docstatus": 1, "status": "Submitted", "salary_slips_created": 1,
        report.MANAGED_RUN_FIELD: run_key,
    }])
    monkeypatch.setattr(financial_readiness, "inspect_payroll_financial_readiness", lambda *_args: {
        "status": "BLOCKED",
        "blockers": [{"code": "COMPONENT_ACCOUNT_MISSING", "employee": "EMP-1",
                       "reference": "Housing", "reason": "Housing has no company account mapping."}],
        "warnings": [], "salary_slip_count": 1,
        "totals": {key: 0 for key in ("gross", "deductions", "net", "daily_wage", "overtime", "income_tax")},
        "slips": [{"employee": "EMP-1", "salary_slip": "SS-1", "status": "BLOCKED",
                    "gross": 1000, "deductions": 100, "net": 900, "income_tax": 0,
                    "component_exceptions": [{"component": "Housing", "action": "Override Amount",
                                              "source": "TPE-12", "amount": 250}]}],
    })

    _columns, rows, _message, _chart, _summary = report.execute({"company": "Company A"})

    assert rows[0]["component_adjustments"] == "Housing: Override Amount (TPE-12) = 250.00"
    assert rows[0]["financial_status"] == "BLOCKED"
    assert rows[0]["financial_result"] == "Gross 1000 · deductions 100 · net 900 · tax 0"
    assert rows[0]["financial_action_kinds"] == "salary_components"
    assert rows[0]["financial_salary_slip"] == "SS-1"
    assert rows[0]["financial_component"] == "Housing"


def test_effective_dated_migration_preview_reports_assignment_conflicts(monkeypatch):
    monkeypatch.setattr(report, "_require_payroll_manager", lambda _company: None)
    monkeypatch.setattr(report, "_report_period", lambda _filters: (
        "Company A", date(2026, 9, 1), date(2026, 9, 30)
    ))
    monkeypatch.setattr(report, "_employees_for_period", lambda *_args: [
        {"name": "EMP-1", "employee_name": "One"},
        {"name": "EMP-2", "employee_name": "Two"},
    ])
    monkeypatch.setattr(report, "resolve_pay_basis", lambda employee, *_args: {
        "status": report.DAILY, "assignment": "SSA-" + employee,
        "salary_structure": "Legacy Daily", "base": 350,
    })
    monkeypatch.setattr(report, "inspect_attendance_integrity", lambda *_args: {"blockers": []})
    monkeypatch.setattr(report, "inspect_daily_wage_structure", lambda *_args: {"status": "READY"})
    monkeypatch.setattr(report.frappe, "get_all", lambda *_args, **_kwargs: [
        {"employee": "EMP-1", "name": "SSA-SAME", "salary_structure": "Legacy Daily", "from_date": date(2026, 10, 1)},
        {"employee": "EMP-2", "name": "SSA-LATER", "salary_structure": "Monthly", "from_date": date(2026, 11, 1)},
    ])

    result = report.get_daily_wage_migration_preview(
        "Company A", "2026-09-01", effective_date="2026-10-01"
    )

    assert result["status"] == "PREVIEW"
    assert result["effective_date"] == date(2026, 10, 1)
    assert "already starts on the proposed effective date" in result["rows"][0]["conflicts"]
    assert "may supersede" in result["rows"][1]["conflicts"]
