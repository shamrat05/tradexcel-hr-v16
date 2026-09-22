from datetime import datetime
from types import SimpleNamespace

import frappe
import pytest

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


def test_event_beyond_maximum_offline_age_is_hard_blocked():
    result = _mobile_event_timing(
        datetime(2026, 9, 22, 15, 12),
        datetime(2026, 9, 18, 10, 3),
        {"offline_max_age_hours": 72, "offline_trust_window_minutes": 5, "offline_time_action": "Flag"},
    )
    assert result["event_time"] == datetime(2026, 9, 18, 10, 3)
    assert result["status"] == "Blocked"
    assert "offline limit" in result["reason"]


def test_old_offline_event_is_hard_blocked_even_when_review_mode_is_flag():
    result = _mobile_event_timing(
        datetime(2026, 9, 22, 15, 12),
        datetime(2026, 9, 18, 10, 3),
        {"offline_max_age_hours": 72, "offline_trust_window_minutes": 5, "offline_time_action": "Flag"},
    )
    assert result["event_time"] == datetime(2026, 9, 18, 10, 3)
    assert result["status"] == "Blocked"
    assert "older" in result["reason"]


def test_mobile_timestamp_string_requires_explicit_timezone_offset():
    from types import SimpleNamespace

    fake_frappe = SimpleNamespace(throw=lambda message: (_ for _ in ()).throw(ValueError(message)))
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(service, "frappe", fake_frappe)
    with pytest.raises(Exception, match="timezone offset"):
        _device_datetime("2026-09-22 10:03:00", require_timezone=True)
    monkeypatch.undo()


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
    monkeypatch.setattr(
        service,
        "frappe",
        SimpleNamespace(db=SimpleNamespace(exists=lambda *args, **kwargs: "EC-FLAGGED")),
    )
    assert service._field_duty_has_unreleased_checkin("DUTY-TEST") is True


def test_approval_uses_receipt_policy_when_current_policy_is_weaker(monkeypatch):
    doc = SimpleNamespace(
        name="EC-FLAGGED",
        employee="EMP-TEST",
        time=datetime(2026, 9, 22, 10, 3),
        custom_tradex_source="Mobile",
        custom_tradex_time_status="Flagged",
        custom_tradex_review_status="Pending",
        log_type="OUT",
        custom_tradex_field_duty=None,
        custom_tradex_policy="RECEIPT-STRONG",
        custom_tradex_location_status="Time Review Required",
        custom_tradex_assigned_location=None,
        custom_tradex_distance_m=None,
        custom_tradex_face_match_status=None,
        custom_tradex_face_match_score=None,
        custom_tradex_location_reason="outside trust window",
        check_permission=lambda action: None,
        as_dict=lambda: {"name": "EC-FLAGGED", "skip_auto_attendance": 0},
        add_comment=lambda *args, **kwargs: None,
    )
    updates = []
    enqueued = []
    fake_frappe = SimpleNamespace(
        session=SimpleNamespace(user="reviewer@example.com"),
        get_roles=lambda user: ["Tradexcel HR Manager"],
        get_doc=lambda *args, **kwargs: (
            doc
            if args[0] == "Employee Checkin"
            else SimpleNamespace(
                name="RECEIPT-STRONG",
                docstatus=1,
                enabled=1,
                require_selfie=1,
                require_gps=0,
                face_match_enabled=0,
            )
        ),
        db=SimpleNamespace(set_value=lambda *args, **kwargs: updates.append((args, kwargs))),
        enqueue=lambda *args, **kwargs: enqueued.append((args, kwargs)),
    )
    monkeypatch.setattr(service, "frappe", fake_frappe)
    monkeypatch.setattr(service, "now_datetime", lambda: datetime(2026, 9, 22, 15, 30))
    event_policy = SimpleNamespace(name="EVENT-WEAKER", require_gps=0, face_match_enabled=0, require_selfie=0)
    employee = SimpleNamespace(name="EMP-TEST")
    validated = []
    monkeypatch.setattr(service, "_employee", lambda value: employee)
    monkeypatch.setattr(service, "_policy", lambda *args: event_policy)
    monkeypatch.setattr(
        service,
        "validate_mobile_event_business_context",
        lambda *args, **kwargs: validated.append((args, kwargs)) or {"policy": event_policy},
    )

    result = service.approve_mobile_checkin("EC-FLAGGED")

    assert result["name"] == "EC-FLAGGED"
    fields = updates[0][0][2]
    assert fields["custom_tradex_review_status"] == "Approved"
    assert fields["skip_auto_attendance"] == 0
    assert validated
    assert validated[0][1]["security_policy"].name == "RECEIPT-STRONG"
    assert validated[0][1]["security_policy"].require_selfie == 1
    assert validated[0][0][3] is event_policy


def test_scoped_reviewer_without_user_permission_is_denied(monkeypatch):
    errors = []
    fake_frappe = SimpleNamespace(
        session=SimpleNamespace(user="manager@example.com"),
        get_roles=lambda user: ["Tradexcel Branch Manager"],
        get_all=lambda *args, **kwargs: [],
        throw=lambda message, exc: errors.append((message, exc)) or (_ for _ in ()).throw(exc(message)),
        PermissionError=PermissionError,
    )
    monkeypatch.setattr(service, "frappe", fake_frappe)

    with pytest.raises(PermissionError):
        service._assert_employee_scope("EMP-OTHER")
    assert errors


def test_scoped_reviewer_with_visible_employee_permission_is_allowed(monkeypatch):
    fake_frappe = SimpleNamespace(
        session=SimpleNamespace(user="manager@example.com"),
        get_roles=lambda user: ["Tradexcel Branch Manager"],
        get_all=lambda *args, **kwargs: [{"allow": "Branch", "for_value": "Factory"}],
        get_list=lambda *args, **kwargs: [{"name": "EMP-IN-SCOPE"}],
        throw=lambda message, exc: (_ for _ in ()).throw(exc(message)),
        PermissionError=PermissionError,
    )
    monkeypatch.setattr(service, "frappe", fake_frappe)

    service._assert_employee_scope("EMP-IN-SCOPE")
