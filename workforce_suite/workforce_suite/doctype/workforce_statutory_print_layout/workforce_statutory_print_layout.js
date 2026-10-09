/* Native Frappe form controls; no Desk monkey patches or global CSS overrides.
 * Layout and column changes use standard DocType fields and child tables.
 */
frappe.ui.form.on("Workforce Statutory Print Layout", {
    refresh(frm) {
        if (frm.doc.docstatus !== 0) {
            frm.add_custom_button(__("A4 Preview / PDF"), () => open_print_options(frm),
                __("Print & Review"));
            return;
        }
        frm.add_custom_button(__("Load Suggested Columns"), () => load_suggested_columns(frm),
            __("Layout Tools"));
        if (!frm.is_new()) {
            frm.add_custom_button(__("A4 Preview / PDF"), () => open_print_options(frm),
                __("Print & Review"));
        }
    },
    form_code(frm) {
        if (frm.doc.form_code && !(frm.doc.columns || []).length) {
            // New records have no source-specific columns; offer an explicit
            // single-click action instead of silently overwriting user edits.
            frm.dashboard.set_headline_alert(
                __("Select Layout Tools → Load Suggested Columns to begin."),
                "blue"
            );
        }
    }
});

async function load_suggested_columns(frm) {
    if (!frm.doc.form_code) {
        frappe.msgprint(__("Choose a DIFE Source Entry first."));
        return;
    }
    if ((frm.doc.columns || []).length) {
        const accept = await new Promise((resolve) =>
            frappe.confirm(
                __("Replace your current column labels and mappings with draft suggestions?"),
                () => resolve(true), () => resolve(false)
            )
        );
        if (!accept) return;
    }
    const result = await frappe.call({
        method: "workforce_suite.workforce_suite.statutory_forms.get_form_spec",
        args: { form_code: frm.doc.form_code }
    });
    const source = result.message;
    if (source.source_issue) {
        frappe.msgprint({
            title: __("Official source warning"),
            message: frappe.utils.escape_html(source.source_issue),
            indicator: "orange"
        });
    }
    frm.clear_table("columns");
    for (const col of source.columns) {
        frm.add_child("columns", {
            field_key: col.field_key,
            label_bn: col.label_bn || "",
            label_en: col.label_en || "",
            width_weight: col.width_weight || 1,
            required_value: col.required_value === false ? 0 : 1,
            section_key: col.section_key || "", section_en: col.section_en || "", section_bn: col.section_bn || "",
        });
    }
    await frm.set_value({
        form_family: source.form_family,
        data_source: source.data_source,
        orientation: source.orientation,
        title_en: source.title,
    });
    frm.refresh_field("columns");
    frm.dirty();
    frappe.show_alert({
        message: __("Draft columns loaded. Review against every page of the source before approving."),
        indicator: "blue"
    });
}

// When called from a report, pass its existing filter values as 'context'.
// The layout editor has no report context, so it asks only for fields that
// matter for this form. This is deliberately NOT a generic 10-filter modal.
async function open_print_options(frm, context = {}) {
    if (frm.is_dirty()) {
        frappe.msgprint(__("Save the layout before generating a preview."));
        return;
    }
    return window.workforceStatutoryPrintLayout(frm.doc.name, context);
}

frappe.ui.form.on("Workforce Statutory Print Layout", {
    refresh(frm) {
        if (!frm.is_new() && ["form_80", "form_81"].includes(frm.doc.form_code) && frm.doc.docstatus !== 2) {
            frm.add_custom_button(__("Prepare Return Evidence"), () => {
                frappe.prompt([
                    {fieldname: "from_date", fieldtype: "Date", label: __("Period From"), reqd: 1},
                    {fieldname: "to_date", fieldtype: "Date", label: __("Period To"), reqd: 1}
                ], (values) => frappe.call({
                    method: "workforce_suite.workforce_suite.statutory_setup.prepare_periodic_evidence",
                    type: "POST", args: {layout_name: frm.doc.name, ...values}, freeze: true,
                    callback: (r) => { if (r.message?.records?.length) frappe.set_route("Form", "Workforce Statutory Record", r.message.records[0]); }
                }), __("Reporting Period"));
            }, __("Layout Tools"));
        }
    }
});
