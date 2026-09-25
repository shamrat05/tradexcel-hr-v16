"""Synthetic decision-boundary tests for maternity and workplace welfare."""

from datetime import date
import os

import frappe
import pytest

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


from tradex_hr.tradexcel_hr.maternity_welfare import (
    calculate_maternity_benefit_preview,
    evaluate_first_aid_readiness,
    service_months_result,
)


def test_service_months_uses_calendar_months_and_rule_value():
    assert service_months_result(date(2026, 1, 31), date(2026, 7, 31), 6) == "MEETS"
    assert service_months_result(date(2026, 1, 31), date(2026, 7, 30), 6) == "BELOW"
    assert service_months_result(None, date(2026, 7, 31), 6) == "REVIEW"


def test_maternity_review_validates_service_against_event_date(monkeypatch):
    from types import SimpleNamespace
    import pytest
    from tradex_hr.tradexcel_hr import maternity_welfare as module

    employee = SimpleNamespace(company="Synthetic Company", date_of_joining=date(2026, 1, 31))
    rule = SimpleNamespace(legal_regime="Bangladesh Labour Act", minimum_service_months=6, maternity_leave_type="Synthetic Maternity")
    doc = SimpleNamespace(
        company="Synthetic Company", employee="EMP-SYNTHETIC", branch=None,
        rule_set="RULE-SYNTHETIC", actual_delivery_date=date(2026, 7, 30),
        expected_delivery_date=date(2026, 7, 31), notice_date=date(2026, 5, 1),
        benefit_eligibility="Eligible", eligibility_reason="Eligible",
        review_notes="synthetic review", evidence_reference="synthetic evidence",
        native_leave_applications=[], historical_work_evidence_reviewed=0,
        get=lambda key: [],
    )
    monkeypatch.setattr(module, "_scope", lambda _doc: None)
    monkeypatch.setattr(module, "_freeze_submitted_fields", lambda *_: None)
    monkeypatch.setattr(module, "_employee_row", lambda _employee: employee)
    monkeypatch.setattr(module, "_validate_maternity_establishment", lambda *_args: None)
    monkeypatch.setattr(module, "_validate_no_overlapping_maternity_review", lambda *_args: None)
    monkeypatch.setattr(module, "_approved_rule", lambda *_: rule)
    monkeypatch.setattr(module, "_historical_work_evidence", lambda *_: False)
    monkeypatch.setattr(module.frappe, "throw", lambda message, title=None: (_ for _ in ()).throw(ValueError(title or str(message))))

    with pytest.raises(ValueError, match="MATERNITY_SERVICE_REQUIREMENT_NOT_MET"):
        module.validate_maternity_review(doc)


def test_maternity_preview_reads_divisor_and_never_defaults_it():
    assert calculate_maternity_benefit_preview(26000, 26, 120) == 120000
    assert calculate_maternity_benefit_preview(26000, 0, 120) is None
    assert calculate_maternity_benefit_preview(None, 26, 120) is None


def test_first_aid_readiness_uses_reviewed_parameters_only():
    ready = evaluate_first_aid_readiness({
        "first_aid_applicability": "Applicable",
        "reviewed_worker_count": 301,
        "workers_per_first_aid_box": 150,
        "first_aid_box_count": 3,
        "trained_custodian_evidence": "synthetic reference",
        "first_aid_accessibility_evidence": "synthetic access reference",
    })
    assert ready == []

    findings = evaluate_first_aid_readiness({
        "first_aid_applicability": "Applicable",
        "reviewed_worker_count": 301,
        "workers_per_first_aid_box": 150,
        "first_aid_box_count": 2,
        "trained_custodian_evidence": "",
    })
    assert {item["code"] for item in findings} == {
        "FIRST_AID_BOX_COUNT_INSUFFICIENT",
        "FIRST_AID_TRAINED_CUSTODIAN_REQUIRED",
        "FIRST_AID_ACCESSIBILITY_EVIDENCE_REQUIRED",
    }


