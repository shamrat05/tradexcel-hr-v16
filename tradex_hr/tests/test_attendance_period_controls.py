import os

import frappe
import pytest

from tradex_hr.tradexcel_hr.doctype.tradexcel_attendance_period import tradexcel_attendance_period

@pytest.fixture(scope="module", autouse=True)
def site():
    frappe.init(
        site=os.environ.get("FRAPPE_TEST_SITE", "hrms-v16.localhost"),
        sites_path=os.environ.get(
            "FRAPPE_TEST_SITES_PATH", "/home/sanchita/frappe-bench-v16/sites"
        ),
    )
    frappe.connect()
    yield
    frappe.destroy()


def _period(company="Tradexcel Ceramics Ltd."):
    return frappe.get_doc(
        {
            "doctype": "Tradexcel Attendance Period",
            "company": company,
            "from_date": "2026-09-01",
            "to_date": "2026-09-30",
        }
    )


def test_exact_period_duplicate_is_rejected():
    save_point = "attendance_period_duplicate"
    frappe.db.savepoint(save_point)
    try:
        _period().insert(ignore_permissions=True)
        with pytest.raises(frappe.ValidationError):
            _period().insert(ignore_permissions=True)
    finally:
        frappe.db.rollback(save_point=save_point)


def test_direct_status_edit_cannot_bypass_actions():
    save_point = "attendance_period_status"
    frappe.db.savepoint(save_point)
    try:
        period = _period()
        period.insert(ignore_permissions=True)
        period.status = "Reviewing"
        with pytest.raises(frappe.ValidationError):
            period.save(ignore_permissions=True)
    finally:
        frappe.db.rollback(save_point=save_point)


def test_reopen_disables_unconsumed_daily_wage_inputs(monkeypatch):
    retired = []
    monkeypatch.setattr(
        tradexcel_attendance_period.frappe,
        "get_all",
        lambda *_args, **_kwargs: [{"name": "AS-1", "docstatus": 1, "disabled": 0}],
    )
    monkeypatch.setattr(tradexcel_attendance_period, "_salary_slips_using_input", lambda _name: [])
    monkeypatch.setattr(
        tradexcel_attendance_period.frappe.db,
        "set_value",
        lambda *args, **_kwargs: retired.append(args),
    )

    tradexcel_attendance_period._retire_daily_wage_inputs("ATT-PER-1")

    assert retired == [("Additional Salary", "AS-1", "disabled", 1)]


def test_reopen_blocks_when_daily_wage_input_is_already_used(monkeypatch):
    monkeypatch.setattr(
        tradexcel_attendance_period.frappe,
        "get_all",
        lambda *_args, **_kwargs: [{"name": "AS-1", "docstatus": 1, "disabled": 0}],
    )
    monkeypatch.setattr(
        tradexcel_attendance_period,
        "_salary_slips_using_input",
        lambda _name: [{"name": "SAL-SLIP-1", "docstatus": 1}],
    )

    with pytest.raises(frappe.ValidationError, match="post-payroll adjustment review"):
        tradexcel_attendance_period._retire_daily_wage_inputs("ATT-PER-1")


def test_attendance_period_successful_finalization_case1():
    company = "Tradexcel Ceramics Ltd."
    start = "2026-11-01"
    end = "2026-11-30"

    tracked = []
    try:
        frappe.set_user("Administrator")
        for name in frappe.get_all("Tradexcel Attendance Period", filters={"company": company, "from_date": start, "to_date": end}, pluck="name"):
            frappe.delete_doc("Tradexcel Attendance Period", name, force=True, ignore_permissions=True)

        period = frappe.get_doc({
            "doctype": "Tradexcel Attendance Period",
            "company": company,
            "from_date": start,
            "to_date": end,
            "status": "Open",
        })
        period.insert(ignore_permissions=True)
        tracked.append(period.name)

        result = tradexcel_attendance_period.finalize_attendance_period(period.name)
        assert result["status"] == "Finalized"
        assert result["revision"] == 1
        assert result["attendance_hash"]

        period.reload()
        assert period.status == "Finalized"
        assert period.revision == 1
        assert period.attendance_hash == result["attendance_hash"]
        assert period.finalized_by == "Administrator"
        assert period.finalized_at is not None
    finally:
        frappe.set_user("Administrator")
        for name in tracked:
            if frappe.db.exists("Tradexcel Attendance Period", name):
                frappe.delete_doc("Tradexcel Attendance Period", name, force=True, ignore_permissions=True)


