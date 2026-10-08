frappe.ui.form.on("Payroll Entry", {
	refresh(frm) {
		if (!frm.doc.custom_workforce_run_key || frm.doc.docstatus !== 1) return;

		frm.remove_custom_button(__("Submit Salary Slip"));
		frm.remove_custom_button(__("Make Bank Entry"));
		frm.remove_custom_button(__("Release Withheld Salaries"));

		frappe.call({
			method: "workforce_suite.workforce_suite.payroll_finalization.get_payroll_accrual_reconciliation",
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
				frm.dashboard.set_headline(__("Payroll finalized and accrual accounting reconciled."));
				frappe.call({
					method: "workforce_suite.workforce_suite.payment_readiness.get_payroll_payment_readiness",
					args: { payroll_entry: frm.doc.name },
				}).then(({ message: payment }) => {
					if (!payment) return;
					const paymentMessages = {
						ACCRUAL_NOT_READY: __("Payroll accrual is not reconciled."),
						PAYMENT_ACCOUNT_MISSING: __("Choose a payment account on Payroll Entry."),
						PAYMENT_ACCOUNT_INVALID: __("The payment account needs Finance review."),
						PAYMENT_BANK_ACCOUNT_INVALID: __("The linked company Bank Account needs Finance review."),
						PAYMENT_MODE_REVIEW_REQUIRED: __("Payment mode needs Finance review."),
						MIXED_PAYMENT_MODE_REVIEW_REQUIRED: __("This payroll has mixed payment modes. Ask Finance to review the batch."),
						PAYMENT_BANK_DETAILS_MISSING: __("Approved Salary Slip bank details are incomplete."),
						PAYMENT_ENTRY_DRAFT: __("Payment entry prepared. Finance review is required."),
						AWAITING_BANK_RECONCILIATION: __("Payment accounting is posted. Waiting for bank reconciliation."),
						BANK_RECONCILED: __("Bank payment reconciled."),
						CASH_PAYMENT_ACCOUNTING_POSTED: __("Cash payment accounting posted. Employee receipt is not confirmed."),
					};
					const warnings = (payment.warnings || []).map((finding) => finding.reason).filter(Boolean);
					if (payment.status === "READY_TO_PREPARE_PAYMENT") {
						frm.dashboard.set_headline([__("Payment readiness is clear."), ...warnings].join(" "));
						frm.add_custom_button(__("Prepare Payment"), () => frm.call({
							doc: frm.doc,
							method: "make_bank_entry",
							args: { for_withheld_salaries: false },
							freeze: true,
							freeze_message: __("Preparing native payment entry"),
						}).then(({ message: journalEntry }) => {
							if (journalEntry && journalEntry.name) {
								frappe.set_route("Form", "Journal Entry", journalEntry.name);
							} else {
								frm.reload_doc();
							}
						})).addClass("btn-primary");
					} else {
						frm.dashboard.set_headline([
							paymentMessages[payment.status] || __("Payment needs review. Check the payment findings and native linked records."),
							...warnings,
						].join(" "));
						if (payment.payment_journal_entry) {
							frm.add_custom_button(__("Open Payment Entry"), () =>
								frappe.set_route("Form", "Journal Entry", payment.payment_journal_entry)
							);
						}
						const transaction = payment.bank_transactions && payment.bank_transactions[0];
						if (transaction && transaction.name) {
							frm.add_custom_button(__("Open Bank Transaction"), () =>
								frappe.set_route("Form", "Bank Transaction", transaction.name)
							);
						}
					}
				});
			} else if (message.status !== "NOT_FINALIZED") {
				frm.dashboard.set_headline(statusMessages[message.status] || __("Payroll needs attention. Open the Payroll Entry and review linked Salary Slips and Journal Entries."));
			}
		});
	},
});
