"""Batching preserves the canonical resolver and never survives a read scope."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import patch
import frappe
import pytest
from tradex_hr.tradexcel_hr import pay_basis as pay


def test_read_snapshot_parity_conflicts_dates_missing_basis_and_reset(monkeypatch):
    rows = [
        frappe._dict(
            name="A",
            employee="MONTH",
            salary_structure="MONTHLY",
            base=100,
            from_date=date(2026, 1, 1),
        ),
        frappe._dict(
            name="B",
            employee="DAY",
            salary_structure="DAILY",
            base=10,
            from_date=date(2026, 1, 1),
        ),
        frappe._dict(
            name="C",
            employee="CHANGE",
            salary_structure="MONTHLY",
            base=100,
            from_date=date(2026, 1, 1),
        ),
        frappe._dict(
            name="D",
            employee="CHANGE",
            salary_structure="MONTHLY",
            base=110,
            from_date=date(2026, 9, 15),
        ),
        frappe._dict(
            name="E",
            employee="CONFLICT",
            salary_structure="MONTHLY",
            base=100,
            from_date=date(2026, 1, 1),
        ),
        frappe._dict(
            name="F",
            employee="CONFLICT",
            salary_structure="MONTHLY",
            base=110,
            from_date=date(2026, 1, 1),
        ),
        frappe._dict(
            name="G",
            employee="UNSET",
            salary_structure="UNSET",
            base=10,
            from_date=date(2026, 1, 1),
        ),
    ]
    rows.append(
        frappe._dict(
            name="JOIN",
            employee="JOINER",
            salary_structure="MONTHLY",
            base=100,
            from_date=date(2026, 9, 15),
        )
    )
    joining = lambda name: date(2026, 9, 15) if name == "JOINER" else date(2020, 1, 1)
    bases = {"MONTHLY": pay.MONTHLY, "DAILY": pay.DAILY, "UNSET": None}
    names = ["MONTH", "DAY", "CHANGE", "CONFLICT", "UNSET", "MISSING", "JOINER"]
    calls = []

    def get_all(dt, filters, **kwargs):
        calls.append(dt)
        if dt == "Salary Structure Assignment":
            if isinstance(filters["employee"], list):
                selected = [r for r in rows if r.employee in filters["employee"][1]]
            else:
                selected = [r for r in rows if r.employee == filters["employee"]]
                operator, value = filters["from_date"]
                selected = [
                    r
                    for r in selected
                    if (
                        r.from_date <= value
                        if operator == "<="
                        else r.from_date > value
                    )
                ]
            return sorted(
                selected,
                key=lambda r: (r.from_date, r.name),
                reverse="desc" in kwargs.get("order_by", ""),
            )
        if dt == "Salary Structure":
            return [
                frappe._dict(name=n, custom_tradex_pay_basis=bases[n])
                for n in filters["name"][1]
            ]
        if dt == "Employee":
            return [
                frappe._dict(name=n, date_of_joining=joining(n))
                for n in filters["name"][1]
            ]
        raise AssertionError(dt)

    def get_value(dt, name, field):
        calls.append(dt)
        return bases.get(name) if dt == "Salary Structure" else joining(name)

    monkeypatch.setattr(
        pay,
        "frappe",
        SimpleNamespace(get_all=get_all, db=SimpleNamespace(get_value=get_value)),
    )

    def resolve():
        return {n: pay.resolve_pay_basis(n, "2026-09-01", "2026-09-30") for n in names}

    expected = resolve()
    calls.clear()
    with pay.pay_basis_read_context(names):
        assert resolve() == expected
        with pay.pay_basis_read_context(names[:2]):
            assert resolve() == expected
        assert calls == ["Salary Structure Assignment", "Salary Structure", "Employee"]
    assert pay._read_snapshot.get() is None
    rows[0].base = 200
    assert pay.resolve_pay_basis("MONTH", "2026-09-01")["base"] == 200
    with pytest.raises(RuntimeError):
        with pay.pay_basis_read_context(names):
            raise RuntimeError("synthetic report failure")
    assert pay._read_snapshot.get() is None
