"""Server-side adapter for mobile check-in, policy resolution and live pings."""

from __future__ import annotations

from datetime import datetime
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
    validate_gps_quality,
)

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


def _employee(employee: str | dict[str, Any]) -> frappe._dict:
    if isinstance(employee, dict):
        return frappe._dict(employee)
    value = frappe.db.get_value(
        "Employee",
        employee,
        ["name", "employee_name", "company", "branch", "department", "designation", "employment_type", "status", "user_id"],
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
        return
    if employee.user_id != frappe.session.user:
        frappe.throw(_("You may only create mobile attendance for your own linked Employee"), frappe.PermissionError)


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
    if doc.time and not doc.get("custom_tradex_device_time"):
        doc.custom_tradex_device_time = get_datetime(doc.time)
    doc.time = now_datetime()
    policy = _policy(employee, doc.time)
    duty = _approved_duty(employee, doc.get("custom_tradex_field_duty"), getdate(doc.time))
    has_gps = doc.latitude not in (None, "") and doc.longitude not in (None, "")
    if policy.require_gps and not has_gps:
        frappe.throw(_("This attendance policy requires GPS coordinates"))
    quality = (
        validate_gps_quality(doc.latitude, doc.longitude, doc.get("custom_tradex_gps_accuracy_m"))
        if has_gps else {"valid": False, "reason": "missing_coordinates", "accuracy_m": None}
    )
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
    doc.custom_tradex_review_status = "Pending" if policy.face_match_enabled else "Not Required"
    if policy.face_match_enabled:
        doc.custom_tradex_face_match_status = "Provider Unavailable"
        doc.custom_tradex_location_reason = "Face-match provider is not configured; attendance remains recorded."
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
    policy = _policy(employee_doc, now_datetime())
    device_time = get_datetime(time) if time else None
    if (policy.require_selfie or policy.face_match_enabled) and not selfie:
        frappe.throw(_("This attendance policy requires a selfie"))
    if selfie:
        owner = frappe.db.get_value("File", {"file_url": selfie}, "owner")
        if owner not in {frappe.session.user, "Administrator"}:
            frappe.throw(_("The selfie file is not owned by the current user"), frappe.PermissionError)
    received_at = now_datetime()
    claimed = _claim_event(sync_id, "Checkin", employee_doc, received_at, device_time)
    if claimed:
        return claimed
    checkin = frappe.get_doc({
        "doctype": "Employee Checkin",
        "employee": employee_doc.name,
        "log_type": log_type,
        # Attendance time is server-authoritative. Browser/device time remains
        # evidence only, preventing client-side backdating or future dating.
        "time": received_at,
        "latitude": latitude,
        "longitude": longitude,
        "custom_tradex_source": "Mobile",
        "custom_tradex_gps_accuracy_m": accuracy_m,
        "custom_tradex_gps_source": "Browser Geolocation API",
        "custom_tradex_device_time": device_time,
        "custom_tradex_clock_skew_seconds": (received_at - device_time).total_seconds() if device_time else None,
        "custom_tradex_field_duty": field_duty,
        "custom_tradex_selfie": selfie,
        "custom_tradex_sync_id": sync_id,
    })
    checkin.insert(ignore_permissions=True)
    frappe.db.set_value("Tradex Mobile Event", sync_id, {
        "target_doctype": "Employee Checkin", "target_name": checkin.name, "status": "Created"
    }, update_modified=False)
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
    device_time = get_datetime(ping_time) if ping_time else None
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
    return {
        "employee": employee.name,
        "employee_name": employee.employee_name,
        "company": employee.company,
        "policy": policy.name,
        "attendance_mode": policy.attendance_mode,
        "require_gps": bool(policy.require_gps),
        "require_selfie": bool(policy.require_selfie),
        "tracking_mode": policy.tracking_mode,
        "next_action": "OUT" if last and last[0].log_type == "IN" else "IN",
        "last_checkin": last[0] if last else None,
    }


@frappe.whitelist(methods=["POST"])
def attach_selfie(checkin, file_url):
    doc = frappe.get_doc("Employee Checkin", checkin)
    employee = _employee(doc.employee)
    _assert_identity(employee)
    file_owner = frappe.db.get_value("File", {"file_url": file_url}, "owner")
    if file_owner not in {frappe.session.user, "Administrator"}:
        frappe.throw(_("The selfie file is not owned by the current user"), frappe.PermissionError)
    doc.db_set("custom_tradex_selfie", file_url)
    return {"checkin": checkin, "file_url": file_url}
