"""Server-side adapter for mobile check-in, policy resolution and live pings."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
import re
from pathlib import Path
from typing import Any

import frappe
from frappe import _
from frappe.exceptions import DuplicateEntryError
from frappe.utils import getdate, get_datetime, now_datetime, today, get_system_timezone
from hrms.hr.doctype.shift_assignment.shift_assignment import get_actual_start_end_datetime_of_shift

from workforce_suite.workforce_suite.field_attendance import (
    detect_impossible_jump,
    evaluate_locations,
    location_status,
    calculate_allowance,
    track_distance_km,
    validate_gps_quality,
)
from workforce_suite.workforce_suite.face_match import FaceMatchUnavailable, match_images

SUPERVISOR_ROLES = {
    "System Manager",
    "Workforce Owner/Director",
    "Workforce Suite Manager",
    "Workforce Suite/Attendance Officer",
    "Workforce Factory Supervisor",
    "Workforce Branch Manager",
    "Workforce Department Manager",
}
MOBILE_REVIEW_ROLES = SUPERVISOR_ROLES | {"Workforce Attendance Correction Approver"}


def _category(employee: dict[str, Any]) -> str:
	return "Worker" if employee.get("employment_type") == "Worker" else "Staff"


def _device_datetime(value, require_timezone=False):
	"""Convert an ISO instant to the Frappe system timezone for MariaDB."""
	if not value:
		return None
	parsed = get_datetime(value)
	if require_timezone and isinstance(value, str) and (not re.search(r"(?:Z|[+-]\d{2}:\d{2})$", value) or not getattr(parsed, "tzinfo", None)):
		frappe.throw(_("Mobile timestamp must include a timezone offset (Z or +/-HH:MM)"))
	if not getattr(parsed, "tzinfo", None):
		return parsed
	# Frappe/MariaDB Datetime values are naive, but Frappe interprets them in
	# the configured system timezone.  Strip tzinfo only after converting the
	# supplied instant; stripping first shifts every UTC browser punch.
	return parsed.astimezone(ZoneInfo(get_system_timezone())).replace(tzinfo=None)


def _mobile_event_timing(received_at, device_time, policy):
    """Resolve canonical event time while retaining server receipt evidence.

    Browser time is not cryptographically trusted. It is nevertheless the only
    available capture time for an offline event, so it is retained as evidence
    and used for attendance date/shift resolution only after the event passes
    the current receipt-time security policy.
    """
    received_at = _device_datetime(received_at) or now_datetime()
    device_time = _device_datetime(device_time)
    if not device_time:
        reason = "No captured device time was supplied."
        status = "Blocked" if policy.get("offline_time_action") == "Block" else "Flagged"
        return {
            "event_time": received_at,
            "received_at": received_at,
            "clock_skew_seconds": None,
            "status": status,
            "reason": reason,
        }

    clock_skew_seconds = (received_at - device_time).total_seconds()
    max_age_hours = min(max(_policy_int(policy, "offline_max_age_hours", 72), 1), 720)
    trust_window_minutes = min(max(_policy_int(policy, "offline_trust_window_minutes", 5), 0), 1440)
    reason = ""
    beyond_acceptance_age = abs(clock_skew_seconds) > max_age_hours * 3600
    if beyond_acceptance_age:
        direction = "older than" if clock_skew_seconds > 0 else "far in the future beyond"
        reason = f"Captured time is {direction} the {max_age_hours}-hour offline limit."
    elif abs(clock_skew_seconds) > trust_window_minutes * 60:
        if clock_skew_seconds < 0:
            reason = f"Captured time is more than {trust_window_minutes} minutes in the future."
        else:
            reason = f"Captured time is outside the {trust_window_minutes}-minute trust window."

    if beyond_acceptance_age:
        # The acceptance age is a hard ingestion boundary.  `Flag` only
        # controls review of events inside that age but outside the trust
        # window; it must not become an unlimited backdating queue.
        status = "Blocked"
    elif not reason:
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
        ["name", "employee_name", "company", "branch", "department", "designation", "employment_type", "status", "user_id", "custom_workforce_face_reference"],
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
        "Workforce Attendance Policy",
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
	"""Use historical business policy only after current-time integrity passes."""
	current_policy = _policy(employee, received_at)
	if not device_time:
		return current_policy
	timing = _mobile_event_timing(received_at, device_time, current_policy)
	if timing["status"] != "Trusted":
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
        duty = frappe.get_doc("Workforce Field Duty", duty_name)
        if duty.employee != employee.name or getdate(duty.duty_date) != getdate(day):
            frappe.throw(_("Field Duty does not belong to this employee/date"))
        if duty.docstatus != 1 or duty.status not in {"Approved", "In Progress", "Completed"}:
            frappe.throw(_("Field Duty must be approved before it can authorize mobile attendance"))
        return duty
    rows = frappe.get_all(
        "Workforce Field Duty",
        filters={"employee": employee.name, "duty_date": day, "docstatus": 1, "status": ["in", ["Approved", "In Progress"]]},
        fields=["name"],
        limit=1,
    )
    return frappe.get_doc("Workforce Field Duty", rows[0].name) if rows else None


def _assert_employee_self(employee: frappe._dict) -> None:
    """Mobile mutation endpoints are employee self-service, not proxy APIs."""
    if frappe.session.user == "Administrator":
        return
    if employee.user_id != frappe.session.user:
        frappe.throw(_("You may only create mobile attendance for your own linked Employee"), frappe.PermissionError)


def _assert_mobile_selfie_file(file_url: str, *, allow_admin_owner=False):
    private_prefix = "/private/files/"
    if not file_url or not file_url.startswith(private_prefix):
        frappe.throw(_("Attendance selfies must use private file storage"), frappe.PermissionError)
    path_parts = file_url[len(private_prefix):].split("/")
    if not path_parts or any(part in {"", ".", ".."} for part in path_parts):
        frappe.throw(_("Attendance selfies must use private file storage"), frappe.PermissionError)
    file_doc = frappe.db.get_value(
        "File", {"file_url": file_url},
        ["name", "owner", "is_private", "attached_to_doctype", "attached_to_name", "attached_to_field"],
        as_dict=True,
    )
    if not file_doc:
        frappe.throw(_("The selfie file could not be found"), frappe.PermissionError)
    is_admin = frappe.session.user == "Administrator"
    if not file_doc.is_private:
        frappe.throw(_("Attendance selfies must be private files"), frappe.PermissionError)
    if file_doc.owner != frappe.session.user and not (is_admin and allow_admin_owner):
        frappe.throw(_("The selfie file is not owned by the current user"), frappe.PermissionError)
    return file_doc


def _assert_field_duty_settlement_actor(employee: frappe._dict) -> None:
    """Permit the originating employee or a currently scoped evidence reviewer."""
    if frappe.session.user == "Administrator":
        return
    if employee.user_id == frappe.session.user:
        return
    if MOBILE_REVIEW_ROLES.intersection(frappe.get_roles()):
        from workforce_suite.workforce_suite.report_scope import permitted_employee_names
        if employee.name in permitted_employee_names(employee.company):
            return
        frappe.throw(_("This employee is outside your permitted scope."), frappe.PermissionError)
    frappe.throw(_("Only the linked employee or a scoped mobile evidence reviewer may settle this duty."), frappe.PermissionError)


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
	settings = frappe.get_single("Workforce Face Match Settings")
	if not settings.enabled or settings.provider != "OpenCV YuNet + SFace":
		raise FaceMatchUnavailable("Face-match provider is not enabled")
	if not employee.custom_workforce_face_reference:
		raise FaceMatchUnavailable("Employee has no face reference photo")
	return match_images(
		_site_file_path(employee.custom_workforce_face_reference),
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
        "Workforce Mobile Event", sync_id,
        ["employee", "target_doctype", "target_name"], as_dict=True,
    )
    if existing:
        if existing.employee != employee.name:
            frappe.throw(_("This sync ID belongs to another employee"), frappe.PermissionError)
        if existing.target_name:
            return frappe.get_doc(existing.target_doctype, existing.target_name).as_dict()
        frappe.throw(_("This event is already being processed; retry with the same sync ID"))
    event = frappe.get_doc({
        "doctype": "Workforce Mobile Event", "sync_id": sync_id,
        "event_type": event_type, "employee": employee.name,
        "company": employee.company, "received_at": received_at,
        "device_time": device_time, "status": "Pending",
    })
    try:
        event.insert(ignore_permissions=True)
    except DuplicateEntryError:
        existing = frappe.db.get_value(
            "Workforce Mobile Event", sync_id,
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
        filters={"employee": employee_name, "custom_workforce_field_duty": duty_name},
        fields=["time", "latitude", "longitude"],
    )
    points += frappe.get_all(
        "Workforce Location Ping",
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
	duty = frappe.get_doc("Workforce Field Duty", duty_name)
	employee = _employee(duty.employee)
	_assert_field_duty_settlement_actor(employee)
	if _field_duty_has_unreleased_checkin(duty_name):
		return {"duty": duty_name, "amount": 0, "status": "Awaiting attendance review"}
	policy = _policy(employee, duty.duty_date)
	if policy.allowance_mode in (None, "None", "Manual"):
		return {"duty": duty.name, "amount": 0, "status": "No automatic allowance"}
	key = f"field-duty:{duty.name}"
	existing = frappe.db.get_value("Additional Salary", {"custom_workforce_allowance_key": key}, "name")
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
		"ref_doctype": "Workforce Field Duty",
		"ref_docname": duty.name,
		"custom_workforce_field_duty": duty.name,
		"custom_workforce_allowance_key": key,
		"custom_workforce_distance_km": result["distance_km"],
		"custom_workforce_calculation_note": f"{result['distance_km']} km × {result['rate_per_km']} × {policy.allowance_multiplier or 1}",
	})
	doc.insert(ignore_permissions=True)
	return {"duty": duty.name, **result, "additional_salary": doc.name, "status": "Draft"}


def enrich_mobile_checkin(doc, method=None):
    """Enrich explicitly mobile-sourced check-ins; terminal rows are untouched."""
    source = doc.get("custom_workforce_source")
    if not source and doc.is_new() and not doc.get("device_id"):
        # HRMS's native PWA does not know this app's source field. Treat a new
        # user-created check-in without a terminal/device id as mobile so the
        # same server-side policy cannot be bypassed through the native route.
        doc.custom_workforce_source = "Mobile"
        source = "Mobile"
    previous = None
    if callable(getattr(doc, "is_new", None)) and not doc.is_new():
        previous = doc.get_doc_before_save()
    if previous and previous.get("custom_workforce_source") == "Mobile":
        protected = (
            "employee", "time", "log_type", "custom_workforce_source", "custom_workforce_device_time",
            "custom_workforce_received_at", "custom_workforce_time_status", "custom_workforce_policy",
            "custom_workforce_review_status", "skip_auto_attendance", "custom_workforce_time_reason",
            "latitude", "longitude", "custom_workforce_gps_accuracy_m", "custom_workforce_selfie",
            "custom_workforce_field_duty", "custom_workforce_reviewed_by", "custom_workforce_reviewed_at",
            "custom_workforce_review_reason", "custom_workforce_clock_skew_seconds",
            "custom_workforce_sync_id", "custom_workforce_gps_source", "custom_workforce_location_status",
            "custom_workforce_assigned_location", "custom_workforce_distance_m",
            "custom_workforce_face_match_status", "custom_workforce_face_match_score",
            "custom_workforce_location_reason",
        )
        if any(doc.get(field) != previous.get(field) for field in protected):
            frappe.throw(_("Use the mobile evidence review actions to change protected evidence."), frappe.PermissionError)
        return
    if source != "Mobile":
        return
    employee = _employee(doc.employee)
    received_at = now_datetime()
    # Do not infer captured time from the canonical `time` field.  The latter
    # may already be server receipt time when a client omitted its timestamp;
    # treating it as device evidence would bypass the missing-time quarantine.
    device_time = _device_datetime(doc.get("custom_workforce_device_time"))
    # Timestamp integrity is always judged with the policy active when the
    # server received the event.  The captured timestamp cannot choose weaker
    # historical security controls.
    receipt_policy = _policy(employee, received_at)
    timing = _mobile_event_timing(received_at, device_time, receipt_policy)
    if timing["status"] == "Blocked":
        frappe.throw(_("Mobile attendance time rejected: {0}").format(timing["reason"]))
    doc.custom_workforce_received_at = timing["received_at"]
    doc.custom_workforce_device_time = device_time
    doc.custom_workforce_time_status = timing["status"]
    doc.custom_workforce_time_reason = timing["reason"]
    doc.custom_workforce_clock_skew_seconds = timing["clock_skew_seconds"]
    doc.time = timing["event_time"]
    has_gps = doc.latitude not in (None, "") and doc.longitude not in (None, "")
    if receipt_policy.require_selfie or receipt_policy.face_match_enabled:
        if not doc.get("custom_workforce_selfie"):
            frappe.throw(_("This attendance policy requires a selfie"))
    if receipt_policy.require_gps and not has_gps:
        frappe.throw(_("This attendance policy requires GPS coordinates"))

    if timing["status"] == "Flagged":
        if receipt_policy.face_match_enabled:
            try:
                face_result = _run_face_match(employee, doc.custom_workforce_selfie)
            except FaceMatchUnavailable as exc:
                frappe.throw(_("Face verification could not be completed: {0}").format(exc))
            rejection = _face_match_rejection_message(face_result)
            if rejection:
                frappe.throw(rejection)
            doc.custom_workforce_face_match_status = face_result["status"]
            doc.custom_workforce_face_match_score = face_result["score"]
        # Native HRMS auto attendance only understands this field.  The
        # Workforce review label alone is not a quarantine boundary.
        doc.skip_auto_attendance = 1
        doc.custom_workforce_policy = receipt_policy.name
        doc.custom_workforce_review_status = "Pending"
        doc.custom_workforce_location_status = "Time Review Required"
        doc.custom_workforce_location_reason = timing["reason"]
        return

    # Only a trusted timestamp may select historical business rules such as
    # shift/location/face-match policy.
    policy = _policy_for_mobile_event(employee, timing["received_at"], timing["event_time"])
    validate_mobile_event_business_context(
        doc,
        employee,
        doc.time,
        policy,
        security_policy=receipt_policy,
    )
    doc.skip_auto_attendance = 0
    doc.custom_workforce_review_status = "Not Required"


@frappe.whitelist(methods=["POST"])
def mobile_checkin(employee, log_type, latitude=None, longitude=None, accuracy_m=None, time=None, field_duty=None, selfie=None, sync_id=None):
    if log_type not in {"IN", "OUT"}:
        frappe.throw(_("Log Type must be IN or OUT"))
    if not sync_id:
        frappe.throw(_("A mobile sync ID is required"))
    employee_doc = _employee(employee)
    _assert_employee_self(employee_doc)
    existing = frappe.db.get_value(
        "Employee Checkin", {"custom_workforce_sync_id": sync_id},
        ["name", "employee"], as_dict=True,
    )
    if existing:
        if existing.employee != employee_doc.name:
            frappe.throw(_("This sync ID belongs to another employee"), frappe.PermissionError)
        return frappe.get_doc("Employee Checkin", existing.name).as_dict()
    received_at = now_datetime()
    device_time = _device_datetime(time, require_timezone=True)
    policy = _policy(employee_doc, received_at)
    timing = _mobile_event_timing(received_at, device_time, policy)
    if timing["status"] == "Blocked":
        frappe.throw(_("Mobile attendance time rejected: {0}").format(timing["reason"]))
    if (policy.require_selfie or policy.face_match_enabled) and not selfie:
        frappe.throw(_("This attendance policy requires a selfie"))
    if selfie:
        _assert_mobile_selfie_file(selfie, allow_admin_owner=True)
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
        "custom_workforce_source": "Mobile",
        "custom_workforce_gps_accuracy_m": accuracy_m,
        "custom_workforce_gps_source": "Browser Geolocation API",
        "custom_workforce_device_time": device_time,
        "custom_workforce_received_at": timing["received_at"],
        "custom_workforce_time_status": timing["status"],
        "custom_workforce_clock_skew_seconds": timing["clock_skew_seconds"],
        "custom_workforce_field_duty": field_duty,
        "custom_workforce_selfie": selfie,
        "custom_workforce_sync_id": sync_id,
    })
    checkin.insert(ignore_permissions=True)
    frappe.db.set_value("Workforce Mobile Event", sync_id, {
        "target_doctype": "Employee Checkin", "target_name": checkin.name, "status": "Created"
    }, update_modified=False)
    if log_type == "OUT" and field_duty and checkin.get("custom_workforce_review_status") == "Not Required":
        frappe.enqueue(
            "workforce_suite.workforce_suite.field_attendance_service.settle_field_duty_allowance",
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
    _assert_employee_self(employee_doc)
    existing = frappe.db.get_value(
        "Workforce Location Ping", {"sync_id": sync_id},
        ["name", "employee"], as_dict=True,
    )
    if existing:
        if existing.employee != employee_doc.name:
            frappe.throw(_("This sync ID belongs to another employee"), frappe.PermissionError)
        return frappe.get_doc("Workforce Location Ping", existing.name).as_dict()
    received_at = now_datetime()
    device_time = _device_datetime(ping_time, require_timezone=True)
    duty = _approved_duty(employee_doc, field_duty, getdate(received_at))
    policy = _policy(employee_doc, received_at)
    if policy.tracking_mode != "Active Duty Pings" or not duty.tracking_enabled:
        frappe.throw(_("Active location pings are not enabled for this duty"))
    if duty.start_time and received_at < get_datetime(duty.start_time):
        frappe.throw(_("This location ping is before the field duty starts"))
    if duty.end_time and received_at > get_datetime(duty.end_time):
        frappe.throw(_("This location ping is after the field duty ends"))
    previous = frappe.get_all(
        "Workforce Location Ping",
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
        "doctype": "Workforce Location Ping",
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
    frappe.db.set_value("Workforce Mobile Event", sync_id, {
        "target_doctype": "Workforce Location Ping", "target_name": ping.name, "status": "Created"
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
        "Workforce Field Duty",
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
        "require_selfie": bool(policy.require_selfie or policy.face_match_enabled),
        "offline_max_age_hours": _policy_int(policy, "offline_max_age_hours", 72),
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
    from workforce_suite.workforce_suite.report_scope import permitted_employee_query

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
        FROM `tabWorkforce Location Ping` p
        JOIN `tabEmployee` e ON e.name=p.employee
        JOIN (
            SELECT employee, MAX(ping_time) AS latest_time
            FROM `tabWorkforce Location Ping`
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
    _assert_employee_self(employee)
    if doc.custom_workforce_source != "Mobile":
        frappe.throw(_("Selfie metadata can only be attached to mobile attendance"), frappe.PermissionError)
    if not doc.custom_workforce_selfie or file_url != doc.custom_workforce_selfie:
        frappe.throw(_("The selfie must match the evidence recorded when attendance was submitted"), frappe.PermissionError)
    file_doc = _assert_mobile_selfie_file(file_url, allow_admin_owner=True)
    if file_doc.attached_to_name and (
        file_doc.attached_to_doctype != "Employee Checkin" or file_doc.attached_to_name != checkin
    ):
        frappe.throw(_("This file is already attached to another document"), frappe.PermissionError)
    if file_doc.attached_to_doctype == "Employee Checkin" and file_doc.attached_to_name == checkin:
        return {"checkin": checkin, "file_url": file_url}
    frappe.db.set_value("File", file_doc.name, {
        "attached_to_doctype": "Employee Checkin",
        "attached_to_name": checkin,
        "attached_to_field": "custom_workforce_selfie",
    }, update_modified=False)
    return {"checkin": checkin, "file_url": file_url}


def _policy_int(policy, fieldname, default):
	try:
		return int(default if policy.get(fieldname) in (None, "") else policy.get(fieldname))
	except (TypeError, ValueError):
		return default


def validate_mobile_event_business_context(
    doc,
    employee: frappe._dict,
    event_time,
    policy: frappe._dict,
    security_policy: frappe._dict | None = None,
):
    """Validate business rules after timestamp integrity is trusted/released.

    This is deliberately shared by normal trusted inserts and reviewer
    approval.  A reviewer never releases a quarantined event without rerunning
    the same duty, GPS, zone, shift and evidence rules.
    """
    security_policy = security_policy or policy
    duty = _approved_duty(employee, doc.get("custom_workforce_field_duty"), getdate(event_time))
    has_gps = doc.latitude not in (None, "") and doc.longitude not in (None, "")
    if policy.require_gps or security_policy.require_gps:
        if not has_gps:
            frappe.throw(_("This attendance policy requires GPS coordinates"))
    requires_selfie = any(
        bool(rule.get(field))
        for rule in (policy, security_policy)
        for field in ("require_selfie", "face_match_enabled")
    )
    if requires_selfie and not doc.get("custom_workforce_selfie"):
        frappe.throw(_("This attendance policy requires a selfie"))

    quality = (
        validate_gps_quality(doc.latitude, doc.longitude, doc.get("custom_workforce_gps_accuracy_m"))
        if has_gps else {"valid": False, "reason": "missing_coordinates", "accuracy_m": None}
    )
    if (policy.require_gps or security_policy.require_gps) and has_gps and doc.get("custom_workforce_gps_accuracy_m") in (None, ""):
        quality = {"valid": False, "reason": "accuracy_missing", "accuracy_m": None}
    if ((policy.require_gps or security_policy.require_gps) or "Block" in (policy.outside_action, security_policy.outside_action)) and not quality["valid"]:
        frappe.throw(_("This attendance policy requires a valid GPS fix"))

    shift_actual = get_actual_start_end_datetime_of_shift(employee.name, get_datetime(event_time), True)
    shift_type = shift_actual.shift_type.name if shift_actual else None
    locations = _assigned_locations(employee, getdate(event_time), duty, shift_type)
    evaluation = evaluate_locations(doc.latitude, doc.longitude, locations) if has_gps else {"inside": False, "nearest": None}
    status = location_status(
        policy.attendance_mode,
        has_gps=has_gps and quality["valid"],
        inside_assigned_zone=evaluation["inside"],
        outside_action="Block" if "Block" in (policy.outside_action, security_policy.outside_action) else policy.outside_action,
        approved_external=bool(duty),
    )
    if status == "Outside Blocked":
        frappe.throw(_("Mobile check-in is outside the permitted area"))

    matched_location = evaluation.get("matched") or evaluation.get("nearest")
    doc.custom_workforce_policy = policy.name
    doc.custom_workforce_field_duty = duty.name if duty else doc.get("custom_workforce_field_duty")
    doc.custom_workforce_location_status = status if quality["valid"] else "GPS Invalid"
    doc.custom_workforce_assigned_location = matched_location["name"] if matched_location else None
    doc.custom_workforce_distance_m = matched_location["distance_m"] if matched_location else None

    if policy.face_match_enabled or security_policy.face_match_enabled:
        try:
            face_result = _run_face_match(employee, doc.custom_workforce_selfie)
        except FaceMatchUnavailable as exc:
            frappe.throw(_("Face verification could not be completed: {0}").format(exc))
        rejection = _face_match_rejection_message(face_result)
        if rejection:
            frappe.throw(rejection)
        doc.custom_workforce_face_match_status = face_result["status"]
        doc.custom_workforce_face_match_score = face_result["score"]
        doc.custom_workforce_location_reason = (
            f"Face match {face_result['status']} ({face_result['score']:.3f}; "
            f"threshold {face_result['threshold']:.3f})."
        )
    elif not quality["valid"]:
        doc.custom_workforce_location_reason = quality["reason"]
    elif status in {"Outside Flagged", "WFH Review"}:
        doc.custom_workforce_location_reason = "Outside/WFH attendance accepted according to policy."
    elif matched_location:
        doc.custom_workforce_location_reason = f"Matched {matched_location['name']} at {matched_location['distance_m']} m."
    return {"policy": policy, "duty": duty, "shift": shift_actual}


def _field_duty_has_unreleased_checkin(duty_name):
    """Keep allowance effects paused while any duty punch awaits review."""
    return bool(
        frappe.db.exists(
            "Employee Checkin",
            {
                "custom_workforce_field_duty": duty_name,
                "custom_workforce_review_status": ["in", ["Pending", "Rejected"]],
            },
        )
    )


def _reviewable_checkin(checkin):
    doc = frappe.get_doc("Employee Checkin", checkin, for_update=True)
    _assert_review_permission(doc)
    if doc.custom_workforce_source != "Mobile":
        frappe.throw(_("Only mobile attendance evidence can be reviewed"))
    if doc.custom_workforce_time_status != "Flagged":
        frappe.throw(_("Only time-integrity flagged check-ins can be reviewed"))
    return doc


@frappe.whitelist(methods=["POST"])
def approve_mobile_checkin(checkin, review_note=None):
    """Release one quarantined check-in for native auto attendance."""
    doc = _reviewable_checkin(checkin)
    if frappe.session.user != "Administrator" and doc.owner == frappe.session.user:
        frappe.throw(_("A different reviewer must approve your own check-in"), frappe.PermissionError)
    review_note = (review_note or "").strip()
    if len(review_note) < 3:
        frappe.throw(_("Enter a reason for this evidence review."))
    if doc.custom_workforce_review_status == "Approved":
        return doc.as_dict()
    if doc.custom_workforce_review_status == "Rejected":
        frappe.throw(_("A rejected check-in cannot be approved"))
    if doc.custom_workforce_review_status != "Pending":
        frappe.throw(_("This check-in is not awaiting review"))

    employee = _employee(doc.employee)
    # The policy stored on the quarantined check-in is the receipt-time
    # security policy. Load that exact document before validation: resolving
    # today's policy here could let a later policy change weaken evidence
    # requirements that applied when the event was received.
    receipt_policy_name = doc.custom_workforce_policy
    if not receipt_policy_name:
        frappe.throw(_("This check-in has no stored receipt-time policy"))
    security_policy = frappe.get_doc("Workforce Attendance Policy", receipt_policy_name)

    # The event-time policy supplies historical business semantics (duty,
    # zone, shift and evidence rules). The captured timestamp cannot skip
    # either policy's security and business validation.
    event_policy = _policy(employee, doc.time)
    validate_mobile_event_business_context(
        doc,
        employee,
        doc.time,
        event_policy,
        security_policy=security_policy,
    )
    doc.custom_workforce_policy = receipt_policy_name
    reviewed_at = now_datetime()
    frappe.db.set_value(
        "Employee Checkin",
        doc.name,
        {
            "custom_workforce_review_status": "Approved",
            "custom_workforce_reviewed_by": frappe.session.user,
            "custom_workforce_reviewed_at": reviewed_at,
            "custom_workforce_review_reason": review_note or "Approved by authorized reviewer.",
            "custom_workforce_policy": doc.custom_workforce_policy,
            "custom_workforce_field_duty": doc.custom_workforce_field_duty,
            "custom_workforce_location_status": doc.custom_workforce_location_status,
            "custom_workforce_assigned_location": doc.custom_workforce_assigned_location,
            "custom_workforce_distance_m": doc.custom_workforce_distance_m or 0,
            "custom_workforce_face_match_status": doc.custom_workforce_face_match_status,
            "custom_workforce_face_match_score": doc.custom_workforce_face_match_score or 0,
            "custom_workforce_location_reason": doc.custom_workforce_location_reason,
            "skip_auto_attendance": 0,
        },
        update_modified=True,
    )
    frappe.get_doc("Employee Checkin", doc.name).add_comment(
        "Info", _("Mobile attendance evidence approved by {0}.").format(frappe.session.user)
    )
    if doc.log_type == "OUT" and doc.custom_workforce_field_duty:
        frappe.enqueue(
            "workforce_suite.workforce_suite.field_attendance_service.settle_field_duty_allowance",
            duty_name=doc.custom_workforce_field_duty,
            queue="short",
            enqueue_after_commit=True,
        )
    return frappe.get_doc("Employee Checkin", doc.name).as_dict()


@frappe.whitelist(methods=["POST"])
def reject_mobile_checkin(checkin, review_note=None):
    """Permanently exclude one quarantined check-in from native attendance."""
    doc = _reviewable_checkin(checkin)
    review_note = (review_note or "").strip()
    if len(review_note) < 3:
        frappe.throw(_("Enter a reason for this evidence review."))
    if doc.custom_workforce_review_status == "Rejected":
        return doc.as_dict()
    if doc.custom_workforce_review_status == "Approved":
        frappe.throw(_("An approved check-in cannot be rejected"))
    if doc.custom_workforce_review_status != "Pending":
        frappe.throw(_("This check-in is not awaiting review"))

    reviewed_at = now_datetime()
    frappe.db.set_value(
        "Employee Checkin",
        doc.name,
        {
            "custom_workforce_review_status": "Rejected",
            "custom_workforce_reviewed_by": frappe.session.user,
            "custom_workforce_reviewed_at": reviewed_at,
            "custom_workforce_review_reason": review_note or "Rejected by authorized reviewer.",
            "skip_auto_attendance": 1,
        },
        update_modified=True,
    )
    frappe.get_doc("Employee Checkin", doc.name).add_comment(
        "Info", _("Mobile attendance evidence rejected by {0}.").format(frappe.session.user)
    )
    return frappe.get_doc("Employee Checkin", doc.name).as_dict()


def _assert_review_permission(doc):
    if frappe.session.user != "Administrator" and not MOBILE_REVIEW_ROLES.intersection(frappe.get_roles()):
        frappe.throw(_("You are not permitted to review mobile attendance evidence."), frappe.PermissionError)
    doc.check_permission("read")
    from workforce_suite.workforce_suite.report_scope import permitted_employee_names
    company = frappe.db.get_value("Employee", doc.employee, "company")
    if doc.employee not in permitted_employee_names(company):
        frappe.throw(_("This employee is outside your permitted scope."), frappe.PermissionError)
