import sys
from pathlib import Path
from types import SimpleNamespace

import frappe

sys.path.insert(0, str(Path(__file__).parent))
from tradex_hr.tradexcel_hr.run_payroll import _create_manual_slip


def test_generated_salary_slip_stays_draft(monkeypatch):
    class Slip:
        docstatus = 0
        earnings = []
        deductions = []
        payment_days = 0
        total_working_days = 0
        def insert(self, **kwargs):
            return self
        def submit(self):
            self.docstatus = 1

    slip = Slip()
    monkeypatch.setattr(frappe, "get_doc", lambda arg, *args: slip if isinstance(arg, dict) else object())
    monkeypatch.setattr(frappe, "flags", SimpleNamespace(in_patch=False))
    import tradex_hr.tradexcel_hr.deduction_rules as deduction_rules
    monkeypatch.setattr(deduction_rules, "structure_deductions", lambda *args, **kwargs: [])
    monkeypatch.setattr(deduction_rules, "recompute_totals", lambda *args, **kwargs: None)
    result = _create_manual_slip({"salary_structure": "Worker", "doctype": "Salary Slip"})
    assert result is slip
    assert result.docstatus == 0
