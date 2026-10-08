from datetime import datetime, timezone
from types import SimpleNamespace

import frappe
import pytest

from workforce_suite.workforce_suite import field_attendance_service as service
from workforce_suite.workforce_suite.field_attendance_service import (
    _device_datetime,
    _face_match_rejection_message,
    _mobile_event_timing,
)


def test_device_iso_timestamp_is_converted_to_site_timezone(monkeypatch):
    monkeypatch.setattr(service, "get_system_timezone", lambda: "Asia/Dhaka")
    value = _device_datetime("2026-09-19T19:43:54.999000+00:00")
    assert value == datetime(2026, 9, 20, 1, 43, 54, 999000)
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
        {"offline_max_age_hours": 72, "offline_trust_window_minutes": 5, "offline_time_action": "Flag"},
    )
    assert result["event_time"] == captured_at
    assert result["received_at"] == received_at
    assert result["status"] == "Flagged"
    assert result["clock_skew_seconds"] == 18540
    assert "trust window" in result["reason"]


def test_old_offline_event_is_hard_blocked_even_when_review_mode_is_flag():
    result = _mobile_event_timing(
        datetime(2026, 9, 22, 15, 12),
        datetime(2026, 9, 18, 10, 3),
        {"offline_max_age_hours": 72, "offline_trust_window_minutes": 5, "offline_time_action": "Flag"},
    )
    assert result["event_time"] == datetime(2026, 9, 18, 10, 3)
    assert result["status"] == "Blocked"
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


def test_mobile_checkin_hook_does_not_replace_captured_time_with_receipt_time(monkeypatch):
    received_at = datetime(2026, 9, 22, 15, 12)
    captured_at = datetime(2026, 9, 22, 10, 3)
    employee = frappe._dict({"name": "EMP-TEST", "status": "Active", "company": "COMPANY_A"})
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
        "custom_workforce_source": "Mobile",
        "custom_workforce_field_duty": None,
        "custom_workforce_device_time": captured_at,
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
    assert doc.custom_workforce_received_at == received_at
    assert doc.custom_workforce_device_time == captured_at
    assert doc.custom_workforce_time_status == "Flagged"


def test_device_iso_timestamp_preserves_date_rollover_at_midnight(monkeypatch):
    monkeypatch.setattr(service, "get_system_timezone", lambda: "Asia/Dhaka")
    value = _device_datetime("2026-09-22T18:30:00+00:00")
    assert value == datetime(2026, 9, 23, 0, 30)


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


def test_mobile_timestamp_string_requires_explicit_timezone_offset():
    from types import SimpleNamespace

    fake_frappe = SimpleNamespace(throw=lambda message: (_ for _ in ()).throw(ValueError(message)))
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(service, "frappe", fake_frappe)
    with pytest.raises(Exception, match="timezone offset"):
        _device_datetime("2026-09-22 10:03:00", require_timezone=True)
    monkeypatch.undo()


def test_missing_device_time_is_quarantined():
    result = _mobile_event_timing(
        datetime(2026, 9, 22, 10, 3),
        None,
        {"offline_max_age_hours": 72, "offline_trust_window_minutes": 5, "offline_time_action": "Flag"},
    )
    assert result["status"] == "Flagged"
    assert "No captured" in result["reason"]


@pytest.mark.parametrize("fieldname", [
    "custom_workforce_sync_id",
    "custom_workforce_gps_source",
    "custom_workforce_location_status",
    "custom_workforce_assigned_location",
    "custom_workforce_distance_m",
    "custom_workforce_face_match_status",
    "custom_workforce_face_match_score",
    "custom_workforce_location_reason",
])
def test_mobile_derived_evidence_fields_are_immutable(fieldname, monkeypatch):
    class FakeDoc:
        def __init__(self, values, previous):
            self.values = values
            self.previous = previous

        def get(self, key, default=None):
            return self.values.get(key, default)

        def is_new(self):
            return False

        def get_doc_before_save(self):
            return self.previous

        def __getattr__(self, key):
            return self.values.get(key)

    previous = {
        "custom_workforce_source": "Mobile",
        "custom_workforce_sync_id": "original",
        "custom_workforce_gps_source": "Browser Geolocation API",
        "custom_workforce_location_status": "Inside Zone",
        "custom_workforce_assigned_location": "SITE-A",
        "custom_workforce_distance_m": 10,
        "custom_workforce_face_match_status": "Matched",
        "custom_workforce_face_match_score": 0.9,
        "custom_workforce_location_reason": "Original evidence",
    }
    values = dict(previous)
    values[fieldname] = "forged"
    doc = FakeDoc(values, previous)
    fake_frappe = SimpleNamespace(
        PermissionError=frappe.PermissionError,
        throw=lambda message, exc=None: (_ for _ in ()).throw((exc or frappe.ValidationError)(message)),
    )
    monkeypatch.setattr(service, "frappe", fake_frappe)
    with pytest.raises(frappe.PermissionError, match="protected evidence"):
        service.enrich_mobile_checkin(doc)


