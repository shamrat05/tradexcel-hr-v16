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

// When called from a report, pass its existing filter values as 'context'.
// The layout editor has no report context, so it asks only for fields that
// matter for this form. This is deliberately NOT a generic 10-filter modal.
async function open_print_options(frm, context = {}) {
    if (frm.is_dirty()) {
        frappe.msgprint(__("Save the layout before generating a preview."));
        return;
    }
    const response = await frappe.call({
        method: "workforce_suite.workforce_suite.statutory_forms.export_options",
        args: {layout_name: frm.doc.name}
    });
    const options = response.message;
    if (!options.languages.length) {
        frappe.msgprint(__("Complete the English layout title and column labels first."));
        return;
    }

    const fields = [];
    if (options.languages.includes("bn")) {
        fields.push({
            fieldname: "print_language", label: __("Print language"),
            fieldtype: "Select", options: "English\\nবাংলা",
            default: "English", reqd: 1
        });
    }

    const today = frappe.datetime.get_today();
    const selectedWeek = (() => {
        // Saturday is the first day shown on the Form 34 week grid.
        const dow = new Date(today + "T12:00:00").getDay();
        return frappe.datetime.add_days(today, -((dow + 1) % 7));
    })();
    const hasSelectedPeriod = Boolean(context.from_date && context.to_date);
    const isSelectedWeek = (() => {
        if (!hasSelectedPeriod) return false;
        const start = new Date(context.from_date + "T12:00:00");
        const end = new Date(context.to_date + "T12:00:00");
        return start.getDay() === 6 &&
            Math.round((end.getTime() - start.getTime()) / 86400000) === 6;
    })();

    if (options.period_mode === "week" && !isSelectedWeek) {
        fields.push({
            fieldname: "week_start", label: __("Week beginning (Saturday)"),
            fieldtype: "Date", reqd: 1, default: selectedWeek,
            description: __("Form 34 prints one Saturday–Friday week. The monthly attendance report remains separate.")
        });
    } else if (options.period_mode === "range" && !hasSelectedPeriod) {
        fields.push(
            {fieldname: "from_date", label: __("From Date"), fieldtype: "Date",
                default: frappe.datetime.month_start(), reqd: 1},
            {fieldname: "to_date", label: __("To Date"), fieldtype: "Date",
                default: today, reqd: 1}
        );
    }
    // Employee service books/cards don't have a reporting period.
    const selectedEmployee = context.employee || "";
    if (options.employee_required && !selectedEmployee) {
        fields.push({
            fieldname: "employee", label: __("Employee"),
            fieldtype: "Link", options: "Employee",
            get_query: () => ({filters: {company: options.company}})
        });
        fields.push({
            fieldname: "include_all", label: __("All matching Employees (max 50)"),
            fieldtype: "Check", default: 0,
            description: __("Explicit bulk choice; never print all personal documents by accident.")
        });
    }
    if (options.allow_worker_filters) {
        const optional = [];
        if (!selectedEmployee && !options.employee_required && !context.employee) {
            optional.push({
                fieldname: "filter_employee", label: __("Employee (optional)"),
                fieldtype: "Link", options: "Employee",
                get_query: () => ({filters: {company: options.company}})
            });
        }
        if (!options.branch && !context.branch) {
            optional.push({
                fieldname: "branch", label: __("Branch (optional)"),
                fieldtype: "Link", options: "Branch",
                get_query: () => ({filters: {company: options.company}})
            });
        }
        if (!context.department) {
            optional.push({
                fieldname: "department", label: __("Department (optional)"),
                fieldtype: "Link", options: "Department",
                get_query: () => ({filters: {company: options.company}})
            });
        }
        if (options.data_source === "Employee" && !context.employment_type) {
            optional.push({
                fieldname: "employment_type", label: __("Employment type (optional)"),
                fieldtype: "Link", options: "Employment Type"
            });
        }
        if (optional.length) {
            fields.push({
                fieldname: "scope_break", label: __("Narrow results"),
                fieldtype: "Section Break", collapsible: 1, collapsible_depends_on: "eval:1"
            }, ...optional);
        }
    }
    if (!fields.length) {
        // A contextual report already has everything needed; no duplicate
        // filter dialogue, but still show the PDF preview before download.
        await show_statutory_preview(frm, options, context);
        return;
    }
    frappe.prompt(fields, async (values) => {
        const args = {...context};
        if (options.period_mode === "week" && !isSelectedWeek) {
            const start = new Date(values.week_start + "T12:00:00");
            if (start.getDay() !== 6) {
                frappe.msgprint(__("Choose a Saturday for the Form 34 register."));
                return;
            }
            args.from_date = values.week_start;
            args.to_date = frappe.datetime.add_days(values.week_start, 6);
        } else if (options.period_mode === "range" && !hasSelectedPeriod) {
            args.from_date = values.from_date;
            args.to_date = values.to_date;
        }
        if (options.period_mode === "none") {
            delete args.from_date;
            delete args.to_date;
        }
        args.language = values.print_language === "বাংলা" ? "bn" : "en";
        for (const key of ["employee", "branch", "department", "employment_type"]) {
            if (values[key]) args[key] = values[key];
        }
        if (values.filter_employee) args.employee = values.filter_employee;
        if (values.include_all) args.include_all = 1;
        if (options.employee_required && !args.employee && !args.include_all) {
            frappe.msgprint(__("Select one Employee, or explicitly choose all matching Employees."));
            return;
        }
        await show_statutory_preview(frm, options, args);
    }, __("Print settings"), __("Preview A4"));
}

async function show_statutory_preview(frm, options, args) {
    const safeArgs = {...args, layout_name: frm.doc.name};
    if (!safeArgs.language) safeArgs.language = "en";
    const response = await frappe.call({
        method: "workforce_suite.workforce_suite.statutory_forms.preview_a4",
        args: safeArgs, freeze: true, freeze_message: __("Preparing A4 preview")
    });
    const preview = new frappe.ui.Dialog({
        title: __("A4 Preview - ") + frm.doc.title,
        size: "extra-large",
        fields: [{fieldname: "document_frame", fieldtype: "HTML"}],
        primary_action_label: __("Download A4 PDF"),
        primary_action() {
            const base = "/api/method/workforce_suite.workforce_suite.statutory_forms.download_a4";
            const query = new URLSearchParams(safeArgs).toString();
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
}
