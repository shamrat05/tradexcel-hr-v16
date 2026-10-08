"""Ensure the linked native Leave Application child table resolves to this app."""

import frappe


def execute():
	name = "Workforce Maternity Leave Application"
	if frappe.db.exists("DocType", name):
		# Older staging metadata registered this source-owned child table under
		# Frappe Core. Correct its module before Frappe's orphan-controller check.
		if frappe.db.get_value("DocType", name, "module") != "Workforce Suite":
			frappe.db.set_value("DocType", name, "module", "Workforce Suite", update_modified=False)
			frappe.clear_cache(doctype=name)
		return

	path = frappe.get_app_path(
		"workforce_suite",
		"workforce_suite",
		"doctype",
		"workforce_maternity_leave_application",
		"workforce_maternity_leave_application.json",
	)
	from frappe.modules.import_file import import_file_by_path

	import_file_by_path(path, force=True, ignore_version=True)
	frappe.clear_cache(doctype=name)
