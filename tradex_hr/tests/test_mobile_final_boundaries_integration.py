"""Synthetic integration regressions for the post-release mobile boundaries."""

from datetime import timedelta
from zoneinfo import ZoneInfo

import frappe
import pytest
from frappe.utils import get_system_timezone, now_datetime
from unittest.mock import patch

from tradex_hr.tests.persona_uat import SyntheticPersonaHarness, PERSONA_ROLES
from tradex_hr.tests.test_bulk_attendance_corrections_integration import site, _masters, _remove_synthetic
from tradex_hr.tradexcel_hr import field_attendance_service as mobile


def _aware_now():
    return now_datetime().replace(tzinfo=ZoneInfo(get_system_timezone())).isoformat()


def test_mobile_mutations_are_employee_self_service_not_supervisor_proxy(site):
    h = SyntheticPersonaHarness("MOBPROXY" + frappe.generate_hash(6).upper())
    tracked = {dt: [] for dt in ("Attendance Request", "Attendance", "Employee Checkin", "Tradex Mobile Event")}
    policies = []
    duties = []
    try:
        company = "Tradexcel Ceramics Ltd."
        branches, departments = _masters(company)
        self_user = h.create_user("self", [PERSONA_ROLES["worker"]], company=company, branch=branches[0])
        own_employee = h.create_employee("linked-self", company, branches[0], departments[0], user=self_user)
        actors = [
            h.create_user("officer", [PERSONA_ROLES["attendance_officer"]], company=company, branch=branches[0]),
            h.create_user("branch", [PERSONA_ROLES["branch_manager"]], company=company, branch=branches[0]),
        ]
        employee = h.create_employee("unlinked", company, branches[0], departments[0])
        policy = frappe.get_doc(dict(
            doctype="Tradexcel Attendance Policy", policy_name=h.token, company=company,
            employee=employee, effective_from="2020-01-01", attendance_mode="Hybrid", outside_action="Accept",
            allowance_mode="None", offline_time_action="Flag", offline_max_age_hours=72,
            offline_trust_window_minutes=5, retention_days=90, tracking_mode="Active Duty Pings",
        )).insert(ignore_permissions=True)
        policies.append(policy.name)
        policy.submit()
        frappe.set_user(self_user)
        own_sync = f"OWN{h.token[-12:]}"
        with patch.object(mobile, "_policy", return_value=policy):
            own_result = mobile.mobile_checkin(own_employee, "IN", time=_aware_now(), sync_id=own_sync)
        tracked["Employee Checkin"].append(own_result["name"])
        tracked["Tradex Mobile Event"].append(own_sync)
        duty = frappe.get_doc(dict(
            doctype="Tradexcel Field Duty", duty_id=f"DUTY{h.token[-12:]}", employee=employee,
            company=company, duty_date=now_datetime().date(), duty_type="Field Work",
            purpose="Synthetic proxy-ping boundary", tracking_enabled=1, allowance_mode="None",
            start_time=now_datetime() - timedelta(hours=1), end_time=now_datetime() + timedelta(hours=1),
        )).insert(ignore_permissions=True)
        duties.append(duty.name)
        duty.submit()
        for index, actor in enumerate(actors):
            frappe.set_user(actor)
            sync_id = f"MOB{h.token[-12:]}{index}"
            with patch.object(mobile, "_policy", return_value=policy):
                with pytest.raises(frappe.PermissionError, match="own linked Employee"):
                    mobile.mobile_checkin(employee, "IN", time=_aware_now(), sync_id=sync_id)
        frappe.set_user(actors[0])
        with patch.object(mobile, "_policy", return_value=policy):
            with pytest.raises(frappe.PermissionError, match="own linked Employee"):
                mobile.location_ping(
                    employee, duty.name, 23.75, 90.39, accuracy_m=5, ping_time=_aware_now(),
                    sync_id=f"PING{h.token[-12:]}",
                )
    finally:
        frappe.set_user("Administrator")
        with patch.object(frappe, "enqueue"):
            for sync_id in tracked["Tradex Mobile Event"]:
                if frappe.db.exists("Tradex Mobile Event", sync_id):
                    frappe.delete_doc("Tradex Mobile Event", sync_id, force=True, ignore_permissions=True)
        with patch.object(frappe, "enqueue"):
            _remove_synthetic(tracked, h)
        with patch.object(frappe, "enqueue"):
            for name in duties:
                if frappe.db.exists("Tradexcel Field Duty", name):
                    doc = frappe.get_doc("Tradexcel Field Duty", name)
                    if doc.docstatus == 1:
                        doc.cancel()
                    frappe.delete_doc(doc.doctype, name, force=True, ignore_permissions=True)
            for name in policies:
                if frappe.db.exists("Tradexcel Attendance Policy", name):
                    doc = frappe.get_doc("Tradexcel Attendance Policy", name)
                    if doc.docstatus == 1:
                        doc.cancel()
                    frappe.delete_doc(doc.doctype, doc.name, force=True, ignore_permissions=True)
        frappe.db.commit()


