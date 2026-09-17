// Copyright (c) 2026, Tradexcel and contributors

frappe.query_reports["Biometric ID Audit"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company" },
		{ fieldname: "device", label: __("Device"), fieldtype: "Link", options: "Tradexcel Biometric Device" },
		{
			fieldname: "employee_status",
			label: __("Employee Status"),
			fieldtype: "Select",
			options: "All\nActive\nInactive\nLeft",
			default: "Active",
		},
		{
			fieldname: "assignment_status",
			label: __("Assignment Status"),
			fieldtype: "Select",
			options: "All\nAssigned\nUnassigned\nDuplicate\nLegacy",
			default: "All",
		},
		{
			fieldname: "show_duplicates",
			label: __("Show Duplicates Only"),
			fieldtype: "Select",
			options: "No\nYes",
			default: "No",
			hidden: 1,
		},
	],
	onload(report) {
		report.page.add_inner_button(__("Assign Biometric ID"), () => {
			frappe.prompt(
				[
					{ fieldname: "employee", label: __("Employee"), fieldtype: "Link", options: "Employee", reqd: 1 },
					{ fieldname: "device", label: __("Device"), fieldtype: "Link", options: "Tradexcel Biometric Device", reqd: 1 },
					{
						fieldname: "biometric_id",
						label: __("Biometric ID / PIN"),
						fieldtype: "Data",
						reqd: 1,
						description: __("Use the exact ID configured on this SenseFace terminal."),
					},
				],
				(values) => {
					frappe.call({ method: "tradex_hr.api.assign_employee_biometric", args: values }).then(() => {
						frappe.show_alert({ message: __("Device-specific biometric assignment saved"), indicator: "green" });
						report.refresh();
					});
				},
				__("Assign Biometric ID"),
				__("Save")
			);
		});
		report.page.add_inner_button(__("Copy Biometric to Device"), () => {
			frappe.prompt(
				[
					{ fieldname: "employee", label: __("Employee"), fieldtype: "Link", options: "Employee", reqd: 1 },
					{ fieldname: "source_device", label: __("Copy From Device"), fieldtype: "Link", options: "Tradexcel Biometric Device", reqd: 1 },
					{ fieldname: "target_device", label: __("Copy To Device"), fieldtype: "Link", options: "Tradexcel Biometric Device", reqd: 1 },
					{
						fieldname: "target_biometric_id",
						label: __("Target Biometric ID / PIN"),
						fieldtype: "Data",
						description: __("Leave blank to reuse the source PIN if it is free on the target."),
					},
				],
				(values) => {
					frappe.confirm(
						__("This queues biometric templates to the target device. Continue?"),
						() => {
							frappe.call({
								method: "tradex_hr.api.transfer_employee_biometric",
								args: { ...values, confirm_transfer: 1 },
							}).then(() => {
								frappe.show_alert({ message: __("Biometric transfer queued"), indicator: "green" });
								report.refresh();
							});
						}
					);
				},
				__("Copy Biometric to Device"),
				__("Queue Transfer")
			);
		});
	},
};
