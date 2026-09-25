from datetime import datetime, timezone
from types import SimpleNamespace

import frappe
import pytest

from tradex_hr.tradexcel_hr import field_attendance_service as service
from tradex_hr.tradexcel_hr.field_attendance_service import (
    _device_datetime,
    _face_match_rejection_message,
    _mobile_event_timing,
)


def test_device_iso_timestamp_is_normalized_for_mariadb_datetime():
    value = _device_datetime("2026-09-19T19:43:54.999000+00:00")
    assert value == datetime(2026, 9, 19, 19, 43, 54, 999000)
    assert value.tzinfo is None


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


def test_field_duty_allowance_requires_company_currency(monkeypatch):
    monkeypatch.setattr(service, "_", lambda message: message)
    fake = SimpleNamespace(
        db=SimpleNamespace(get_value=lambda *_args: None),
        throw=lambda message: (_ for _ in ()).throw(frappe.ValidationError(message)),
    )
    monkeypatch.setattr(service, "frappe", fake)
    with pytest.raises(frappe.ValidationError, match="default currency"):
        service._company_currency("Synthetic Company")


def test_field_duty_allowance_uses_company_currency(monkeypatch):
    fake = SimpleNamespace(db=SimpleNamespace(get_value=lambda *_args: "EUR"))
    monkeypatch.setattr(service, "frappe", fake)
    assert service._company_currency("Synthetic Company") == "EUR"


def test_delayed_offline_event_keeps_captured_time_as_canonical():
    received_at = datetime(2026, 9, 22, 15, 12)
    captured_at = datetime(2026, 9, 22, 10, 3)
    result = _mobile_event_timing(
        received_at,
        captured_at,
        {"offline_max_age_hours": 72, "offline_future_tolerance_minutes": 10, "offline_time_action": "Flag"},
    )
    assert result["event_time"] == captured_at
    assert result["received_at"] == received_at
    assert result["status"] == "Trusted"
    assert result["clock_skew_seconds"] == 18540


def test_old_offline_event_is_flagged_by_default_policy():
    result = _mobile_event_timing(
        datetime(2026, 9, 22, 15, 12),
        datetime(2026, 9, 18, 10, 3),
        {"offline_max_age_hours": 72, "offline_future_tolerance_minutes": 10, "offline_time_action": "Flag"},
    )
    assert result["event_time"] == datetime(2026, 9, 18, 10, 3)
    assert result["status"] == "Flagged"
    assert "older" in result["reason"]


def test_future_device_clock_is_rejected_when_policy_blocks():
    result = _mobile_event_timing(
        datetime(2026, 9, 22, 10, 3),
        datetime(2026, 9, 22, 10, 30),
        {"offline_max_age_hours": 72, "offline_future_tolerance_minutes": 10, "offline_time_action": "Block"},
    )
    assert result["event_time"] == datetime(2026, 9, 22, 10, 30)
    assert result["status"] == "Blocked"
    assert "future" in result["reason"]


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
        "offline_future_tolerance_minutes": 10,
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
    })
    monkeypatch.setattr(service, "now_datetime", lambda: received_at)
    monkeypatch.setattr(service, "_employee", lambda value: employee)
    monkeypatch.setattr(service, "_policy_for_mobile_event", lambda *args: policy)
    monkeypatch.setattr(service, "_approved_duty", lambda *args: None)
    monkeypatch.setattr(service, "_assigned_locations", lambda *args: [])
    monkeypatch.setattr(service, "get_actual_start_end_datetime_of_shift", lambda *args: None)
    monkeypatch.setattr(service, "location_status", lambda *args, **kwargs: "GPS Invalid")

    service.enrich_mobile_checkin(doc)

    assert doc.time == captured_at
    assert doc.custom_tradex_received_at == received_at
    assert doc.custom_tradex_device_time == captured_at
    assert doc.custom_tradex_time_status == "Trusted"