def test_selfie_attachment_is_private_canonical_and_idempotent(site):
    h = SyntheticPersonaHarness("MOBSELFIE" + frappe.generate_hash(6).upper())
    tracked = {dt: [] for dt in ("Attendance Request", "Attendance", "Employee Checkin")}
    files = []
    policies = []
    try:
        company = "Tradexcel Ceramics Ltd."
        branches, departments = _masters(company)
        actor = h.create_user("employee", [PERSONA_ROLES["worker"]], company=company, branch=branches[0])
        employee = h.create_employee("target", company, branches[0], departments[0], user=actor)
        other_actor = h.create_user("other", [PERSONA_ROLES["worker"]], company=company, branch=branches[0])
        policy = frappe.get_doc(dict(
            doctype="Tradexcel Attendance Policy", policy_name=h.token, company=company,
            employee=employee, effective_from="2020-01-01", attendance_mode="Hybrid", outside_action="Accept",
            allowance_mode="None", offline_time_action="Flag", offline_max_age_hours=72,
            offline_trust_window_minutes=5, retention_days=90,
        )).insert(ignore_permissions=True)
        policies.append(policy.name)
        policy.submit()
        from io import BytesIO
        from PIL import Image

        def png(color):
            output = BytesIO()
            Image.new("RGB", (2, 2), color).save(output, format="PNG")
            return output.getvalue()
        frappe.set_user(actor)
        canonical = frappe.get_doc(dict(doctype="File", file_name=f"{h.token}-a.png", content=png((10, 10, 10)), is_private=1)).insert(ignore_permissions=True)
        replacement = frappe.get_doc(dict(doctype="File", file_name=f"{h.token}-b.png", content=png((20, 20, 20)), is_private=1)).insert(ignore_permissions=True)
        public = frappe.get_doc(dict(doctype="File", file_name=f"{h.token}-public.png", content=png((30, 30, 30)), is_private=0)).insert(ignore_permissions=True)
        frappe.set_user(other_actor)
        foreign = frappe.get_doc(dict(doctype="File", file_name=f"{h.token}-foreign.png", content=png((40, 40, 40)), is_private=1)).insert(ignore_permissions=True)
        for file_doc in (canonical, replacement, public):
            file_doc.db_set("owner", actor)
        foreign.db_set("owner", other_actor)
        files.extend([canonical.name, replacement.name, public.name, foreign.name])
        frappe.set_user("Administrator")
        captured = now_datetime() - timedelta(hours=1)
        doc = frappe.get_doc(dict(
            doctype="Employee Checkin", employee=employee, log_type="IN", time=captured,
            custom_tradex_source="Mobile", custom_tradex_device_time=captured,
            custom_tradex_selfie=canonical.file_url,
        ))
        with patch.object(mobile, "_policy", return_value=policy):
            doc.insert(ignore_permissions=True)
        tracked["Employee Checkin"].append(doc.name)
        frappe.set_user(actor)
        with pytest.raises(frappe.PermissionError, match="match the evidence"):
            mobile.attach_selfie(doc.name, replacement.file_url)
        assert frappe.db.get_value("Employee Checkin", doc.name, "custom_tradex_selfie") == canonical.file_url
        result = mobile.attach_selfie(doc.name, canonical.file_url)
        assert result["file_url"] == canonical.file_url
        assert mobile.attach_selfie(doc.name, canonical.file_url) == result
        assert frappe.db.get_value("File", canonical.name, "attached_to_name") == doc.name

        second = frappe.get_doc(dict(
            doctype="Employee Checkin", employee=employee, log_type="OUT", time=captured + timedelta(minutes=1),
            custom_tradex_source="Mobile", custom_tradex_device_time=captured + timedelta(minutes=1),
            custom_tradex_selfie=canonical.file_url,
        ))
        frappe.set_user("Administrator")
        with patch.object(mobile, "_policy", return_value=policy):
            second.insert(ignore_permissions=True)
        tracked["Employee Checkin"].append(second.name)
        frappe.set_user(actor)
        with pytest.raises(frappe.PermissionError, match="already attached"):
            mobile.attach_selfie(second.name, canonical.file_url)

        third = frappe.get_doc(dict(
            doctype="Employee Checkin", employee=employee, log_type="OUT", time=captured + timedelta(minutes=2),
            custom_tradex_source="Mobile", custom_tradex_device_time=captured + timedelta(minutes=2),
            custom_tradex_selfie=public.file_url,
        ))
        frappe.set_user("Administrator")
        with patch.object(mobile, "_policy", return_value=policy):
            third.insert(ignore_permissions=True)
        tracked["Employee Checkin"].append(third.name)
        frappe.set_user(actor)
        with pytest.raises(frappe.PermissionError, match="private"):
            mobile.attach_selfie(third.name, public.file_url)

        with patch.object(mobile, "_policy", return_value=policy):
            with pytest.raises(frappe.PermissionError, match="private"):
                mobile.mobile_checkin(employee, "IN", time=_aware_now(), selfie=public.file_url, sync_id=f"PUB{h.token[-12:]}")
            with pytest.raises(frappe.PermissionError, match="owned"):
                mobile.mobile_checkin(employee, "IN", time=_aware_now(), selfie=foreign.file_url, sync_id=f"FOR{h.token[-12:]}")
    finally:
        frappe.set_user("Administrator")
        with patch.object(frappe, "enqueue"):
            _remove_synthetic(tracked, h)
        with patch.object(frappe, "enqueue"):
            for name in files:
                if frappe.db.exists("File", name):
                    frappe.delete_doc("File", name, force=True, ignore_permissions=True)
            for name in policies:
                if frappe.db.exists("Tradexcel Attendance Policy", name):
                    doc = frappe.get_doc("Tradexcel Attendance Policy", name)
                    if doc.docstatus == 1:
                        doc.cancel()
                    frappe.delete_doc(doc.doctype, doc.name, force=True, ignore_permissions=True)
        frappe.db.commit()


