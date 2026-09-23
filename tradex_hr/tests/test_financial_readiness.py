from types import SimpleNamespace

import frappe
import pytest

from tradex_hr import hooks
from tradex_hr.tradexcel_hr import company_context, component_exceptions, financial_readiness, native_payroll, tax_review


def test_tax_exemption_policy_is_not_called_for_salary_slip_calculation():
    assert hooks.doc_events["Salary Slip"]["before_validate"] == (
        "tradex_hr.tradexcel_hr.component_exceptions.apply_to_salary_slip"
    )


def test_historical_tax_exception_is_reported_not_deleted(monkeypatch):
    rows = [
        frappe._dict(name="TPE-SUBMITTED", docstatus=1, effective_from="2026-09-01", effective_to=None),
        frappe._dict(name="TPE-DRAFT", docstatus=0, effective_from="2026-09-01", effective_to=None),
    ]
    monkeypatch.setattr(financial_readiness, "frappe", SimpleNamespace(get_all=lambda *_args, **_kwargs: rows))
    findings = financial_readiness._tax_exception_findings("TCL", "2026-09-01", "2026-09-30")
    assert {item["reference"] for item in findings} == {"TPE-SUBMITTED", "TPE-DRAFT"}
    assert {item["reference"]: item["severity"] for item in findings} == {
        "TPE-SUBMITTED": "BLOCKER", "TPE-DRAFT": "WARNING"
    }


def _tax_check(
    monkeypatch, *, period=True, review="Approved", effective="2026-01-01",
    current_period="PP-1", assigned_slab="SLAB-1",
):
    from hrms.payroll.doctype.payroll_period import payroll_period

    period_doc = frappe._dict(name="PP-1", start_date="2026-01-01", end_date="2026-12-31")
    monkeypatch.setattr(payroll_period, "get_payroll_period", lambda *_: period_doc if period else None)
    slab = frappe._dict(
        company="TCL", effective_from=effective, disabled=0, docstatus=1,
        custom_tradex_review_status=review,
    )
    def get_value(doctype, name, field, **kwargs):
        if doctype == "Income Tax Slab":
            return slab
        raise AssertionError((doctype, name, field))
    monkeypatch.setattr(financial_readiness, "frappe", SimpleNamespace(db=SimpleNamespace(get_value=get_value)))
    entry = frappe._dict(company="TCL", start_date="2026-09-01", end_date="2026-09-30")
    slips = [frappe._dict(name="SS-1", employee="EMP-1", current_payroll_period=current_period)]
    details = [frappe._dict(salary_component="Tax")]
    components = {"Tax": frappe._dict(variable_based_on_taxable_salary=1, is_income_tax_component=0)}
    return financial_readiness._tax_configuration_findings(
        entry, slips, details, components, {"SS-1": frappe._dict(income_tax_slab=assigned_slab)}
    )


def test_taxable_salary_without_native_tax_component_blocks(monkeypatch):
    details = [frappe._dict(parentfield="earnings", salary_component="Base")]
    components = {"Base": frappe._dict(is_tax_applicable=1, variable_based_on_taxable_salary=0, is_income_tax_component=0)}
    findings = financial_readiness._tax_configuration_findings(None, [], details, components, {})
    assert findings[0]["code"] == "TAX_COMPONENT_MISSING"

def test_missing_native_payroll_period_blocks_tax_configuration(monkeypatch):
    findings = _tax_check(monkeypatch, period=False)
    assert findings[0]["code"] == "TAX_PERIOD_MISSING"


def test_unassigned_slab_routes_to_salary_assignment(monkeypatch):
    findings = _tax_check(monkeypatch, assigned_slab=None)
    assert findings[0]["code"] == "TAX_ASSIGNMENT_MISSING"


def test_missing_salary_assignment_has_an_assignment_fix_action():
    from tradex_hr.tradexcel_hr.report.tradexcel_payroll_readiness.tradexcel_payroll_readiness import _financial_action_kinds

    assert _financial_action_kinds([{"code": "TAX_ASSIGNMENT_MISSING"}]) == "salary_assignments"
    assert _financial_action_kinds([{"code": "TAX_PERIOD_MISSING"}]) == "payroll_periods"
    assert _financial_action_kinds([{"code": "TAX_SLAB_UNAPPROVED"}]) == "tax_slabs"


