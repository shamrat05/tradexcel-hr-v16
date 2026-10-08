"""Focused guard tests around native Payroll Correction and Arrear."""
from __future__ import annotations

import os
from datetime import date

import frappe
import pytest

from workforce_suite.workforce_suite import payroll_adjustments as adjustments


@pytest.fixture(scope="module", autouse=True)
def frappe_site():
    frappe.init(
        site=os.environ.get("FRAPPE_TEST_SITE", "hrms-v16.localhost"),
        sites_path=os.environ.get("FRAPPE_TEST_SITES_PATH", "/home/sanchita/frappe-bench-v16/sites"),
        force=True,
    )
    frappe.connect()
    yield
    frappe.destroy()


def _correction():
    return frappe._dict(
        doctype="Payroll Correction",
        name="PAYCORR-TEST",
        employee="EMP-1",
        company="COMPANY_A",
        payroll_period="PERIOD-2026",
        payroll_date="2026-10-01",
        salary_slip_reference="SS-1",
        days_to_reverse=1,
    )


def _source_records(*, employee="EMP-1", company="COMPANY_A", payroll_period="PERIOD-2026",
                    start="2026-09-01", end="2026-09-30", working=30, payment=28):
    period = frappe._dict(
        company="COMPANY_A", start_date=date(2026, 9, 1), end_date=date(2026, 9, 30)
    )
    slip = frappe._dict(
        name="SS-1", docstatus=1, employee=employee, company=company,
        current_payroll_period=payroll_period, start_date=start, end_date=end,
        total_working_days=working, payment_days=payment, leave_without_pay=working-payment,
        payroll_entry=None,
    )
    return period, slip


def _patch_source(monkeypatch, period, slip, *, employee_company="COMPANY_A", target_slips=None):
    monkeypatch.setattr(adjustments, "_authorize_document", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(adjustments, "_validate_managed_source_slip", lambda *_args: None)
    monkeypatch.setattr(
        frappe.db, "get_value",
        lambda doctype, *_args, **_kwargs: employee_company if doctype == "Employee" else None,
    )
    monkeypatch.setattr(
        frappe, "get_doc",
        lambda doctype, *_args, **_kwargs: period if doctype == "Payroll Period" else slip,
    )
    monkeypatch.setattr(frappe, "get_all", lambda *_args, **_kwargs: target_slips or [])


@pytest.mark.parametrize(("slip_changes", "message"), [
    ({"employee": "EMP-2"}, "same employee and company"),
    ({"company": "COMPANY_B"}, "same employee and company"),
    ({"current_payroll_period": "PERIOD-OTHER"}, "selected Payroll Period"),
    ({"start_date": "2026-08-31"}, "inside the selected Payroll Period"),
])
def test_correction_source_must_match_employee_company_and_period(monkeypatch, slip_changes, message):
    period, slip = _source_records()
    slip.update(slip_changes)
    _patch_source(monkeypatch, period, slip)
    with pytest.raises(frappe.ValidationError, match=message):
        adjustments.validate_payroll_correction(_correction())


def test_correction_needs_future_unprocessed_payroll_date(monkeypatch):
    period, slip = _source_records()
    _patch_source(monkeypatch, period, slip)
    correction = _correction()
    correction.payroll_date = "2026-09-30"
    with pytest.raises(frappe.ValidationError, match="after the source Salary Slip"):
        adjustments.validate_payroll_correction(correction)

    correction.payroll_date = "2026-10-01"
    monkeypatch.setattr(frappe, "get_all", lambda *_args, **_kwargs: ["SS-TARGET"])
    with pytest.raises(frappe.ValidationError, match="TARGET_PAYROLL_ALREADY_STARTED"):
        adjustments.validate_payroll_correction(correction)


def test_correction_keeps_native_cumulative_lwp_validation_authoritative(monkeypatch):
    period, slip = _source_records(working=30, payment=29)
    _patch_source(monkeypatch, period, slip)
    correction = _correction()
    correction.days_to_reverse = 2
    with pytest.raises(frappe.ValidationError, match="eligible LWP days"):
        adjustments.validate_payroll_correction(correction)


def test_arrear_selector_is_limited_to_selected_period_and_company(monkeypatch):
    calls = []
    rows = [frappe._dict(name="SS-IN-PERIOD", start_date=date(2026, 9, 1),
                         end_date=date(2026, 9, 30), posting_date=date(2026, 9, 30))]
    monkeypatch.setattr(frappe, "get_all", lambda doctype, **kwargs: calls.append((doctype, kwargs)) or rows)
    arrear = adjustments.WorkforceArrearMixin()
    arrear.employee = "EMP-1"
    arrear.company = "COMPANY_A"
    arrear.payroll_period = "PERIOD-2026"
    arrear.arrear_start_date = date(2026, 9, 1)
    arrear.payroll_period_details = frappe._dict(
        company="COMPANY_A", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31)
    )
    assert [row.name for row in arrear.get_existing_salary_slips()] == ["SS-IN-PERIOD"]
    filters = calls[0][1]["filters"]
    assert filters["company"] == "COMPANY_A"
    assert filters["start_date"] == [">=", date(2026, 9, 1)]
    assert filters["end_date"] == ["<=", date(2026, 12, 31)]


