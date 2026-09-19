from datetime import datetime, timezone

from tradex_hr.tradexcel_hr.field_attendance_service import (
    _device_datetime,
    _face_match_rejection_message,
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