def test_unreviewed_and_not_applicable_welfare_are_distinct():
    assert evaluate_first_aid_readiness({"first_aid_applicability": "Review Required"})[0]["code"] == "FIRST_AID_APPLICABILITY_REVIEW_REQUIRED"
    assert evaluate_first_aid_readiness({"first_aid_applicability": "Not Applicable"}) == []


def test_first_aid_threshold_is_taken_from_reviewed_rule_not_code():
    assert evaluate_first_aid_readiness({
        "first_aid_applicability": "Applicable",
        "reviewed_worker_count": 151,
        "workers_per_first_aid_box": 100,
        "first_aid_box_count": 2,
        "trained_custodian_evidence": "reference",
        "first_aid_accessibility_evidence": "synthetic access reference",
    }) == []


def test_approved_welfare_review_freezes_accessibility_evidence():
    from tradex_hr.tradexcel_hr.maternity_welfare import WELFARE_FROZEN_FIELDS

    assert "first_aid_accessibility_evidence" in WELFARE_FROZEN_FIELDS


def test_child_room_needs_reviewed_applicability_and_evidence():
    from tradex_hr.tradexcel_hr.maternity_welfare import evaluate_child_room_readiness

    assert evaluate_child_room_readiness({"child_room_applicability": "Review Required"}) == [
        {"code": "CHILD_ROOM_APPLICABILITY_REVIEW_REQUIRED"}
    ]
    assert evaluate_child_room_readiness({
        "child_room_applicability": "Applicable",
        "child_room_status": "Available",
        "child_room_evidence_reference": "synthetic",
    }) == []
    assert evaluate_child_room_readiness({
        "child_room_applicability": "Applicable",
        "child_room_status": "Not Available",
    }) == [{"code": "CHILD_ROOM_FACILITY_REQUIRED"}]
    assert evaluate_child_room_readiness({"child_room_applicability": "Not Applicable"}) == []


def test_welfare_findings_are_not_payroll_readiness_codes():
    from tradex_hr.tradexcel_hr.maternity_welfare import evaluate_child_room_readiness

    findings = evaluate_child_room_readiness({"child_room_applicability": "Review Required"})
    assert findings[0]["code"].startswith("CHILD_ROOM")
    assert "Payroll Entry" not in findings[0]["code"]


def test_sensitive_roles_exclude_payroll_and_factory_roles(monkeypatch):
    from tradex_hr.tradexcel_hr import maternity_welfare as module

    monkeypatch.setattr(module.frappe, "get_roles", lambda _user=None: ["Tradexcel Payroll Manager"])
    assert module.maternity_sensitive_has_permission(
        {"company": "Synthetic Company"}, ptype="read", user="payroll@example.invalid"
    ) is False
    monkeypatch.setattr(module.frappe, "get_roles", lambda _user=None: ["Tradexcel Factory Supervisor"])
    assert module.maternity_sensitive_has_permission(
        {"company": "Synthetic Company"}, ptype="read", user="supervisor@example.invalid"
    ) is False


def test_payroll_finding_codes_are_generic_and_do_not_include_sensitive_case_fields(monkeypatch):
    from tradex_hr.tradexcel_hr import maternity_welfare as module

    monkeypatch.setattr(module, "prepare_maternity_payroll_context", lambda *_args: {
        "EMP-SYNTHETIC": [
            "MATERNITY_BENEFIT_PAYMENT_PATH_REVIEW_REQUIRED",
            "MATERNITY_LEAVE_CONFIGURATION_MISMATCH",
        ]
    })
    result = module.maternity_payroll_review_codes("EMP-SYNTHETIC", "2026-01-01", "2026-01-31", company="Synthetic Company")
    assert result == [
        "MATERNITY_BENEFIT_PAYMENT_PATH_REVIEW_REQUIRED",
        "MATERNITY_LEAVE_CONFIGURATION_MISMATCH",
    ]
    assert "expected_delivery_date" not in repr(result)
    assert "eligibility_reason" not in repr(result)