def test_attendance_period_refuses_finalization_on_unresolved_blocker_case2(monkeypatch):
    company = "Tradexcel Ceramics Ltd."
    start = "2026-11-01"
    end = "2026-11-30"

    tracked = []
    try:
        frappe.set_user("Administrator")
        for name in frappe.get_all("Tradexcel Attendance Period", filters={"company": company, "from_date": start, "to_date": end}, pluck="name"):
            frappe.delete_doc("Tradexcel Attendance Period", name, force=True, ignore_permissions=True)

        period = frappe.get_doc({
            "doctype": "Tradexcel Attendance Period",
            "company": company,
            "from_date": start,
            "to_date": end,
            "status": "Open",
        })
        period.insert(ignore_permissions=True)
        tracked.append(period.name)

        # Inject an attendance integrity blocker
        monkeypatch.setattr(
            tradexcel_attendance_period,
            "inspect_attendance_integrity",
            lambda *_args, **_kwargs: {
                "status": "BLOCKED",
                "blockers": [{"code": "ATTENDANCE_UNMARKED", "reason": "Unmarked synthetic attendance days."}],
            },
        )

        with pytest.raises(frappe.ValidationError, match="Attendance cannot be finalized yet"):
            tradexcel_attendance_period.finalize_attendance_period(period.name)

        period.reload()
        assert period.status == "Open"
        assert period.attendance_hash is None
        assert period.revision == 0
    finally:
        frappe.set_user("Administrator")
        for name in tracked:
            if frappe.db.exists("Tradexcel Attendance Period", name):
                frappe.delete_doc("Tradexcel Attendance Period", name, force=True, ignore_permissions=True)


def test_payroll_readiness_clears_blocked_attendance_period_case3():
    from tradex_hr.tradexcel_hr.native_payroll import _period_attendance_gate

    company = "Tradexcel Ceramics Ltd."
    start = "2026-11-01"
    end = "2026-11-30"
    synthetic_employee = "SYN-DAILY-EMP-001"

    tracked = []
    try:
        frappe.set_user("Administrator")
        for name in frappe.get_all("Tradexcel Attendance Period", filters={"company": company, "from_date": start, "to_date": end}, pluck="name"):
            frappe.delete_doc("Tradexcel Attendance Period", name, force=True, ignore_permissions=True)

        # Before period creation/finalization: gate returns BLOCKED_ATTENDANCE_PERIOD
        before_findings = _period_attendance_gate(company, start, end, [synthetic_employee])
        assert len(before_findings) == 1
        assert before_findings[0]["code"] == "BLOCKED_ATTENDANCE_PERIOD"

        period = frappe.get_doc({
            "doctype": "Tradexcel Attendance Period",
            "company": company,
            "from_date": start,
            "to_date": end,
            "status": "Open",
        })
        period.insert(ignore_permissions=True)
        tracked.append(period.name)

        # Still Open: gate returns BLOCKED_ATTENDANCE_PERIOD
        open_findings = _period_attendance_gate(company, start, end, [synthetic_employee])
        assert len(open_findings) == 1
        assert open_findings[0]["code"] == "BLOCKED_ATTENDANCE_PERIOD"

        # Finalize period
        tradexcel_attendance_period.finalize_attendance_period(period.name)

        # After finalization: BLOCKED_ATTENDANCE_PERIOD disappears
        after_findings = _period_attendance_gate(company, start, end, [synthetic_employee])
        assert after_findings == []
    finally:
        frappe.set_user("Administrator")
        for name in tracked:
            if frappe.db.exists("Tradexcel Attendance Period", name):
                frappe.delete_doc("Tradexcel Attendance Period", name, force=True, ignore_permissions=True)


