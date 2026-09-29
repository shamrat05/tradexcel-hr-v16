"""Custom review metadata for native Income Tax Slab records."""
from __future__ import annotations

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def ensure_income_tax_review_fields():
    create_custom_fields({
        "Income Tax Slab": [
            {
                "fieldname": "custom_tradex_review_status",
                "label": "Tradexcel Review Status",
                "fieldtype": "Select",
                "options": "Review Required\nApproved",
                "default": "Review Required",
                "insert_after": "effective_from",
                "read_only": 1,
                "allow_on_submit": 1,
                "in_list_view": 1,
                "description": "A submitted native slab requires authorized review before Tradexcel payroll can use it.",
            },
            {
                "fieldname": "custom_tradex_source_reference",
                "label": "Tradexcel Source Reference",
                "fieldtype": "Data",
                "insert_after": "custom_tradex_review_status",
                "read_only": 1,
                "allow_on_submit": 1,
            },
            {
                "fieldname": "custom_tradex_reviewed_by",
                "label": "Tradexcel Reviewed By",
                "fieldtype": "Link",
                "options": "User",
                "insert_after": "custom_tradex_source_reference",
                "read_only": 1,
                "allow_on_submit": 1,
            },
            {
                "fieldname": "custom_tradex_reviewed_at",
                "label": "Tradexcel Reviewed At",
                "fieldtype": "Datetime",
                "insert_after": "custom_tradex_reviewed_by",
                "read_only": 1,
                "allow_on_submit": 1,
            },
            {
                "fieldname": "custom_tradex_review_notes",
                "label": "Tradexcel Review Notes",
                "fieldtype": "Small Text",
                "insert_after": "custom_tradex_reviewed_at",
                "read_only": 1,
                "allow_on_submit": 1,
            },
        ]
    }, update=True)


def ensure_payroll_adjustment_workflow_fields():
    """Provide Frappe Workflow's state field on native adjustment DocTypes."""
    create_custom_fields({
        "Payroll Correction": [{
            "fieldname": "workflow_state",
            "label": "Workflow State",
            "fieldtype": "Link",
            "options": "Workflow State",
            "read_only": 1,
            "no_copy": 1,
            "insert_after": "company",
        }],
        "Arrear": [{
            "fieldname": "workflow_state",
            "label": "Workflow State",
            "fieldtype": "Link",
            "options": "Workflow State",
            "read_only": 1,
            "no_copy": 1,
            "insert_after": "company",
        }],
    }, update=True)