def test_maternity_payroll_context_batches_cases_and_returns_only_generic_codes(monkeypatch):
    from types import SimpleNamespace
    from tradex_hr.tradexcel_hr import maternity_welfare as module

    review = SimpleNamespace(
        employee="EMP-SYNTHETIC", company="Synthetic Company", rule_set="RULE-SYNTHETIC",
        actual_delivery_date=date(2026, 9, 20), expected_delivery_date=date(2026, 9, 25),
        benefit_eligibility="Eligible",
    )
    rule = SimpleNamespace(
        docstatus=1, company="Synthetic Company", pre_delivery_days=60, post_delivery_days=60,
        maternity_leave_type="TEST Maternity", leave_is_lwp=0, leave_is_ppl=0,
        leave_include_holidays=1, leave_max_continuous_days=120,
    )
    calls = []
    monkeypatch.setattr(module, "_maternity_schema_installed", lambda: True)
    monkeypatch.setattr(module.frappe, "get_all", lambda _doctype, **kwargs: calls.append(kwargs) or [review])
    monkeypatch.setattr(module.frappe, "get_doc", lambda *_args: rule)
    monkeypatch.setattr(module, "_validate_native_leave_type", lambda _rule: [])
    context = module.prepare_maternity_payroll_context(
        "Synthetic Company", ["EMP-SYNTHETIC", "EMP-OTHER"], date(2026, 9, 1), date(2026, 9, 30)
    )
    assert context == {
        "EMP-SYNTHETIC": ["MATERNITY_BENEFIT_PAYMENT_PATH_REVIEW_REQUIRED"]
    }
    assert len(calls) == 1
    assert calls[0]["filters"]["employee"] == ["in", ["EMP-SYNTHETIC", "EMP-OTHER"]]
    assert "actual_delivery_date" not in repr(context)
    assert "eligibility_reason" not in repr(context)


def test_expected_amount_preview_is_not_a_salary_or_payroll_mutation():
    from tradex_hr.tradexcel_hr import maternity_welfare as module

    assert calculate_maternity_benefit_preview("26000", "26", "60") == 60000
    assert not hasattr(module, "create_maternity_additional_salary")
    assert not hasattr(module, "create_maternity_journal_entry")


def test_separation_maternity_review_gate_runs_at_submit_not_draft_save():
    from tradex_hr.hooks import doc_events

    assert doc_events["Employee Separation"]["validate"] == "tradex_hr.tradexcel_hr.employee_separation.validate_employee_separation"
    assert doc_events["Employee Separation"]["before_submit"] == "tradex_hr.tradexcel_hr.maternity_welfare.validate_maternity_employee_separation"


def test_pending_maternity_eligibility_blocks_with_only_generic_code(monkeypatch):
    from tradex_hr.tradexcel_hr import maternity_welfare as module

    monkeypatch.setattr(module, "prepare_maternity_payroll_context", lambda *_args: {
        "EMP-SYNTHETIC": ["MATERNITY_BENEFIT_ELIGIBILITY_REVIEW_REQUIRED"]
    })
    result = module.maternity_payroll_review_codes("EMP-SYNTHETIC", "2026-01-01", "2026-01-31", company="Synthetic Company")
    assert result == ["MATERNITY_BENEFIT_ELIGIBILITY_REVIEW_REQUIRED"]


def test_leave_only_review_does_not_create_statutory_payment_blocker(monkeypatch):
    from tradex_hr.tradexcel_hr import maternity_welfare as module

    monkeypatch.setattr(module, "prepare_maternity_payroll_context", lambda *_args: {})
    assert module.maternity_payroll_review_codes("EMP-SYNTHETIC", "2026-01-01", "2026-01-31", company="Synthetic Company") == []


def test_general_and_epz_rate_methods_require_different_explicit_inputs():
    from tradex_hr.tradexcel_hr.maternity_welfare import benefit_rate_configuration_error

    assert benefit_rate_configuration_error("Monthly Gross / Divisor", 26, None) is None
    assert benefit_rate_configuration_error("Monthly Gross / Divisor", None, 3) == "MATERNITY_RATE_DIVISOR_REQUIRED"
    assert benefit_rate_configuration_error("Average Wages / Actual Days Worked", None, 3) is None
    assert benefit_rate_configuration_error("Average Wages / Actual Days Worked", 26, None) == "MATERNITY_REFERENCE_PERIOD_REQUIRED"
    assert benefit_rate_configuration_error("Manual Legal Review", None, None) is None


