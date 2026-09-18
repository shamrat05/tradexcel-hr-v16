from types import SimpleNamespace

import pytest

from tradex_hr.tradexcel_hr.deduction_rules import compute_deductions, recompute_totals
import tradex_hr.tradexcel_hr.deduction_rules as deduction_rules


def row(component="Income Tax", amount=None, formula=None, abbr="ITX"):
    return {
        "salary_component": component,
        "abbr": abbr,
        "amount": amount,
        "amount_based_on_formula": 1 if formula else 0,
        "formula": formula,
    }


class Slip:
    def __init__(self, earnings, deductions):
        self.earnings = [SimpleNamespace(**item) for item in earnings]
        self.deductions = [SimpleNamespace(**item) for item in deductions]


def test_compute_fixed_formula_and_zero_rows():
    result = compute_deductions(
        [row(amount=100), row("Provident Fund", formula="base * 0.05", abbr="PF"), row(amount=0)],
        gross=1000,
    )
    assert [(item["salary_component"], item["amount"]) for item in result] == [
        ("Income Tax", 100.0), ("Provident Fund", 50.0),
    ]


def test_compute_raises_on_bad_formula_instead_of_guessing():
    with pytest.raises(ValueError, match="Income Tax"):
        compute_deductions([row(formula="base * * 2")], gross=1000)


def test_compute_skips_rows_without_component():
    assert compute_deductions([{"amount": 100}], gross=1000) == []


def test_formula_base_is_assignment_base_not_gross():
    result = compute_deductions([row(formula="base * 0.05")], gross=1200, base=1000)
    assert result[0]["amount"] == 50


def test_condition_and_payment_day_flags_are_honoured():
    taxable = row(formula="gross * 0.1") | {"condition": "payment_days >= 10", "depends_on_payment_days": 0}
    assert compute_deductions([taxable], gross=1000, base=900, payment_days=9) == []
    result = compute_deductions([taxable], gross=1000, base=900, payment_days=10)
    assert result[0]["amount"] == 100
    assert result[0]["depends_on_payment_days"] == 0


def test_reject_non_finite_or_negative_deductions():
    with pytest.raises(ValueError):
        compute_deductions([row(amount=-1)], gross=1000)
    with pytest.raises(ValueError):
        compute_deductions([row(formula="1e309")], gross=1000)
    with pytest.raises(ValueError, match="working days"):
        compute_deductions([row(amount=50) | {"depends_on_payment_days": 1}], gross=1000,
                           payment_days=0, total_working_days=0)


def test_fixed_deduction_prorates_only_when_configured():
    rows = [row(amount=100) | {"depends_on_payment_days": 1}]
    assert compute_deductions(rows, gross=1000, payment_days=10, total_working_days=20)[0]["amount"] == 50
    assert compute_deductions([row(amount=100)], gross=1000, payment_days=10,
                              total_working_days=20)[0]["amount"] == 100


def test_net_pay_is_not_rounded_early(monkeypatch):
    monkeypatch.setattr(deduction_rules, "rounded", round)
    slip = Slip(earnings=[{"amount": 1000.25}], deductions=[{"amount": 100.10}])
    recompute_totals(slip)
    assert round(slip.net_pay, 2) == 900.15
    assert slip.rounded_total == 900


def test_negative_net_is_rejected(monkeypatch):
    monkeypatch.setattr(deduction_rules, "rounded", round)
    with pytest.raises(ValueError, match="negative net pay"):
        recompute_totals(Slip(earnings=[{"amount": 0}], deductions=[{"amount": 10}]))


def test_recompute_totals_reflects_exceptions(monkeypatch):
    monkeypatch.setattr(deduction_rules, "rounded", round)
    slip = Slip(
        earnings=[{"amount": 1000}],
        deductions=[{"amount": 100}],
    )
    recompute_totals(slip)
    assert slip.net_pay == 900.0 and slip.total_deduction == 100.0
    slip.deductions = []  # tax exemption stripped the line
    recompute_totals(slip)
    assert slip.net_pay == 1000.0 and slip.rounded_total == 1000
