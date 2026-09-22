import pytest

from tradex_hr.tradexcel_hr.company_context import resolve_company


def test_explicit_company_is_required_when_no_user_default(monkeypatch):
    monkeypatch.setattr("tradex_hr.tradexcel_hr.company_context.user_default_company", lambda: None)
    with pytest.raises(ValueError, match="Company is required"):
        resolve_company({})


def test_user_default_company_is_used_when_filter_is_blank(monkeypatch):
    monkeypatch.setattr(
        "tradex_hr.tradexcel_hr.company_context.user_default_company",
        lambda: "Elegance Footwear Ltd.",
    )
    assert resolve_company({}) == "Elegance Footwear Ltd."


def test_explicit_company_wins_over_user_default(monkeypatch):
    monkeypatch.setattr(
        "tradex_hr.tradexcel_hr.company_context.user_default_company",
        lambda: "Elegance Footwear Ltd.",
    )
    assert resolve_company({"company": "Tradexcel Ceramics Ltd."}) == "Tradexcel Ceramics Ltd."
