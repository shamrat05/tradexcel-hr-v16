frappe.ui.form.on("Income Tax Slab", {
  refresh(frm) {
    const approved = frm.doc.custom_workforce_review_status === "Approved";
    if (frm.doc.docstatus === 0) {
      frm.set_intro(__("Draft tax configuration: it is not in force. Submit it, then have an authorized reviewer approve it against an authoritative source before payroll treats it as approved."), "blue");
    } else if (!approved) {
      frm.set_intro(__("Submitted tax configuration that has not been reviewed. Unreviewed slabs are not treated as approved payroll tax; approval needs an authoritative source reference and stays limited to authorized reviewers."), "orange");
    }
    if (frm.doc.docstatus !== 1 || approved) return;
    if (!frappe.user.has_role("System Manager") && !frappe.user.has_role("Workforce Owner/Director")) return;
    frm.add_custom_button(__("Approve Tax Configuration"), () => {
      frappe.prompt([
        {fieldname: "source_reference", label: __("Authoritative Source Reference"), fieldtype: "Data", reqd: 1},
        {fieldname: "notes", label: __("Review Notes"), fieldtype: "Small Text"}
      ], values => frappe.call({
        method: "workforce_suite.workforce_suite.tax_review.approve_income_tax_slab",
        args: {name: frm.doc.name, source_reference: values.source_reference, notes: values.notes}
      }).then(() => frm.reload_doc()), __("Approve Native Tax Configuration"), __("Approve"));
    });
  }
});