def test_stale_attendance_reopen_and_refinalize_flow_case4(monkeypatch):
    from tradex_hr.tradexcel_hr import native_payroll
    from tradex_hr.tradexcel_hr.native_payroll import _period_attendance_gate

    company = "Tradexcel Ceramics Ltd."
    start = "2026-11-01"
    end = "2026-11-30"
    synthetic_employee = "SYN-DAILY-EMP-002"

    tracked = []
    try:
        frappe.set_user("Administrator")
        for name in frappe.get_all("Tradexcel Attendance Period", filters={"company": company, "from_date": start, "to_date": end}, pluck="name"):
            frappe.delete_doc("Tradexcel Attendance Period", name, force=True, ignore_permissions=True)

        period = frappe.get_doc({
            "doctype": "Tradexcel Attendance Period",
            "company": company,
            "from_date": start,
            "to_date": end,
            "status": "Open",
        })
        period.insert(ignore_permissions=True)
        tracked.append(period.name)

        tradexcel_attendance_period.finalize_attendance_period(period.name)
        period.reload()
        initial_hash = period.attendance_hash
        assert period.status == "Finalized"
        assert period.revision == 1

        # Simulate payroll-relevant attendance change creating a hash mismatch
        altered_hash = "simulated_new_attendance_hash_9999"
        monkeypatch.setattr(native_payroll, "current_attendance_period_hash", lambda *_args: altered_hash)

        # Gate detects stale attendance
        stale_findings = _period_attendance_gate(company, start, end, [synthetic_employee])
        assert len(stale_findings) == 1
        assert stale_findings[0]["code"] == "BLOCKED_ATTENDANCE_STALE"

        # Reopen attendance
        reopen_result = tradexcel_attendance_period.reopen_attendance_period(period.name)
        assert reopen_result["status"] == "Reopened"
        period.reload()
        assert period.status == "Reopened"

        # Refinalize attendance under the new hash state
        monkeypatch.setattr(
            tradexcel_attendance_period,
            "current_attendance_period_hash",
            lambda *_args: altered_hash,
        )
        fin_again = tradexcel_attendance_period.finalize_attendance_period(period.name)
        assert fin_again["status"] == "Finalized"
        assert fin_again["revision"] == 2
        assert fin_again["attendance_hash"] == altered_hash

        period.reload()
        assert period.status == "Finalized"
        assert period.revision == 2
        assert period.attendance_hash == altered_hash

        # Stale blocker clears
        cleared_findings = _period_attendance_gate(company, start, end, [synthetic_employee])
        assert cleared_findings == []
    finally:
        frappe.set_user("Administrator")
        for name in tracked:
            if frappe.db.exists("Tradexcel Attendance Period", name):
                frappe.delete_doc("Tradexcel Attendance Period", name, force=True, ignore_permissions=True)


def test_attendance_period_permission_denial_case5():
    from tradex_hr.tests.persona_uat import PERSONA_ROLES, SyntheticPersonaHarness

    company = "Tradexcel Ceramics Ltd."
    start = "2026-11-01"
    end = "2026-11-30"

    h = SyntheticPersonaHarness("PERMDENY" + frappe.generate_hash(4).upper())
    tracked = []
    try:
        frappe.set_user("Administrator")
        for name in frappe.get_all("Tradexcel Attendance Period", filters={"company": company, "from_date": start, "to_date": end}, pluck="name"):
            frappe.delete_doc("Tradexcel Attendance Period", name, force=True, ignore_permissions=True)

        period = frappe.get_doc({
            "doctype": "Tradexcel Attendance Period",
            "company": company,
            "from_date": start,
            "to_date": end,
            "status": "Open",
        })
        period.insert(ignore_permissions=True)
        tracked.append(period.name)

        # Create Payroll Manager user (read-only on Attendance Period)
        pm_user = h.create_user("payroll_mgr", [PERSONA_ROLES["payroll_manager"]], company=company)

        # Finalize period as Administrator first to test reopen permission denial as well
        tradexcel_attendance_period.finalize_attendance_period(period.name)
        period.reload()
        assert period.status == "Finalized"

        # Switch to Payroll Manager
        frappe.set_user(pm_user)
        assert frappe.has_permission("Tradexcel Attendance Period", "read")
        assert not frappe.has_permission("Tradexcel Attendance Period", "write")

        # Calling reopen_attendance_period directly must fail with PermissionError
        with pytest.raises(frappe.PermissionError):
            tradexcel_attendance_period.reopen_attendance_period(period.name)

        # Reset to Open as Administrator to test finalize denial
        frappe.set_user("Administrator")
        period.status = "Open"
        period._reopen_context = True
        period.save(ignore_permissions=True)

        # Switch back to Payroll Manager
        frappe.set_user(pm_user)
        with pytest.raises(frappe.PermissionError):
            tradexcel_attendance_period.finalize_attendance_period(period.name)

    finally:
        frappe.set_user("Administrator")
        for name in tracked:
            if frappe.db.exists("Tradexcel Attendance Period", name):
                frappe.delete_doc("Tradexcel Attendance Period", name, force=True, ignore_permissions=True)
        h.cleanup()