def test_maternity_approval_is_maker_checker_and_company_scoped(monkeypatch):
    from types import SimpleNamespace
    import pytest
    from tradex_hr.tradexcel_hr import maternity_welfare as module

    monkeypatch.setattr(module.frappe, "session", SimpleNamespace(user="reviewer"))
    monkeypatch.setattr(module, "_roles", lambda _user=None: {"Tradexcel Owner/Director"})
    monkeypatch.setattr(module, "_scope", lambda _doc: None)
    doc = SimpleNamespace(company="Synthetic Company", owner="maker")
    module._assert_maker_checker(doc)
    doc.owner = "reviewer"
    monkeypatch.setattr(module.frappe, "throw", lambda *_a, **_k: (_ for _ in ()).throw(PermissionError()))
    with pytest.raises(PermissionError):
        module._assert_maker_checker(doc)


def test_protected_period_blocks_actual_attendance_ot_and_field_duty(monkeypatch):
    from types import SimpleNamespace
    import pytest
    from tradex_hr.tradexcel_hr import maternity_welfare as module

    monkeypatch.setattr(module, "_maternity_schema_installed", lambda: True)
    monkeypatch.setattr(module, "_review_for_protected_period", lambda *_: (object(), object()))
    monkeypatch.setattr(module.frappe, "throw", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("blocked")))
    attendance = SimpleNamespace(employee="EMP-SYNTHETIC", attendance_date=date(2026, 9, 1), status="Present", working_hours=6)
    with pytest.raises(RuntimeError, match="blocked"):
        module.validate_maternity_attendance(attendance)
    overtime = SimpleNamespace(employee="EMP-SYNTHETIC", start_date=date(2026, 9, 1), end_date=date(2026, 9, 1))
    with pytest.raises(RuntimeError, match="blocked"):
        module.validate_maternity_overtime(overtime)
    duty = SimpleNamespace(employee="EMP-SYNTHETIC", duty_date=date(2026, 9, 1))
    with pytest.raises(RuntimeError, match="blocked"):
        module.validate_maternity_field_duty(duty)


def test_work_protection_period_is_independent_of_benefit_period(monkeypatch):
    from types import SimpleNamespace
    from tradex_hr.tradexcel_hr import maternity_welfare as module

    review = SimpleNamespace(
        actual_delivery_date=date(2026, 9, 1),
        expected_delivery_date=date(2026, 9, 10),
        rule_set="RULE-SYNTHETIC",
        benefit_eligibility="Eligible",
    )
    rule = SimpleNamespace(
        docstatus=1, company="Synthetic Company", legal_regime="Bangladesh Labour Act",
        pre_delivery_days=10, post_delivery_days=30, post_delivery_work_protection_days=60,
    )
    monkeypatch.setattr(module, "_maternity_schema_installed", lambda: True)
    monkeypatch.setattr(module.frappe, "get_all", lambda *_args, **_kwargs: ["CASE-SYNTHETIC"])
    monkeypatch.setattr(module.frappe, "get_doc", lambda doctype, _name: review if doctype == module.MATERNITY_REVIEW else rule)

    active = module._active_maternity_reviews("EMP-SYNTHETIC", date(2026, 10, 15), date(2026, 10, 15))

    assert active == [(review, rule, date(2026, 9, 1), date(2026, 10, 30))]


def test_zero_work_on_leave_is_not_treated_as_protected_actual_work(monkeypatch):
    from types import SimpleNamespace
    from tradex_hr.tradexcel_hr import maternity_welfare as module

    called = []
    monkeypatch.setattr(module, "validate_maternity_protected_work", lambda *_: called.append(True))
    module.validate_maternity_attendance(SimpleNamespace(status="On Leave", working_hours=0))
    module.validate_maternity_attendance(SimpleNamespace(status="Absent", working_hours=0))
    assert called == []


