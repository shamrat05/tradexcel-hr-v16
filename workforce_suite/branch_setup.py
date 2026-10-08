"""Company-neutral Branch metadata installed by the Workforce app.

Existing organizational records belong to the company. Migration only
converges the schema and never renames or edits Branch/Employee records.
"""

from __future__ import annotations

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


BRANCH_TYPE_OPTIONS = "Headquarters\nZonal Office\nSub-branch\nBranch\nFactory / Plant"


def _branch_fields() -> dict[str, list[dict[str, object]]]:
    return {
        "Branch": [
            {
                "fieldname": "parent_branch",
                "label": "Parent Organizational Unit",
                "fieldtype": "Link",
                "options": "Branch",
                "insert_after": "branch",
                "description": "Organizational unit above this branch, such as a headquarters or zonal office",
            },
            {
                "fieldname": "branch_type",
                "label": "Organizational Unit Type",
                "fieldtype": "Select",
                "options": BRANCH_TYPE_OPTIONS,
                "default": "Branch",
                "insert_after": "parent_branch",
            },
            {
                "fieldname": "company",
                "label": "Company",
                "fieldtype": "Link",
                "options": "Company",
                # Never create a company-specific Branch default on generic installs.
                "default": "",
                "insert_after": "branch_type",
            },
            {
                "fieldname": "address_line1",
                "label": "Address",
                "fieldtype": "Data",
                "insert_after": "company",
            },
            {
                "fieldname": "city",
                "label": "City",
                "fieldtype": "Data",
                "insert_after": "address_line1",
            },
        ]
    }


def ensure_branch_fields() -> None:
    """Converge metadata without creating or changing business records."""
    create_custom_fields(_branch_fields(), update=True)