def test_checkin_evidence_write_permissions_for_synthetic_operator(site):
    h = SyntheticPersonaHarness("MOBPERM" + frappe.generate_hash(6).upper())
    try:
        company = "Tradexcel Ceramics Ltd."
        branches, _ = _masters(company)
        roles = (
            PERSONA_ROLES["attendance_officer"], PERSONA_ROLES["hr_manager"],
            PERSONA_ROLES["branch_manager"], PERSONA_ROLES["attendance_correction_approver"],
        )
        for index, role in enumerate(roles):
            actor = h.create_user(f"writer-{index}", [role], company=company, branch=branches[0])
            frappe.set_user(actor)
            assert not frappe.has_permission("Employee Checkin", "write"), role
    finally:
        frappe.set_user("Administrator")
        with patch.object(frappe, "enqueue"):
            h.cleanup()


def test_mobile_checkin_owner_cannot_review_own_flagged_evidence(site):
    h = SyntheticPersonaHarness("MOBREVIEW" + frappe.generate_hash(6).upper())
    tracked = {dt: [] for dt in ("Attendance Request", "Attendance", "Employee Checkin")}
    policies = []
    try:
        company = "Tradexcel Ceramics Ltd."
        branches, departments = _masters(company)
        maker = h.create_user("maker", [PERSONA_ROLES["worker"], PERSONA_ROLES["attendance_officer"]], company=company, branch=branches[0])
        employee = h.create_employee("self", company, branches[0], departments[0], user=maker)
        reviewer = h.create_user(
            "reviewer", [PERSONA_ROLES["attendance_correction_approver"]], company=company, branch=branches[0]
        )
        policy = frappe.get_doc(dict(
            doctype="Tradexcel Attendance Policy", policy_name=h.token, company=company,
            effective_from="2020-01-01", attendance_mode="Hybrid", outside_action="Accept",
            allowance_mode="None", offline_time_action="Flag", offline_max_age_hours=72,
            offline_trust_window_minutes=5, retention_days=90,
        )).insert(ignore_permissions=True)
        policies.append(policy.name)
        policy.submit()
        captured = now_datetime() - timedelta(hours=6)
        frappe.set_user(maker)
        with patch.object(mobile, "_policy", return_value=policy):
            result = mobile.mobile_checkin(
                employee, "IN", time=captured.replace(tzinfo=ZoneInfo(get_system_timezone())).isoformat(),
                sync_id=f"REV{h.token[-12:]}",
            )
        tracked["Employee Checkin"].append(result["name"])
        frappe.set_user("Administrator")
        user = frappe.get_doc("User", maker)
        user.set("roles", [{"role": PERSONA_ROLES["worker"]}, {"role": PERSONA_ROLES["attendance_correction_approver"]}])
        with patch.object(frappe, "enqueue"):
            user.save(ignore_permissions=True)
        frappe.clear_cache(user=maker)
        frappe.set_user(maker)
        with pytest.raises(frappe.PermissionError, match="different reviewer"):
            mobile.approve_mobile_checkin(result["name"], "Synthetic independent review")
        assert frappe.db.get_value("Employee Checkin", result["name"], "custom_tradex_review_status") == "Pending"

        frappe.set_user(reviewer)
        approved = mobile.approve_mobile_checkin(result["name"], "Synthetic independent review")
        assert approved["custom_tradex_review_status"] == "Approved"
        assert approved["skip_auto_attendance"] == 0
    finally:
        frappe.set_user("Administrator")
        with patch.object(frappe, "enqueue"):
            _remove_synthetic(tracked, h)
        with patch.object(frappe, "enqueue"):
            for name in policies:
                if frappe.db.exists("Tradexcel Attendance Policy", name):
                    doc = frappe.get_doc("Tradexcel Attendance Policy", name)
                    if doc.docstatus == 1:
                        doc.cancel()
                    frappe.delete_doc(doc.doctype, name, force=True, ignore_permissions=True)
        frappe.db.commit()
