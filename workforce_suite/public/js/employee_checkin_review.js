frappe.ui.form.on("Employee Checkin", {
  refresh(frm) {
    if (frm.is_new()) return;
    const reviewerRoles = ["System Manager", "Workforce Owner/Director", "Workforce Suite Manager",
      "Workforce Suite/Attendance Officer", "Workforce Factory Supervisor", "Workforce Branch Manager",
      "Workforce Department Manager", "Workforce Attendance Correction Approver"];
    const isReviewer = frappe.session.user === "Administrator" || reviewerRoles.some(role => frappe.user.has_role(role));
    const source = frm.doc.custom_workforce_source;
    const time_status = frm.doc.custom_workforce_time_status;
    const review_status = frm.doc.custom_workforce_review_status;
    const quarantined = source === "Mobile" && time_status === "Flagged" && review_status === "Pending";

    if (quarantined) {
      if (isReviewer) {
        frm.set_intro(__("Quarantined mobile evidence awaiting review. Check the reason below, then Approve or Reject with a review reason. Approval releases it to native auto-attendance; rejection excludes it. Neither action alone creates approved Attendance."), "orange");
      } else {
        frm.set_intro(__("Quarantined mobile evidence awaiting an authorized reviewer. It is not Attendance."), "orange");
      }
    } else if (source === "Mobile" && review_status === "Approved") {
      frm.set_intro(__("Approved evidence. It was released to native auto-attendance; native rules decide whether it becomes Attendance."), "green");
    } else if (source === "Mobile" && review_status === "Rejected") {
      frm.set_intro(__("Rejected evidence. It is excluded from attendance and cannot be approved later. The review reason is recorded below."), "red");
    } else if (source === "Mobile" && time_status === "Trusted") {
      frm.set_intro(__("Trusted mobile evidence. Native auto-attendance decides whether it becomes Attendance."), "blue");
    }

    if (!quarantined || !isReviewer) return;
    for (const [label, method] of [[__("Approve Evidence"), "approve_mobile_checkin"], [__("Reject Evidence"), "reject_mobile_checkin"]]) {
      frm.add_custom_button(label, () => frappe.prompt(
        [{fieldname: "review_note", fieldtype: "Small Text", label: __("Review Reason"), reqd: 1}],
        values => frappe.call({method: `workforce_suite.workforce_suite.field_attendance_service.${method}`,
          type: "POST", args: {checkin: frm.doc.name, review_note: values.review_note},
          freeze: true, callback: () => frm.reload_doc()}), label, __("Confirm")), __("Evidence Review"));
    }
  }
});
