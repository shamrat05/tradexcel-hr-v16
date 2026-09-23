import os
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
    current_period="PP-1", assigned_slab="SLAB-1", tax_component="Tax",
):
    from hrms.payroll.doctype.payroll_period import payroll_period
    from hrms.payroll.doctype.salary_structure_assignment import salary_structure_assignment

    period_doc = frappe._dict(name="PP-1", start_date="2026-01-01", end_date="2026-12-31")
    monkeypatch.setattr(payroll_period, "get_payroll_period", lambda *_args, **_kwargs: period_doc if period else None)
    slab = frappe._dict(
        company="TCL", effective_from=effective, disabled=0, docstatus=1,
        custom_tradex_review_status=review,
    )

    def get_value(doctype, name, field, **kwargs):
        if doctype == "Income Tax Slab":
            return slab
        raise AssertionError((doctype, name, field))

    monkeypatch.setattr(
        financial_readiness, "frappe", SimpleNamespace(db=SimpleNamespace(get_value=get_value))
    )
    entry = frappe._dict(company="TCL", start_date="2026-09-01", end_date="2026-09-30")
    slips = [frappe._dict(
        name="SS-1", employee="EMP-1", salary_structure="STRUCT-TAX",
        current_payroll_period=current_period,
    )]
    details = [frappe._dict(salary_component="Tax")]
    components = {"Tax": frappe._dict(variable_based_on_taxable_salary=1, is_income_tax_component=0)}
    monkeypatch.setattr(
        salary_structure_assignment, "get_tax_component", lambda _structure: tax_component
    )
    return financial_readiness._tax_configuration_findings(
        entry, slips, details, components, {"SS-1": frappe._dict(income_tax_slab=assigned_slab)}
    )


def test_non_tax_structure_does_not_require_company_tax_component_slab(monkeypatch):
    from hrms.payroll.doctype.salary_structure_assignment import salary_structure_assignment

    monkeypatch.setattr(salary_structure_assignment, "get_tax_component", lambda _structure: None)
    assert _tax_check(monkeypatch, assigned_slab=None, tax_component=None) == []


