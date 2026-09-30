frappe.ui.form.on("Employee Separation", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.docstatus !== 1) return;

		// Owner/Director review is required by the server; the separation maker cannot review their own document.
		const can_review = (frappe.user.has_role("Tradexcel Owner/Director") || frappe.session.user === "Administrator")
			&& (frappe.session.user === "Administrator" || frm.doc.owner !== frappe.session.user);

		if (!can_review) return;

		frm.add_custom_button(__("Record Legal Review"), () => {
			const dialog = new frappe.ui.Dialog({
				title: __("Legal / Statutory Review"),
				fields: [
					{
						fieldname: "status",
						label: __("Decision"),
						fieldtype: "Select",
						options: "Approved\nNot Applicable",
						default: "Approved",
						reqd: 1,
						change() {
							const is_approved = dialog.get_value("status") === "Approved";
							dialog.set_df_property("rule_set", "reqd", is_approved ? 1 : 0);
							dialog.set_df_property("classification", "reqd", is_approved ? 1 : 0);
						},
					},
					{
						fieldname: "rule_set",
						label: __("Approved Rule Set"),
						fieldtype: "Link",
						options: "Tradexcel Statutory Rule Set",
						reqd: 1,
						get_query() {
							return {
								filters: {
									company: frm.doc.company,
									docstatus: 1,
								},
							};
						},
					},
					{
						fieldname: "classification",
						label: __("Legal Classification"),
						fieldtype: "Select",
						options: "Worker under selected regime\nOutside worker scope\nOther approved service-rule category",
						reqd: 1,
					},
					{
						fieldname: "notes",
						label: __("Review Notes"),
						fieldtype: "Small Text",
						reqd: 1,
					},
				],
				primary_action_label: __("Record Review"),
				primary_action(values) {
					frappe.call({
						method: "tradex_hr.tradexcel_hr.employee_separation.review_separation_statutory_status",
						args: { separation_name: frm.doc.name, ...values },
					}).then(() => {
						dialog.hide();
						frm.reload_doc();
					});
				},
			});
			dialog.show();
		}, __("Separation"));
	},
});