def test_mobile_checkin_allows_native_auto_attendance_linkage_updates(monkeypatch):
    previous = {"custom_workforce_source": "Mobile", "shift": "SHIFT-A", "attendance": None}

    class FakeDoc:
        def get(self, key, default=None):
            return {"custom_workforce_source": "Mobile", "shift": "SHIFT-B", "attendance": "ATT-1"}.get(key, default)

        def is_new(self):
            return False

        def get_doc_before_save(self):
            return previous

    monkeypatch.setattr(service, "frappe", SimpleNamespace())
    assert service.enrich_mobile_checkin(FakeDoc()) is None


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


def test_suspicious_mobile_checkin_is_quarantined_from_native_auto_attendance(monkeypatch):
    received_at = datetime(2026, 9, 22, 15, 12)
    captured_at = datetime(2026, 9, 22, 10, 3)
    employee = frappe._dict({"name": "EMP-TEST", "status": "Active", "company": "COMPANY_A"})
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
        "custom_workforce_source": "Mobile",
        "custom_workforce_field_duty": None,
        "custom_workforce_device_time": captured_at,
        "skip_auto_attendance": 0,
    })
    monkeypatch.setattr(service, "now_datetime", lambda: received_at)
    monkeypatch.setattr(service, "_employee", lambda value: employee)
    monkeypatch.setattr(service, "_policy", lambda *args: policy)

    service.enrich_mobile_checkin(doc)

    assert doc.custom_workforce_time_status == "Flagged"
    assert doc.custom_workforce_review_status == "Pending"
    assert doc.skip_auto_attendance == 1


def test_mobile_checkin_without_captured_time_cannot_fall_back_to_doc_time(monkeypatch):
    received_at = datetime(2026, 9, 22, 15, 12)
    employee = frappe._dict({"name": "EMP-TEST", "status": "Active", "company": "COMPANY_A"})
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
        "custom_workforce_source": "Mobile",
        "custom_workforce_field_duty": None,
        "custom_workforce_device_time": None,
        "skip_auto_attendance": 0,
    })
    monkeypatch.setattr(service, "now_datetime", lambda: received_at)
    monkeypatch.setattr(service, "_employee", lambda value: employee)
    monkeypatch.setattr(service, "_policy", lambda *args: policy)

    service.enrich_mobile_checkin(doc)

    assert doc.custom_workforce_time_status == "Flagged"
    assert doc.custom_workforce_review_status == "Pending"
    assert doc.skip_auto_attendance == 1


def test_flagged_outcome_does_not_settle_field_duty_allowance(monkeypatch):
    monkeypatch.setattr(
        service,
        "frappe",
        SimpleNamespace(db=SimpleNamespace(exists=lambda *args, **kwargs: "EC-FLAGGED")),
    )
    assert service._field_duty_has_unreleased_checkin("DUTY-TEST") is True


@pytest.mark.parametrize('hours,action,status', [(6,'Flag','Flagged'),(-6,'Flag','Flagged'),(-6,'Block','Blocked'),(73,'Flag','Blocked'),(-73,'Flag','Blocked')])
def test_bidirectional_acceptance_boundary(hours, action, status):
    from datetime import timedelta
    received = datetime(2026, 9, 27, 12)
    assert _mobile_event_timing(received, received-timedelta(hours=hours), {'offline_time_action':action})['status'] == status


def test_zero_trust_window_and_missing_block():
    from datetime import timedelta
    now = datetime(2026, 9, 27, 12)
    assert _mobile_event_timing(now, now-timedelta(seconds=1), {'offline_trust_window_minutes':0})['status'] == 'Flagged'
    assert _mobile_event_timing(now, None, {'offline_time_action':'Block'})['status'] == 'Blocked'


def test_receipt_security_cannot_be_weakened_by_event_business_policy(monkeypatch):
    monkeypatch.setattr(service, '_approved_duty', lambda *a: None)
    monkeypatch.setattr(service, '_', lambda x: x)
    monkeypatch.setattr(service.frappe, 'throw', lambda message: (_ for _ in ()).throw(ValueError(message)))
    doc = frappe._dict(latitude=None, longitude=None)
    event = frappe._dict(attendance_mode='Hybrid', require_gps=0, require_selfie=0)
    with pytest.raises(ValueError, match='GPS'):
        service.validate_mobile_event_business_context(doc, frappe._dict(name='SYNTHETIC'), datetime(2026,9,27), event, frappe._dict(require_gps=1))
    with pytest.raises(ValueError, match='selfie'):
        service.validate_mobile_event_business_context(doc, frappe._dict(name='SYNTHETIC'), datetime(2026,9,27), event, frappe._dict(require_selfie=1))


def test_unreleased_field_duty_cannot_reach_money_creation(monkeypatch):
    duty = frappe._dict(name='synthetic-duty', employee='synthetic')
    monkeypatch.setattr(service.frappe, 'get_doc', lambda *a: duty)
    monkeypatch.setattr(service.frappe, 'get_roles', lambda: [])
    monkeypatch.setattr(service, '_employee', lambda *a: frappe._dict(name='synthetic'))
    monkeypatch.setattr(service, '_assert_field_duty_settlement_actor', lambda *a: None)
    monkeypatch.setattr(service, '_field_duty_has_unreleased_checkin', lambda *a: True)
    monkeypatch.setattr(service, '_policy', lambda *a: pytest.fail('Quarantined evidence reached allowance policy'))
    assert service.settle_field_duty_allowance(duty.name)['status'] == 'Awaiting attendance review'
