"""Synthetic maker-checker and effective-version proofs for exit law review."""
from __future__ import annotations

import os
from datetime import date, timedelta

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


def _rule(company, token, title, start, end, holiday_list):
    doc = frappe.get_doc({
        "doctype": "Workforce Statutory Rule Set",
        "title": title,
        "company": company,
        "jurisdiction": "Bangladesh",
        "legal_regime": "Approved Company Service Rules",
        "effective_from": start,
        "effective_to": end,
        "applicability_date_basis": "Employee Relieving Date (Legal Review)",
        "service_calculation_method": "Manual Legal Review",
        "settlement_deadline_working_days": 5,
        "holiday_list": holiday_list,
        "legal_review_notes": f"SYNTHETIC TEST ONLY {token}; no legal decision.",
        "sources": [{
            "source_title": f"Synthetic source {token}",
            "source_type": "Other",
            "act_or_rule": "Synthetic",
            "section_reference": "TEST-EXIT-1",
            "effective_date": start,
            "official_reference": f"https://example.test/{token}",
            "notes": "Synthetic fixture; not an authoritative legal source.",
        }],
        "entitlements": [
            {
                "separation_type": "Resignation",
                "classification": "Worker under selected regime",
                "entitlement_type": "Final dues deadline",
                "handling": "Deadline Only",
                "source_section": "TEST-EXIT-1",
            },
            {
                "separation_type": "Resignation",
                "classification": "Worker under selected regime",
                "entitlement_type": "Separation compensation",
                "handling": "Manual Legal Calculation",
                "source_section": "TEST-EXIT-1",
            },
            {
                "separation_type": "Resignation",
                "classification": "Other approved service-rule category",
                "entitlement_type": "Final dues deadline",
                "handling": "Deadline Only",
                "source_section": "TEST-EXIT-1",
            },
        ],
    })
    return doc


def _submit_for_review(doc, tracked_rules):
    from frappe.model.workflow import apply_workflow
    doc.insert()
    tracked_rules.append(doc.name)
    pending = apply_workflow(doc.as_dict(), "Submit for Legal Review")
    assert pending.workflow_state == "Workforce Statutory Pending Approval"
    assert pending.docstatus == 0
    return pending


def _reset_synthetic_review(separation):
    """Clear only a disposable fixture between distinct applicability scenarios."""
    separation.db_set({
        "custom_workforce_statutory_review_status": None,
        "custom_workforce_statutory_rule_set": None,
        "custom_workforce_legal_classification": None,
        "custom_workforce_statutory_applicability_date": None,
        "custom_workforce_statutory_reviewed_by": None,
        "custom_workforce_statutory_reviewed_at": None,
        "custom_workforce_statutory_review_notes": None,
    })