def test_approved_effective_native_slab_allows_zero_tax(monkeypatch):
    # A zero calculated amount is not an error: configuration validity is what
    # this boundary checks, not a positive per-employee deduction.
    assert _tax_check(monkeypatch) == []


def test_zero_tax_without_salary_detail_row_uses_native_tax_setup(monkeypatch):
    from hrms.payroll.doctype.payroll_period import payroll_period

    monkeypatch.setattr(
        payroll_period, "get_payroll_period",
        lambda *_: frappe._dict(name="PP-1", start_date="2026-01-01", end_date="2026-12-31"),
    )
    slab = frappe._dict(company="TCL", effective_from="2026-01-01", disabled=0, docstatus=1,
                        custom_tradex_review_status="Approved")
    monkeypatch.setattr(financial_readiness, "frappe", SimpleNamespace(db=SimpleNamespace(
        get_value=lambda *_args, **_kwargs: slab
    )))
    findings = financial_readiness._tax_configuration_findings(
        frappe._dict(company="TCL", start_date="2026-09-01", end_date="2026-09-30"),
        [frappe._dict(name="SS-1", employee="EMP-1", current_payroll_period="PP-1")],
        [],
        {"Tax": frappe._dict(variable_based_on_taxable_salary=1)},
        {"SS-1": frappe._dict(income_tax_slab="SLAB-1")},
    )
    assert findings == []


def test_salary_slip_must_have_native_period_resolved(monkeypatch):
    findings = _tax_check(monkeypatch, current_period="WRONG-PERIOD")
    assert any("TAX_PERIOD_MISSING" == row["code"] for row in findings)


def test_unapproved_or_late_effective_slab_blocks(monkeypatch):
    assert _tax_check(monkeypatch, review="Review Required")[0]["code"] == "TAX_SLAB_UNAPPROVED"
    assert _tax_check(monkeypatch, effective="2026-10-01")[0]["code"] == "TAX_SLAB_MISSING"


def _ready_entry():
    return frappe._dict(
        name="PE-TEST", company="TCL", docstatus=1, status="Submitted",
        salary_slips_created=1, start_date="2026-09-01", end_date="2026-09-30",
        payroll_payable_account="Payable - TCL", custom_tradex_run_key="RUN-1",
        employees=[frappe._dict(employee="EMP-1")],
        get_payroll_cost_centers_for_employee=lambda *_: {"Cost Center - TCL": 100},
    )


def _install_financial_fixture(
    monkeypatch, *, gross=1000, deductions=100, net=900, employees=None, mapping=True,
    payable_disabled=False, component_account_disabled=False,
):
    entry = _ready_entry()
    if employees is not None:
        entry.employees = [frappe._dict(employee=employee) for employee in employees]
    slip = frappe._dict(
        name="SS-TEST", employee="EMP-1", company="TCL", start_date=entry.start_date,
        end_date=entry.end_date, salary_structure="SS-STRUCT",
        current_payroll_period="PP-1", gross_pay=gross, total_deduction=deductions, net_pay=net,
    )
    details = [
        frappe._dict(parent="SS-TEST", parentfield="earnings", salary_component="Basic", amount=gross,
                     do_not_include_in_total=0, do_not_include_in_accounts=0, additional_salary=None, cost_center=None),
        frappe._dict(parent="SS-TEST", parentfield="earnings", salary_component="Zero", amount=0,
                     do_not_include_in_total=0, do_not_include_in_accounts=0, additional_salary=None),
        frappe._dict(parent="SS-TEST", parentfield="deductions", salary_component="Deduction", amount=deductions,
                     do_not_include_in_total=0, do_not_include_in_accounts=0, additional_salary=None, cost_center=None),
    ]
    calls = []
    def get_all(doctype, **kwargs):
        calls.append(doctype)
        if doctype == "Salary Slip": return [slip]
        if doctype == "Employee": return [frappe._dict(name="EMP-1", company="TCL", branch=None, department=None, designation=None, date_of_joining=None)]
        if doctype == "Salary Structure Assignment": return []
        if doctype == "Salary Detail":
            if kwargs.get("filters", {}).get("parenttype") == "Salary Structure":
                return [frappe._dict(parent="SS-STRUCT", salary_component="Basic")]
            return details
        if doctype == "Salary Component":
            return [frappe._dict(name=name, variable_based_on_taxable_salary=0,
                                 is_income_tax_component=0, type="Earning", statistical_component=0)
                    for name in ("Basic", "Deduction", "Zero", "Unused")]
        if doctype == "Tradexcel Policy Exception": return []
        raise AssertionError(doctype)
    def get_value(doctype, name, field, **kwargs):
        if doctype == "Cost Center": return frappe._dict(company="TCL", is_group=0, disabled=0)
        if doctype == "Account":
            disabled = payable_disabled if name == "Payable - TCL" else component_account_disabled
            account = frappe._dict(account_type="Payable", company="TCL", is_group=0,
                                   root_type="Expense", disabled=int(disabled))
            if isinstance(field, list):
                return frappe._dict({key: account.get(key) for key in field})
            return account.get(field)
        if doctype == "Salary Component Account": return "Expense - TCL" if mapping else None
        raise AssertionError((doctype, name, field))
    from erpnext.accounts.doctype.accounting_dimension import accounting_dimension
    monkeypatch.setattr(accounting_dimension, "get_checks_for_pl_and_bs_accounts", lambda: [])

    monkeypatch.setattr(financial_readiness, "frappe", SimpleNamespace(
        get_all=get_all,
        get_doc=lambda *_args, **_kwargs: SimpleNamespace(get_tax_components=lambda: []),
        db=SimpleNamespace(get_value=get_value, sql=lambda *_args, **_kwargs: []),
    ))
    monkeypatch.setattr(financial_readiness, "_previous_slips", lambda *_: {})
    monkeypatch.setattr(component_exceptions, "load_component_rules", lambda *_: [])
    monkeypatch.setattr(
        "tradex_hr.tradexcel_hr.company_context.assert_company_access", lambda *_, **__: None
    )
    return entry, calls


