"""Idempotent Tradexcel organizational hierarchy and branch-type setup."""

from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


COMPANY = "Tradexcel Ceramics Ltd."
EFL = "Elegance Footwear Ltd."
HEADQUARTERS = "Tradexcel Headquarters"
LEGACY_HEADQUARTERS = "Tradexcel HO"
FACTORY = "TCL Factory"
EFL_HEADQUARTERS = "Elegance Footwear Ltd. (H O)"
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
                "default": COMPANY,
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


def _rename_legacy_headquarters() -> bool:
    if not frappe.db.exists("Branch", LEGACY_HEADQUARTERS):
        return False
    if not frappe.db.exists("Branch", HEADQUARTERS):
        frappe.rename_doc("Branch", LEGACY_HEADQUARTERS, HEADQUARTERS, force=True)
        return True

    # If both records exist from an earlier attempt, repoint known links before
    # removing the duplicate. The canonical name remains the only valid value.
    for doctype in ("Employee", "Tradexcel Biometric Device"):
        if frappe.db.exists("DocType", doctype):
            frappe.db.sql(
                "UPDATE `tab{0}` SET branch=%s WHERE branch=%s".format(doctype),
                (HEADQUARTERS, LEGACY_HEADQUARTERS),
            )
    frappe.delete_doc("Branch", LEGACY_HEADQUARTERS, force=True, ignore_permissions=True)
    return True


def ensure_branch_hierarchy() -> dict[str, object]:
    """Apply one clear TCL hierarchy without changing employee records."""
    create_custom_fields(_branch_fields(), update=True)
    renamed = _rename_legacy_headquarters()

    if frappe.db.exists("Branch", HEADQUARTERS):
        headquarters = frappe.get_doc("Branch", HEADQUARTERS)
        headquarters.parent_branch = None
        headquarters.branch_type = "Headquarters"
        headquarters.company = COMPANY
        headquarters.address_line1 = "Eastern Trade Center, 56, Purana Paltan Line"
        headquarters.city = "Dhaka"
        headquarters.save(ignore_permissions=True)

    if frappe.db.exists("Branch", FACTORY):
        factory = frappe.get_doc("Branch", FACTORY)
        factory.parent_branch = HEADQUARTERS
        factory.branch_type = "Factory / Plant"
        factory.company = COMPANY
        factory.address_line1 = "Angutiachala, Bhawal Mirzapur"
        factory.city = "Gazipur"
        factory.save(ignore_permissions=True)

    if frappe.db.exists("Branch", EFL_HEADQUARTERS):
        efl_headquarters = frappe.get_doc("Branch", EFL_HEADQUARTERS)
        efl_headquarters.parent_branch = None
        efl_headquarters.branch_type = "Headquarters"
        efl_headquarters.company = EFL
        efl_headquarters.city = "Dhaka"
        efl_headquarters.save(ignore_permissions=True)

    return {
        "headquarters": HEADQUARTERS,
        "factory": FACTORY,
        "legacy_renamed": renamed,
    }