def test_statutory_rules_are_versioned_scoped_and_non_calculating(monkeypatch):
    from frappe.model.workflow import apply_workflow
    from workforce_suite import role_setup
    from workforce_suite.tests.test_payroll_finalization_integration import (
        _create_employee,
        _create_scoped_user,
        _create_synthetic_company,
        cleanup_synthetic_finalization_company,
    )
    from workforce_suite.workforce_suite.statutory_exit import (
        inspect_statutory_exit_readiness,
        review_separation_statutory_status,
    )

    token = frappe.generate_hash(8).upper()[:8]
    other_token = frappe.generate_hash(8).upper()[:8]
    company = other_company = None
    separation = None
    rules = []
    users = []
    old_user = frappe.session.user
    old_in_test = getattr(frappe, "in_test", False)
    old_local_in_test = getattr(frappe.local.flags, "in_test", False)
    try:
        frappe.set_user("Administrator")
        company, _abbr, _payable, _expense, _cost, holiday_list = _create_synthetic_company(token, monkeypatch)
        calendar = frappe.get_doc("Holiday List", holiday_list)
        calendar.append("holidays", {
            "holiday_date": "2026-09-21", "description": "Synthetic statutory deadline holiday",
        })
        calendar.save(ignore_permissions=True)
        other_company, _abbr2, _payable2, _expense2, _cost2, _holidays2 = _create_synthetic_company(other_token, monkeypatch)
        role_setup.ensure_workforce_roles()
        maker = _create_scoped_user("Workforce Suite Manager", company, token)
        maker_doc = frappe.get_doc("User", maker)
        maker_doc.append("roles", {"role": "Workforce Owner/Director"})
        maker_doc.save(ignore_permissions=True)
        director = _create_scoped_user("Workforce Owner/Director", company, token)
        other_director = _create_scoped_user("Workforce Owner/Director", other_company, token + "X")
        users.extend((maker, director, other_director))

        employee = _create_employee(f"Statutory Test {token}", company, holiday_list)
        employee.date_of_joining = "2020-01-01"
        employee.resignation_letter_date = "2026-09-01"
        employee.relieving_date = "2026-09-20"
        employee.save(ignore_permissions=True)
        frappe.set_user(maker)
        separation = frappe.get_doc({
            "doctype": "Employee Separation",
            "employee": employee.name,
            "company": company,
            "boarding_begins_on": "2026-09-01",
            "custom_workforce_separation_type": "Resignation",
        }).insert()
        separation.submit()

        first = _rule(company, token, f"Synthetic rules {token} v1", "2026-01-01", "2026-12-31", holiday_list)
        pending = _submit_for_review(first, rules)
        frappe.set_user(director)
        with pytest.raises(frappe.ValidationError, match="not approved"):
            review_separation_statutory_status(
                separation.name, "Approved", "Draft rules cannot be used.",
                rule_set=first.name, classification="Worker under selected regime",
            )
        frappe.set_user(maker)
        with pytest.raises((frappe.ValidationError, frappe.PermissionError)):
            apply_workflow(pending.as_dict(), "Approve Rule Set")

        frappe.set_user(other_director)
        with pytest.raises((frappe.ValidationError, frappe.PermissionError)):
            apply_workflow(pending.as_dict(), "Approve Rule Set")
        with pytest.raises(frappe.PermissionError):
            review_separation_statutory_status(
                separation.name, "Approved", "Synthetic cross-company denial.",
                rule_set=first.name, classification="Worker under selected regime",
            )

        frappe.set_user(director)
        approved_v1 = apply_workflow(pending.as_dict(), "Approve Rule Set")
        assert approved_v1.docstatus == 1
        assert approved_v1.reviewed_by == director
        assert approved_v1.reviewed_at
        assert approved_v1.sources[0].official_reference.startswith("https://example.test/")

        # The preparer also has Owner/Director, but must not review their own
        # separation's legal applicability.
        frappe.set_user(maker)
        with pytest.raises(frappe.PermissionError):
            review_separation_statutory_status(
                separation.name, "Approved", "Maker cannot self-review.",
                rule_set=approved_v1.name, classification="Worker under selected regime",
            )
        with pytest.raises(frappe.PermissionError):
            review_separation_statutory_status(
                separation.name, "Not Applicable", "Maker cannot self-review.",
                classification="Outside worker scope",
            )

        frappe.set_user(director)
        with pytest.raises(frappe.ValidationError):
            review_separation_statutory_status(
                separation.name, "Not Applicable", "Other category is not not-applicable.",
                classification="Other approved service-rule category",
            )
        result = review_separation_statutory_status(
            separation.name, "Not Applicable", "Synthetic outside-scope review.",
            classification="Outside worker scope",
        )
        assert result["status"] == "Not Applicable"
        assert result["reviewed_by"] == director

        # Reset only this disposable fixture to exercise the distinct approved
        # service-rule route; this cannot be done to a real decision.
        frappe.set_user("Administrator")
        _reset_synthetic_review(separation)
        frappe.set_user(director)
        result = review_separation_statutory_status(
            separation.name, "Approved", "Synthetic service-rule mapping.",
            rule_set=approved_v1.name,
            classification="Other approved service-rule category",
        )
        assert result["status"] == "Approved"
        assert result["rule_set"] == approved_v1.name

        frappe.set_user("Administrator")
        _reset_synthetic_review(separation)

        approved_v1.legal_regime = "Bangladesh EPZ Labour Act"
        with pytest.raises(frappe.ValidationError):
            approved_v1.save()

        frappe.set_user(maker)
        overlap = _rule(company, token, f"Overlapping rules {token}", "2026-06-01", "2027-03-01", holiday_list)
        pending_overlap = _submit_for_review(overlap, rules)
        frappe.set_user(director)
        with pytest.raises(frappe.ValidationError, match="overlaps"):
            apply_workflow(pending_overlap.as_dict(), "Approve Rule Set")

        frappe.set_user(maker)
        second = _rule(company, token, f"Synthetic rules {token} v2", "2027-01-01", None, holiday_list)
        pending_v2 = _submit_for_review(second, rules)
        frappe.set_user(director)
        approved_v2 = apply_workflow(pending_v2.as_dict(), "Approve Rule Set")
        assert approved_v2.docstatus == 1
        assert approved_v2.name != approved_v1.name

        # The older Separation explicitly uses v1; a future version cannot
        # silently win based on latest creation time.
        with pytest.raises(frappe.ValidationError, match="not effective"):
            review_separation_statutory_status(
                separation.name, "Approved", "Synthetic wrong-version check.",
                rule_set=approved_v2.name, classification="Worker under selected regime",
            )
        with pytest.raises(frappe.ValidationError, match="reviewed legal classification"):
            review_separation_statutory_status(
                separation.name, "Approved", "Missing classification cannot be inferred.",
                rule_set=approved_v1.name,
            )
        result = review_separation_statutory_status(
            separation.name, "Approved", "Synthetic version binding test; not a legal decision.",
            rule_set=approved_v1.name, classification="Worker under selected regime",
        )
        assert result["rule_set"] == approved_v1.name
        separation.reload()
        assert separation.custom_workforce_statutory_rule_set == approved_v1.name
        assert separation.custom_workforce_legal_classification == "Worker under selected regime"
        assert str(separation.custom_workforce_statutory_applicability_date) == "2026-09-20"

        with pytest.raises(frappe.ValidationError, match="immutable"):
            review_separation_statutory_status(
                separation.name, "Not Applicable", "Attempt to replace approved history.",
                classification="Outside worker scope",
            )
        separation.reload()
        assert separation.custom_workforce_statutory_review_status == "Approved"
        assert separation.custom_workforce_statutory_rule_set == approved_v1.name

        readiness = inspect_statutory_exit_readiness(separation.name)
        assert readiness["status"] == "REVIEW_REQUIRED"
        assert any(row["code"] == "MANUAL_STATUTORY_CALCULATION_REQUIRED"
                   for row in readiness["findings"])
        assert readiness["rule_set"] == approved_v1.name
        assert readiness["legal_regime"] == "Approved Company Service Rules"
        assert readiness["settlement_deadline"]["working_days"] == 5
        assert readiness["settlement_deadline"]["holiday_list"] == holiday_list
        assert str(readiness["settlement_deadline"]["due_date"]) == "2026-09-26"
        assert "amount" not in repr(readiness)
        assert "gross_pay" not in repr(readiness)
        frappe.db.set_value("Employee", employee.name, "relieving_date", "2026-10-01")
        stale_date = inspect_statutory_exit_readiness(separation.name)
        assert stale_date["status"] == "REVIEW_REQUIRED"
        assert stale_date["findings"][0]["code"] == "LEGAL_DATE_BASIS_REVIEW_REQUIRED"

        # Company-scoped list access returns only the caller's company rules.
        frappe.set_user(other_director)
        visible = frappe.get_list("Workforce Statutory Rule Set", pluck="company")
        assert company not in visible
        assert set(visible) <= {other_company}
    finally:
        frappe.set_user("Administrator")
        if separation and frappe.db.exists("Employee Separation", separation.name):
            doc = frappe.get_doc("Employee Separation", separation.name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Employee Separation", doc.name, force=True, ignore_permissions=True)
        for name in rules:
            if frappe.db.exists("Workforce Statutory Rule Set", name):
                doc = frappe.get_doc("Workforce Statutory Rule Set", name)
                if doc.docstatus == 1:
                    doc.cancel()
                frappe.delete_doc("Workforce Statutory Rule Set", name, force=True, ignore_permissions=True)
        for user in users:
            for name in frappe.get_all("User Permission", filters={"user": user}, pluck="name"):
                frappe.delete_doc("User Permission", name, force=True, ignore_permissions=True)
            if frappe.db.exists("User", user):
                frappe.delete_doc("User", user, force=True, ignore_permissions=True)
        for test_company in (company, other_company):
            if test_company:
                cleanup_synthetic_finalization_company(test_company)
        frappe.in_test = old_in_test
        frappe.local.flags.in_test = old_local_in_test
        frappe.set_user(old_user)
        assert all(not frappe.db.exists("Workforce Statutory Rule Set", name) for name in rules)