def test_maternity_detail_inspection_never_invents_native_payment_amount(monkeypatch):
    from types import SimpleNamespace
    from tradex_hr.tradexcel_hr import maternity_welfare as module

    review = SimpleNamespace(
        rule_set="RULE-SYNTHETIC",
        actual_delivery_date=None,
        expected_delivery_date=date(2026, 9, 30),
        notice_date=date(2026, 8, 1),
        benefit_eligibility="Pending Review",
    )
    rule = SimpleNamespace(
        name="RULE-SYNTHETIC",
        minimum_service_months=6,
        benefit_rate_method="Average Wages / Actual Days Worked",
        benefit_reference_period_months=3,
    )
    monkeypatch.setattr(module, "_employee_row", lambda _employee: SimpleNamespace(company="Synthetic Company", date_of_joining=date(2020, 1, 1)))
    monkeypatch.setattr(module.frappe, "session", SimpleNamespace(user="Administrator"))
    monkeypatch.setattr(module.frappe, "get_roles", lambda _user=None: [])
    monkeypatch.setattr(module, "assert_company_access", lambda *_a, **_k: None)
    monkeypatch.setattr(module.frappe, "get_all", lambda *_a, **_k: ["CASE-SYNTHETIC"])
    monkeypatch.setattr(module.frappe, "get_doc", lambda _doctype, _name: review if _doctype == module.MATERNITY_REVIEW else rule)
    monkeypatch.setattr(module, "_validate_native_leave_type", lambda _rule: [])
    result = module.inspect_maternity_benefit("EMP-SYNTHETIC", date(2026, 9, 30))
    assert result["benefit_rate_method"] == "Average Wages / Actual Days Worked"
    assert result["expected_amount"] is None
    assert result["payment_path"] == "MATERNITY_BENEFIT_ELIGIBILITY_REVIEW_REQUIRED"


def test_sensitive_doc_types_do_not_grant_payroll_or_supervisor_access():
    import json
    from pathlib import Path

    review_path = Path(__file__).parents[1] / "tradexcel_hr" / "doctype" / "tradexcel_maternity_review" / "tradexcel_maternity_review.json"
    definition = json.loads(review_path.read_text())
    roles = {row["role"] for row in definition["permissions"]}
    fields = {row["fieldname"] for row in definition["fields"]}
    assert roles == {"Tradexcel HR Manager", "Tradexcel Owner/Director"}
    assert not {"gender", "number_of_children", "diagnosis", "medical_history"} & fields


def test_protected_separation_requires_independent_proceed_review(monkeypatch):
    from types import SimpleNamespace
    import pytest
    from tradex_hr.tradexcel_hr import maternity_welfare as module

    review = SimpleNamespace(actual_delivery_date=date(2026, 9, 1), rule_set="RULE-SYNTHETIC")
    rule = SimpleNamespace(
        separation_protection_before_months=6,
        separation_protection_after_days=60,
    )
    monkeypatch.setattr(module, "_maternity_schema_installed", lambda: True)
    monkeypatch.setattr(module.frappe, "get_all", lambda doctype, **_k: ["CASE-SYNTHETIC"] if doctype == module.MATERNITY_REVIEW else [])
    monkeypatch.setattr(module.frappe, "get_doc", lambda doctype, _name: review if doctype == module.MATERNITY_REVIEW else rule)
    monkeypatch.setattr(module.frappe.db, "get_value", lambda doctype, name, field: date(2026, 9, 20))
    monkeypatch.setattr(module.frappe, "throw", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("review required")))
    separation = SimpleNamespace(employee="EMP-SYNTHETIC", company="Synthetic Company", name="SEP-SYNTHETIC")
    with pytest.raises(RuntimeError, match="review required"):
        module.validate_maternity_employee_separation(separation)


