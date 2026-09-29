frappe.ui.form.on("Income Tax Slab", {
  refresh(frm) {
    if (frm.doc.docstatus !== 1 || frm.doc.custom_tradex_review_status === "Approved") return;
    if (!frappe.user.has_role("System Manager") && !frappe.user.has_role("Tradexcel Owner/Director")) return;
    frm.add_custom_button(__("Approve Tax Configuration"), () => {
      frappe.prompt([
        {fieldname: "source_reference", label: __("Authoritative Source Reference"), fieldtype: "Data", reqd: 1},
        {fieldname: "notes", label: __("Review Notes"), fieldtype: "Small Text"}
      ], values => frappe.call({
        method: "tradex_hr.tradexcel_hr.tax_review.approve_income_tax_slab",
        args: {name: frm.doc.name, source_reference: values.source_reference, notes: values.notes}
      }).then(() => frm.reload_doc()), __("Approve Native Tax Configuration"), __("Approve"));
    });
  }
});
