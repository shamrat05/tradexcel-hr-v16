from datetime import date, datetime
from types import SimpleNamespace

import pytest


def test_boundary_validator_rejects_work_records_after_relieving_date(monkeypatch):
    from workforce_suite.workforce_suite import employee_separation

    class FakeFrappe:
        class db:
            @staticmethod
            def get_value(*_args, **_kwargs):
                return date(2026, 9, 15)

        ValidationError = ValueError

        @staticmethod
        def throw(message, **_kwargs):
            raise ValueError(message)

    monkeypatch.setattr(employee_separation, "frappe", FakeFrappe)
    for doc in (
        SimpleNamespace(doctype="Attendance", employee="EMP-1", attendance_date=date(2026, 9, 16)),
        SimpleNamespace(doctype="Attendance Request", employee="EMP-1", from_date=date(2026, 9, 15), to_date=date(2026, 9, 16)),
        SimpleNamespace(doctype="Overtime Slip", employee="EMP-1", overtime_details=[SimpleNamespace(date=date(2026, 9, 16))]),
        SimpleNamespace(doctype="Workforce Field Duty", employee="EMP-1", duty_date=date(2026, 9, 16), status="Approved"),
    ):
        with pytest.raises(ValueError, match="relieving date"):
            employee_separation.validate_no_payable_work_after_relieving_date(doc)


def test_boundary_validator_allows_work_through_relief_date(monkeypatch):
    from workforce_suite.workforce_suite import employee_separation

    class FakeFrappe:
        class db:
            @staticmethod
            def get_value(*_args, **_kwargs):
                return date(2026, 9, 15)

        ValidationError = ValueError

        @staticmethod
        def throw(message, **_kwargs):
            raise ValueError(message)

    monkeypatch.setattr(employee_separation, "frappe", FakeFrappe)
    doc = SimpleNamespace(doctype="Attendance", employee="EMP-1", attendance_date=date(2026, 9, 15))
    assert employee_separation.validate_no_payable_work_after_relieving_date(doc) is None


def test_mobile_event_classification_uses_captured_device_time():
    from workforce_suite.workforce_suite.employee_separation import classify_evidence_date

    relieving = date(2026, 9, 15)
    assert classify_evidence_date(datetime(2026, 9, 14, 23, 58), datetime(2026, 9, 17, 8), relieving) == "PRE_EXIT_HISTORY"
    assert classify_evidence_date(datetime(2026, 9, 16, 0, 1), datetime(2026, 9, 16, 0, 2), relieving) == "POST_EXIT_REVIEW"
    assert classify_evidence_date(None, datetime(2026, 9, 14), relieving) == "CAPTURE_TIME_MISSING"


def test_employment_boundary_no_longer_blocks_native_midperiod_dates():
    from workforce_suite.workforce_suite.attendance_payroll_boundary import READY, classify_employment_boundaries

    result = classify_employment_boundaries(
        [
            {"name": "JOIN", "date_of_joining": date(2026, 9, 15), "status": "Active"},
            {"name": "LEAVER", "date_of_joining": date(2024, 1, 1), "relieving_date": date(2026, 9, 15), "status": "Left"},
        ],
        date(2026, 9, 1), date(2026, 9, 30),
    )
    assert {row["status"] for row in result.values()} == {READY}


@pytest.mark.parametrize(
    ("payables", "receivables", "assets", "expected"),
    [
        ([SimpleNamespace(status="Unsettled")], [], [], 1),
        ([], [SimpleNamespace(status="Unsettled")], [], 1),
        ([], [], [SimpleNamespace(action="Return", status="Owned", cost=0, account=None)], 1),
        ([], [], [SimpleNamespace(action="Recover Cost", status="Owned", cost=0, account=None)], 1),
        ([SimpleNamespace(status="Settled")], [], [], 0),
        ([], [], [SimpleNamespace(action="Return", status="Returned", cost=0, account=None)], 0),
        ([], [], [SimpleNamespace(action="Recover Cost", status="Owned", cost=25, account="Expense")], 0),
    ],
)
def test_native_full_and_final_pending_sources_match_submission_blockers(
    payables, receivables, assets, expected
):
    from workforce_suite.workforce_suite.employee_separation import _native_settlement_pending_count

    assert _native_settlement_pending_count(payables, receivables, assets) == expected