def test_expected_delivery_date_still_triggers_pre_delivery_separation_review(monkeypatch):
    from types import SimpleNamespace
    import pytest
    from tradex_hr.tradexcel_hr import maternity_welfare as module

    review = SimpleNamespace(
        actual_delivery_date=None,
        expected_delivery_date=date(2026, 12, 1),
        rule_set="RULE-SYNTHETIC",
    )
    rule = SimpleNamespace(
        separation_protection_before_months=6,
        separation_protection_after_days=60,
    )
    monkeypatch.setattr(module, "_maternity_schema_installed", lambda: True)
    monkeypatch.setattr(module.frappe, "get_all", lambda *_args, **_kwargs: ["CASE-SYNTHETIC"])
    monkeypatch.setattr(module.frappe, "get_doc", lambda doctype, _name: review if doctype == module.MATERNITY_REVIEW else rule)
    monkeypatch.setattr(module.frappe.db, "get_value", lambda doctype, name, field: date(2026, 9, 1))
    monkeypatch.setattr(module.frappe, "throw", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("review required")))
    separation = SimpleNamespace(employee="EMP-SYNTHETIC", company="Synthetic Company", name="SEP-SYNTHETIC")
    with pytest.raises(RuntimeError, match="review required"):
        module.validate_maternity_employee_separation(separation)


def test_independent_proceed_review_allows_separation_to_continue(monkeypatch):
    from types import SimpleNamespace
    from tradex_hr.tradexcel_hr import maternity_welfare as module

    review = SimpleNamespace(actual_delivery_date=date(2026, 9, 1), rule_set="RULE-SYNTHETIC")
    rule = SimpleNamespace(
        separation_protection_before_months=6,
        separation_protection_after_days=60,
    )
    monkeypatch.setattr(module, "_maternity_schema_installed", lambda: True)
    monkeypatch.setattr(module.frappe, "get_all", lambda doctype, **_k: ["CASE-SYNTHETIC"] if doctype == module.MATERNITY_REVIEW else ["Proceed After Legal Review"])
    monkeypatch.setattr(module.frappe, "get_doc", lambda doctype, _name: review if doctype == module.MATERNITY_REVIEW else rule)
    monkeypatch.setattr(module.frappe.db, "get_value", lambda doctype, name, field: date(2026, 9, 20))
    separation = SimpleNamespace(employee="EMP-SYNTHETIC", company="Synthetic Company", name="SEP-SYNTHETIC")
    assert module.validate_maternity_employee_separation(separation) is None


def test_permission_hooks_accept_real_frappe_call_keywords(monkeypatch):
    from tradex_hr.tradexcel_hr import maternity_welfare as module

    monkeypatch.setattr(module.frappe, "get_roles", lambda user=None: {
        "hr@example.test": ["Tradexcel HR Manager"],
        "auditor@example.test": ["Tradexcel Compliance Auditor"],
    }.get(user, []))
    monkeypatch.setattr(module.frappe.db, "exists", lambda *_args, **_kwargs: True)
    doc = {"company": "Synthetic Company"}
    assert module.maternity_sensitive_has_permission(
        doc=doc, ptype="read", user="hr@example.test", debug=False
    )
    assert module.maternity_rule_has_permission(
        doc=doc, ptype="read", user="auditor@example.test", debug=False
    )
    assert module.welfare_has_permission(
        doc=doc, ptype="read", user="auditor@example.test", debug=False
    )
    assert not module.maternity_sensitive_has_permission(
        doc=doc, ptype="read", user="auditor@example.test", debug=False
    )


def test_maternity_rule_submission_blocks_native_leave_findings(monkeypatch):
    import pytest
    from types import SimpleNamespace
    from tradex_hr.tradexcel_hr import maternity_welfare as module

    monkeypatch.setattr(module.frappe, "session", SimpleNamespace(user="reviewer@example.test"))
    monkeypatch.setattr(module, "_assert_maker_checker", lambda _doc: None)
    monkeypatch.setattr(module, "validate_maternity_rule_set", lambda _doc: None)
    monkeypatch.setattr(module, "_validate_native_leave_type", lambda _doc: [
        {"code": "MATERNITY_LEAVE_CONFIGURATION_MISMATCH"}
    ])
    monkeypatch.setattr(
        module.frappe, "throw",
        lambda _message, title=None: (_ for _ in ()).throw(ValueError(title)),
    )
    with pytest.raises(ValueError, match="MATERNITY_LEAVE_CONFIGURATION_MISMATCH"):
        module.validate_maternity_rule_submit(SimpleNamespace())


