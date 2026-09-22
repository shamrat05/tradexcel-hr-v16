import os

import frappe
import pytest

from tradex_hr.tradexcel_hr.doctype.tradexcel_attendance_period import tradexcel_attendance_period

@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(
        site=os.environ.get("FRAPPE_TEST_SITE", "hrms-v16.localhost"),
        sites_path=os.environ.get(
            "FRAPPE_TEST_SITES_PATH", "/home/sanchita/frappe-bench-v16/sites"
        ),
    )
    frappe.connect()
    yield
    frappe.destroy()


def _period(company="Tradexcel Ceramics Ltd."):
    return frappe.get_doc(
        {
            "doctype": "Tradexcel Attendance Period",
            "company": company,
            "from_date": "2026-09-01",
            "to_date": "2026-09-30",
        }
    )


def test_exact_period_duplicate_is_rejected():
    save_point = "attendance_period_duplicate"
    frappe.db.savepoint(save_point)
    try:
        _period().insert(ignore_permissions=True)
        with pytest.raises(frappe.ValidationError):
            _period().insert(ignore_permissions=True)
    finally:
        frappe.db.rollback(save_point=save_point)


def test_direct_status_edit_cannot_bypass_actions():
    save_point = "attendance_period_status"
    frappe.db.savepoint(save_point)
    try:
        period = _period()
        period.insert(ignore_permissions=True)
        period.status = "Reviewing"
        with pytest.raises(frappe.ValidationError):
            period.save(ignore_permissions=True)
    finally:
        frappe.db.rollback(save_point=save_point)


def test_reopen_disables_unconsumed_daily_wage_inputs(monkeypatch):
    retired = []
    monkeypatch.setattr(
        tradexcel_attendance_period.frappe,
        "get_all",
        lambda *_args, **_kwargs: [{"name": "AS-1", "docstatus": 1, "disabled": 0}],
    )
    monkeypatch.setattr(tradexcel_attendance_period, "_salary_slips_using_input", lambda _name: [])
    monkeypatch.setattr(
        tradexcel_attendance_period.frappe.db,
        "set_value",
        lambda *args, **_kwargs: retired.append(args),
    )

    tradexcel_attendance_period._retire_daily_wage_inputs("ATT-PER-1")

    assert retired == [("Additional Salary", "AS-1", "disabled", 1)]


def test_reopen_blocks_when_daily_wage_input_is_already_used(monkeypatch):
    monkeypatch.setattr(
        tradexcel_attendance_period.frappe,
        "get_all",
        lambda *_args, **_kwargs: [{"name": "AS-1", "docstatus": 1, "disabled": 0}],
    )
    monkeypatch.setattr(
        tradexcel_attendance_period,
        "_salary_slips_using_input",
        lambda _name: [{"name": "SAL-SLIP-1", "docstatus": 1}],
    )

    with pytest.raises(frappe.ValidationError, match="payroll correction"):
        tradexcel_attendance_period._retire_daily_wage_inputs("ATT-PER-1")
