frappe.ui.form.on("Workforce Statutory Record", {
    refresh(frm) {
        if (frm.doc.docstatus || !frm.doc.layout) return;
        const load = (history) => frappe.call({
            method: "workforce_suite.workforce_suite.statutory_setup.evidence_field_options",
            args: {layout_name: frm.doc.layout},
            callback: (r) => {
                const options = r.message;
                if (!options) return;
                const insert = (table) => {
                    const tableKeys = new Set(options.tables.flatMap((t) => t.keys));
                    const keys = table ? new Set(table.keys) : new Set(options.fields.filter((f) => !tableKeys.has(f.key)).map((f) => f.key));
                    const current = frm.doc.entries || [];
                    const row = table ? Math.max(0, ...current.filter((c) => keys.has(c.field_key)).map((c) => c.row_number || 0)) + 1 : 0;
                    for (const field of options.fields.filter((f) => keys.has(f.key))) {
                        if (!table && current.some((c) => c.field_key === field.key && !c.row_number)) continue;
                        frm.add_child("entries", {field_key: field.key, field_label: field.label,
                            row_number: row, value_status: "Unresolved"});
                    }
                    frm.refresh_field("entries");
                };
                if (!history) return insert(null);
                if (!options.tables.length) return frappe.msgprint(__("This form has no prescribed history tables."));
                frappe.prompt([{fieldname: "table", fieldtype: "Select", label: __("Prescribed Table"),
                    options: options.tables.map((t) => ({label: t.title_en, value: t.id})), reqd: 1}],
                    (v) => insert(options.tables.find((t) => t.id === v.table)), __("Add History Row"));
            }
        });
        if (frm.doc.reporting_from && frm.doc.reporting_to) {
            frm.add_custom_button(__("Fill Reviewed Calendar Range"), () => {
                frappe.prompt([
                    {fieldname: "from", fieldtype: "Date", label: __("From"), default: frm.doc.reporting_from, reqd: 1},
                    {fieldname: "to", fieldtype: "Date", label: __("To"), default: frm.doc.reporting_to, reqd: 1},
                    {fieldname: "working", fieldtype: "Check", label: __("These Are Working Days")},
                    {fieldname: "reference", fieldtype: "Small Text", label: __("Reviewed Schedule / Holiday Source"), reqd: 1}
                ], (v) => {
                    if (v.from < frm.doc.reporting_from || v.to > frm.doc.reporting_to || v.to < v.from) return frappe.msgprint(__("Choose dates within the reporting period."));
                    for (let day = v.from; day <= v.to; day = frappe.datetime.add_days(day, 1)) {
                        const row = (frm.doc.workforce_calendar || []).find((r) => r.work_date === day) || frm.add_child("workforce_calendar", {work_date: day});
                        row.is_working_day = v.working ? 1 : 0;
                        row.source_reference = v.reference;
                    }
                    frm.dirty(); frm.refresh_field("workforce_calendar");
                }, __("Reviewed Calendar Range"));
            }, __("Evidence"));
        }
        if (!frm.doc.evidence_kind || frm.doc.evidence_kind === "Supplemental Facts") {
            frm.add_custom_button(__("Load Missing Fields"), () => load(false), __("Evidence"));
            frm.add_custom_button(__("Add History Row"), () => load(true), __("Evidence"));
        }
        frm.add_custom_button(__("Preview Return"), () => {
            if (frm.is_dirty()) return frappe.msgprint(__("Save your evidence draft first."));
            window.workforceStatutoryPrintLayout(frm.doc.layout, {
                employee: frm.doc.employee || "", branch: frm.doc.branch || "",
                from_date: frm.doc.reporting_from || "", to_date: frm.doc.reporting_to || ""
            });
        }, __("Evidence"));
    },
    layout(frm) { frm.trigger("refresh"); },
    evidence_kind(frm) { frm.clear_custom_buttons(); frm.trigger("refresh"); }
});
