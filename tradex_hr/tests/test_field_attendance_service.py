from datetime import datetime

import frappe

from tradex_hr.tradexcel_hr import field_attendance_service as service
from tradex_hr.tradexcel_hr.field_attendance_service import (
    _device_datetime,
    _face_match_rejection_message,
    _mobile_event_timing,
)


def test_device_iso_timestamp_is_converted_to_site_timezone(monkeypatch):
    monkeypatch.setattr(service, "get_system_timezone", lambda: "Asia/Dhaka")
    value = _device_datetime("2026-09-19T19:43:54.999000+00:00")
    assert value == datetime(2026, 9, 20, 1, 43, 54, 999000)
    assert value.tzinfo is None


def test_device_iso_timestamp_preserves_date_rollover_at_midnight(monkeypatch):
    monkeypatch.setattr(service, "get_system_timezone", lambda: "Asia/Dhaka")
    value = _device_datetime("2026-09-22T18:30:00+00:00")
    assert value == datetime(2026, 9, 23, 0, 30)


def test_device_datetime_keeps_naive_values_naive():
    value = _device_datetime(datetime(2026, 9, 19, 19, 43, 54))
    assert value.tzinfo is None


def test_mismatched_face_has_a_clear_rejection_message():
    message = _face_match_rejection_message(
        {"status": "Mismatch", "score": 0.12, "threshold": 0.363}
    )
    assert "does not match" in message
    assert "0.120" in message


def test_matched_face_is_not_rejected():
    assert _face_match_rejection_message(
        {"status": "Matched", "score": 0.91, "threshold": 0.363}
    ) is None


def test_delayed_offline_event_keeps_captured_time_as_canonical():
    received_at = datetime(2026, 9, 22, 15, 12)
    captured_at = datetime(2026, 9, 22, 10, 3)
    result = _mobile_event_timing(
        received_at,
        captured_at,
        {"offline_max_age_hours": 72, "offline_trust_window_minutes": 5, "offline_time_action": "Flag"},
    )
    assert result["event_time"] == captured_at
    assert result["received_at"] == received_at
    assert result["status"] == "Flagged"
    assert result["clock_skew_seconds"] == 18540
    assert "trust window" in result["reason"]


def test_online_event_inside_trust_window_is_trusted():
    result = _mobile_event_timing(
        datetime(2026, 9, 22, 10, 5),
        datetime(2026, 9, 22, 10, 3),
        {"offline_max_age_hours": 72, "offline_trust_window_minutes": 5, "offline_time_action": "Flag"},
    )
    assert result["status"] == "Trusted"


def test_old_event_is_flagged_for_review_but_not_trusted():
    result = _mobile_event_timing(
        datetime(2026, 9, 22, 15, 12),
        datetime(2026, 9, 18, 10, 3),
        {"offline_max_age_hours": 72, "offline_trust_window_minutes": 5, "offline_time_action": "Flag"},
    )
    assert result["event_time"] == datetime(2026, 9, 18, 10, 3)
    assert result["status"] == "Flagged"
    assert "offline limit" in result["reason"]


def test_old_offline_event_is_flagged_by_default_policy():
    result = _mobile_event_timing(
        datetime(2026, 9, 22, 15, 12),
        datetime(2026, 9, 18, 10, 3),
        {"offline_max_age_hours": 72, "offline_trust_window_minutes": 5, "offline_time_action": "Flag"},
    )
    assert result["event_time"] == datetime(2026, 9, 18, 10, 3)
    assert result["status"] == "Flagged"
    assert "older" in result["reason"]


def test_future_device_clock_is_rejected_when_policy_blocks():
    result = _mobile_event_timing(
        datetime(2026, 9, 22, 10, 3),
        datetime(2026, 9, 22, 10, 30),
        {"offline_max_age_hours": 72, "offline_trust_window_minutes": 5, "offline_time_action": "Block"},
    )
    assert result["event_time"] == datetime(2026, 9, 22, 10, 30)
    assert result["status"] == "Blocked"
    assert "future" in result["reason"]