def test_account_mapping_and_reconciliation_use_actual_draft_rows(monkeypatch):
    entry, _ = _install_financial_fixture(monkeypatch)
    result = financial_readiness.inspect_payroll_financial_readiness(entry)
    assert result["status"] == "READY"
    assert result["totals"]["gross"] == 1000
    assert result["totals"]["deductions"] == 100
    assert result["totals"]["net"] == 900


def test_missing_actual_component_account_blocks_but_unreferenced_components_are_ignored(monkeypatch):
    entry, _ = _install_financial_fixture(monkeypatch, mapping=False)
    result = financial_readiness.inspect_payroll_financial_readiness(entry)
    assert {row["reference"] for row in result["blockers"] if row["code"] == "COMPONENT_ACCOUNT_MISSING"} == {"Basic", "Deduction"}


def test_disabled_payable_or_salary_component_account_blocks(monkeypatch):
    entry, _ = _install_financial_fixture(monkeypatch, payable_disabled=True)
    result = financial_readiness.inspect_payroll_financial_readiness(entry)
    assert "PAYROLL_PAYABLE_INVALID" in {row["code"] for row in result["blockers"]}

    entry, _ = _install_financial_fixture(monkeypatch, component_account_disabled=True)
    result = financial_readiness.inspect_payroll_financial_readiness(entry)
    assert "COMPONENT_ACCOUNT_MISSING" in {row["code"] for row in result["blockers"]}


def test_negative_net_and_arithmetic_mismatch_block(monkeypatch):
    entry, _ = _install_financial_fixture(monkeypatch, gross=100, deductions=150, net=-50)
    result = financial_readiness.inspect_payroll_financial_readiness(entry)
    assert "NEGATIVE_NET_PAY" in {row["code"] for row in result["blockers"]}


def test_salary_slip_employee_universe_mismatch_blocks(monkeypatch):
    entry, _ = _install_financial_fixture(monkeypatch, employees=["EMP-1", "EMP-2"])
    result = financial_readiness.inspect_payroll_financial_readiness(entry)
    assert "DRAFT_SLIP_UNIVERSE_MISMATCH" in {row["code"] for row in result["blockers"]}


def test_invalid_cost_center_distribution_blocks(monkeypatch):
    entry, _ = _install_financial_fixture(monkeypatch)
    entry.get_payroll_cost_centers_for_employee = lambda *_: {"Cost Center - TCL": 80}
    result = financial_readiness.inspect_payroll_financial_readiness(entry)
    assert "ACCOUNTING_DIMENSION_MISSING" in {row["code"] for row in result["blockers"]}


