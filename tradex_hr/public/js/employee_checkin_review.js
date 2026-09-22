frappe.ui.form.on("Employee Checkin", {
	refresh(frm) {
		const reviewable =
			frm.doc.custom_tradex_source === "Mobile" &&
			frm.doc.custom_tradex_time_status === "Flagged" &&
			frm.doc.custom_tradex_review_status === "Pending";
		const allowed = (frappe.user_roles || []).some((role) =>
			[
				"System Manager",
				"Tradexcel Owner/Director",
				"Tradexcel HR Manager",
				"Tradexcel HR/Attendance Officer",
				"Tradexcel Factory Supervisor",
				"Tradexcel Branch Manager",
				"Tradexcel Department Manager",
				"Tradexcel Attendance Correction Approver",
			].includes(role)
		);
		if (!reviewable || !allowed) return;

		frm.add_custom_button(
			__("Approve Attendance"),
			() =>
				frappe.call({
					method: "tradex_hr.tradexcel_hr.field_attendance_service.approve_mobile_checkin",
					args: { checkin: frm.doc.name },
				}).then(() => frm.reload_doc()),
			__("Evidence Review")
		);
		frm.add_custom_button(
			__("Reject Attendance"),
			() =>
				frappe.prompt(
					[
						{
							fieldname: "review_note",
							label: __("Reason"),
							fieldtype: "Small Text",
							reqd: 1,
						},
					],
					(values) =>
						frappe.call({
							method: "tradex_hr.tradexcel_hr.field_attendance_service.reject_mobile_checkin",
							args: { checkin: frm.doc.name, review_note: values.review_note },
						}).then(() => frm.reload_doc()),
					__("Reject Mobile Attendance"),
					__("Reject")
				),
			__("Evidence Review")
		);
	},
});
