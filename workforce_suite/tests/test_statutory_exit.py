from datetime import date
from types import SimpleNamespace

import pytest


def test_approval_without_official_source_is_blocked(monkeypatch):
    from workforce_suite.workforce_suite import statutory_exit

    class FakeFrappe:
        session = SimpleNamespace(user="approver")

        @staticmethod
        def throw(message, **_kwargs):
            raise ValueError(str(message))

    doc = SimpleNamespace(
        workflow_state=statutory_exit.APPROVED,
        owner="maker",
        company="COMPANY_A",
        jurisdiction="Bangladesh",
        legal_regime="Synthetic",
        service_calculation_method="Manual Legal Review",
        applicability_date_basis="Manual Legal Review Required",
        effective_from=date(2026, 1, 1),
        effective_to=None,
        legal_review_notes="synthetic test review",
        sources=[],
        entitlements=[],
        settlement_deadline_working_days=0,
    )
    monkeypatch.setattr(statutory_exit, "frappe", FakeFrappe)
    with pytest.raises(ValueError, match="source is required"):
        statutory_exit._validate_for_approval(doc)


def test_deadline_counts_only_dates_not_marked_as_holidays(monkeypatch):
    from workforce_suite.workforce_suite import statutory_exit

    import erpnext.setup.doctype.holiday_list.holiday_list as holiday_list_module

    class FakeFrappe:
        @staticmethod
        def get_cached_doc(_doctype, _name):
            return object()

    monkeypatch.setattr(statutory_exit, "frappe", FakeFrappe)
    monkeypatch.setattr(holiday_list_module, "is_holiday", lambda _list, day: day == date(2026, 9, 21))
    rule = SimpleNamespace(settlement_deadline_working_days=3, holiday_list="Synthetic Calendar")
    result = statutory_exit._deadline(rule, date(2026, 9, 20))
    assert result == {
        "due_date": date(2026, 9, 24),
        "working_days": 3,
        "holiday_list": "Synthetic Calendar",
    }


def test_deadline_without_calendar_returns_review_finding(monkeypatch):
    from workforce_suite.workforce_suite import statutory_exit

    class FakeFrappe:
        pass

    monkeypatch.setattr(statutory_exit, "frappe", FakeFrappe)
    rule = SimpleNamespace(settlement_deadline_working_days=5, holiday_list=None)
    assert statutory_exit._deadline(rule, date(2026, 9, 20)) == {
        "code": "LEGAL_DATE_BASIS_REVIEW_REQUIRED"
    }