from datetime import datetime, timezone

import pytest

from workforce_suite.workforce_suite.field_attendance import (
    calculate_allowance,
    detect_impossible_jump,
    distance_meters,
    evaluate_locations,
    location_status,
    validate_coordinates,
    validate_gps_quality,
    track_distance_km,
)


def test_coordinates_are_strictly_validated():
    assert validate_coordinates("23.79", "90.41") == (23.79, 90.41)
    with pytest.raises(ValueError, match="Latitude"):
        validate_coordinates(91, 90)
    with pytest.raises(ValueError, match="Longitude"):
        validate_coordinates(23, 181)


def test_distance_is_zero_at_same_coordinate():
    assert distance_meters(23.79, 90.41, 23.79, 90.41) == pytest.approx(0)


def test_all_assigned_locations_are_evaluated_and_nearest_wins():
    result = evaluate_locations(23.7901, 90.4101, [
        {"name": "far", "latitude": 23.80, "longitude": 90.42, "checkin_radius": 50},
        {"name": "near", "latitude": 23.79, "longitude": 90.41, "checkin_radius": 1000},
    ])
    assert result["inside"] is True
    assert result["nearest"]["name"] == "near"
    assert len(result["candidates"]) == 2


def test_any_containing_zone_counts_even_when_nearest_zone_is_outside():
    result = evaluate_locations(23.7900, 90.4100, [
        {"name": "near-but-outside", "latitude": 23.7901, "longitude": 90.4101, "checkin_radius": 1},
        {"name": "farther-but-inside", "latitude": 23.7904, "longitude": 90.4100, "checkin_radius": 100},
    ])
    assert result["nearest"]["name"] == "near-but-outside"
    assert result["matched"]["name"] == "farther-but-inside"
    assert result["inside"] is True


def test_location_modes_keep_terminal_path_separate():
    assert location_status("Office Only", has_gps=False, inside_assigned_zone=False) == "Unassigned"
    assert location_status("Field Only", has_gps=False, inside_assigned_zone=False) == "GPS Missing"
    assert location_status("Hybrid", has_gps=True, inside_assigned_zone=False) == "Outside Flagged"
    assert location_status("Hybrid", has_gps=True, inside_assigned_zone=False, approved_external=True) == "Outside Approved"
    assert location_status("Work From Home", has_gps=False, inside_assigned_zone=False, approved_external=True) == "WFH Approved"


def test_low_accuracy_is_flagged_not_silently_accepted():
    assert validate_gps_quality(23.79, 90.41, 25)["valid"] is True
    result = validate_gps_quality(23.79, 90.41, 250)
    assert result == {"valid": False, "accuracy_m": 250.0, "reason": "low_accuracy"}


def test_allowance_is_configurable_and_capped():
    result = calculate_allowance("Per Km", distance_km=12.8, rate_per_km=10, multiplier=1.5, max_km=10)
    assert result["distance_km"] == 10
    assert result["amount"] == 150
    assert calculate_allowance("Fixed Area", fixed_amount=75)["amount"] == 75
    assert calculate_allowance("None", distance_km=100, rate_per_km=100)["amount"] == 0


def test_track_distance_is_time_ordered_and_ignores_bad_points():
    points = [
        {"time": "2026-09-19T09:10:00+00:00", "latitude": 23.80, "longitude": 90.42},
        {"time": "2026-09-19T09:00:00+00:00", "latitude": 23.79, "longitude": 90.41},
        {"time": "bad", "latitude": 500, "longitude": 500},
    ]
    assert track_distance_km(points) == pytest.approx(distance_meters(23.79, 90.41, 23.80, 90.42) / 1000, abs=0.001)


def test_impossible_jump_is_a_flag_not_a_rejection():
    previous = {"latitude": 23.79, "longitude": 90.41, "time": datetime(2026, 9, 19, 8, 0, tzinfo=timezone.utc)}
    current = {"latitude": 24.90, "longitude": 91.87, "time": datetime(2026, 9, 19, 8, 5, tzinfo=timezone.utc)}
    result = detect_impossible_jump(previous, current)
    assert result["suspicious"] is True
    assert result["reason"] == "impossible_speed"
