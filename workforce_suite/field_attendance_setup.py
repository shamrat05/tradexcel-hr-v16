"""Idempotent custom fields for mobile/field attendance evidence."""

from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def _fields() -> dict[str, list[dict[str, object]]]:
    return {
        "Employee": [
            {
                "fieldname": "custom_workforce_face_reference",
                "label": "Face Reference Photo",
                "fieldtype": "Attach Image",
                "insert_after": "image",
                "description": "Optional reference photo for the configured face-match provider.",
            },
        ],
        "Employee Checkin": [
            {"fieldname": "custom_workforce_time_reason", "label": "Original Time Integrity Reason",
             "fieldtype": "Small Text", "read_only": 1, "insert_after": "custom_workforce_time_status"},
            {
                "fieldname": "custom_workforce_source",
                "label": "Workforce Source",
                "fieldtype": "Select",
                "options": "Terminal\u000aMobile\u000aManual\u000aBridge",
                "insert_after": "device_id",
                "description": "Terminal/Bridge records never require GPS. Mobile records are validated by the Workforce policy service.",
            },
            {
                "fieldname": "custom_workforce_policy",
                "label": "Attendance Policy",
                "fieldtype": "Link",
                "options": "Workforce Attendance Policy",
                "insert_after": "custom_workforce_source",
            },
            {
                "fieldname": "custom_workforce_field_duty",
                "label": "Field Duty",
                "fieldtype": "Link",
                "options": "Workforce Field Duty",
                "insert_after": "custom_workforce_policy",
            },
            {
                "fieldname": "custom_workforce_location_status",
                "label": "Location Status",
                "fieldtype": "Select",
                "options": "Inside Zone\u000aOutside Approved\u000aOutside Accepted\u000aOutside Flagged\u000aOutside Blocked\u000aGPS Missing\u000aGPS Invalid\u000aWFH Approved\u000aWFH Review\u000aUnassigned\u000aTime Review Required",
                "insert_after": "custom_workforce_field_duty",
                "read_only": 1,
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_workforce_assigned_location",
                "label": "Matched Location",
                "fieldtype": "Link",
                "options": "Shift Location",
                "insert_after": "custom_workforce_location_status",
            },
            {
                "fieldname": "custom_workforce_distance_m",
                "label": "Distance from Location (m)",
                "fieldtype": "Float",
                "insert_after": "custom_workforce_assigned_location",
                "read_only": 1,
            },
            {
                "fieldname": "custom_workforce_gps_accuracy_m",
                "label": "GPS Accuracy (m)",
                "fieldtype": "Float",
                "insert_after": "longitude",
            },
            {
                "fieldname": "custom_workforce_gps_source",
                "label": "GPS Source",
                "fieldtype": "Data",
                "insert_after": "custom_workforce_gps_accuracy_m",
            },
            {
                "fieldname": "custom_workforce_selfie",
                "label": "Check-in Selfie",
                "fieldtype": "Attach Image",
                "insert_after": "custom_workforce_gps_source",
            },
            {
                "fieldname": "custom_workforce_face_match_status",
                "label": "Face Match",
                "fieldtype": "Select",
                "options": "Not Run\u000aMatched\u000aLow Confidence\u000aProvider Unavailable\u000aMismatch",
                "insert_after": "custom_workforce_selfie",
                "read_only": 1,
            },
            {
                "fieldname": "custom_workforce_face_match_score",
                "label": "Face Match Score",
                "fieldtype": "Float",
                "insert_after": "custom_workforce_face_match_status",
                "read_only": 1,
            },
            {
                "fieldname": "custom_workforce_review_status",
                "label": "Evidence Review",
                "fieldtype": "Select",
                "options": "Not Required\u000aPending\u000aApproved\u000aRejected",
                "insert_after": "custom_workforce_face_match_score",
                "read_only": 1,
            },
            {
                "fieldname": "custom_workforce_location_reason",
                "label": "Location/Integrity Note",
                "fieldtype": "Small Text",
                "insert_after": "custom_workforce_review_status",
                "read_only": 1,
            },
            {
                "fieldname": "custom_workforce_device_time",
                "label": "Device Time",
                "fieldtype": "Datetime",
                "insert_after": "custom_workforce_location_reason",
            },
            {
                "fieldname": "custom_workforce_received_at",
                "label": "Server Received At",
                "fieldtype": "Datetime",
                "insert_after": "custom_workforce_device_time",
                "read_only": 1,
            },
            {
                "fieldname": "custom_workforce_time_status",
                "label": "Time Integrity",
                "fieldtype": "Select",
                "options": "Trusted\u000aFlagged\u000aNo Device Time\u000aBlocked",
                "insert_after": "custom_workforce_received_at",
                "read_only": 1,
                "in_list_view": 1,
            },
            {
                "fieldname": "custom_workforce_clock_skew_seconds",
                "label": "Device Clock Skew (seconds)",
                "fieldtype": "Float",
                "insert_after": "custom_workforce_device_time",
                "read_only": 1,
            },
            {
                "fieldname": "custom_workforce_sync_id",
                "label": "Mobile Sync ID",
                "fieldtype": "Data",
                "insert_after": "custom_workforce_device_time",
            },
            {'fieldname': 'custom_workforce_reviewed_by', 'label': 'Reviewed By', 'fieldtype': 'Link', 'read_only': 1, 'insert_after': 'custom_workforce_review_status', 'options': 'User'},
            {'fieldname': 'custom_workforce_reviewed_at', 'label': 'Reviewed At', 'fieldtype': 'Datetime', 'read_only': 1, 'insert_after': 'custom_workforce_review_status'},
            {'fieldname': 'custom_workforce_review_reason', 'label': 'Review Reason', 'fieldtype': 'Small Text', 'read_only': 1, 'insert_after': 'custom_workforce_review_status'},
        ],
        "Additional Salary": [
            {
                "fieldname": "custom_workforce_payroll_input_key",
                "label": "Workforce Payroll Input Key",
                "fieldtype": "Data",
                "insert_after": "ref_docname",
                "read_only": 1,
                "unique": 1,
                "description": "Stable key for an idempotent derived payroll input.",
            },
            {
                "fieldname": "custom_workforce_field_duty",
                "label": "Field Duty",
                "fieldtype": "Link",
                "options": "Workforce Field Duty",
                "insert_after": "ref_docname",
                "read_only": 1,
            },
            {
                "fieldname": "custom_workforce_allowance_key",
                "label": "Allowance Idempotency Key",
                "fieldtype": "Data",
                "insert_after": "custom_workforce_field_duty",
                "read_only": 1,
            },
            {
                "fieldname": "custom_workforce_distance_km",
                "label": "Approved Travel (Km)",
                "fieldtype": "Float",
                "insert_after": "custom_workforce_allowance_key",
                "read_only": 1,
            },
            {
                "fieldname": "custom_workforce_calculation_note",
                "label": "Allowance Calculation",
                "fieldtype": "Small Text",
                "insert_after": "custom_workforce_distance_km",
                "read_only": 1,
            },
        ],
        "Payroll Entry": [
            {
                "fieldname": "custom_workforce_run_key",
                "label": "Workforce Managed Run Key",
                "fieldtype": "Data",
                "insert_after": "payroll_frequency",
                "read_only": 1,
                "permlevel": 1,
                "unique": 1,
            },
            {
                "fieldname": "custom_workforce_population_hash",
                "label": "Workforce Payroll Population Fingerprint",
                "fieldtype": "Data",
                "insert_after": "custom_workforce_run_key",
                "read_only": 1,
                "permlevel": 1,
            },
            {
                "fieldname": "custom_workforce_attendance_revision",
                "label": "Workforce Attendance Revision",
                "fieldtype": "Data",
                "insert_after": "custom_workforce_population_hash",
                "read_only": 1,
                "permlevel": 1,
            },
        ],
        "Salary Structure": [
            {
                "fieldname": "custom_workforce_pay_basis",
                "label": "Workforce Pay Basis",
                "fieldtype": "Select",
                "options": "Monthly Salary\nDaily Wage",
                "insert_after": "payroll_frequency",
                "description": "Explicit financial pay basis. Never inferred from Employment Type.",
            },
            {
                "fieldname": "custom_workforce_daily_wage_component",
                "label": "Daily Wage Salary Component",
                "fieldtype": "Link",
                "options": "Salary Component",
                "insert_after": "custom_workforce_pay_basis",
                "depends_on": 'eval:doc.custom_workforce_pay_basis=="Daily Wage"',
                "mandatory_depends_on": 'eval:doc.custom_workforce_pay_basis=="Daily Wage"',
                "description": (
                    "For Daily Wage structures, the native Salary Component that receives the regular wage "
                    "amount derived from finalized Attendance and the effective Salary Structure Assignment base rate."
                ),
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
