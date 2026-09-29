frappe.ui.form.on("Employee Checkin", {
  refresh(frm) {
    const roles = ["System Manager", "Tradexcel Owner/Director", "Tradexcel HR Manager",
      "Tradexcel HR/Attendance Officer", "Tradexcel Factory Supervisor", "Tradexcel Branch Manager",
      "Tradexcel Department Manager", "Tradexcel Attendance Correction Approver"];
    if (frm.is_new() || frm.doc.custom_tradex_source !== "Mobile" ||
        frm.doc.custom_tradex_time_status !== "Flagged" || frm.doc.custom_tradex_review_status !== "Pending" ||
        !(frappe.session.user === "Administrator" || roles.some(role => frappe.user.has_role(role)))) return;
    for (const [label, method] of [[__("Approve Evidence"), "approve_mobile_checkin"], [__("Reject Evidence"), "reject_mobile_checkin"]]) {
      frm.add_custom_button(label, () => frappe.prompt(
        [{fieldname: "review_note", fieldtype: "Small Text", label: __("Review Reason"), reqd: 1}],
        values => frappe.call({method: `tradex_hr.tradexcel_hr.field_attendance_service.${method}`,
          type: "POST", args: {checkin: frm.doc.name, review_note: values.review_note},
          freeze: true, callback: () => frm.reload_doc()}), label, __("Confirm")), __("Evidence Review"));
    }
  }
});
