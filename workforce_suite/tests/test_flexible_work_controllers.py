from types import SimpleNamespace
import pytest
import frappe
from frappe.exceptions import PermissionError as FrappePermissionError

from workforce_suite.workforce_suite import flexible_work_records as records
from workforce_suite.workforce_suite.flexible_work_records import (
    WorkforceFlexibleWorkPolicy,
    WorkforceOperationalDayOverride,
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
        (WorkforceFlexibleWorkPolicy, records.APPROVER_ROLE, {
            "effective_from": "2026-10-01", "effective_to": "2026-10-31",
            "flexible_shift_enabled": 0,
        }),
        (WorkforceOperationalDayOverride, records.PAY_APPROVER_ROLE, {
            "operational_date": "2026-10-01", "preview_hash": "preview",
        }),
    ],
)
def test_flexible_work_money_decision_maker_cannot_self_approve(monkeypatch, controller, role, fields):
    _frappe_request(monkeypatch, "maker", role)
    doc = frappe._dict({"company": "COMPANY_A", "owner": "maker", **fields})
    monkeypatch.setattr(records, "assert_company_access", lambda company, require_explicit_scope: None)
    with pytest.raises(FrappePermissionError):
        controller.before_submit(doc)


def test_company_scoped_independent_policy_reviewer_can_approve(monkeypatch):
    _frappe_request(monkeypatch, "reviewer", records.APPROVER_ROLE)
    monkeypatch.setattr(records, "now_datetime", lambda: "2026-09-24 16:00:00")
    doc = frappe._dict({
        "company": "COMPANY_A", "owner": "maker", "effective_from": "2026-10-01",
        "effective_to": "2026-10-31", "flexible_shift_enabled": 0,
    })
    scope = []
    monkeypatch.setattr(
        records, "assert_company_access",
        lambda company, require_explicit_scope: scope.append((company, require_explicit_scope)),
    )
    WorkforceFlexibleWorkPolicy.before_submit(doc)
    assert doc.approved_by == "reviewer"
    assert scope == [("COMPANY_A", True)]


def test_flexible_override_requires_independent_company_scoped_pay_approver(monkeypatch):
    _frappe_request(monkeypatch, "pay-approver", records.PAY_APPROVER_ROLE)
    monkeypatch.setattr(records, "now_datetime", lambda: "2026-09-24 16:00:00")
    doc = frappe._dict({
        "company": "COMPANY_A", "owner": "maker", "operational_date": "2026-10-01",
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
    WorkforceOperationalDayOverride.before_submit(doc)
    assert doc.approved_by == "pay-approver"
    assert scope == [("COMPANY_A", True)]


def test_policy_payroll_started_check_covers_the_entire_effective_range(monkeypatch):
    calls = []

    def get_all(doctype, filters=None, **kwargs):
        calls.append((doctype, filters))
        return ["SAL-SLIP-1"] if doctype == "Salary Slip" else []

    monkeypatch.setattr(frappe, "get_all", get_all)
    assert records._payroll_has_started("COMPANY_A", "2026-01-01", "2026-12-31")
    assert calls[0][1]["start_date"] == ["<=", frappe.utils.getdate("2026-12-31")]
    assert calls[0][1]["end_date"] == [">=", frappe.utils.getdate("2026-01-01")]


@pytest.mark.parametrize(
    ("controller", "role", "fields"),
    [
        (WorkforceFlexibleWorkPolicy, records.APPROVER_ROLE, {
            "effective_from": "2026-10-01", "effective_to": "2026-10-31",
            "flexible_shift_enabled": 0,
        }),
        (WorkforceOperationalDayOverride, records.PAY_APPROVER_ROLE, {
            "operational_date": "2026-10-01", "preview_hash": "preview",
        }),
    ],
)
def test_out_of_company_flexible_work_approver_is_denied(monkeypatch, controller, role, fields):
    _frappe_request(monkeypatch, "foreign-reviewer", role)
    doc = frappe._dict({"company": "COMPANY_B", "owner": "maker", **fields})

    def deny_company_scope(company, require_explicit_scope):
        assert company == "COMPANY_B"
        assert require_explicit_scope is True
        raise FrappePermissionError("No COMPANY_B Company scope")

    monkeypatch.setattr(records, "assert_company_access", deny_company_scope)
    with pytest.raises(FrappePermissionError):
        controller.before_submit(doc)
