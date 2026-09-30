"""TXUX-260930-007: payroll/finance recovery UI and privacy contracts.

Offline Node projection of the candidate client scripts, server-resolution
guards and negative financial-privacy checks. No payroll is created or
submitted and no real employee data is mutated.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import frappe
import pytest

from tradex_hr.tests.persona_uat import PERSONA_ROLES, SyntheticPersonaHarness
from tradex_hr.tradexcel_hr.report.tradexcel_payroll_readiness import tradexcel_payroll_readiness as readiness

ROOT = Path(__file__).resolve().parents[1]
COMPANY = "Tradexcel Ceramics Ltd."
READINESS = "Tradexcel Payroll Readiness"


@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(
        site=os.environ.get("FRAPPE_TEST_SITE", "hrms-v16.localhost"),
        sites_path=os.environ.get("FRAPPE_TEST_SITES_PATH", "/home/sanchita/frappe-bench-v16/sites"),
        force=True,
    )
    frappe.connect()
    frappe.set_user("Administrator")
    yield
    frappe.set_user("Administrator")
    frappe.destroy()


def test_offline_payroll_recovery_ui_contracts():
    node = shutil.which("node") or "/home/sanchita/.nvm/versions/node/v24.15.0/bin/node"
    subprocess.run([node, str(ROOT / "tests/js/payroll_recovery.cjs")], check=True, capture_output=True, text=True)


def test_readiness_js_never_calculates_money_or_claims_ready():
    source = (ROOT / "tradexcel_hr/report/tradexcel_payroll_readiness/tradexcel_payroll_readiness.js").read_text()
    for forbidden in ("parseFloat", "parseInt", "toFixed(", "net_pay", "gross_pay", "ready:"):
        assert forbidden not in source, f"client must not compute or claim: {forbidden}"
    # Only the readiness preparation and the read-only migration preview are called.
    assert source.count("frappe.call(") == 2
    assert "prepare_payroll" in source and "get_daily_wage_migration_preview" in source
    # Every next step is an existing native record.
    for target in ('"Payroll Entry"', '"Income Tax Slab"', '"Salary Slip"', '"Tradexcel Policy Exception"', '"Payroll Period"'):
        assert target in source, target


def test_non_financial_personas_cannot_open_readiness_or_receive_money():
    from frappe.desk.query_report import run

    h = SyntheticPersonaHarness("TXUX007PRIV" + frappe.generate_hash(6).upper())
    try:
        for key in ("finance", "attendance_officer", "hr_manager", "worker"):
            user = h.create_user(key, [PERSONA_ROLES[key]], company=COMPANY)
            frappe.set_user(user)
            assert not frappe.get_doc("Report", READINESS).is_permitted(), key
            with pytest.raises(frappe.PermissionError):
                run(READINESS, filters={"company": COMPANY, "payroll_month": "2026-09-01"})
    finally:
        frappe.set_user("Administrator")
        h.cleanup()
        assert not frappe.get_all("User", filters={"name": ["like", "persona-txux007priv%"]}, pluck="name")


def test_scoped_payroll_manager_cannot_read_whole_company_results(monkeypatch):
    branches = frappe.get_all("Branch", filters={"company": COMPANY}, pluck="name", order_by="name")
    departments = frappe.get_all("Department", filters={"company": COMPANY}, pluck="name", order_by="name")
    assert len(branches) >= 2 and departments
    h = SyntheticPersonaHarness("TXUX007SCOPE" + frappe.generate_hash(6).upper())
    try:
        user = h.create_user("payroll_manager", [PERSONA_ROLES["payroll_manager"]], company=COMPANY, branch=branches[0])
        in_scope = h.create_employee("in", COMPANY, branches[0], departments[0])
        out_of_scope = h.create_employee("out", COMPANY, branches[1], departments[0])

        def outcomes():
            return {
                "employee_count": 2, "ready_count": 2, "blocked_count": 0,
                "outcomes": [
                    {"employee": in_scope, "employee_data": {"employee_name": "Synthetic In"},
                     "status": "READY", "pay_basis": {"status": "Monthly Salary"}, "findings": []},
                    {"employee": out_of_scope, "employee_data": {"employee_name": "Synthetic Out"},
                     "status": "READY", "pay_basis": {"status": "Monthly Salary"}, "findings": []},
                ],
            }

        monkeypatch.setattr(readiness, "inspect_native_payroll_readiness", lambda *_args: outcomes())
        monkeypatch.setattr(readiness, "_existing_payroll_entry", lambda *_args: [])
        frappe.set_user(user)
        with pytest.raises(frappe.PermissionError, match="access to every employee"):
            readiness.execute({"company": COMPANY, "payroll_month": "2026-09-01"})
    finally:
        frappe.set_user("Administrator")
        h.cleanup()


def test_company_scoped_payroll_manager_gets_one_row_each_without_client_money(monkeypatch):
    branches = frappe.get_all("Branch", filters={"company": COMPANY}, pluck="name", order_by="name")
    departments = frappe.get_all("Department", filters={"company": COMPANY}, pluck="name", order_by="name")
    h = SyntheticPersonaHarness("TXUX007ALLOW" + frappe.generate_hash(6).upper())
    try:
        user = h.create_user("payroll_manager", [PERSONA_ROLES["payroll_manager"]], company=COMPANY)
        first = h.create_employee("one", COMPANY, branches[0], departments[0])
        second = h.create_employee("two", COMPANY, branches[0], departments[0])
        monkeypatch.setattr(readiness, "inspect_native_payroll_readiness", lambda *_args: {
            "employee_count": 2, "ready_count": 2, "blocked_count": 0,
            "outcomes": [
                {"employee": first, "employee_data": {"employee_name": "Synthetic One"},
                 "status": "READY", "pay_basis": {"status": "Monthly Salary"}, "findings": []},
                {"employee": second, "employee_data": {"employee_name": "Synthetic Two"},
                 "status": "READY", "pay_basis": {"status": "Monthly Salary"}, "findings": []},
            ],
        })
        monkeypatch.setattr(readiness, "_existing_payroll_entry", lambda *_args: [])
        frappe.set_user(user)
        _columns, rows, message, _chart, _summary = readiness.execute({"company": COMPANY, "payroll_month": "2026-09-01"})
        assert {row["employee"] for row in rows} == {first, second}
        assert len(rows) == 2
        for row in rows:
            assert row["status_label"] == "READY"
            assert not row["financial_result"]
            assert row["previous_net"] in (None, 0)
            assert not row["financial_action_kinds"]
            assert not row["run_action_kinds"]
        assert "record(s) ready" in message and "server rechecks readiness" in message
    finally:
        frappe.set_user("Administrator")
        h.cleanup()


def test_finance_may_read_salary_coverage_but_worker_or_operator_may_not(monkeypatch):
    from frappe.desk.query_report import run

    h = SyntheticPersonaHarness("TXUX007COV" + frappe.generate_hash(6).upper())
    try:
        finance = h.create_user("finance", [PERSONA_ROLES["finance"]], company=COMPANY)
        worker = h.create_user("worker", [PERSONA_ROLES["worker"]], company=COMPANY)
        frappe.set_user(finance)
        result = run("Tradexcel Salary Coverage Board", filters={"company": COMPANY, "as_of_date": "2026-09-01"})
        assert isinstance(result["result"], list)
        frappe.set_user(worker)
        with pytest.raises(frappe.PermissionError):
            run("Tradexcel Salary Coverage Board", filters={"company": COMPANY, "as_of_date": "2026-09-01"})
    finally:
        frappe.set_user("Administrator")
        h.cleanup()


def test_tax_review_endpoint_rejects_unauthorized_roles():
    from tradex_hr.tradexcel_hr import tax_review

    h = SyntheticPersonaHarness("TXUX007TAX" + frappe.generate_hash(6).upper())
    try:
        user = h.create_user("payroll_manager", [PERSONA_ROLES["payroll_manager"]], company=COMPANY)
        frappe.set_user(user)
        with pytest.raises(frappe.PermissionError, match="System Manager or Tradexcel Owner/Director"):
            tax_review.approve_income_tax_slab("ANY-SLAB", "Official gazette reference")
    finally:
        frappe.set_user("Administrator")
        h.cleanup()
