from tradex_hr import hooks
from tradex_hr.tradexcel_hr import tax_exceptions


def test_legacy_tax_action_is_preserved_but_not_attached_to_salary_slip_calculation():
    assert tax_exceptions.TAX_ACTIONS == ("Mark Tax Exempt",)
    salary_slip_events = hooks.doc_events["Salary Slip"]
    assert "tax_exceptions.apply_tax_exemption" not in str(salary_slip_events)
    assert salary_slip_events["before_validate"] == (
        "tradex_hr.tradexcel_hr.component_exceptions.apply_to_salary_slip"
    )


def test_legacy_tax_module_has_no_salary_slip_mutation_api():
    assert not hasattr(tax_exceptions, "apply_tax_exemption")
    assert not hasattr(tax_exceptions, "strip_tax_deductions")