def test_missing_mandatory_accounting_dimension_blocks(monkeypatch):
    entry, _ = _install_financial_fixture(monkeypatch)
    from erpnext.accounts.doctype.accounting_dimension import accounting_dimension

    monkeypatch.setattr(accounting_dimension, "get_checks_for_pl_and_bs_accounts", lambda: [
        frappe._dict(fieldname="project", label="Project", default_dimension=None,
                     company="TCL", mandatory_for_pl=1, mandatory_for_bs=0)
    ])
    monkeypatch.setattr(accounting_dimension, "get_accounting_dimensions", lambda **_kwargs: [
        frappe._dict(fieldname="project", document_type="Project")
    ])
    result = financial_readiness.inspect_payroll_financial_readiness(entry)
    assert any(row.get("reference") == "project" for row in result["blockers"])


def test_direct_salary_slip_submit_obeys_financial_readiness(monkeypatch):
    entry = frappe._dict(name="PE-APPROVED", docstatus=1, workflow_state="Tradexcel Payroll Approved",
                         salary_slips_created=1, status="Submitted")
    monkeypatch.setattr(native_payroll, "frappe", SimpleNamespace(
        db=SimpleNamespace(get_value=lambda *_args, **_kwargs: "RUN-1"),
        get_doc=lambda *_args, **_kwargs: entry,
        local=SimpleNamespace(tradex_financial_readiness={}), throw=lambda message, **kwargs: (_ for _ in ()).throw(frappe.ValidationError(str(message))),
    ))
    monkeypatch.setattr(financial_readiness, "inspect_payroll_financial_readiness", lambda *_: {
        "status": "BLOCKED", "blockers": [{"reason": "missing mapping"}]
    })
    with pytest.raises(frappe.ValidationError, match="financial readiness is blocked"):
        native_payroll.validate_salary_slip_before_submit(frappe._dict(payroll_entry=entry.name))


def test_component_exception_effect_keeps_source_and_action_visible(monkeypatch):
    rules = {
        "Housing": {"name": "TPE-12", "component_action": "Override Amount", "component_amount": 250},
        "Meal": {"name": "TPE-13", "component_action": "Exclude", "component_amount": None},
    }
    monkeypatch.setattr(component_exceptions, "resolve_component", lambda _employee, _day, _rules, component: rules.get(component))
    traces = financial_readiness._component_exception_provenance(
        {"name": "EMP-1"}, "2026-09-01", {"Housing": 250}, {"Housing", "Meal"}, rules
    )
    assert traces == [
        {"component": "Housing", "source": "TPE-12", "action": "Override Amount", "amount": financial_readiness._money(250)},
        {"component": "Meal", "source": "TPE-13", "action": "Exclude", "amount": None},
    ]

def test_company_scope_is_checked_before_financial_rows_are_read(monkeypatch):
    seen = []
    def deny(company, **kwargs):
        seen.append(company)
        raise PermissionError("out of scope")
    monkeypatch.setattr("tradex_hr.tradexcel_hr.company_context.assert_company_access", deny)
    with pytest.raises(PermissionError, match="out of scope"):
        financial_readiness.inspect_payroll_financial_readiness(frappe._dict(company="EFL"))
    assert seen == ["EFL"]


@pytest.mark.parametrize("role", ["Tradexcel Payroll Manager", "Tradexcel Payroll Approver", "Tradexcel Owner/Director"])
def test_scoped_payroll_roles_need_an_explicit_company_permission(monkeypatch, role):
    user = "operator@example.com"
    monkeypatch.setattr(company_context, "frappe", SimpleNamespace(
        db=SimpleNamespace(exists=lambda doctype, filters: (
            True if doctype == "Company" else filters == {
                "user": user, "allow": "Company", "for_value": "TCL"
            }
        )),
        session=SimpleNamespace(user=user),
        get_roles=lambda _user: [role],
        has_permission=lambda *_args, **_kwargs: pytest.fail("scoped role must not use broad Company read"),
        throw=lambda message, exc=None: (_ for _ in ()).throw(exc(str(message)) if exc else frappe.ValidationError(str(message))),
        get_list=lambda *_args, **_kwargs: [],
    ))
    assert company_context.assert_company_access("TCL", require_explicit_scope=True) == "TCL"


