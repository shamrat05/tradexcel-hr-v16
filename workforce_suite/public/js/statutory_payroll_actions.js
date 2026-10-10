/* Native grouped action; server permissions authorize every layout/source. */
frappe.ui.form.on("Payroll Entry", {
    refresh(frm) {
        if (frm.is_new() || !frappe.model.can_read("Workforce Statutory Print Layout")) return;
        frm.add_custom_button(__("Wage register working draft"), () => {
            if (frm.is_dirty()) {
                frappe.msgprint(__("Save the current payroll context before exporting."));
                return;
            }
            return window.workforceStatutoryExport("form_38", {
                company: frm.doc.company, branch: frm.doc.branch,
                department: frm.doc.department, from_date: frm.doc.start_date,
                to_date: frm.doc.end_date,
            });
        }, __("Statutory drafts"));
    },
});