@pytest.mark.parametrize(
    ("cost", "account_name", "account_data", "should_raise"),
    [
        (0, "Expense", {"company": "COMPANY_A", "is_group": 0, "disabled": 0}, True),
        (25, None, {"company": "COMPANY_A", "is_group": 0, "disabled": 0}, True),
        (25, "Expense", {"company": "COMPANY_B", "is_group": 0, "disabled": 0}, True),
        (25, "Expense", {"company": "COMPANY_A", "is_group": 1, "disabled": 0}, True),
        (25, "Expense", {"company": "COMPANY_A", "is_group": 0, "disabled": 1}, True),
        (25, "Expense", {"company": "COMPANY_A", "is_group": 0, "disabled": 0}, False),
    ],
)
def test_asset_recovery_requires_explicit_positive_cost_and_valid_company_account(
    monkeypatch, cost, account_name, account_data, should_raise
):
    from workforce_suite.workforce_suite import employee_separation

    class FakeFrappe:
        class utils:
            @staticmethod
            def flt(value):
                return float(value or 0)

        class db:
            @staticmethod
            def get_value(*_args, **_kwargs):
                return SimpleNamespace(**account_data) if account_data else None

        @staticmethod
        def throw(message, **_kwargs):
            raise ValueError(str(message))

    monkeypatch.setattr(employee_separation, "frappe", FakeFrappe)

    class FakeDoc:
        company = "COMPANY_A"

        @staticmethod
        def get(fieldname, default=None):
            return [SimpleNamespace(action="Recover Cost", cost=cost, account=account_name, asset_name="Laptop")]

    if should_raise:
        with pytest.raises(ValueError):
            employee_separation._validate_asset_recovery_inputs(FakeDoc())
    else:
        assert employee_separation._validate_asset_recovery_inputs(FakeDoc()) is None


def test_full_and_final_readiness_is_whitelisted_but_internal_classifier_is_not():
    import frappe
    from workforce_suite.workforce_suite.employee_separation import (
        _native_settlement_pending_count,
        inspect_full_and_final_readiness,
    )

    assert inspect_full_and_final_readiness in frappe.whitelisted
    assert _native_settlement_pending_count not in frappe.whitelisted


def test_death_separation_surfaces_claim_for_active_group_insurance(monkeypatch):
    import frappe
    from workforce_suite.workforce_suite import employee_separation, statutory_benefits, statutory_exit

    employee = frappe._dict(name="EMP-SYNTHETIC", company="COMPANY_A", relieving_date=date(2026, 9, 30))
    separation = frappe._dict(name="SEP-SYNTHETIC", custom_workforce_separation_type="Death")
    preview = frappe._dict(payables=[], receivables=[], assets_allocated=[])
    preview.get_outstanding_statements = lambda: None

    class FakeFrappe:
        @staticmethod
        def get_all(*_args, **_kwargs):
            return []

        @staticmethod
        def get_doc(*_args, **_kwargs):
            return preview

    monkeypatch.setattr(employee_separation, "frappe", FakeFrappe)
    monkeypatch.setattr(employee_separation, "_authorized_employee", lambda _name: employee)
    monkeypatch.setattr(employee_separation, "_latest_separation", lambda _name: separation)
    monkeypatch.setattr(employee_separation, "_native_settlement_pending_count", lambda *_args: 0)
    monkeypatch.setattr(employee_separation, "_full_and_final_payment_status", lambda _fnf: {"status": "NONE", "journal_entries": []})
    monkeypatch.setattr(statutory_exit, "inspect_statutory_exit_readiness", lambda _name: {"findings": []})
    monkeypatch.setattr(
        statutory_benefits,
        "inspect_statutory_benefit_readiness",
        lambda *_args: {"benefits": [{"benefit_type": "Group Insurance", "status": "READY"}]},
    )

    result = employee_separation.inspect_full_and_final_readiness(employee.name)
    assert any(item["code"] == "GROUP_INSURANCE_CLAIM_REQUIRED" for item in result["findings"])


def test_death_separation_without_active_group_coverage_does_not_claim_ready(monkeypatch):
    import frappe
    from workforce_suite.workforce_suite import employee_separation, statutory_benefits, statutory_exit

    employee = frappe._dict(name="EMP-SYNTHETIC", company="COMPANY_A", relieving_date=date(2026, 9, 30))
    separation = frappe._dict(name="SEP-SYNTHETIC", custom_workforce_separation_type="Death")
    preview = frappe._dict(payables=[], receivables=[], assets_allocated=[])
    preview.get_outstanding_statements = lambda: None

    class FakeFrappe:
        @staticmethod
        def get_all(*_args, **_kwargs):
            return []

        @staticmethod
        def get_doc(*_args, **_kwargs):
            return preview

    monkeypatch.setattr(employee_separation, "frappe", FakeFrappe)
    monkeypatch.setattr(employee_separation, "_authorized_employee", lambda _name: employee)
    monkeypatch.setattr(employee_separation, "_latest_separation", lambda _name: separation)
    monkeypatch.setattr(employee_separation, "_native_settlement_pending_count", lambda *_args: 0)
    monkeypatch.setattr(employee_separation, "_full_and_final_payment_status", lambda _fnf: {"status": "NONE", "journal_entries": []})
    monkeypatch.setattr(statutory_exit, "inspect_statutory_exit_readiness", lambda _name: {"findings": []})
    monkeypatch.setattr(
        statutory_benefits,
        "inspect_statutory_benefit_readiness",
        lambda *_args: {"benefits": [{"benefit_type": "Group Insurance", "status": "GROUP_INSURANCE_POLICY_REQUIRED"}]},
    )

    result = employee_separation.inspect_full_and_final_readiness(employee.name)
    assert not any(item["code"] == "GROUP_INSURANCE_CLAIM_REQUIRED" for item in result["findings"])