def test_attendance_period_discoverability_and_navigation_resolution():
    from tradex_hr.install import WORKSPACE_SECTIONS, WORKSPACE_SHORTCUTS, WORKSPACE_SHORTCUT_ICONS
    from tradex_hr.tests.persona_uat import PERSONA_ROLES, SyntheticPersonaHarness

    # 1. Configured in install.py
    assert ("Attendance Periods", "Tradexcel Attendance Period", "DocType") in WORKSPACE_SHORTCUTS
    assert WORKSPACE_SHORTCUT_ICONS.get("Attendance Periods") == "calendar"

    att_sections = [labels for title, _, labels in WORKSPACE_SECTIONS if title == "Attendance & Shifts"]
    assert len(att_sections) == 1
    assert "Attendance Periods" in att_sections[0]

    # 2. Workspace Sidebar reflects Attendance Periods
    sidebar = frappe.get_doc("Workspace Sidebar", "Tradexcel HR")
    sidebar_items = {item.label: (item.link_type, item.link_to) for item in sidebar.items if item.type == "Link"}
    assert "Attendance Periods" in sidebar_items
    assert sidebar_items["Attendance Periods"] == ("DocType", "Tradexcel Attendance Period")

    # 3. Persona Discoverability and write boundary
    h = SyntheticPersonaHarness("DISCOV" + frappe.generate_hash(4).upper())
    try:
        frappe.set_user("Administrator")
        att_officer = h.create_user("att_officer", [PERSONA_ROLES["attendance_officer"]], company="Tradexcel Ceramics Ltd.")
        payroll_mgr = h.create_user("payroll_mgr", [PERSONA_ROLES["payroll_manager"]], company="Tradexcel Ceramics Ltd.")

        # Attendance Officer can resolve route and has write/create permission
        frappe.set_user(att_officer)
        assert frappe.has_permission("Tradexcel Attendance Period", "read")
        assert frappe.has_permission("Tradexcel Attendance Period", "write")
        assert frappe.has_permission("Tradexcel Attendance Period", "create")

        # Payroll Manager can resolve route (read) but cannot write
        frappe.set_user(payroll_mgr)
        assert frappe.has_permission("Tradexcel Attendance Period", "read")
        assert not frappe.has_permission("Tradexcel Attendance Period", "write")
        assert not frappe.has_permission("Tradexcel Attendance Period", "create")
    finally:
        frappe.set_user("Administrator")
        h.cleanup()


