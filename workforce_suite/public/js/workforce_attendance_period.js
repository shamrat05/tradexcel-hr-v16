frappe.ui.form.on("Workforce Attendance Period", {
	refresh(frm) {
		if (frm.is_new()) return;

		const revision = frm.doc.revision || 0;
		const finalized_by = frm.doc.finalized_by || __("not recorded");
		const finalized_at = frm.doc.finalized_at ? frappe.datetime.str_to_user(frm.doc.finalized_at) : __("not recorded");
		if (frm.doc.status === "Finalized") {
			frm.set_intro(__("Finalized revision {0} by {1} on {2}. Attendance is a recorded version; finalized history is never silently rewritten. Reopen only for an authorized correction — reopening disables unconsumed daily-wage inputs, and payroll already consumed by a Salary Slip requires the post-payroll adjustment review instead.", [revision, finalized_by, finalized_at]), "green");
		} else if (frm.doc.status === "Reopened") {
			frm.set_intro(__("Reopened after finalization. Attendance may change while the period is open; finalize again to record a new revision. The previous revision stays in history."), "orange");
		} else {
			frm.set_intro(__("Open period: attendance may still change. Finalize when the period is complete — finalization checks native attendance integrity, working-time review and operational-day decisions, then records a version."), "blue");
		}

		if (!frm.has_perm("write")) {
			return;
		}

		if (frm.doc.status !== "Finalized") {
			frm.add_custom_button(__("Finalize Attendance"), () => {
				frappe.call({
					method: "workforce_suite.workforce_suite.doctype.workforce_attendance_period.workforce_attendance_period.finalize_attendance_period",
					args: { name: frm.doc.name },
					freeze: true,
					freeze_message: __("Finalizing attendance..."),
					callback(r) {
						if (!r.exc) {
							frm.reload_doc();
						}
					},
				});
			});
		} else {
			frm.add_custom_button(__("Reopen Attendance"), () => {
				frappe.confirm(
					__("Reopen this finalized period? Unconsumed daily-wage inputs will be disabled. If submitted payroll already consumed them, reopening is blocked and the post-payroll adjustment review must be used."),
					() => {
						frappe.call({
							method: "workforce_suite.workforce_suite.doctype.workforce_attendance_period.workforce_attendance_period.reopen_attendance_period",
							args: { name: frm.doc.name },
							freeze: true,
							freeze_message: __("Reopening attendance..."),
							callback(r) {
								if (!r.exc) {
									frm.reload_doc();
								}
							},
						});
					}
				);
			});
		}
	},
});
