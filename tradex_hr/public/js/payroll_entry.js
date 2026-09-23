frappe.ui.form.on("Payroll Entry", {
	refresh(frm) {
		if (!frm.doc.custom_tradex_run_key || frm.doc.docstatus !== 1) return;

		frm.remove_custom_button(__("Submit Salary Slip"));
		frm.remove_custom_button(__("Make Bank Entry"));
		frm.remove_custom_button(__("Release Withheld Salaries"));

		frappe.call({
			method: "tradex_hr.tradexcel_hr.payroll_finalization.get_payroll_accrual_reconciliation",
			args: { payroll_entry: frm.doc.name },
		}).then(({ message }) => {
			if (!message) return;

			const statusMessages = {
				PARTIAL_SUBMISSION: __("Some Salary Slips remain unsubmitted. Review the remaining slips before retrying."),
				SUBMISSION_FAILED: __("Payroll finalization stopped. Review the Payroll Entry error before retrying."),
				ACCRUAL_MISSING: __("A submitted Salary Slip is missing its native accrual Journal Entry."),
				ACCRUAL_UNBALANCED: __("A native accrual Journal Entry is not balanced."),
				SLIP_UNIVERSE_MISMATCH: __("Salary Slips do not match the employees in this Payroll Entry."),
				NOT_FINALIZED: __("Salary Slip finalization has not started."),
			};
			if (statusMessages[message.status]) {
				frm.dashboard.set_headline(statusMessages[message.status]);
			}

			if (message.safe_to_retry && message.draft_slip_count) {
				const retry = message.submitted_slip_count > 0 || frm.doc.status === "Failed";
				frm.add_custom_button(
					retry ? __("Retry Unsubmitted Salary Slips") : __("Finalize Payroll"),
					() => frm.call({
						doc: frm.doc,
						method: "submit_salary_slips",
						freeze: true,
						freeze_message: retry
							? __("Retrying remaining Salary Slips")
							: __("Finalizing Payroll"),
					}).then(() => frm.reload_doc()),
				).addClass("btn-primary");
				return;
			}

			if (message.status === "SUBMISSION_IN_PROGRESS") {
				frm.dashboard.set_headline(__("Payroll finalization is running. Payment has not started."));
			} else if (message.status === "READY") {
				frm.dashboard.set_headline(__("Payroll finalized and accrual accounting reconciled. Payment has not started."));
			} else if (message.status !== "NOT_FINALIZED") {
				frm.dashboard.set_headline(statusMessages[message.status] || __("Payroll needs attention. Open the Payroll Entry and review linked Salary Slips and Journal Entries."));
			}
		});
	},
});