def test_attendance_period_form_js_registration_and_contract():
    from pathlib import Path

    app_root = Path(__file__).resolve().parents[2]

    # 1. Registered in hooks.py doctype_js
    from tradex_hr import hooks
    assert "Tradexcel Attendance Period" in hooks.doctype_js
    js_relpath = hooks.doctype_js["Tradexcel Attendance Period"]
    assert js_relpath == "public/js/tradexcel_attendance_period.js"

    # 2. File exists and has required event handlers and buttons
    js_file = app_root / "tradex_hr" / js_relpath
    assert js_file.exists(), f"Form script {js_file} does not exist"

    content = js_file.read_text(encoding="utf-8")
    assert 'frappe.ui.form.on("Tradexcel Attendance Period"' in content
    assert 'refresh(frm)' in content
    assert 'frm.has_perm("write")' in content
    assert '__("Finalize Attendance")' in content
    assert '__("Reopen Attendance")' in content
    assert "finalize_attendance_period" in content
    assert "reopen_attendance_period" in content
    assert "frm.reload_doc()" in content


def test_attendance_officer_persona_finalization_and_reopen_lifecycle():
    from tradex_hr.tests.persona_uat import (
        PERSONA_ROLES,
        SyntheticPersonaHarness,
        assert_only_tradexcel_roles,
    )

    company = "Tradexcel Ceramics Ltd."
    start = "2026-11-01"
    end = "2026-11-30"

    h = SyntheticPersonaHarness("ATTOFF" + frappe.generate_hash(4).upper())
    tracked = []
    try:
        frappe.set_user("Administrator")
        for name in frappe.get_all(
            "Tradexcel Attendance Period",
            filters={"company": company, "from_date": start, "to_date": end},
            pluck="name",
        ):
            frappe.delete_doc(
                "Tradexcel Attendance Period", name, force=True, ignore_permissions=True
            )

        period = frappe.get_doc(
            {
                "doctype": "Tradexcel Attendance Period",
                "company": company,
                "from_date": start,
                "to_date": end,
                "status": "Open",
            }
        )
        period.insert(ignore_permissions=True)
        tracked.append(period.name)

        att_officer = h.create_user(
            "att_officer",
            [PERSONA_ROLES["attendance_officer"]],
            company=company,
        )
        assert_only_tradexcel_roles(att_officer)

        frappe.set_user(att_officer)

        result = tradexcel_attendance_period.finalize_attendance_period(period.name)
        assert result["status"] == "Finalized"
        assert result["revision"] == 1
        assert result["attendance_hash"]

        period.reload()
        assert period.status == "Finalized"
        assert period.revision == 1
        assert period.attendance_hash == result["attendance_hash"]
        assert period.finalized_by == att_officer
        assert period.finalized_at is not None

        reopen_result = tradexcel_attendance_period.reopen_attendance_period(period.name)
        assert reopen_result["status"] == "Reopened"

        period.reload()
        assert period.status == "Reopened"
    finally:
        frappe.set_user("Administrator")
        for name in tracked:
            if frappe.db.exists("Tradexcel Attendance Period", name):
                frappe.delete_doc(
                    "Tradexcel Attendance Period", name, force=True, ignore_permissions=True
                )
        h.cleanup()


def test_attendance_officer_cross_company_access_denied():
    from tradex_hr.tests.persona_uat import (
        PERSONA_ROLES,
        SyntheticPersonaHarness,
        assert_only_tradexcel_roles,
    )

    company_a = "Tradexcel Ceramics Ltd."
    company_b = "Elegance Footwear Ltd."
    start = "2026-11-01"
    end = "2026-11-30"

    h = SyntheticPersonaHarness("ATTCROSS" + frappe.generate_hash(4).upper())
    tracked = []
    try:
        frappe.set_user("Administrator")
        for c in (company_a, company_b):
            for name in frappe.get_all(
                "Tradexcel Attendance Period",
                filters={"company": c, "from_date": start, "to_date": end},
                pluck="name",
            ):
                frappe.delete_doc(
                    "Tradexcel Attendance Period", name, force=True, ignore_permissions=True
                )

        period_b = frappe.get_doc(
            {
                "doctype": "Tradexcel Attendance Period",
                "company": company_b,
                "from_date": start,
                "to_date": end,
                "status": "Open",
            }
        )
        period_b.insert(ignore_permissions=True)
        tracked.append(period_b.name)

        att_officer = h.create_user(
            "att_officer",
            [PERSONA_ROLES["attendance_officer"]],
            company=company_a,
        )
        assert_only_tradexcel_roles(att_officer)

        frappe.set_user(att_officer)

        with pytest.raises(frappe.PermissionError):
            tradexcel_attendance_period.finalize_attendance_period(period_b.name)

        frappe.set_user("Administrator")
        tradexcel_attendance_period.finalize_attendance_period(period_b.name)
        period_b.reload()
        assert period_b.status == "Finalized"

        frappe.set_user(att_officer)
        with pytest.raises(frappe.PermissionError):
            tradexcel_attendance_period.reopen_attendance_period(period_b.name)
    finally:
        frappe.set_user("Administrator")
        for name in tracked:
            if frappe.db.exists("Tradexcel Attendance Period", name):
                frappe.delete_doc(
                    "Tradexcel Attendance Period", name, force=True, ignore_permissions=True
                )
        h.cleanup()


