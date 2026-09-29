frappe.ui.form.on("Tradexcel Attendance Period", {
	refresh(frm) {
		if (frm.is_new() || !frm.has_perm("write")) {
			return;
		}

		if (frm.doc.status !== "Finalized") {
			frm.add_custom_button(__("Finalize Attendance"), () => {
				frappe.call({
					method: "tradex_hr.tradexcel_hr.doctype.tradexcel_attendance_period.tradexcel_attendance_period.finalize_attendance_period",
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
				frappe.call({
					method: "tradex_hr.tradexcel_hr.doctype.tradexcel_attendance_period.tradexcel_attendance_period.reopen_attendance_period",
					args: { name: frm.doc.name },
					freeze: true,
					freeze_message: __("Reopening attendance..."),
					callback(r) {
						if (!r.exc) {
							frm.reload_doc();
						}
					},
				});
			});
		}
	},
});