def test_missing_device_time_is_quarantined():
    result = _mobile_event_timing(
        datetime(2026, 9, 22, 10, 3),
        None,
        {"offline_max_age_hours": 72, "offline_trust_window_minutes": 5, "offline_time_action": "Flag"},
    )
    assert result["status"] == "Flagged"
    assert "No captured" in result["reason"]


def test_untrusted_timestamp_cannot_select_historical_security_policy(monkeypatch):
    current = frappe._dict({
        "offline_max_age_hours": 72,
        "offline_trust_window_minutes": 5,
        "offline_time_action": "Flag",
        "name": "CURRENT",
    })
    historical = frappe._dict({"name": "HISTORICAL"})
    calls = []

    def choose_policy(employee, as_of=None):
        calls.append(as_of)
        return current if len(calls) == 1 else historical

    monkeypatch.setattr(service, "_policy", choose_policy)
    result = service._policy_for_mobile_event(
        frappe._dict({"name": "EMP-TEST"}),
        datetime(2026, 9, 22, 15, 12),
        datetime(2026, 9, 22, 10, 3),
    )

    assert result.name == "CURRENT"
    assert len(calls) == 1


def test_mobile_checkin_hook_does_not_replace_captured_time_with_receipt_time(monkeypatch):
    received_at = datetime(2026, 9, 22, 15, 12)
    captured_at = datetime(2026, 9, 22, 10, 3)
    employee = frappe._dict({"name": "EMP-TEST", "status": "Active", "company": "TCL"})
    policy = frappe._dict({
        "attendance_mode": "Hybrid",
        "outside_action": "Accept",
        "require_gps": 0,
        "face_match_enabled": 0,
        "offline_max_age_hours": 72,
        "offline_trust_window_minutes": 5,
        "offline_time_action": "Flag",
    })
    doc = frappe._dict({
        "employee": "EMP-TEST",
        "time": captured_at,
        "log_type": "IN",
        "latitude": None,
        "longitude": None,
        "custom_tradex_source": "Mobile",
        "custom_tradex_field_duty": None,
        "custom_tradex_device_time": captured_at,
    })
    monkeypatch.setattr(service, "now_datetime", lambda: received_at)
    monkeypatch.setattr(service, "_employee", lambda value: employee)
    monkeypatch.setattr(service, "_policy", lambda *args: policy)
    monkeypatch.setattr(service, "_approved_duty", lambda *args: None)
    monkeypatch.setattr(service, "_assigned_locations", lambda *args: [])
    monkeypatch.setattr(service, "get_actual_start_end_datetime_of_shift", lambda *args: None)
    monkeypatch.setattr(service, "location_status", lambda *args, **kwargs: "GPS Invalid")

    service.enrich_mobile_checkin(doc)

    assert doc.time == captured_at
    assert doc.custom_tradex_received_at == received_at
    assert doc.custom_tradex_device_time == captured_at
    assert doc.custom_tradex_time_status == "Flagged"


def test_suspicious_mobile_checkin_is_quarantined_from_native_auto_attendance(monkeypatch):
    received_at = datetime(2026, 9, 22, 15, 12)
    captured_at = datetime(2026, 9, 22, 10, 3)
    employee = frappe._dict({"name": "EMP-TEST", "status": "Active", "company": "TCL"})
    policy = frappe._dict({
        "attendance_mode": "Hybrid",
        "outside_action": "Accept",
        "require_gps": 0,
        "face_match_enabled": 0,
        "offline_max_age_hours": 72,
        "offline_trust_window_minutes": 5,
        "offline_time_action": "Flag",
        "name": "POLICY-TEST",
    })
    doc = frappe._dict({
        "employee": "EMP-TEST",
        "time": captured_at,
        "log_type": "IN",
        "latitude": None,
        "longitude": None,
        "custom_tradex_source": "Mobile",
        "custom_tradex_field_duty": None,
        "custom_tradex_device_time": captured_at,
        "skip_auto_attendance": 0,
    })
    monkeypatch.setattr(service, "now_datetime", lambda: received_at)
    monkeypatch.setattr(service, "_employee", lambda value: employee)
    monkeypatch.setattr(service, "_policy", lambda *args: policy)

    service.enrich_mobile_checkin(doc)

    assert doc.custom_tradex_time_status == "Flagged"
    assert doc.custom_tradex_review_status == "Pending"
    assert doc.skip_auto_attendance == 1


