frappe.ui.form.on("Shift Assignment Tool", {
	onload(frm) {
		const tradexcel_shift_operator =
			frappe.user.has_role("Tradexcel HR Manager") ||
			frappe.user.has_role("Tradexcel HR/Attendance Officer");

		if (!tradexcel_shift_operator) return;

		frm.set_df_property("action", "options", "Assign Shift");
		if (frm.doc.action !== "Assign Shift") {
			frm.set_value("action", "Assign Shift");
		}
	},
});
