"""Server-side adapter for mobile check-in, policy resolution and live pings."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import frappe
from frappe import _
from frappe.exceptions import DuplicateEntryError
from frappe.utils import getdate, get_datetime, now_datetime, today
from hrms.hr.doctype.shift_assignment.shift_assignment import get_actual_start_end_datetime_of_shift

from tradex_hr.tradexcel_hr.field_attendance import (
    detect_impossible_jump,
    evaluate_locations,
    location_status,
    calculate_allowance,
    track_distance_km,
    validate_gps_quality,
)
from tradex_hr.tradexcel_hr.face_match import FaceMatchUnavailable, match_images

SUPERVISOR_ROLES = {
    "System Manager",
    "Tradexcel Owner/Director",
    "Tradexcel HR Manager",
    "Tradexcel HR/Attendance Officer",
    "Tradexcel Factory Supervisor",
    "Tradexcel Branch Manager",
    "Tradexcel Department Manager",
}


def _category(employee: dict[str, Any]) -> str:
	return "Worker" if employee.get("employment_type") == "Worker" else "Staff"


def _device_datetime(value):
	"""Normalize browser ISO timestamps before writing MariaDB Datetime fields."""
	if not value:
		return None
	parsed = get_datetime(value)
	return parsed.replace(tzinfo=None) if getattr(parsed, "tzinfo", None) else parsed


def _mobile_event_timing(received_at, device_time, policy):
    """Resolve canonical event time while retaining server receipt evidence.

    Browser time is not cryptographically trusted. It is nevertheless the only
    available capture time for an offline event, so it is used for attendance
    date/shift resolution and checked against the server clock. Suspicious
    clocks are flagged by default; a policy may block them.
    """
    received_at = _device_datetime(received_at) or now_datetime()
    device_time = _device_datetime(device_time)
    if not device_time:
        return {
            "event_time": received_at,
            "received_at": received_at,
            "clock_skew_seconds": None,
            "status": "No Device Time",
            "reason": "No captured device time was supplied.",
        }

    clock_skew_seconds = (received_at - device_time).total_seconds()
    max_age_hours = max(int(policy.get("offline_max_age_hours") or 72), 1)
    future_tolerance_minutes = max(int(policy.get("offline_future_tolerance_minutes") or 10), 0)
    reason = ""
    if clock_skew_seconds > max_age_hours * 3600:
        reason = f"Captured time is older than the {max_age_hours}-hour offline limit."
    elif clock_skew_seconds < -(future_tolerance_minutes * 60):
        reason = f"Captured time is more than {future_tolerance_minutes} minutes in the future."

    if not reason:
        status = "Trusted"
    elif policy.get("offline_time_action") == "Block":
        status = "Blocked"
    else:
        status = "Flagged"
    return {
        "event_time": device_time,
        "received_at": received_at,
        "clock_skew_seconds": clock_skew_seconds,
        "status": status,
        "reason": reason or "Captured time is within the configured clock limits.",
    }


def _employee(employee: str | dict[str, Any]) -> frappe._dict:
    if isinstance(employee, dict):
        return frappe._dict(employee)
    value = frappe.db.get_value(
        "Employee",
        employee,
        ["name", "employee_name", "company", "branch", "department", "designation", "employment_type", "status", "user_id", "custom_tradex_face_reference"],
        as_dict=True,
    )
    if not value:
        frappe.throw(_("Employee not found"))
    if value.status != "Active":
        frappe.throw(_("Only active employees can use mobile attendance"))
    return value


def _policy(employee: frappe._dict, as_of: str | datetime | None = None) -> frappe._dict:
    day = getdate(as_of or today())
    candidates = frappe.get_all(
        "Tradexcel Attendance Policy",
        filters={"company": employee.company, "enabled": 1, "docstatus": 1, "effective_from": ["<=", day]},
        fields="*",
    )
    matching = []
    for row in candidates:
        if row.effective_to and getdate(row.effective_to) < day:
            continue
        if row.employee_category not in (None, "", "All", _category(employee)):
            continue
        if row.employee and row.employee != employee.name:
            continue
        if row.branch and row.branch != employee.branch:
            continue
        if row.department and row.department != employee.department:
            continue
        if row.designation and row.designation != employee.designation:
            continue
        specificity = sum(bool(row.get(field)) for field in ("employee", "designation", "department", "branch"))
        if row.employee:
            specificity += 100
        elif row.designation:
            specificity += 40
        elif row.department:
            specificity += 30
        elif row.branch:
            specificity += 20
        matching.append((specificity, getdate(row.effective_from), row.modified, row))
    if not matching:
        frappe.throw(_("No submitted attendance policy applies to {0} on {1}").format(employee.name, day))
    matching.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    winner = matching[0]
    ties = [item for item in matching if item[0:2] == winner[0:2]]
    if len(ties) > 1:
        frappe.throw(_("Conflicting attendance policies apply to {0}").format(employee.name))
    return frappe._dict(winner[3])


def _policy_for_mobile_event(employee: frappe._dict, received_at, device_time):
    """Use historical policy for delayed events, current policy for future clocks."""
    if not device_time:
        return _policy(employee, received_at)
    current_policy = _policy(employee, received_at)
    tolerance = max(int(current_policy.get("offline_future_tolerance_minutes") or 10), 0)
    if device_time > received_at + timedelta(minutes=tolerance):
        return current_policy
    return _policy(employee, device_time)


def _assigned_locations(employee: frappe._dict, day: str, duty=None, shift_type: str | None = None) -> list[frappe._dict]:
    names: list[str] = []
    if duty:
        if duty.primary_location:
            names.append(duty.primary_location)
        names.extend(row.location for row in duty.stops or [] if row.location)
    assignments = frappe.get_all(
        "Shift Assignment",
        filters={
            "employee": employee.name,
            "docstatus": 1,
            "status": "Active",
            "start_date": ["<=", day],
            **({"shift_type": shift_type} if shift_type else {}),
        },
        fields=["shift_location", "end_date"],
    )
    names.extend(
        row.shift_location
        for row in assignments
        if row.shift_location and (not row.end_date or getdate(row.end_date) >= getdate(day))
    )
    names = list(dict.fromkeys(names))
    return [
        frappe._dict(row)
        for row in frappe.get_all(
            "Shift Location",
            filters={"name": ["in", names]} if names else {"name": "__none__"},
            fields=["name", "latitude", "longitude", "checkin_radius"],
        )
    ]


def _approved_duty(employee: frappe._dict, duty_name: str | None, day: str):
    if duty_name:
        duty = frappe.get_doc("Tradexcel Field Duty", duty_name)
        if duty.employee != employee.name or getdate(duty.duty_date) != getdate(day):
            frappe.throw(_("Field Duty does not belong to this employee/date"))
        if duty.docstatus != 1 or duty.status not in {"Approved", "In Progress", "Completed"}:
            frappe.throw(_("Field Duty must be approved before it can authorize mobile attendance"))
        return duty
    rows = frappe.get_all(
        "Tradexcel Field Duty",
        filters={"employee": employee.name, "duty_date": day, "docstatus": 1, "status": ["in", ["Approved", "In Progress"]]},
        fields=["name"],
        limit=1,
    )
    return frappe.get_doc("Tradexcel Field Duty", rows[0].name) if rows else None


def _assert_identity(employee: frappe._dict) -> None:
    if set(frappe.get_roles(frappe.session.user)) & SUPERVISOR_ROLES:
        frappe.has_permission("Employee", "select", employee.name, throw=True)
        return
    if employee.user_id != frappe.session.user:
        frappe.throw(_("You may only create mobile attendance for your own linked Employee"), frappe.PermissionError)


def _site_file_path(file_url: str) -> str:
	if not file_url or not file_url.startswith(("/private/files/", "/files/")):
		raise FaceMatchUnavailable("Face evidence must be a local Frappe file")
	root = Path(frappe.get_site_path()).resolve()
	candidate = (root / file_url.lstrip("/")).resolve()
	if root not in candidate.parents or not candidate.is_file():
		raise FaceMatchUnavailable("Face evidence file is unavailable")
	return str(candidate)


def _model_file_path(relative_path: str) -> str:
	if not relative_path or str(relative_path).startswith("/"):
		raise FaceMatchUnavailable("Face model paths must be relative to the site")
	root = Path(frappe.get_site_path()).resolve()
	candidate = (root / str(relative_path)).resolve()
	if root not in candidate.parents or not candidate.is_file():
		raise FaceMatchUnavailable("Configured face model is unavailable")
	return str(candidate)


def _run_face_match(employee: frappe._dict, selfie_url: str) -> dict[str, Any]:
	settings = frappe.get_single("Tradex Face Match Settings")
	if not settings.enabled or settings.provider != "OpenCV YuNet + SFace":
		raise FaceMatchUnavailable("Face-match provider is not enabled")
	if not employee.custom_tradex_face_reference:
		raise FaceMatchUnavailable("Employee has no face reference photo")
	return match_images(
		_site_file_path(employee.custom_tradex_face_reference),
		_site_file_path(selfie_url),
		_model_file_path(settings.detector_model_path),
		_model_file_path(settings.recognizer_model_path),
		cosine_threshold=float(settings.cosine_threshold or 0.363),
		minimum_face_confidence=float(settings.minimum_face_confidence or 0.90),
	)


def _face_match_rejection_message(face_result: dict[str, Any]) -> str | None:
	"""Return a user-facing rejection for a non-matching verified selfie."""
	if face_result.get("status") == "Matched":
		return None
	score = float(face_result.get("score") or 0)
	threshold = float(face_result.get("threshold") or 0)
	return _(
		"Selfie does not match the enrolled face (score {0:.3f}; required {1:.3f})"
	).format(score, threshold)


def _claim_event(sync_id, event_type, employee, received_at, device_time=None):
    """Claim an immutable client event before creating its target document."""
    existing = frappe.db.get_value(
        "Tradex Mobile Event", sync_id,
        ["employee", "target_doctype", "target_name"], as_dict=True,
    )
    if existing:
        if existing.employee != employee.name:
            frappe.throw(_("This sync ID belongs to another employee"), frappe.PermissionError)
        if existing.target_name:
            return frappe.get_doc(existing.target_doctype, existing.target_name).as_dict()
        frappe.throw(_("This event is already being processed; retry with the same sync ID"))
    event = frappe.get_doc({
        "doctype": "Tradex Mobile Event", "sync_id": sync_id,
        "event_type": event_type, "employee": employee.name,
        "company": employee.company, "received_at": received_at,
        "device_time": device_time, "status": "Pending",
    })
    try:
        event.insert(ignore_permissions=True)
    except DuplicateEntryError:
        existing = frappe.db.get_value(
            "Tradex Mobile Event", sync_id,
            ["employee", "target_doctype", "target_name"], as_dict=True,
        )
        if not existing or existing.employee != employee.name:
            frappe.throw(_("This sync ID belongs to another employee"), frappe.PermissionError)
        if existing.target_name:
            return frappe.get_doc(existing.target_doctype, existing.target_name).as_dict()
        frappe.throw(_("This event is already being processed; retry with the same sync ID"))
    return None


def _duty_points(duty_name, employee_name):
    points = frappe.get_all(
        "Employee Checkin",
        filters={"employee": employee_name, "custom_tradex_field_duty": duty_name},
        fields=["time", "latitude", "longitude"],
    )
    points += frappe.get_all(
        "Tradexcel Location Ping",
        filters={"employee": employee_name, "field_duty": duty_name},
        fields=["ping_time as time", "latitude", "longitude"],
    )
    return points


def _company_currency(company):
	currency = frappe.db.get_value("Company", company, "default_currency")
	if not currency:
		frappe.throw(_("Set the Company's default currency before preparing a field-duty allowance."))
	return currency


def settle_field_duty_allowance(duty_name):
	"""Create one draft Additional Salary from a completed duty, idempotently."""
	duty = frappe.get_doc("Tradexcel Field Duty", duty_name)
	employee = _employee(duty.employee)
	policy = _policy(employee, duty.duty_date)
	if policy.allowance_mode in (None, "None", "Manual"):
		return {"duty": duty.name, "amount": 0, "status": "No automatic allowance"}
	key = f"field-duty:{duty.name}"
	existing = frappe.db.get_value("Additional Salary", {"custom_tradex_allowance_key": key}, "name")
	if existing:
		return {"duty": duty.name, "amount": frappe.db.get_value("Additional Salary", existing, "amount"), "additional_salary": existing, "status": "Existing"}
	distance_km = track_distance_km(_duty_points(duty.name, employee.name))
	result = calculate_allowance(
		policy.allowance_mode,
		distance_km=distance_km,
		rate_per_km=policy.rate_per_km,
		fixed_amount=policy.fixed_area_amount,
		multiplier=policy.allowance_multiplier or 1,
		max_km=policy.max_km_per_day,
	)
	if result["amount"] <= 0:
		return {"duty": duty.name, **result, "status": "Zero allowance"}
	currency = _company_currency(employee.company)
	doc = frappe.get_doc({
		"doctype": "Additional Salary",
		"employee": employee.name,
		"company": employee.company,
		"salary_component": policy.allowance_salary_component,
		"amount": result["amount"],
		"currency": currency,
		"is_recurring": 0,
		"payroll_date": duty.duty_date,
		"ref_doctype": "Tradexcel Field Duty",
		"ref_docname": duty.name,
		"custom_tradex_field_duty": duty.name,
		"custom_tradex_allowance_key": key,
		"custom_tradex_distance_km": result["distance_km"],
		"custom_tradex_calculation_note": f"{result['distance_km']} km × {result['rate_per_km']} × {policy.allowance_multiplier or 1}",
	})
	doc.insert(ignore_permissions=True)
	return {"duty": duty.name, **result, "additional_salary": doc.name, "status": "Draft"}


def enrich_mobile_checkin(doc, method=None):
    """Enrich explicitly mobile-sourced check-ins; terminal rows are untouched."""
    source = doc.get("custom_tradex_source")
    if not source and doc.is_new() and not doc.get("device_id"):
        # HRMS's native PWA does not know this app's source field. Treat a new
        # user-created check-in without a terminal/device id as mobile so the
        # same server-side policy cannot be bypassed through the native route.
        doc.custom_tradex_source = "Mobile"
        source = "Mobile"
    if source != "Mobile":
        return
    employee = _employee(doc.employee)
    received_at = _device_datetime(doc.get("custom_tradex_received_at")) or now_datetime()
    device_time = _device_datetime(doc.get("custom_tradex_device_time")) or _device_datetime(doc.time)
    policy = _policy_for_mobile_event(employee, received_at, device_time)
    timing = _mobile_event_timing(received_at, device_time, policy)
    if timing["status"] == "Blocked":
        frappe.throw(_("Mobile attendance time rejected: {0}").format(timing["reason"]))
    doc.custom_tradex_received_at = timing["received_at"]
    doc.custom_tradex_device_time = device_time
    doc.custom_tradex_time_status = timing["status"]
    doc.custom_tradex_clock_skew_seconds = timing["clock_skew_seconds"]
    doc.time = timing["event_time"]
    policy = _policy_for_mobile_event(employee, timing["received_at"], timing["event_time"])
    duty = _approved_duty(employee, doc.get("custom_tradex_field_duty"), getdate(doc.time))
    has_gps = doc.latitude not in (None, "") and doc.longitude not in (None, "")
    if policy.require_gps and not has_gps:
        frappe.throw(_("This attendance policy requires GPS coordinates"))
    quality = (
        validate_gps_quality(doc.latitude, doc.longitude, doc.get("custom_tradex_gps_accuracy_m"))
        if has_gps else {"valid": False, "reason": "missing_coordinates", "accuracy_m": None}
    )
    if policy.require_gps and has_gps and doc.get("custom_tradex_gps_accuracy_m") in (None, ""):
        quality = {"valid": False, "reason": "accuracy_missing", "accuracy_m": None}
    if (policy.require_gps or policy.outside_action == "Block") and not quality["valid"]:
        frappe.throw(_("This attendance policy requires a valid GPS fix"))
    shift_actual = get_actual_start_end_datetime_of_shift(employee.name, get_datetime(doc.time), True)
    shift_type = shift_actual.shift_type.name if shift_actual else None
    locations = _assigned_locations(employee, getdate(doc.time), duty, shift_type)
    evaluation = evaluate_locations(doc.latitude, doc.longitude, locations) if has_gps else {"inside": False, "nearest": None}
    status = location_status(
        policy.attendance_mode,
        has_gps=has_gps and quality["valid"],
        inside_assigned_zone=evaluation["inside"],
        outside_action=policy.outside_action,
        approved_external=bool(duty),
    )
    if status == "Outside Blocked":
        frappe.throw(_("Mobile check-in is outside the permitted area"))
    matched_location = evaluation.get("matched") or evaluation.get("nearest")
    doc.custom_tradex_policy = policy.name
    doc.custom_tradex_field_duty = duty.name if duty else doc.get("custom_tradex_field_duty")
    doc.custom_tradex_location_status = status if quality["valid"] else "GPS Invalid"
    doc.custom_tradex_assigned_location = matched_location["name"] if matched_location else None
    doc.custom_tradex_distance_m = matched_location["distance_m"] if matched_location else None
    doc.custom_tradex_review_status = "Pending" if timing["status"] == "Flagged" else "Not Required"
    if timing["status"] == "Flagged":
        doc.custom_tradex_location_reason = timing["reason"]
    if policy.face_match_enabled:
        if not doc.get("custom_tradex_selfie"):
            frappe.throw(_("Face matching requires a selfie"))
        try:
            face_result = _run_face_match(employee, doc.custom_tradex_selfie)
        except FaceMatchUnavailable as exc:
            frappe.throw(_("Face verification could not be completed: {0}").format(exc))
        rejection = _face_match_rejection_message(face_result)
        if rejection:
            frappe.throw(rejection)
        doc.custom_tradex_face_match_status = face_result["status"]
        doc.custom_tradex_face_match_score = face_result["score"]
        doc.custom_tradex_location_reason = (
            f"Face match {face_result['status']} ({face_result['score']:.3f}; "
            f"threshold {face_result['threshold']:.3f})."
        )
    elif not quality["valid"]:
        doc.custom_tradex_location_reason = quality["reason"]
    elif status in {"Outside Flagged", "WFH Review"}:
        doc.custom_tradex_location_reason = "Outside/WFH attendance accepted according to policy."
    elif matched_location:
        doc.custom_tradex_location_reason = f"Matched {matched_location['name']} at {matched_location['distance_m']} m."


@frappe.whitelist(methods=["POST"])
def mobile_checkin(employee, log_type, latitude=None, longitude=None, accuracy_m=None, time=None, field_duty=None, selfie=None, sync_id=None):
    if log_type not in {"IN", "OUT"}:
        frappe.throw(_("Log Type must be IN or OUT"))
    if not sync_id:
        frappe.throw(_("A mobile sync ID is required"))
    employee_doc = _employee(employee)
    _assert_identity(employee_doc)
    existing = frappe.db.get_value(
        "Employee Checkin", {"custom_tradex_sync_id": sync_id},
        ["name", "employee"], as_dict=True,
    )
    if existing:
        if existing.employee != employee_doc.name:
            frappe.throw(_("This sync ID belongs to another employee"), frappe.PermissionError)
        return frappe.get_doc("Employee Checkin", existing.name).as_dict()
    received_at = now_datetime()
    device_time = _device_datetime(time)
    policy = _policy_for_mobile_event(employee_doc, received_at, device_time)
    timing = _mobile_event_timing(received_at, device_time, policy)
    if timing["status"] == "Blocked":
        frappe.throw(_("Mobile attendance time rejected: {0}").format(timing["reason"]))
    if (policy.require_selfie or policy.face_match_enabled) and not selfie:
        frappe.throw(_("This attendance policy requires a selfie"))
    if selfie:
        owner = frappe.db.get_value("File", {"file_url": selfie}, "owner")
        if owner not in {frappe.session.user, "Administrator"}:
            frappe.throw(_("The selfie file is not owned by the current user"), frappe.PermissionError)
    claimed = _claim_event(sync_id, "Checkin", employee_doc, received_at, device_time)
    if claimed:
        return claimed
    checkin = frappe.get_doc({
        "doctype": "Employee Checkin",
        "employee": employee_doc.name,
        "log_type": log_type,
        # The captured event time is canonical for shift/date resolution. The
        # server receipt time is separate evidence for audit and clock checks.
        "time": timing["event_time"],
        "latitude": latitude,
        "longitude": longitude,
        "custom_tradex_source": "Mobile",
        "custom_tradex_gps_accuracy_m": accuracy_m,
        "custom_tradex_gps_source": "Browser Geolocation API",
        "custom_tradex_device_time": device_time,
        "custom_tradex_received_at": timing["received_at"],
        "custom_tradex_time_status": timing["status"],
        "custom_tradex_clock_skew_seconds": timing["clock_skew_seconds"],
        "custom_tradex_field_duty": field_duty,
        "custom_tradex_selfie": selfie,
        "custom_tradex_sync_id": sync_id,
    })
    checkin.insert(ignore_permissions=True)
    frappe.db.set_value("Tradex Mobile Event", sync_id, {
        "target_doctype": "Employee Checkin", "target_name": checkin.name, "status": "Created"
    }, update_modified=False)
    if log_type == "OUT" and field_duty:
        frappe.enqueue(
            "tradex_hr.tradexcel_hr.field_attendance_service.settle_field_duty_allowance",
            duty_name=field_duty,
            queue="short",
            enqueue_after_commit=True,
        )
    return checkin.as_dict()


@frappe.whitelist(methods=["POST"])
def location_ping(employee, field_duty, latitude, longitude, accuracy_m=None, ping_time=None, sync_id=None):
    if not sync_id:
        frappe.throw(_("A ping sync ID is required"))
    employee_doc = _employee(employee)
    _assert_identity(employee_doc)
    existing = frappe.db.get_value(
        "Tradexcel Location Ping", {"sync_id": sync_id},
        ["name", "employee"], as_dict=True,
    )
    if existing:
        if existing.employee != employee_doc.name:
            frappe.throw(_("This sync ID belongs to another employee"), frappe.PermissionError)
        return frappe.get_doc("Tradexcel Location Ping", existing.name).as_dict()
    received_at = now_datetime()
    device_time = _device_datetime(ping_time)
    duty = _approved_duty(employee_doc, field_duty, getdate(received_at))
    policy = _policy(employee_doc, received_at)
    if policy.tracking_mode != "Active Duty Pings" or not duty.tracking_enabled:
        frappe.throw(_("Active location pings are not enabled for this duty"))
    if duty.start_time and received_at < get_datetime(duty.start_time):
        frappe.throw(_("This location ping is before the field duty starts"))
    if duty.end_time and received_at > get_datetime(duty.end_time):
        frappe.throw(_("This location ping is after the field duty ends"))
    previous = frappe.get_all(
        "Tradexcel Location Ping",
        filters={"employee": employee_doc.name, "field_duty": duty.name},
        fields=["latitude", "longitude", "ping_time"],
        order_by="ping_time desc",
        limit=1,
    )
    if previous:
        elapsed = (received_at - get_datetime(previous[0].ping_time)).total_seconds()
        interval = max(1, int(policy.tracking_interval_minutes or 1)) * 60
        if elapsed < interval:
            frappe.throw(_("Location ping interval has not elapsed yet"))
    quality = validate_gps_quality(latitude, longitude, accuracy_m)
    if not quality["valid"]:
        frappe.throw(_("GPS accuracy is not acceptable for a live location ping"))
    claimed = _claim_event(sync_id, "Location Ping", employee_doc, received_at, device_time)
    if claimed:
        return claimed
    jump = detect_impossible_jump(
        {"latitude": previous[0].latitude, "longitude": previous[0].longitude, "time": previous[0].ping_time}
        if previous else None,
        {"latitude": latitude, "longitude": longitude, "time": received_at},
    )
    ping = frappe.get_doc({
        "doctype": "Tradexcel Location Ping",
        "employee": employee_doc.name,
        "company": employee_doc.company,
        "field_duty": duty.name,
        "ping_time": received_at,
        "device_time": device_time,
        "received_at": received_at,
        "clock_skew_seconds": (received_at - device_time).total_seconds() if device_time else None,
        "suspicious_jump": int(jump["suspicious"]),
        "speed_kmh": jump["speed_kmh"],
        "integrity_reason": jump["reason"],
        "latitude": latitude,
        "longitude": longitude,
        "accuracy_m": accuracy_m,
        "sync_id": sync_id,
        "source": "Browser Geolocation API",
    })
    ping.insert(ignore_permissions=True)
    frappe.db.set_value("Tradex Mobile Event", sync_id, {
        "target_doctype": "Tradexcel Location Ping", "target_name": ping.name, "status": "Created"
    }, update_modified=False)
    return ping.as_dict()


@frappe.whitelist()
def get_mobile_context():
    employee_name = frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"}, "name")
    if not employee_name:
        frappe.throw(_("Your Frappe user is not linked to an active Employee"))
    employee = _employee(employee_name)
    policy = _policy(employee)
    last = frappe.get_all("Employee Checkin", filters={"employee": employee.name}, fields=["name", "log_type", "time"], order_by="time desc", limit=1)
    duty_rows = frappe.get_all(
        "Tradexcel Field Duty",
        filters={"employee": employee.name, "duty_date": today(), "docstatus": 1, "status": ["in", ["Approved", "In Progress"]]},
        fields=["name", "duty_type", "purpose", "tracking_enabled"], limit=1,
    )
    duty = duty_rows[0] if duty_rows else None
    return {
        "employee": employee.name,
        "employee_name": employee.employee_name,
        "company": employee.company,
        "policy": policy.name,
        "attendance_mode": policy.attendance_mode,
        "require_gps": bool(policy.require_gps),
        "require_selfie": bool(policy.require_selfie),
        "tracking_mode": policy.tracking_mode,
        "field_duty": duty,
        "tracking_active": bool(duty and duty.tracking_enabled and last and last[0].log_type == "IN"),
        "tracking_interval_minutes": int(policy.tracking_interval_minutes or 30),
        "next_action": "OUT" if last and last[0].log_type == "IN" else "IN",
        "last_checkin": last[0] if last else None,
    }


@frappe.whitelist()
def get_live_locations(employee=None, company=None):
    """Return latest active-duty positions to authorized HR/supervisor users."""
    if not (set(frappe.get_roles(frappe.session.user)) & SUPERVISOR_ROLES):
        frappe.throw(_("Live location is restricted to authorized HR and managers"), frappe.PermissionError)
    from tradex_hr.tradexcel_hr.report_scope import permitted_employee_query

    frappe.has_permission("Employee", "select", throw=True)
    # Native Query Builder produces the permission predicate; no caller text
    # is interpolated into SQL. Optional filters only narrow that population.
    scope_sql = permitted_employee_query().get_sql()
    filters = ""
    values = []
    if employee:
        filters += " AND p.employee=%s"
        values.append(employee)
    if company:
        filters += " AND p.company=%s"
        values.append(company)
    return frappe.db.sql(
        f"""
        SELECT p.employee, e.employee_name, p.company, p.field_duty,
               p.ping_time, p.latitude, p.longitude, p.accuracy_m,
               p.suspicious_jump, p.speed_kmh
        FROM `tabTradexcel Location Ping` p
        JOIN `tabEmployee` e ON e.name=p.employee
        JOIN (
            SELECT employee, MAX(ping_time) AS latest_time
            FROM `tabTradexcel Location Ping`
            GROUP BY employee
        ) latest ON latest.employee=p.employee AND latest.latest_time=p.ping_time
        WHERE e.name IN ({scope_sql}) {filters}
        ORDER BY p.ping_time DESC
        """,
        values,
        as_dict=True,
    )


@frappe.whitelist(methods=["POST"])
def attach_selfie(checkin, file_url):
    doc = frappe.get_doc("Employee Checkin", checkin)
    employee = _employee(doc.employee)
    _assert_identity(employee)
    file_doc = frappe.db.get_value(
        "File", {"file_url": file_url},
        ["name", "owner", "attached_to_doctype", "attached_to_name"], as_dict=True,
    )
    if not file_doc or file_doc.owner != frappe.session.user:
        frappe.throw(_("The selfie file is not owned by the current user"), frappe.PermissionError)
    if file_doc.attached_to_name and (
        file_doc.attached_to_doctype != "Employee Checkin" or file_doc.attached_to_name != checkin
    ):
        frappe.throw(_("This file is already attached to another document"), frappe.PermissionError)
    frappe.db.set_value("File", file_doc.name, {
        "attached_to_doctype": "Employee Checkin",
        "attached_to_name": checkin,
        "attached_to_field": "custom_tradex_selfie",
    }, update_modified=False)
    doc.db_set("custom_tradex_selfie", file_url)
    return {"checkin": checkin, "file_url": file_url}