def test_arrear_selector_rejects_period_from_other_company(monkeypatch):
    arrear = adjustments.WorkforceArrearMixin()
    arrear.employee = "EMP-1"
    arrear.company = "COMPANY_A"
    arrear.payroll_period = "PERIOD-COMPANY_B"
    arrear.arrear_start_date = date(2026, 9, 1)
    arrear.payroll_period_details = frappe._dict(company="COMPANY_B")
    with pytest.raises(frappe.ValidationError, match="must match its Payroll Period"):
        arrear.get_existing_salary_slips()


def test_adjustment_cannot_be_cancelled_after_salary_slip_consumes_additional_salary(monkeypatch):
    doc = frappe._dict(
        doctype="Payroll Correction", name="PAYCORR-TEST", company="COMPANY_A",
        workflow_state=adjustments.CANCELLED,
    )
    monkeypatch.setattr(adjustments, "_authorize_document", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        adjustments, "_adjustment_additional_salaries",
        lambda *_args: [frappe._dict(name="ADD-SAL-1")],
    )
    monkeypatch.setattr(
        adjustments, "_additional_salary_consumers",
        lambda names: ["SAL-SLIP-1"] if names == ["ADD-SAL-1"] else [],
    )
    cancelled = []
    monkeypatch.setattr(frappe, "get_doc", lambda *_args, **_kwargs: cancelled.append(True))
    with pytest.raises(frappe.ValidationError, match="ADJUSTMENT_ALREADY_CONSUMED"):
        adjustments.validate_adjustment_before_cancel(doc)
    assert not cancelled


def test_adjustment_additional_salary_cannot_be_cancelled_directly(monkeypatch):
    doc = frappe._dict(ref_doctype="Arrear", ref_docname="ARREAR-1")
    monkeypatch.setattr(frappe.db, "get_value", lambda *_args, **_kwargs: 1)
    with pytest.raises(frappe.ValidationError, match="through its approved workflow"):
        adjustments.validate_additional_salary_before_cancel(doc)


