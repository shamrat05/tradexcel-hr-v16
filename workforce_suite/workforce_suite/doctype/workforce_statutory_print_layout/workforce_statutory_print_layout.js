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
            required_value: col.required ? 1 : 0,
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

function open_print_options(frm) {
    const today = frappe.datetime.get_today();
    frappe.prompt([
        {fieldname: "from_date", label: __("From Date"), fieldtype: "Date",
            reqd: 1, default: today},
        {fieldname: "to_date", label: __("To Date"), fieldtype: "Date",
            reqd: 1, default: today},
    ], async (values) => {
        const args = {
            layout_name: frm.doc.name,
            from_date: values.from_date,
            to_date: values.to_date,
        };
        const response = await frappe.call({
            method: "workforce_suite.workforce_suite.statutory_forms.preview_a4",
            args, freeze: true, freeze_message: __("Preparing A4 preview")
        });
        const preview = new frappe.ui.Dialog({
            title: __("A4 Preview - ") + frm.doc.title,
            size: "extra-large",
            fields: [
                {fieldname: "document_frame", fieldtype: "HTML"}
            ],
            primary_action_label: __("Download A4 PDF"),
            primary_action() {
                const base = "/api/method/workforce_suite.workforce_suite.statutory_forms.download_a4";
                const query = new URLSearchParams(args).toString();
                window.open(base + "?" + query, "_blank", "noopener,noreferrer");
            },
        });
        const frame = document.createElement("iframe");
        frame.setAttribute("title", __("Statutory A4 document preview"));
        frame.setAttribute("sandbox", "allow-same-origin");
        frame.style.cssText = "width:100%;min-height:65vh;border:1px solid var(--border-color,#ccc)";
        frame.srcdoc = response.message.html;
        preview.fields_dict.document_frame.$wrapper.append(frame);
        preview.show();
    }, __("Select Print Period"), __("Preview"));
}
