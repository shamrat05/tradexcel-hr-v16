frappe.ui.form.on("Shift Assignment Tool", {
	onload(frm) {
		if (!tradexcel_shift_operator_only()) return;

		frm.set_df_property("action", "options", "Assign Shift");
		if (frm.doc.action !== "Assign Shift") {
			frm.set_value("action", "Assign Shift");
		}
	},
	refresh(frm) {
		if (!tradexcel_shift_operator_only()) return;

		frm.set_intro(__("Assignments are created only after you review this list, select Employees and confirm Assign Shift. Nothing is assigned before that native confirmation; existing assignments and overlaps stay with native validation."), "blue");
	},
});

function tradexcel_shift_operator_only() {
	const tradexcel_shift_operator =
		frappe.user.has_role("Tradexcel HR Manager") ||
		frappe.user.has_role("Tradexcel HR/Attendance Officer");

	return Boolean(tradexcel_shift_operator) && !frappe.user.has_role("HR User") && !frappe.user.has_role("HR Manager");
}