def test_daily_wage_adjustment_readiness_requires_review(monkeypatch):
    slip = frappe._dict(
        name="SS-DW", docstatus=1, employee="EMP-1", company="COMPANY_A",
        start_date="2026-09-01", end_date="2026-09-30",
    )
    monkeypatch.setattr(frappe.db, "get_value", lambda *_args, **_kwargs: "COMPANY_A")
    monkeypatch.setattr(adjustments, "_authorize_company", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(frappe, "has_permission", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(frappe, "get_doc", lambda *_args, **_kwargs: slip)
    result = adjustments.inspect_payroll_adjustment_readiness("SS-DW", "daily_wage")
    assert result["status"] == "DAILY_WAGE_RETRO_ADJUSTMENT_REVIEW_REQUIRED"


def test_overpayment_never_generates_automatic_recovery(monkeypatch):
    slip = frappe._dict(name="SS-OVER", docstatus=1, employee="EMP-1", company="COMPANY_A")
    monkeypatch.setattr(frappe.db, "get_value", lambda *_args, **_kwargs: "COMPANY_A")
    monkeypatch.setattr(adjustments, "_authorize_company", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(frappe, "has_permission", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(frappe, "get_doc", lambda *_args, **_kwargs: slip)
    result = adjustments.inspect_payroll_adjustment_readiness("SS-OVER", "overpayment")
    assert result["status"] == "RETRO_OVERPAYMENT_DECISION_REQUIRED"


def test_adjustment_permission_requires_explicit_company_scope(monkeypatch):
    user = "payroll-maker@example.com"
    monkeypatch.setattr(frappe, "get_roles", lambda _user=None: ["Workforce Payroll Manager"])
    monkeypatch.setattr(frappe.db, "exists", lambda doctype, filters=None: doctype != "User Permission")
    doc = frappe._dict(company="COMPANY_A", docstatus=0, workflow_state=adjustments.DRAFT)
    assert adjustments.adjustment_has_permission(doc, "create", user=user) is False

    monkeypatch.setattr(frappe.db, "exists", lambda *_args, **_kwargs: True)
    assert adjustments.adjustment_has_permission(doc, "create", user=user) is True

    monkeypatch.setattr(frappe, "get_roles", lambda _user=None: ["Workforce Employee/Worker"])
    assert adjustments.adjustment_has_permission(doc, "create", user=user) is False

def test_approver_write_is_limited_to_frappe_approval_transition(monkeypatch):
    user = "payroll-approver@example.test"
    monkeypatch.setattr(frappe, "get_roles", lambda _user=None: ["Workforce Payroll Approver"])
    monkeypatch.setattr(frappe.db, "exists", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        frappe.db,
        "get_value",
        lambda _doctype, _name, field: adjustments.PENDING if field == "workflow_state" else None,
    )
    doc = frappe._dict(
        doctype="Arrear",
        name="AR-TEST",
        owner="payroll-maker@example.test",
        company="COMPANY_A",
        docstatus=1,
        workflow_state=adjustments.APPROVED,
    )
    assert adjustments.adjustment_has_permission(doc, "write", user=user) is True

    monkeypatch.setattr(frappe.db, "get_value", lambda *_args, **_kwargs: adjustments.APPROVED)
    assert adjustments.adjustment_has_permission(doc, "write", user=user) is False

    doc.owner = user
    monkeypatch.setattr(frappe.db, "get_value", lambda *_args, **_kwargs: adjustments.PENDING)
    assert adjustments.adjustment_has_permission(doc, "write", user=user) is False


def test_pending_adjustment_cannot_be_edited_by_maker_or_approver():
    class Meta:
        fields = [frappe._dict(fieldname="employee"), frappe._dict(fieldname="workflow_state")]

    doc = frappe._dict(employee="EMP-2", workflow_state=adjustments.PENDING, meta=Meta())
    old = frappe._dict(employee="EMP-1", workflow_state=adjustments.PENDING)
    doc.get_doc_before_save = lambda: old
    with pytest.raises(frappe.ValidationError, match="cannot be edited"):
        adjustments.validate_adjustment_before_save(doc)


def test_maker_cannot_self_approve_adjustment(monkeypatch):
    user = "same-user@example.com"
    monkeypatch.setattr(frappe, "_dict", frappe._dict)
    monkeypatch.setattr(frappe.session, "user", user, raising=False)
    monkeypatch.setattr(frappe, "get_roles", lambda _user=None: ["Workforce Payroll Approver"])
    monkeypatch.setattr(
        frappe.db, "get_value", lambda *_args, **_kwargs: adjustments.PENDING
    )
    monkeypatch.setattr(adjustments, "_authorize_document", lambda *_args, **_kwargs: None)
    doc = frappe._dict(
        doctype="Payroll Correction", name="PAYCORR-1", owner=user,
        workflow_state=adjustments.APPROVED, company="COMPANY_A",
    )
    with pytest.raises(frappe.ValidationError, match="independent Payroll Approver"):
        adjustments.validate_adjustment_before_submit(doc)


def test_native_adjustment_salary_provenance_is_preserved(monkeypatch):
    created = []

    class FakeAdditionalSalary:
        def __init__(self, values):
            self.values = values
            self.flags = frappe._dict()
            self.docstatus = 0

        def insert(self, ignore_permissions=False):
            assert ignore_permissions is True
            created.append(self.values)
            return self

        def submit(self):
            assert self.flags.ignore_permissions is True
            self.docstatus = 1
            return self

    monkeypatch.setattr(frappe, "get_doc", lambda values: FakeAdditionalSalary(values))
    correction = adjustments.PayrollCorrectionMixin()
    correction.employee = "EMP-1"
    correction.company = "COMPANY_A"
    correction.payroll_date = "2026-10-01"
    correction.currency = "BDT"
    correction.name = "PAYCORR-1"
    correction.earning_arrears = [
        frappe._dict(salary_component="Basic Salary", amount=500)
    ]
    correction.deduction_arrears = []
    correction.create_additional_salary()
    assert len(created) == 1
    assert created[0]["doctype"] == "Additional Salary"
    assert created[0]["amount"] == 500
    assert created[0]["ref_doctype"] == "Payroll Correction"
    assert created[0]["ref_docname"] == "PAYCORR-1"


def test_unconsumed_linked_adjustment_is_cancelled_with_parent(monkeypatch):
    doc = frappe._dict(
        doctype="Arrear", name="ARREAR-1", company="COMPANY_A",
        workflow_state=adjustments.CANCELLED,
    )
    monkeypatch.setattr(adjustments, "_authorize_document", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        adjustments, "_adjustment_additional_salaries",
        lambda *_args: [frappe._dict(name="ADD-SAL-1")],
    )
    monkeypatch.setattr(adjustments, "_additional_salary_consumers", lambda _names: [])
    monkeypatch.setattr(adjustments, "_benefit_ledger_consumers", lambda _doc: [])
    child = frappe._dict(flags=frappe._dict(), cancelled=False)
    child.cancel = lambda: setattr(child, "cancelled", True)
    monkeypatch.setattr(frappe, "get_doc", lambda *_args, **_kwargs: child)
    adjustments.validate_adjustment_before_cancel(doc)
    assert child.cancelled is True
    assert frappe.flags.workforce_adjustment_parent_cancel is False


def test_arrear_readiness_blocks_completed_target_payroll(monkeypatch):
    slip = frappe._dict(
        name="SS-OLD", docstatus=1, employee="EMP-1", company="COMPANY_A",
        start_date="2026-09-01", end_date="2026-09-30", payroll_entry=None,
    )
    monkeypatch.setattr(adjustments, "_authorize_company", lambda _company: None)
    monkeypatch.setattr(frappe, "has_permission", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(frappe.db, "get_value", lambda *_args, **_kwargs: "COMPANY_A")
    monkeypatch.setattr(frappe, "get_doc", lambda doctype, *_args, **_kwargs: slip)
    monkeypatch.setattr(frappe, "get_all", lambda *_args, **_kwargs: ["SS-TARGET"])

    result = adjustments.inspect_payroll_adjustment_readiness(
        "SS-OLD", "salary_structure", "2026-10-01"
    )
    assert result["status"] == "TARGET_PAYROLL_ALREADY_STARTED"

@pytest.mark.parametrize("docstatus", [0, 1])
def test_non_cancelled_target_slip_blocks_adjustment(monkeypatch, docstatus):
    calls = []

    def get_all(doctype, **kwargs):
        calls.append((doctype, kwargs))
        if doctype != "Salary Slip":
            return []
        requested_docstatus = kwargs["filters"].get("docstatus")
        if requested_docstatus == ["<", 2]:
            return ["SS-TARGET"] if docstatus < 2 else []
        if requested_docstatus == 1:
            return ["SS-TARGET"] if docstatus == 1 else []
        return []

    monkeypatch.setattr(frappe, "get_all", get_all)

    assert adjustments._target_payroll_has_started("EMP-1", "COMPANY_A", "2026-10-01")
    slip_query = next(kwargs for doctype, kwargs in calls if doctype == "Salary Slip")
    assert slip_query["filters"]["docstatus"] == ["<", 2]
    assert slip_query["filters"]["employee"] == "EMP-1"
    assert slip_query["filters"]["company"] == "COMPANY_A"


def test_queued_managed_target_payroll_blocks_for_selected_employee(monkeypatch):
    calls = []

    def get_all(doctype, **kwargs):
        calls.append((doctype, kwargs))
        if doctype == "Salary Slip":
            return []
        if doctype == "Payroll Entry":
            return [frappe._dict(
                name="PE-TARGET", status="Queued", salary_slips_created=0,
                custom_workforce_run_key="TRAD-2026-10",
            )]
        if doctype == "Payroll Employee Detail":
            return ["PE-TARGET"]
        return []

    monkeypatch.setattr(frappe, "get_all", get_all)

    assert adjustments._target_payroll_has_started("EMP-1", "COMPANY_A", "2026-10-01")
    detail_query = next(kwargs for doctype, kwargs in calls if doctype == "Payroll Employee Detail")
    assert detail_query["filters"]["employee"] == "EMP-1"
    assert detail_query["filters"]["parent"] == ["in", ["PE-TARGET"]]


@pytest.mark.parametrize(
    "payroll_entry,employee_rows,expected",
    [
        (frappe._dict(name="PE-OTHER", status="Queued", salary_slips_created=0,
                      custom_workforce_run_key="TRAD-2026-10"), [], False),
        (frappe._dict(name="PE-UNMANAGED", status="Queued", salary_slips_created=0,
                      custom_workforce_run_key=""), ["PE-UNMANAGED"], False),
        (frappe._dict(name="PE-DRAFT", status="Draft", salary_slips_created=0,
                      custom_workforce_run_key="TRAD-2026-10"), ["PE-DRAFT"], False),
        (frappe._dict(name="PE-CREATED", status="Submitted", salary_slips_created=1,
                      custom_workforce_run_key="TRAD-2026-10"), ["PE-CREATED"], True),
    ],
)
def test_managed_target_payroll_requires_processing_and_employee_membership(
    monkeypatch, payroll_entry, employee_rows, expected
):
    def get_all(doctype, **kwargs):
        if doctype == "Salary Slip":
            return []
        if doctype == "Payroll Entry":
            return [payroll_entry]
        if doctype == "Payroll Employee Detail":
            return employee_rows
        return []

    monkeypatch.setattr(frappe, "get_all", get_all)

    assert adjustments._target_payroll_has_started("EMP-1", "COMPANY_A", "2026-10-01") is expected


def test_untouched_target_payroll_draft_does_not_block_adjustment(monkeypatch):
    calls = []

    def get_all(doctype, **kwargs):
        calls.append((doctype, kwargs))
        return []

    monkeypatch.setattr(frappe, "get_all", get_all)

    assert not adjustments._target_payroll_has_started("EMP-1", "COMPANY_A", "2026-10-01")


def test_independent_approver_can_validate_submitted_adjustment(monkeypatch):
    period, slip = _source_records()
    real_authorize = adjustments._authorize_document
    _patch_source(monkeypatch, period, slip)
    monkeypatch.setattr(adjustments, "_authorize_document", real_authorize)
    user = "approver@example.com"
    monkeypatch.setattr(frappe, "get_roles", lambda _user=None: ["Workforce Payroll Approver"])
    monkeypatch.setattr(frappe.db, "exists", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(frappe.session, "user", user, raising=False)
    monkeypatch.setattr(
        frappe.db, "exists",
        lambda doctype, filters=None: doctype == "Company"
        or (doctype == "User Permission" and filters.get("for_value") == "COMPANY_A"),
    )
    monkeypatch.setattr(
        frappe.db, "get_value",
        lambda doctype, *_args, **_kwargs: (
            "COMPANY_A" if doctype == "Employee"
            else adjustments.PENDING if doctype == "Payroll Correction"
            else None
        ),
    )
    correction = _correction()
    correction.owner = "maker@example.com"
    correction.workflow_state = adjustments.APPROVED

    adjustments.validate_adjustment_before_submit(correction)


def test_arrear_blocks_component_reduction_even_when_another_component_increases():
    class NativeArrear:
        def compute_component_differences(self, existing_components, new_components):
            return {"earnings": {"Allowance": 100}, "deductions": {}, "accruals": {}}

    class GuardedArrear(adjustments.WorkforceArrearMixin, NativeArrear):
        pass

    arrear = GuardedArrear()
    existing = {"earnings": {"Basic": 1000}, "deductions": {}, "accruals": {}}
    proposed = {"earnings": {"Basic": 900, "Allowance": 100}, "deductions": {}, "accruals": {}}
    with pytest.raises(frappe.ValidationError, match="RETRO_OVERPAYMENT_DECISION_REQUIRED"):
        arrear.compute_component_differences(existing, proposed)


def test_adjustment_workflow_edit_roles_match_doc_permissions():
    from workforce_suite.approval_setup import WORKFLOWS, _transition_row

    for workflow_name in ("Workforce Payroll Correction Approval", "Workforce Arrear Approval"):
        definition = WORKFLOWS[workflow_name]
        for state in (adjustments.DRAFT, adjustments.PENDING, adjustments.REJECTED):
            state_row = next(row for row in definition["states"] if row[0] == state)
            assert state_row[2] == "All"

        approval = next(
            transition for transition in definition["transitions"]
            if transition[0] == adjustments.PENDING and transition[1] == "Approve"
        )
        assert approval[2] == adjustments.APPROVED
        assert approval[3] == "Workforce Payroll Approver"
        assert _transition_row(approval)["allow_self_approval"] == 0



@pytest.mark.parametrize(
    ("doctype", "next_state"),
    [
        ("Payroll Correction", adjustments.APPROVED),
        ("Payroll Correction", adjustments.REJECTED),
        ("Arrear", adjustments.APPROVED),
        ("Arrear", adjustments.REJECTED),
    ],
)
def test_pending_approval_and_rejection_validate_as_reviewer(monkeypatch, doctype, next_state):
    monkeypatch.setattr(
        frappe.db,
        "get_value",
        lambda found_doctype, *_args, **_kwargs: (
            adjustments.PENDING if found_doctype == doctype else None
        ),
    )
    meta = frappe._dict(has_field=lambda fieldname: fieldname == "workflow_state")
    doc = frappe._dict(doctype=doctype, name="ADJUSTMENT-1",
                       workflow_state=next_state, meta=meta)
    assert adjustments._validation_action(doc) == "validate"



def test_maker_cannot_use_reviewer_validation_action(monkeypatch):
    monkeypatch.setattr(adjustments, "_authorize_company", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        frappe, "get_roles", lambda _user=None: ["Workforce Payroll Manager"]
    )
    monkeypatch.setattr(frappe.session, "user", "maker@example.com", raising=False)
    with pytest.raises(frappe.PermissionError):
        adjustments._authorize_document(
            frappe._dict(company="COMPANY_A"), action="validate"
        )



def test_benefit_cancellation_requires_native_same_component_slip_link(monkeypatch):
    queries = []

    def get_all(doctype, filters=None, fields=None, pluck=None, **_kwargs):
        queries.append((doctype, filters, fields, pluck))
        if doctype == "Employee Benefit Ledger" and fields:
            return [frappe._dict(
                name="EBL-ADJUSTMENT",
                employee="EMP-1",
                payroll_period="PERIOD-1",
                salary_component="Flexible Benefit",
                creation="2026-09-01 10:00:00",
            )]
        if doctype == "Employee Benefit Ledger":
            return ["SS-CONSUMED"]
        return ["SS-CONSUMED"]

    monkeypatch.setattr(frappe, "get_all", get_all)
    result = adjustments._benefit_ledger_consumers(
        frappe._dict(doctype="Arrear", name="ARREAR-1")
    )
    assert result == ["SS-CONSUMED"]
    benefit_lookup = queries[1][1]
    assert benefit_lookup["salary_component"] == "Flexible Benefit"
    assert benefit_lookup["reference_doctype"] == ["!=", "Arrear"]
    assert benefit_lookup["salary_slip"] == ["is", "set"]
    assert queries[2][1]["docstatus"] == 1
