"""Idempotent custom fields for mobile/field attendance evidence."""

from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def _fields() -> dict[str, list[dict[str, object]]]:
    return {
        "Employee": [
            {
                "fieldname": "custom_tradex_face_reference",
                "label": "Face Reference Photo",
                "fieldtype": "Attach Image",
                "insert_after": "image",
                "description": "Optional reference photo for the configured face-match provider.",
            },
        ],
        "Employee Checkin": [
            {
                "fieldname": "custom_tradex_source",
                "label": "Tradexcel Source",
                "fieldtype": "Select",
                "options": "Terminal\u000aMobile\u000aManual\u000aBridge",
                "insert_after": "device_id",
                "description": "Terminal/Bridge records never require GPS. Mobile records are validated by the Tradexcel policy service.",
            },
            {
                "fieldname": "custom_tradex_policy",
                "label": "Attendance Policy",
                "fieldtype": "Link",
                "options": "Tradexcel Attendance Policy",
                "insert_after": "custom_tradex_source",
            },
            {
                "fieldname": "custom_tradex_field_duty",
                "label": "Field Duty",
                "fieldtype": "Link",
                "options": "Tradexcel Field Duty",
                "insert_after": "custom_tradex_policy",
            },
            {
                "fieldname": "custom_tradex_location_status",
                "label": "Location Status",
                "fieldtype": "Select",
                "options": "Inside Zone\u000aOutside Approved\u000aOutside Accepted\u000aOutside Flagged\u000aOutside Blocked\u000aGPS Missing\u000aGPS Invalid\u000aWFH Approved\u000aWFH Review\u000aUnassigned",
                "insert_after": "custom_tradex_field_duty",
                "read_only": 1,
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_tradex_assigned_location",
                "label": "Matched Location",
                "fieldtype": "Link",
                "options": "Shift Location",
                "insert_after": "custom_tradex_location_status",
            },
            {
                "fieldname": "custom_tradex_distance_m",
                "label": "Distance from Location (m)",
                "fieldtype": "Float",
                "insert_after": "custom_tradex_assigned_location",
                "read_only": 1,
            },
            {
                "fieldname": "custom_tradex_gps_accuracy_m",
                "label": "GPS Accuracy (m)",
                "fieldtype": "Float",
                "insert_after": "longitude",
            },
            {
                "fieldname": "custom_tradex_gps_source",
                "label": "GPS Source",
                "fieldtype": "Data",
                "insert_after": "custom_tradex_gps_accuracy_m",
            },
            {
                "fieldname": "custom_tradex_selfie",
                "label": "Check-in Selfie",
                "fieldtype": "Attach Image",
                "insert_after": "custom_tradex_gps_source",
            },
            {
                "fieldname": "custom_tradex_face_match_status",
                "label": "Face Match",
                "fieldtype": "Select",
                "options": "Not Run\u000aMatched\u000aLow Confidence\u000aProvider Unavailable\u000aMismatch",
                "insert_after": "custom_tradex_selfie",
                "read_only": 1,
            },
            {
                "fieldname": "custom_tradex_face_match_score",
                "label": "Face Match Score",
                "fieldtype": "Float",
                "insert_after": "custom_tradex_face_match_status",
                "read_only": 1,
            },
            {
                "fieldname": "custom_tradex_review_status",
                "label": "Evidence Review",
                "fieldtype": "Select",
                "options": "Not Required\u000aPending\u000aApproved\u000aRejected",
                "insert_after": "custom_tradex_face_match_score",
                "read_only": 1,
            },
            {
                "fieldname": "custom_tradex_location_reason",
                "label": "Location/Integrity Note",
                "fieldtype": "Small Text",
                "insert_after": "custom_tradex_review_status",
                "read_only": 1,
            },
            {
                "fieldname": "custom_tradex_device_time",
                "label": "Device Time",
                "fieldtype": "Datetime",
                "insert_after": "custom_tradex_location_reason",
            },
            {
                "fieldname": "custom_tradex_received_at",
                "label": "Server Received At",
                "fieldtype": "Datetime",
                "insert_after": "custom_tradex_device_time",
                "read_only": 1,
            },
            {
                "fieldname": "custom_tradex_time_status",
                "label": "Time Integrity",
                "fieldtype": "Select",
                "options": "Trusted\u000aFlagged\u000aNo Device Time\u000aBlocked",
                "insert_after": "custom_tradex_received_at",
                "read_only": 1,
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_tradex_clock_skew_seconds",
                "label": "Device Clock Skew (seconds)",
                "fieldtype": "Float",
                "insert_after": "custom_tradex_device_time",
                "read_only": 1,
            },
            {
                "fieldname": "custom_tradex_sync_id",
                "label": "Mobile Sync ID",
                "fieldtype": "Data",
                "insert_after": "custom_tradex_device_time",
            },
        ],
        "Additional Salary": [
            {
                "fieldname": "custom_tradex_field_duty",
                "label": "Field Duty",
                "fieldtype": "Link",
                "options": "Tradexcel Field Duty",
                "insert_after": "ref_docname",
                "read_only": 1,
            },
            {
                "fieldname": "custom_tradex_allowance_key",
                "label": "Allowance Idempotency Key",
                "fieldtype": "Data",
                "insert_after": "custom_tradex_field_duty",
                "read_only": 1,
            },
            {
                "fieldname": "custom_tradex_distance_km",
                "label": "Approved Travel (Km)",
                "fieldtype": "Float",
                "insert_after": "custom_tradex_allowance_key",
                "read_only": 1,
            },
            {
                "fieldname": "custom_tradex_calculation_note",
                "label": "Allowance Calculation",
                "fieldtype": "Small Text",
                "insert_after": "custom_tradex_distance_km",
                "read_only": 1,
            },
        ],
    }


def ensure_field_attendance_fields() -> None:
    create_custom_fields(_fields(), update=True)


def ensure_field_transport_component() -> None:
    if frappe.db.exists("Salary Component", "Field Transport Allowance"):
        return
    frappe.get_doc({
        "doctype": "Salary Component",
        "salary_component": "Field Transport Allowance",
        "salary_component_abbr": "FTA",
        "type": "Earning",
        "amount": 0,
        "is_tax_applicable": 0,
    }).insert(ignore_permissions=True)