def test_mobile_checkin_without_captured_time_cannot_fall_back_to_doc_time(monkeypatch):
    received_at = datetime(2026, 9, 22, 15, 12)
    employee = frappe._dict({"name": "EMP-TEST", "status": "Active", "company": "TCL"})
    policy = frappe._dict({
        "attendance_mode": "Hybrid",
        "outside_action": "Accept",
        "require_gps": 0,
        "face_match_enabled": 0,
        "offline_max_age_hours": 72,
        "offline_trust_window_minutes": 5,
        "offline_time_action": "Flag",
        "name": "POLICY-TEST",
    })
    doc = frappe._dict({
        "employee": "EMP-TEST",
        "time": received_at,
        "log_type": "IN",
        "latitude": None,
        "longitude": None,
        "custom_tradex_source": "Mobile",
        "custom_tradex_field_duty": None,
        "custom_tradex_device_time": None,
        "skip_auto_attendance": 0,
    })
    monkeypatch.setattr(service, "now_datetime", lambda: received_at)
    monkeypatch.setattr(service, "_employee", lambda value: employee)
    monkeypatch.setattr(service, "_policy", lambda *args: policy)

    service.enrich_mobile_checkin(doc)

    assert doc.custom_tradex_time_status == "Flagged"
    assert doc.custom_tradex_review_status == "Pending"
    assert doc.skip_auto_attendance == 1


def test_flagged_outcome_does_not_settle_field_duty_allowance(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(
        service,
        "frappe",
        SimpleNamespace(db=SimpleNamespace(exists=lambda *args, **kwargs: "EC-FLAGGED")),
    )
    assert service._field_duty_has_unreleased_checkin("DUTY-TEST") is True


def test_approval_releases_native_auto_attendance_once(monkeypatch):
    from types import SimpleNamespace

    doc = SimpleNamespace(
        name="EC-FLAGGED",
        custom_tradex_source="Mobile",
        custom_tradex_time_status="Flagged",
        custom_tradex_review_status="Pending",
        log_type="OUT",
        custom_tradex_field_duty="DUTY-TEST",
        check_permission=lambda action: None,
        as_dict=lambda: {"name": "EC-FLAGGED", "skip_auto_attendance": 0},
        add_comment=lambda *args, **kwargs: None,
    )
    updates = []
    enqueued = []
    fake_frappe = SimpleNamespace(
        session=SimpleNamespace(user="reviewer@example.com"),
        get_roles=lambda user: ["Tradexcel HR Manager"],
        get_doc=lambda *args, **kwargs: doc,
        db=SimpleNamespace(set_value=lambda *args, **kwargs: updates.append((args, kwargs))),
        enqueue=lambda *args, **kwargs: enqueued.append((args, kwargs)),
    )
    monkeypatch.setattr(service, "frappe", fake_frappe)
    monkeypatch.setattr(service, "now_datetime", lambda: datetime(2026, 9, 22, 15, 30))

    result = service.approve_mobile_checkin("EC-FLAGGED")

    assert result["name"] == "EC-FLAGGED"
    fields = updates[0][0][2]
    assert fields["custom_tradex_review_status"] == "Approved"
    assert fields["skip_auto_attendance"] == 0
    assert enqueued