def test_only_taxable_structure_requires_period_and_assignment_slab(monkeypatch):
    from hrms.payroll.doctype.payroll_period import payroll_period
    from hrms.payroll.doctype.salary_structure_assignment import salary_structure_assignment

    monkeypatch.setattr(
        payroll_period, "get_payroll_period",
        lambda *_args, **_kwargs: frappe._dict(name="PP-1", start_date="2026-01-01", end_date="2026-12-31"),
    )
    monkeypatch.setattr(
        salary_structure_assignment, "get_tax_component",
        lambda structure: "TDS" if structure == "STRUCT-TAX" else None,
    )
    slab = frappe._dict(company="TCL", effective_from="2026-01-01", disabled=0, docstatus=1,
                        custom_tradex_review_status="Approved")
    monkeypatch.setattr(
        financial_readiness, "frappe",
        SimpleNamespace(db=SimpleNamespace(get_value=lambda *_args, **_kwargs: slab)),
    )
    entry = frappe._dict(company="TCL", start_date="2026-09-01", end_date="2026-09-30")
    slips = [
        frappe._dict(name="SS-TAX", employee="EMP-TAX", salary_structure="STRUCT-TAX",
                     current_payroll_period="PP-1"),
        frappe._dict(name="SS-UNTAXED", employee="EMP-UNTAXED", salary_structure="STRUCT-UNTAXED",
                     current_payroll_period=None),
    ]
    details = [frappe._dict(parentfield="deductions", salary_component="TDS")]
    components = {"TDS": frappe._dict(variable_based_on_taxable_salary=1, is_income_tax_component=1)}
    assignments = {
        "SS-TAX": frappe._dict(income_tax_slab="SLAB-1"),
        "SS-UNTAXED": frappe._dict(income_tax_slab=None),
    }

    assert financial_readiness._tax_configuration_findings(entry, slips, details, components, assignments) == []
    assignments["SS-TAX"].income_tax_slab = None
    findings = financial_readiness._tax_configuration_findings(entry, slips, details, components, assignments)
    assert [(row["code"], row["employee"]) for row in findings] == [
        ("TAX_ASSIGNMENT_MISSING", "EMP-TAX")
    ]


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
        lambda *_args, **_kwargs: frappe._dict(name="PP-1", start_date="2026-01-01", end_date="2026-12-31"),
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
        payroll_payable_account="Payable - TCL", cost_center="Company Cost Center - TCL",
        custom_tradex_run_key="RUN-1",
        employees=[frappe._dict(employee="EMP-1")],
        get_payroll_cost_centers_for_employee=lambda *_args, **_kwargs: {"Cost Center - TCL": 100},
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
        flags=SimpleNamespace(via_payroll_entry=False),
    ))
    monkeypatch.setattr(financial_readiness, "_previous_slips", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(component_exceptions, "load_component_rules", lambda *_args, **_kwargs: [])
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
    entry.get_payroll_cost_centers_for_employee = lambda *_args, **_kwargs: {"Cost Center - TCL": 80}
    result = financial_readiness.inspect_payroll_financial_readiness(entry)
    assert "ACCOUNTING_DIMENSION_MISSING" in {row["code"] for row in result["blockers"]}


def test_missing_payroll_entry_cost_center_blocks_payable_line(monkeypatch):
    entry, _ = _install_financial_fixture(monkeypatch)
    entry.cost_center = None

    result = financial_readiness.inspect_payroll_financial_readiness(entry)

    assert any(
        row["code"] == "ACCOUNTING_DIMENSION_MISSING"
        and row.get("reference") == "Cost Center"
        for row in result["blockers"]
    )


def test_queued_native_submission_worker_is_not_blocked_by_financial_readiness(monkeypatch):
    entry, _ = _install_financial_fixture(monkeypatch)
    entry.status = "Queued"
    financial_readiness.frappe.flags.via_payroll_entry = True

    result = financial_readiness.inspect_payroll_financial_readiness(entry)

    assert result["status"] == "READY"


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


def test_direct_individual_managed_salary_slip_submit_is_blocked(monkeypatch):
    entry = frappe._dict(name="PE-APPROVED", docstatus=1, workflow_state="Tradexcel Payroll Approved",
                         salary_slips_created=1, status="Submitted")
    monkeypatch.setattr(native_payroll, "frappe", SimpleNamespace(
        db=SimpleNamespace(get_value=lambda *_args, **_kwargs: "RUN-1"),
        get_doc=lambda *_args, **_kwargs: entry,
        local=SimpleNamespace(),
        flags=SimpleNamespace(via_payroll_entry=False),
        throw=lambda message, **kwargs: (_ for _ in ()).throw(frappe.ValidationError(str(message))),
    ))
    monkeypatch.setattr(
        "tradex_hr.tradexcel_hr.financial_readiness.inspect_payroll_financial_readiness",
        lambda *_args: pytest.fail("direct Salary Slip submit must be blocked before financial inspection"),
    )
    with pytest.raises(frappe.ValidationError, match="Submit managed Salary Slips from the approved Payroll Entry"):
        native_payroll.validate_salary_slip_before_submit(frappe._dict(payroll_entry=entry.name))


def test_unmanaged_salary_slip_keeps_native_submission_path(monkeypatch):
    monkeypatch.setattr(native_payroll, "frappe", SimpleNamespace(
        db=SimpleNamespace(get_value=lambda *_args, **_kwargs: None),
        flags=SimpleNamespace(via_payroll_entry=False),
    ))
    assert native_payroll.validate_salary_slip_before_submit(
        frappe._dict(payroll_entry="UNMANAGED-PE")
    ) is None


@pytest.fixture
def frappe_site():
    frappe.init(
        site=os.environ.get("FRAPPE_TEST_SITE", "hrms-v16.localhost"),
        sites_path=os.environ.get("FRAPPE_TEST_SITES_PATH", "/home/sanchita/frappe-bench-v16/sites"),
        force=True,
    )
    frappe.connect()
    yield
    frappe.destroy()


def test_native_payroll_batch_sets_authorized_submission_flag(frappe_site, monkeypatch):
    from hrms.payroll.doctype.payroll_entry import payroll_entry as hrms_payroll_entry
    from tradex_hr.tradexcel_hr import payroll_finalization

    monkeypatch.setattr(frappe, "in_test", True)
    monkeypatch.setattr(frappe, "publish_realtime", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(frappe.db, "get_value", lambda *_args, **_kwargs: "RUN-1")
    monkeypatch.setattr(financial_readiness, "inspect_payroll_financial_readiness", lambda *_args, **_kwargs: {
        "status": "READY", "blockers": []
    })
    monkeypatch.setattr(payroll_finalization, "readiness_for_batch_submission", lambda *_args, **_kwargs: {
        "status": "READY", "blockers": []
    })
    calls = []
    slip = frappe._dict(payroll_entry="PE-APPROVED", net_pay=900)

    def submit():
        assert frappe.flags.via_payroll_entry is True
        native_payroll.validate_salary_slip_before_submit(slip)
        calls.append("slip")

    slip.submit = submit
    entry = frappe._dict(
        name="PE-APPROVED", docstatus=1, workflow_state="Tradexcel Payroll Approved",
        salary_slips_created=1, status="Queued",
        make_accrual_jv_entry=lambda submitted: calls.append(("accrual", len(submitted))),
        email_salary_slip=lambda _submitted: None,
        db_set=lambda _values: None,
    )

    def get_doc(doctype, _name):
        return slip if doctype == "Salary Slip" else entry

    monkeypatch.setattr(frappe, "get_doc", get_doc)
    monkeypatch.setattr(hrms_payroll_entry, "show_payroll_submission_status", lambda *_args: None)
    hrms_payroll_entry.submit_salary_slips_for_employees(entry, [("SS-1",)], publish_progress=False)

    assert calls == ["slip", ("accrual", 1)]
    assert frappe.flags.via_payroll_entry is False


def test_direct_salary_slip_submit_obeys_financial_readiness(monkeypatch):
    from tradex_hr.tradexcel_hr import payroll_finalization

    entry = frappe._dict(name="PE-APPROVED", docstatus=1, workflow_state="Tradexcel Payroll Approved",
                         salary_slips_created=1, status="Submitted")
    monkeypatch.setattr(native_payroll, "frappe", SimpleNamespace(
        db=SimpleNamespace(get_value=lambda *_args, **_kwargs: "RUN-1"),
        get_doc=lambda *_args, **_kwargs: entry,
        local=SimpleNamespace(tradex_financial_readiness={}),
        flags=SimpleNamespace(via_payroll_entry=True),
        throw=lambda message, **kwargs: (_ for _ in ()).throw(frappe.ValidationError(str(message))),
    ))
    monkeypatch.setattr(financial_readiness, "inspect_payroll_financial_readiness", lambda *_args, **_kwargs: {
        "status": "BLOCKED", "blockers": [{"reason": "missing mapping"}]
    })
    monkeypatch.setattr(payroll_finalization, "readiness_for_batch_submission", lambda *_args, **_kwargs: {
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


@pytest.mark.parametrize(
    ("user", "roles", "has_scope", "allowed"),
    [
        ("Administrator", ["Administrator"], False, True),
        ("system@example.com", ["System Manager"], False, True),
        ("director@example.com", ["Tradexcel Owner/Director"], True, True),
        ("director@example.com", ["Tradexcel Owner/Director"], False, False),
    ],
)
def test_tax_review_company_scope_role_matrix(monkeypatch, user, roles, has_scope, allowed):
    monkeypatch.setattr(company_context, "frappe", SimpleNamespace(
        db=SimpleNamespace(exists=lambda doctype, filters: (
            True if doctype == "Company" else has_scope
        )),
        session=SimpleNamespace(user=user),
        get_roles=lambda _user: roles,
        has_permission=lambda *_args, **_kwargs: True,
        get_list=lambda *_args, **_kwargs: [{"name": "TCL"}],
        PermissionError=frappe.PermissionError,
        throw=lambda message, exc=None: (_ for _ in ()).throw(
            (exc or frappe.ValidationError)(str(message))
        ),
    ))
    if allowed:
        assert company_context.assert_company_access("TCL", require_explicit_scope=True) == "TCL"
    else:
        with pytest.raises(frappe.PermissionError, match="explicit Company User Permission"):
            company_context.assert_company_access("TCL", require_explicit_scope=True)


def test_direct_director_approval_rechecks_financial_readiness(monkeypatch):
    doc = frappe._dict(custom_tradex_run_key="RUN-1", workflow_state="Tradexcel Payroll Pending Director Approval")
    monkeypatch.setattr(financial_readiness, "inspect_payroll_financial_readiness", lambda *_args, **_kwargs: {
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
        get_roles=lambda *_args, **_kwargs: ["System Manager"], session=SimpleNamespace(user="reviewer@example.com"),
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
        get_roles=lambda *_args, **_kwargs: ["System Manager"],
        session=SimpleNamespace(user="reviewer@example.com"),
        throw=lambda message, *args, **kwargs: (_ for _ in ()).throw(frappe.ValidationError(str(message))),
        PermissionError=frappe.PermissionError,
    ))
    monkeypatch.setattr("tradex_hr.tradexcel_hr.company_context.assert_company_access", lambda *_args, **_kwargs: None)
    with pytest.raises(frappe.ValidationError, match="Approve Tax Configuration action"):
        tax_review.validate_income_tax_slab_review(doc)


def test_tax_review_endpoint_checks_company_scope_before_writing(monkeypatch):
    writes = []
    scope_checks = []
    slab = SimpleNamespace(
        name="ITS-EFL", company="Elegance Footwear Ltd.", docstatus=1,
        flags=SimpleNamespace(), save=lambda **_kwargs: writes.append("save"),
    )
    monkeypatch.setattr(tax_review, "frappe", SimpleNamespace(
        get_roles=lambda *_args, **_kwargs: ["System Manager"],
        session=SimpleNamespace(user="reviewer@example.com"),
        get_doc=lambda *_args: slab,
    ))

    def deny_scope(company, **kwargs):
        scope_checks.append((company, kwargs.get("require_explicit_scope")))
        raise frappe.PermissionError("company scope denied")

    monkeypatch.setattr(
        "tradex_hr.tradexcel_hr.company_context.assert_company_access", deny_scope
    )
    with pytest.raises(frappe.PermissionError, match="company scope denied"):
        tax_review.approve_income_tax_slab("ITS-EFL", "NBR publication")
    assert scope_checks == [("Elegance Footwear Ltd.", True)]
    assert writes == []


@pytest.mark.parametrize(
    ("user", "roles", "allowed"),
    [
        ("Administrator", ["Administrator"], True),
        ("system@example.com", ["System Manager"], True),
        ("director@example.com", ["Tradexcel Owner/Director"], True),
        ("payroll@example.com", ["Tradexcel Payroll Manager"], False),
    ],
)
def test_tax_review_reviewer_role_matrix(monkeypatch, user, roles, allowed):
    def throw(message, exc=None):
        raise (exc or RuntimeError)(message)

    monkeypatch.setattr(tax_review, "frappe", SimpleNamespace(
        session=SimpleNamespace(user=user),
        get_roles=lambda _user: roles,
        PermissionError=frappe.PermissionError,
        throw=throw,
    ))
    if allowed:
        assert tax_review._require_reviewer() is None
    else:
        with pytest.raises(frappe.PermissionError, match="System Manager or Tradexcel Owner/Director"):
            tax_review._require_reviewer()


def test_native_tax_calculation_and_financial_tax_readiness_use_same_synthetic_setup(frappe_site, monkeypatch):
    from erpnext.setup.doctype.company.company import Company
    from hrms.payroll.doctype.salary_structure.salary_structure import make_salary_slip

    # Avoid touching staging's global Mode of Payment rows and its incomplete
    # country-specific tax fixtures while the disposable chart is created.
    import erpnext.setup.doctype.company.company as company_module
    import hrms.overrides.company as hrms_company
    monkeypatch.setattr(Company, "set_mode_of_payment_account", lambda _self: None)
    monkeypatch.setattr(company_module, "install_country_fixtures", lambda *_args: None)
    monkeypatch.setattr(hrms_company, "set_expense_claim_type_accounts", lambda *_args: None)
    monkeypatch.setattr(hrms_company, "set_default_hr_accounts", lambda *_args: None)

    token = frappe.generate_hash(6).upper()
    company_name = f"Tradexcel Tax Test {token}"
    company_abbr = f"TT{token[:3]}"
    created = {"company": None, "fiscal_year": None, "period": None, "slab": None, "components": [],
               "structure": None, "assignments": [], "employees": [], "slips": [], "holiday_list": None, "holiday_assignment": None}

    def cleanup_doc(doctype, name):
        if not name or not frappe.db.exists(doctype, name):
            return
        doc = frappe.get_doc(doctype, name)
        if doc.docstatus == 1:
            doc.cancel()
        frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)

    try:
        company = frappe.new_doc("Company")
        company.company_name = company_name
        company.abbr = company_abbr
        company.default_currency = "BDT"
        company.country = "Bangladesh"
        company.create_chart_of_accounts_based_on = "Existing Company"
        company.existing_company = "Tradexcel Ceramics Ltd."
        company.set_mode_of_payment_account = lambda: None
        # Save the intended identity before on_update; if setup fails after the
        # row is inserted, finally can still remove this partial test company.
        created["company"] = company_name
        company.save()
        created["company"] = company.name

        payable = frappe.db.get_value(
            "Account", {"company": company.name, "is_group": 0, "root_type": "Liability"}, "name"
        )
        expense = frappe.db.get_value(
            "Account", {"company": company.name, "is_group": 0, "root_type": "Expense"}, "name"
        )
        payment_account = frappe.db.get_value(
            "Account", {"company": company.name, "is_group": 0, "root_type": "Asset",
                        "account_currency": "BDT"}, "name"
        )
        assert payable and expense and payment_account
        frappe.db.set_value("Account", payable, "account_type", "Payable")
        frappe.db.set_value("Company", company.name, "default_payroll_payable_account", payable)

        fiscal_year = frappe.get_doc({
            "doctype": "Fiscal Year", "year": f"Tax Test FY {token}",
            "year_start_date": "2026-01-01", "year_end_date": "2026-12-31",
            "companies": [{"company": company.name}],
        }).insert()
        created["fiscal_year"] = fiscal_year.name

        holiday_list = frappe.get_doc({
            "doctype": "Holiday List", "holiday_list_name": f"Tax Test Holidays {token}",
            "from_date": "2026-01-01", "to_date": "2026-12-31", "holidays": [],
        }).insert()
        created["holiday_list"] = holiday_list.name
        frappe.db.set_value("Company", company.name, "default_holiday_list", holiday_list.name)
        holiday_assignment = frappe.get_doc({
            "doctype": "Holiday List Assignment", "applicable_for": "Company",
            "assigned_to": company.name, "employee_company": company.name,
            "holiday_list": holiday_list.name, "from_date": "2026-01-01",
        }).insert()
        holiday_assignment.submit()
        created["holiday_assignment"] = holiday_assignment.name

        period = frappe.get_doc({
            "doctype": "Payroll Period", "name": f"Tax Test Period {token}",
            "company": company.name, "start_date": "2026-01-01", "end_date": "2026-12-31",
        }).insert()
        created["period"] = period.name
        from hrms.payroll.doctype.payroll_period.payroll_period import get_payroll_period
        get_payroll_period.clear_cache()

        slab = frappe.get_doc({
            "doctype": "Income Tax Slab", "name": f"Tax Test Slab {token}",
            "company": company.name, "currency": "BDT", "effective_from": "2026-01-01",
            "slabs": [
                {"from_amount": 250000, "to_amount": 500000, "percent_deduction": 5,
                 "condition": "annual_taxable_earning > 500000"},
                {"from_amount": 500001, "to_amount": 1000000, "percent_deduction": 20},
                {"from_amount": 1000001, "percent_deduction": 30},
            ],
        }).insert()
        created["slab"] = slab.name
        slab.submit()
        tax_review.approve_income_tax_slab(
            slab.name, "Synthetic HRMS integration fixture; not statutory guidance"
        )
        slab.reload()

        base_component = f"Tax Test Base {token}"
        tax_component = f"Tax Test TDS {token}"
        for name, abbr, component_type, account, variable in (
            (base_component, f"B{token[:3]}", "Earning", expense, 0),
            (tax_component, f"T{token[:3]}", "Deduction", payable, 1),
        ):
            component = frappe.get_doc({
                "doctype": "Salary Component", "salary_component": name,
                "salary_component_abbr": abbr, "type": component_type,
                "depends_on_payment_days": 0, "variable_based_on_taxable_salary": variable,
                "is_tax_applicable": 1 if component_type == "Earning" else 0,
                "accounts": [{"company": company.name, "account": account}],
            }).insert()
            created["components"].append(component.name)

        structure_name = f"Tax Test Structure {token}"
        structure = frappe.get_doc({
            "doctype": "Salary Structure", "name": structure_name, "company": company.name,
            "currency": "BDT", "payroll_frequency": "Monthly", "is_active": "Yes",
            "payment_account": payment_account,
            "earnings": [{"salary_component": base_component, "abbr": f"B{token[:3]}",
                          "amount": 0, "amount_based_on_formula": 1, "formula": "base",
                          "depends_on_payment_days": 1}],
            "deductions": [{"salary_component": tax_component, "abbr": f"T{token[:3]}",
                            "amount": 0, "depends_on_payment_days": 0}],
        }).insert()
        created["structure"] = structure.name
        structure.submit()
        from hrms.payroll.doctype.salary_structure_assignment.salary_structure_assignment import get_tax_component
        assert get_tax_component(structure.name) == tax_component

        results = []
        for label, base in (("positive", 150000), ("zero", 1000)):
            employee_doc = frappe.get_doc({
                "doctype": "Employee",
                "first_name": f"Tax {label} {token}",
                "company": company.name,
                "date_of_birth": "1990-05-08",
                "date_of_joining": "2020-01-01",
                "gender": "Female",
                "employment_type": "Intern",
                "status": "Active",
            }).insert()
            employee = employee_doc.name
            created["employees"].append(employee)
            assignment = frappe.get_doc({
                "doctype": "Salary Structure Assignment", "employee": employee,
                "company": company.name, "currency": "BDT", "salary_structure": structure.name,
                "from_date": "2026-01-01", "base": base,
                "payroll_payable_account": payable, "income_tax_slab": slab.name,
            }).insert()
            assignment.submit()
            created["assignments"].append(assignment.name)

            slip = make_salary_slip(
                structure.name, employee=employee, posting_date="2026-09-30"
            )
            slip.insert()
            created["slips"].append(slip.name)
            assert slip.current_payroll_period == period.name
            assert slip._salary_structure_assignment.income_tax_slab == slab.name
            tax_amount = sum(
                row.amount for row in slip.deductions if row.salary_component == tax_component
            )
            results.append((slip, assignment, tax_amount))

        assert results[0][2] > 0
        assert results[1][2] == 0

        from hrms.payroll.doctype.salary_structure_assignment.salary_structure_assignment import (
            get_tax_component,
        )
        assert get_tax_component(structure.name) == tax_component

        details = [row for slip, _assignment, _amount in results
                   for row in [*slip.earnings, *slip.deductions]]
        component_docs = {
            name: frappe.get_doc("Salary Component", name)
            for name in {row.salary_component for row in details}
        }
        assignments_by_slip = {
            slip.name or f"PREVIEW-{index}": assignment
            for index, (slip, assignment, _amount) in enumerate(results)
        }
        # Tax readiness inspects the native-calculated draft slips and their
        # matching submitted assignments; this test never submits a Salary Slip.
        test_slips = [slip for slip, _assignment, _amount in results]
        entry = frappe._dict(company=company.name, start_date="2026-09-01", end_date="2026-09-30")
        findings = financial_readiness._tax_configuration_findings(
            entry, test_slips, details, component_docs, assignments_by_slip
        )
        assert findings == []
    finally:
        frappe.set_user("Administrator")
        for doctype, key in (
            ("Salary Slip", "slips"),
            ("Salary Structure Assignment", "assignments"),
            ("Salary Structure", "structure"),
            ("Salary Component", "components"),
            ("Income Tax Slab", "slab"),
            ("Payroll Period", "period"),
            ("Fiscal Year", "fiscal_year"),
            ("Employee", "employees"),
            ("Holiday List Assignment", "holiday_assignment"),
            ("Holiday List", "holiday_list"),
        ):
            values = created[key] if isinstance(created[key], list) else [created[key]]
            for value in values:
                cleanup_doc(doctype, value)
        if created["company"] and frappe.db.exists("Company", created["company"]):
            frappe.delete_doc("Company", created["company"], force=True, ignore_permissions=True)
        frappe.db.commit()
