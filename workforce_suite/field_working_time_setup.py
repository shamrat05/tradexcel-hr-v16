"""Install the narrow holiday classification field used by working-time review."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def ensure_working_time_holiday_category_field():
	if not frappe.db.exists("DocType", "Holiday"):
		return
	create_custom_fields(
		{
			"Holiday": [
				{
					"fieldname": "custom_workforce_holiday_category",
					"label": "Workforce Holiday Category",
					"fieldtype": "Select",
					"options": "Weekly Rest\nFestival Holiday\nPublic / Government Holiday\nCompany Closure\nOther",
					"insert_after": "weekly_off",
					"description": "Reviewed calendar category used for statutory holiday reporting; it does not calculate pay.",
				},
			]
		},
		update=True,
	)