def test_maternity_review_submission_uses_employee_exit_date_without_nonexistent_separation_field(monkeypatch):
    import pytest
    from types import SimpleNamespace
    from tradex_hr.tradexcel_hr import maternity_welfare as module

    doc = SimpleNamespace(
        employee="EMP-SYNTHETIC", rule_set="RULE-SYNTHETIC", actual_delivery_date=None,
        expected_delivery_date="2026-10-01", notice_date=None,
        benefit_eligibility="Pending Review", reviewed_by=None, reviewed_at=None,
    )
    rule = SimpleNamespace(minimum_service_months=6)
    monkeypatch.setattr(module, "_assert_maker_checker", lambda _doc: None)
    monkeypatch.setattr(module, "validate_maternity_review", lambda _doc: None)
    monkeypatch.setattr(module.frappe, "get_doc", lambda *_args: rule)
    monkeypatch.setattr(module, "service_months_result", lambda *_args: "MEETS")
    monkeypatch.setattr(module, "now_datetime", lambda: "synthetic timestamp")

    active_employee = SimpleNamespace(
        date_of_joining="2020-01-01", status="Active", relieving_date=None,
    )
    monkeypatch.setattr(module, "_employee_row", lambda *_args: active_employee)
    module.before_submit_maternity_review(doc)
    assert doc.reviewed_at == "synthetic timestamp"

    left_employee = SimpleNamespace(
        date_of_joining="2020-01-01", status="Left", relieving_date="2026-09-30",
    )
    monkeypatch.setattr(module, "_employee_row", lambda *_args: left_employee)
    monkeypatch.setattr(
        module.frappe, "throw",
        lambda _message, title=None: (_ for _ in ()).throw(ValueError(title)),
    )
    with pytest.raises(ValueError, match="MATERNITY_SERVICE_HISTORY_REVIEW_REQUIRED"):
        module.before_submit_maternity_review(doc)


def test_maternity_review_establishment_uses_native_branch_history(monkeypatch):
    import pytest
    from types import SimpleNamespace
    from tradex_hr.tradexcel_hr import maternity_welfare as module

    employee = SimpleNamespace(branch="FACTORY-A", internal_work_history=[])
    employee.get = lambda field: getattr(employee, field)
    monkeypatch.setattr(module.frappe, "get_doc", lambda *_args: employee)
    monkeypatch.setattr(module.frappe, "throw", lambda _message, title=None: (_ for _ in ()).throw(ValueError(title)))
    today = module.getdate(module.today())
    module._validate_maternity_establishment("EMP-SYNTHETIC", "FACTORY-A", today)
    with pytest.raises(ValueError, match="MATERNITY_ESTABLISHMENT_SCOPE_MISMATCH"):
        module._validate_maternity_establishment("EMP-SYNTHETIC", "FACTORY-B", today)

    employee.internal_work_history = [
        SimpleNamespace(branch="FACTORY-B", from_date="2026-01-01", to_date="2026-08-31"),
        SimpleNamespace(branch="FACTORY-A", from_date="2026-09-01", to_date=None),
    ]
    module._validate_maternity_establishment("EMP-SYNTHETIC", "FACTORY-B", "2026-08-01")
    employee.internal_work_history = [
        SimpleNamespace(branch="FACTORY-A", from_date="2026-09-01", to_date=None),
    ]
    with pytest.raises(ValueError, match="MATERNITY_ESTABLISHMENT_HISTORY_REVIEW_REQUIRED"):
        module._validate_maternity_establishment("EMP-SYNTHETIC", "FACTORY-B", "2026-08-01")


