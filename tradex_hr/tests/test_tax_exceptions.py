from types import SimpleNamespace

from tradex_hr.tradexcel_hr.tax_exceptions import is_tax_exempt, strip_tax_deductions


def rule(name="R1", employee="E1", action="Mark Tax Exempt", **overrides):
    base = {
        "name": name, "company": "TCL", "employee": employee,
        "tax_action": action, "effective_from": "2026-09-01",
    }
    base.update(overrides)
    return base


class Slip:
    def __init__(self, deductions):
        self.deductions = [SimpleNamespace(**row) for row in deductions]

    def append(self, fieldname, row):
        getattr(self, fieldname).append(SimpleNamespace(**row))


def test_is_tax_exempt_scope_window_and_company():
    rules = [rule(), rule("R2", action="No Action")]
    assert is_tax_exempt("E1", "TCL", "2026-09-10", rules) is True
    assert is_tax_exempt("E2", "TCL", "2026-09-10", rules) is False
    assert is_tax_exempt("E1", "EFL", "2026-09-10", rules) is False
    expired = [rule(effective_to="2026-09-05")]
    assert is_tax_exempt("E1", "TCL", "2026-09-10", expired) is False


def test_strip_removes_only_tax_components():
    slip = Slip([
        {"salary_component": "Income Tax", "abbr": "IT", "amount": 500},
        {"salary_component": "Provident Fund", "abbr": "PF", "amount": 200},
    ])
    assert strip_tax_deductions(slip, {"Income Tax"}) is True
    assert [row.salary_component for row in slip.deductions] == ["Provident Fund"]
    assert slip.deductions[0].amount == 200


def test_strip_is_noop_when_nothing_to_remove():
    slip = Slip([{"salary_component": "Provident Fund", "abbr": "PF", "amount": 200}])
    assert strip_tax_deductions(slip, {"Income Tax"}) is False
    assert strip_tax_deductions(slip, set()) is False
