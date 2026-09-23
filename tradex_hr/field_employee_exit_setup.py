"""Idempotent setup for native employee exit fields and checklist."""
from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def ensure_employee_exit_fields():
    create_custom_fields({
        "Employee Separation": [
            {
                "fieldname": "custom_tradex_separation_type",
                "label": "Separation Type",
                "fieldtype": "Select",
                "options": "Resignation\nEmployer Termination\nRetrenchment\nDischarge\nDismissal / Removal\nRetirement\nContract Completion\nDeath\nOther / Legal Review",
                "reqd": 1,
                "insert_after": "resignation_letter_date",
                "description": "Process category only. It does not calculate statutory entitlement.",
            },
            {
                "fieldname": "custom_tradex_statutory_review_status",
                "label": "Legal / Statutory Review",
                "fieldtype": "Select",
                "options": "Pending\nApproved\nNot Applicable",
                "default": "Pending",
                "read_only": 1,
                "allow_on_submit": 1,
                "in_list_view": 1,
                "insert_after": "custom_tradex_separation_type",
            },
            {
                "fieldname": "custom_tradex_statutory_reviewed_by",
                "label": "Review Recorded By",
                "fieldtype": "Link",
                "options": "User",
                "read_only": 1,
                "allow_on_submit": 1,
                "insert_after": "custom_tradex_statutory_review_status",
            },
            {
                "fieldname": "custom_tradex_statutory_reviewed_at",
                "label": "Review Recorded At",
                "fieldtype": "Datetime",
                "read_only": 1,
                "allow_on_submit": 1,
                "insert_after": "custom_tradex_statutory_reviewed_by",
            },
            {
                "fieldname": "custom_tradex_statutory_review_notes",
                "label": "Legal / Statutory Review Notes",
                "fieldtype": "Small Text",
                "read_only": 1,
                "allow_on_submit": 1,
                "insert_after": "custom_tradex_statutory_reviewed_at",
            },
        ],
        "Full and Final Statement": [{
            "fieldname": "workflow_state",
            "label": "Workflow State",
            "fieldtype": "Link",
            "options": "Workflow State",
            "read_only": 1,
            "no_copy": 1,
            "insert_after": "status",
        }],
    }, update=True)


def ensure_default_exit_template():
    title = "Tradexcel Standard Exit Checklist"
    if frappe.db.exists("Employee Separation Template", {"title": title}):
        return
    if not frappe.db.exists("DocType", "Employee Separation Template"):
        return
    activities = [
        "Confirm approved last working day",
        "Review Attendance and Leave through relieving date",
        "Resolve Attendance Requests and captured mobile evidence",
        "Review future Shift Assignments",
        "Review company assets and access card",
        "Review Employee Advances and Expense Claims",
        "Prepare native Full & Final Statement",
        "Review legal classification and statutory applicability",
        "Prepare service certificate where applicable",
        "Remove biometric enrollment from physical attendance device",
    ]
    doc = frappe.get_doc({
        "doctype": "Employee Separation Template",
        "title": title,
        "activities": [
            {"activity_name": name, "begin_on": 0, "duration": 1}
            for name in activities
        ],
    })
    doc.insert(ignore_permissions=True)