def test_direct_director_approval_rechecks_financial_readiness(monkeypatch):
    doc = frappe._dict(custom_tradex_run_key="RUN-1", workflow_state="Tradexcel Payroll Pending Director Approval")
    monkeypatch.setattr(financial_readiness, "inspect_payroll_financial_readiness", lambda *_: {
        "status": "BLOCKED", "blockers": [{"reason": "payable account missing"}]
    })
    monkeypatch.setattr(financial_readiness, "frappe", SimpleNamespace(
        throw=lambda message, **kwargs: (_ for _ in ()).throw(frappe.ValidationError(str(message)))
    ))
    with pytest.raises(frappe.ValidationError, match="payable account missing"):
        financial_readiness.validate_payroll_financial_readiness_before_approval(doc)

def test_tax_review_approval_requires_system_manager_and_submitted_native_slab(monkeypatch):
    doc = frappe._dict(name="ITS-1", docstatus=1, custom_tradex_review_status="Approved",
                       custom_tradex_source_reference="NBR circular", flags=frappe._dict())
    doc.flags.tradex_tax_review_action = True
    monkeypatch.setattr(tax_review, "frappe", SimpleNamespace(
        db=SimpleNamespace(get_value=lambda *_args, **_kwargs: frappe._dict(custom_tradex_review_status="Review Required")),
        get_roles=lambda *_: ["System Manager"], session=SimpleNamespace(user="reviewer@example.com"),
        throw=lambda message, *args, **kwargs: (_ for _ in ()).throw(frappe.ValidationError(str(message))),
        PermissionError=frappe.PermissionError,
    ))
    monkeypatch.setattr("tradex_hr.tradexcel_hr.company_context.assert_company_access", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(tax_review, "now_datetime", lambda: "2026-09-23 00:00:00")
    tax_review.validate_income_tax_slab_review(doc)
    assert doc.custom_tradex_reviewed_by == "reviewer@example.com"
    assert doc.custom_tradex_reviewed_at


def test_tax_review_provenance_cannot_be_edited_outside_controlled_action(monkeypatch):
    previous = frappe._dict(
        custom_tradex_review_status="Approved",
        custom_tradex_source_reference="Original law reference",
        custom_tradex_reviewed_by="reviewer@example.com",
        custom_tradex_reviewed_at="2026-09-23 00:00:00",
        custom_tradex_review_notes="Reviewed",
    )
    doc = frappe._dict(
        name="ITS-1", company="TCL", docstatus=1, flags=frappe._dict(),
        custom_tradex_review_status="Approved",
        custom_tradex_source_reference="Changed reference",
        custom_tradex_reviewed_by="reviewer@example.com",
        custom_tradex_reviewed_at="2026-09-23 00:00:00",
        custom_tradex_review_notes="Reviewed",
    )
    monkeypatch.setattr(tax_review, "frappe", SimpleNamespace(
        db=SimpleNamespace(get_value=lambda *_args, **_kwargs: previous),
        get_roles=lambda *_: ["System Manager"],
        session=SimpleNamespace(user="reviewer@example.com"),
        throw=lambda message, *args, **kwargs: (_ for _ in ()).throw(frappe.ValidationError(str(message))),
        PermissionError=frappe.PermissionError,
    ))
    monkeypatch.setattr("tradex_hr.tradexcel_hr.company_context.assert_company_access", lambda *_args, **_kwargs: None)
    with pytest.raises(frappe.ValidationError, match="Approve Tax Configuration action"):
        tax_review.validate_income_tax_slab_review(doc)


def test_tax_review_endpoint_checks_company_scope_before_writing(monkeypatch):
    writes = []
    slab = SimpleNamespace(
        name="ITS-EFL", company="Elegance Footwear Ltd.", docstatus=1,
        flags=SimpleNamespace(), save=lambda **_kwargs: writes.append("save"),
    )
    monkeypatch.setattr(tax_review, "frappe", SimpleNamespace(
        get_roles=lambda *_: ["System Manager"],
        session=SimpleNamespace(user="reviewer@example.com"),
        get_doc=lambda *_args: slab,
    ))
    monkeypatch.setattr(
        "tradex_hr.tradexcel_hr.company_context.assert_company_access",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(frappe.PermissionError("company scope denied")),
    )
    with pytest.raises(frappe.PermissionError, match="company scope denied"):
        tax_review.approve_income_tax_slab("ITS-EFL", "NBR publication")
    assert writes == []
