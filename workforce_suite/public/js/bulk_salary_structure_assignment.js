frappe.ui.form.on("Bulk Salary Structure Assignment", {
	refresh(frm) {
		if (
			frappe.user.has_role("HR User") ||
			frappe.user.has_role("HR Manager") ||
			(!frappe.user.has_role("Workforce Suite Manager") && !frappe.user.has_role("Workforce Payroll Manager"))
		) {
			return;
		}
		frm.set_df_property("payroll_payable_account", "read_only", 1);
		frm.trigger("show_workforce_pay_basis_help");
	},

	salary_structure(frm) {
		frm.trigger("show_workforce_pay_basis_help");
	},

	show_workforce_pay_basis_help(frm) {
		if (
			frappe.user.has_role("HR User") ||
			frappe.user.has_role("HR Manager") ||
			(!frappe.user.has_role("Workforce Suite Manager") && !frappe.user.has_role("Workforce Payroll Manager"))
		) {
			return;
		}
		if (!frm.doc.salary_structure) {
			frm.set_intro(__("Choose a submitted Salary Structure with an explicit pay basis."), "blue");
			return;
		}
		frappe.db.get_value("Salary Structure", frm.doc.salary_structure, "custom_workforce_pay_basis").then((r) => {
			const basis = r.message && r.message.custom_workforce_pay_basis;
			if (basis === "Monthly Salary") {
				frm.set_intro(
					__("Monthly Salary: Base is the monthly base amount. The Employee Grade value is only a starting suggestion. This action saves draft assignments; a different Payroll Approver must submit them."),
					"blue",
				);
			} else if (basis === "Daily Wage") {
				frm.set_intro(
					__("Daily Wage: Base is the daily rate. The Employee Grade value is only a starting suggestion. This action saves draft assignments; a different Payroll Approver must submit them."),
					"blue",
				);
			} else {
				frm.set_intro(__("This Salary Structure has no valid explicit Workforce pay basis."), "orange");
			}
		});
	},
});