def test_attendance_period_denied_for_unrelated_personas():
    from tradex_hr.tests.persona_uat import (
        PERSONA_ROLES,
        SyntheticPersonaHarness,
        assert_only_tradexcel_roles,
    )

    company = "Tradexcel Ceramics Ltd."
    start = "2026-11-01"
    end = "2026-11-30"

    h = SyntheticPersonaHarness("ATTUNREL" + frappe.generate_hash(4).upper())
    tracked = []
    try:
        frappe.set_user("Administrator")
        for name in frappe.get_all(
            "Tradexcel Attendance Period",
            filters={"company": company, "from_date": start, "to_date": end},
            pluck="name",
        ):
            frappe.delete_doc(
                "Tradexcel Attendance Period", name, force=True, ignore_permissions=True
            )

        period = frappe.get_doc(
            {
                "doctype": "Tradexcel Attendance Period",
                "company": company,
                "from_date": start,
                "to_date": end,
                "status": "Open",
            }
        )
        period.insert(ignore_permissions=True)
        tracked.append(period.name)

        branch_mgr = h.create_user(
            "branch_mgr",
            [PERSONA_ROLES["branch_manager"]],
            company=company,
        )
        worker = h.create_user(
            "worker",
            [PERSONA_ROLES["worker"]],
            company=company,
        )
        assert_only_tradexcel_roles(branch_mgr)
        assert_only_tradexcel_roles(worker)

        for user in (branch_mgr, worker):
            frappe.set_user(user)
            with pytest.raises(frappe.PermissionError):
                tradexcel_attendance_period.finalize_attendance_period(period.name)
            with pytest.raises(frappe.PermissionError):
                tradexcel_attendance_period.reopen_attendance_period(period.name)
    finally:
        frappe.set_user("Administrator")
        for name in tracked:
            if frappe.db.exists("Tradexcel Attendance Period", name):
                frappe.delete_doc(
                    "Tradexcel Attendance Period", name, force=True, ignore_permissions=True
                )
        h.cleanup()


def test_attendance_officer_denied_payroll_and_broad_explicit_scope():
    from tradex_hr.tests.persona_uat import (
        PERSONA_ROLES,
        SyntheticPersonaHarness,
        assert_only_tradexcel_roles,
    )
    from tradex_hr.tradexcel_hr.company_context import assert_company_access
    from tradex_hr.tradexcel_hr.native_payroll import prepare_native_payroll

    company = "Tradexcel Ceramics Ltd."
    start = "2026-11-01"
    end = "2026-11-30"

    h = SyntheticPersonaHarness("ATTPAYDENY" + frappe.generate_hash(4).upper())
    try:
        frappe.set_user("Administrator")
        att_officer = h.create_user(
            "att_officer",
            [PERSONA_ROLES["attendance_officer"]],
            company=company,
        )
        assert_only_tradexcel_roles(att_officer)

        frappe.set_user(att_officer)

        with pytest.raises(frappe.PermissionError, match="explicit Company User Permission"):
            assert_company_access(company, require_explicit_scope=True)

        with pytest.raises(frappe.PermissionError):
            prepare_native_payroll(company, start, end)
    finally:
        frappe.set_user("Administrator")
        h.cleanup()
