"""Pure field-attendance rules shared by mobile check-in and reports.

This module deliberately has no Frappe imports.  The boundary adapter can use
it for terminal/mobile/API requests without making the terminal path depend on
browser GPS or global HR Settings.
"""

from __future__ import annotations

from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt
from typing import Any, Iterable

EARTH_RADIUS_M = 6_371_008.8
VALID_MODES = {"Office Only", "Field Only", "Hybrid", "Work From Home"}
VALID_OUTSIDE_ACTIONS = {"Accept", "Flag", "Block"}


def _number(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if result != result or result in (float("inf"), float("-inf")):
        raise ValueError(f"{label} must be finite")
    return result


def validate_coordinates(latitude: Any, longitude: Any) -> tuple[float, float]:
    lat = _number(latitude, "Latitude")
    lon = _number(longitude, "Longitude")
    if not -90 <= lat <= 90:
        raise ValueError("Latitude must be between -90 and 90")
    if not -180 <= lon <= 180:
        raise ValueError("Longitude must be between -180 and 180")
    return lat, lon


def distance_meters(
    latitude_a: Any, longitude_a: Any, latitude_b: Any, longitude_b: Any
) -> float:
    """Return great-circle distance in metres using the Haversine formula."""
    lat_a, lon_a = validate_coordinates(latitude_a, longitude_a)
    lat_b, lon_b = validate_coordinates(latitude_b, longitude_b)
    d_lat = radians(lat_b - lat_a)
    d_lon = radians(lon_b - lon_a)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat_a)) * cos(radians(lat_b)) * sin(d_lon / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(sqrt(min(1.0, a)))


def evaluate_locations(
    latitude: Any, longitude: Any, locations: Iterable[dict[str, Any]]
) -> dict[str, Any]:
    """Evaluate every assigned zone and return the nearest one.

    Native HRMS currently reads the first matching Shift Location.  This
    function intentionally evaluates all locations so roster and temporary
    field-duty assignments cannot fail open because of row ordering.
    """
    lat, lon = validate_coordinates(latitude, longitude)
    candidates = []
    for location in locations:
        if not location.get("name"):
            continue
        try:
            zone_lat, zone_lon = validate_coordinates(location.get("latitude"), location.get("longitude"))
            radius = _number(location.get("checkin_radius", 0), "Check-in radius")
        except ValueError:
            continue
        if radius < 0:
            continue
        distance = distance_meters(lat, lon, zone_lat, zone_lon)
        candidates.append({
            "name": location["name"],
            "distance_m": round(distance, 3),
            "radius_m": radius,
            "inside": distance <= radius if radius else False,
        })
    candidates.sort(key=lambda item: item["distance_m"])
    nearest = candidates[0] if candidates else None
    return {
        "nearest": nearest,
        "inside": bool(nearest and nearest["inside"]),
        "candidates": candidates,
    }


def validate_gps_quality(
    latitude: Any,
    longitude: Any,
    accuracy_m: Any = None,
    *,
    max_accuracy_m: float = 200,
) -> dict[str, Any]:
    validate_coordinates(latitude, longitude)
    if accuracy_m in (None, ""):
        return {"valid": True, "accuracy_m": None, "reason": None}
    accuracy = _number(accuracy_m, "GPS accuracy")
    if accuracy < 0:
        return {"valid": False, "accuracy_m": accuracy, "reason": "negative_accuracy"}
    if accuracy > max_accuracy_m:
        return {"valid": False, "accuracy_m": accuracy, "reason": "low_accuracy"}
    return {"valid": True, "accuracy_m": accuracy, "reason": None}


def location_status(
    mode: str,
    *,
    has_gps: bool,
    inside_assigned_zone: bool,
    outside_action: str = "Flag",
    approved_external: bool = False,
) -> str:
    if mode not in VALID_MODES:
        raise ValueError(f"Unsupported attendance mode: {mode}")
    if outside_action not in VALID_OUTSIDE_ACTIONS:
        raise ValueError(f"Unsupported outside action: {outside_action}")
    if mode == "Work From Home":
        return "WFH Approved" if approved_external else "WFH Review"
    if not has_gps:
        return "GPS Missing" if mode in {"Field Only", "Hybrid"} else "Unassigned"
    if inside_assigned_zone:
        return "Inside Zone"
    if approved_external:
        return "Outside Approved"
    if outside_action == "Block":
        return "Outside Blocked"
    if outside_action == "Accept":
        return "Outside Accepted"
    return "Outside Flagged"


def calculate_allowance(
    allowance_mode: str,
    *,
    distance_km: Any = 0,
    rate_per_km: Any = 0,
    fixed_amount: Any = 0,
    multiplier: Any = 1,
    max_km: Any = None,
) -> dict[str, float | str]:
    """Calculate a payable estimate; the caller must still approve it."""
    if allowance_mode not in {"None", "Per Km", "Fixed Area", "Manual"}:
        raise ValueError(f"Unsupported allowance mode: {allowance_mode}")
    distance = max(0.0, _number(distance_km, "Distance"))
    rate = max(0.0, _number(rate_per_km, "Rate per km"))
    fixed = max(0.0, _number(fixed_amount, "Fixed amount"))
    factor = max(0.0, _number(multiplier, "Allowance multiplier"))
    if max_km not in (None, ""):
        distance = min(distance, max(0.0, _number(max_km, "Maximum kilometres")))
    if allowance_mode == "Per Km":
        amount = distance * rate * factor
    elif allowance_mode == "Fixed Area":
        amount = fixed * factor
    else:
        amount = 0.0
    return {
        "mode": allowance_mode,
        "distance_km": round(distance, 3),
        "rate_per_km": round(rate, 2),
        "amount": round(amount, 2),
    }


def detect_impossible_jump(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
    *,
    max_speed_kmh: float = 150,
) -> dict[str, Any]:
    """Flag a suspicious jump without rejecting attendance."""
    if not previous:
        return {"suspicious": False, "speed_kmh": None, "reason": None}
    previous_time = _as_utc(previous.get("time"))
    current_time = _as_utc(current.get("time"))
    if not previous_time or not current_time:
        return {"suspicious": True, "speed_kmh": None, "reason": "missing_timestamp"}
    seconds = (current_time - previous_time).total_seconds()
    if seconds <= 0:
        return {"suspicious": True, "speed_kmh": None, "reason": "non_increasing_timestamp"}
    distance_km = distance_meters(
        previous["latitude"], previous["longitude"], current["latitude"], current["longitude"]
    ) / 1000
    speed = distance_km / (seconds / 3600)
    return {
        "suspicious": speed > max_speed_kmh,
        "speed_kmh": round(speed, 3),
        "reason": "impossible_speed" if speed > max_speed_kmh else None,
    }


def _as_utc(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, str):
        value = value.replace("Z", "+00:00")
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
