frappe.ui.form.on("Employee Separation", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.docstatus !== 1) return;
		frm.add_custom_button(__("Record Legal Review"), () => {
			const dialog = new frappe.ui.Dialog({
				title: __("Legal / Statutory Review"),
				fields: [
					{ fieldname: "status", label: __("Decision"), fieldtype: "Select", options: "Approved\nNot Applicable", reqd: 1 },
					{ fieldname: "notes", label: __("Review Notes"), fieldtype: "Small Text", reqd: 1 },
				],
				primary_action_label: __("Record Review"),
				primary_action(values) {
					frappe.call({
						method: "tradex_hr.tradexcel_hr.employee_separation.review_separation_statutory_status",
						args: { separation_name: frm.doc.name, ...values },
					}).then(() => { dialog.hide(); frm.reload_doc(); });
				},
			});
			dialog.show();
		}, __("Separation"));
	},
});