def test_submitted_maternity_reviews_cannot_have_overlapping_legal_windows(monkeypatch):
    import pytest
    from types import SimpleNamespace
    from tradex_hr.tradexcel_hr import maternity_welfare as module

    current = SimpleNamespace(
        name="CASE-NEW", employee="EMP-SYNTHETIC", company="Synthetic Company",
        actual_delivery_date="2026-07-20", expected_delivery_date=None,
    )
    existing = SimpleNamespace(
        name="CASE-OLD", rule_set="RULE-OLD",
        actual_delivery_date="2026-06-01", expected_delivery_date=None,
    )
    rule = SimpleNamespace(pre_delivery_days=60, post_delivery_days=60, post_delivery_work_protection_days=60)
    monkeypatch.setattr(module.frappe, "get_all", lambda *_args, **_kwargs: [existing])
    monkeypatch.setattr(module.frappe, "get_doc", lambda *_args: rule)
    monkeypatch.setattr(module.frappe, "throw", lambda _message, title=None: (_ for _ in ()).throw(ValueError(title)))
    with pytest.raises(ValueError, match="MATERNITY_REVIEW_CONFLICT"):
        module._validate_no_overlapping_maternity_review(current, rule)

    non_overlapping = SimpleNamespace(
        name="CASE-NEW", employee="EMP-SYNTHETIC", company="Synthetic Company",
        actual_delivery_date="2026-09-30", expected_delivery_date=None,
    )
    module._validate_no_overlapping_maternity_review(non_overlapping, rule)


def test_work_status_is_protected_even_without_positive_attendance_hours(monkeypatch):
    import pytest
    from types import SimpleNamespace
    from tradex_hr.tradexcel_hr import maternity_welfare as module

    monkeypatch.setattr(module, "_maternity_schema_installed", lambda: True)
    monkeypatch.setattr(module, "_review_for_protected_period", lambda *_args: (object(), object()))
    monkeypatch.setattr(module.frappe, "throw", lambda _message, title=None: (_ for _ in ()).throw(ValueError(title)))
    for status, hours in (("Present", 0), ("Present", None), ("Half Day", 0), ("Work From Home", 0)):
        attendance = SimpleNamespace(
            employee="EMP-SYNTHETIC", attendance_date="2026-09-01",
            status=status, working_hours=hours,
        )
        with pytest.raises(ValueError, match="MATERNITY_PROTECTED_WORK_PERIOD"):
            module.validate_maternity_attendance(attendance)

    calls = []
    monkeypatch.setattr(module, "validate_maternity_protected_work", lambda *_args: calls.append(True))
    module.validate_maternity_attendance(SimpleNamespace(status="On Leave", working_hours=0))
    module.validate_maternity_attendance(SimpleNamespace(status="Absent", working_hours=0))
    assert calls == []


def test_historical_protected_work_check_includes_zero_hour_work_status(monkeypatch):
    from types import SimpleNamespace
    from tradex_hr.tradexcel_hr import maternity_welfare as module

    review = SimpleNamespace(employee="EMP-SYNTHETIC", actual_delivery_date="2026-09-01")
    rule = SimpleNamespace(post_delivery_work_protection_days=60)
    captured = {}
    monkeypatch.setattr(module.frappe.db, "exists", lambda doctype, filters: captured.update(
        doctype=doctype, filters=filters
    ) or True)
    assert module._historical_work_evidence(review, rule)
    assert captured["filters"]["status"] == ["in", tuple(module.WORK_STATUSES)]
    assert "working_hours" not in captured["filters"]


def test_rule_frozen_fields_exist_in_rule_doctype_schema():
    import json
    from pathlib import Path
    from tradex_hr.tradexcel_hr.maternity_welfare import RULE_FROZEN_FIELDS

    schema = Path(__file__).parents[1] / "tradexcel_hr" / "doctype" / "tradexcel_maternity_rule_set" / "tradexcel_maternity_rule_set.json"
    fieldnames = {field["fieldname"] for field in json.loads(schema.read_text())["fields"]}
    assert set(RULE_FROZEN_FIELDS) <= fieldnames
