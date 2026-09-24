from types import SimpleNamespace
import pytest
import frappe
from frappe.exceptions import PermissionError as FrappePermissionError

from tradex_hr.tradexcel_hr import flexible_work_records as records
from tradex_hr.tradexcel_hr.flexible_work_records import (
    TradexcelFlexibleWorkPolicy,
    TradexcelOperationalDayOverride,
)


def _frappe_request(monkeypatch, user, role, db=None):
    monkeypatch.setattr(frappe, "session", frappe._dict(user=user))
    monkeypatch.setattr(frappe, "get_roles", lambda user=None: [role])
    monkeypatch.setattr(frappe, "db", db or SimpleNamespace(
        get_value=lambda *args, **kwargs: "preview",
        get_single_value=lambda *args, **kwargs: 0,
    ))
    monkeypatch.setattr(frappe, "get_all", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        frappe, "throw",
        lambda message, exc=None, **kwargs: (_ for _ in ()).throw(
            (exc or frappe.ValidationError)(message)
        ),
    )


@pytest.mark.parametrize(
    ("controller", "role", "fields"),
    [
        (TradexcelFlexibleWorkPolicy, records.APPROVER_ROLE, {
            "effective_from": "2026-10-01", "effective_to": "2026-10-31",
            "flexible_shift_enabled": 0,
        }),
        (TradexcelOperationalDayOverride, records.PAY_APPROVER_ROLE, {
            "operational_date": "2026-10-01", "preview_hash": "preview",
        }),
    ],
)
def test_flexible_work_money_decision_maker_cannot_self_approve(monkeypatch, controller, role, fields):
    _frappe_request(monkeypatch, "maker", role)
    doc = frappe._dict({"company": "TCL", "owner": "maker", **fields})
    monkeypatch.setattr(records, "assert_company_access", lambda company, require_explicit_scope: None)
    with pytest.raises(FrappePermissionError):
        controller.before_submit(doc)


def test_company_scoped_independent_policy_reviewer_can_approve(monkeypatch):
    _frappe_request(monkeypatch, "reviewer", records.APPROVER_ROLE)
    monkeypatch.setattr(records, "now_datetime", lambda: "2026-09-24 16:00:00")
    doc = frappe._dict({
        "company": "TCL", "owner": "maker", "effective_from": "2026-10-01",
        "effective_to": "2026-10-31", "flexible_shift_enabled": 0,
    })
    scope = []
    monkeypatch.setattr(
        records, "assert_company_access",
        lambda company, require_explicit_scope: scope.append((company, require_explicit_scope)),
    )
    TradexcelFlexibleWorkPolicy.before_submit(doc)
    assert doc.approved_by == "reviewer"
    assert scope == [("TCL", True)]


def test_flexible_override_requires_independent_company_scoped_pay_approver(monkeypatch):
    _frappe_request(monkeypatch, "pay-approver", records.PAY_APPROVER_ROLE)
    monkeypatch.setattr(records, "now_datetime", lambda: "2026-09-24 16:00:00")
    doc = frappe._dict({
        "company": "TCL", "owner": "maker", "operational_date": "2026-10-01",
        "preview_hash": "preview",
    })
    scope = []
    monkeypatch.setattr(
        records, "assert_company_access",
        lambda company, require_explicit_scope: scope.append((company, require_explicit_scope)),
    )
    monkeypatch.setattr(
        records, "build_operational_day_override_preview",
        lambda _doc: {"status": "READY", "affected_count": 1, "attendance_hash": "preview"},
    )
    monkeypatch.setattr(records, "_payroll_has_started", lambda *args: False)
    TradexcelOperationalDayOverride.before_submit(doc)
    assert doc.approved_by == "pay-approver"
    assert scope == [("TCL", True)]


def test_policy_payroll_started_check_covers_the_entire_effective_range(monkeypatch):
    calls = []

    def get_all(doctype, filters=None, **kwargs):
        calls.append((doctype, filters))
        return ["SAL-SLIP-1"] if doctype == "Salary Slip" else []

    monkeypatch.setattr(frappe, "get_all", get_all)
    assert records._payroll_has_started("TCL", "2026-01-01", "2026-12-31")
    assert calls[0][1]["start_date"] == ["<=", frappe.utils.getdate("2026-12-31")]
    assert calls[0][1]["end_date"] == [">=", frappe.utils.getdate("2026-01-01")]


@pytest.mark.parametrize(
    ("controller", "role", "fields"),
    [
        (TradexcelFlexibleWorkPolicy, records.APPROVER_ROLE, {
            "effective_from": "2026-10-01", "effective_to": "2026-10-31",
            "flexible_shift_enabled": 0,
        }),
        (TradexcelOperationalDayOverride, records.PAY_APPROVER_ROLE, {
            "operational_date": "2026-10-01", "preview_hash": "preview",
        }),
    ],
)
def test_out_of_company_flexible_work_approver_is_denied(monkeypatch, controller, role, fields):
    _frappe_request(monkeypatch, "foreign-reviewer", role)
    doc = frappe._dict({"company": "EFL", "owner": "maker", **fields})

    def deny_company_scope(company, require_explicit_scope):
        assert company == "EFL"
        assert require_explicit_scope is True
        raise FrappePermissionError("No EFL Company scope")

    monkeypatch.setattr(records, "assert_company_access", deny_company_scope)
    with pytest.raises(FrappePermissionError):
        controller.before_submit(doc)
