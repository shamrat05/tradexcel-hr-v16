frappe.ui.form.on("Shift Assignment Tool", {
	onload(frm) {
		if (!workforce_shift_operator_only()) return;

		frm.set_df_property("action", "options", "Assign Shift");
		if (frm.doc.action !== "Assign Shift") {
			frm.set_value("action", "Assign Shift");
		}
	},
	refresh(frm) {
		if (!workforce_shift_operator_only()) return;

		frm.set_intro(__("Assignments are created only after you review this list, select Employees and confirm Assign Shift. Nothing is assigned before that native confirmation; existing assignments and overlaps stay with native validation."), "blue");
	},
});

function workforce_shift_operator_only() {
	const workforce_shift_operator =
		frappe.user.has_role("Workforce Suite Manager") ||
		frappe.user.has_role("Workforce Suite/Attendance Officer");

	return Boolean(workforce_shift_operator) && !frappe.user.has_role("HR User") && !frappe.user.has_role("HR Manager");
}
