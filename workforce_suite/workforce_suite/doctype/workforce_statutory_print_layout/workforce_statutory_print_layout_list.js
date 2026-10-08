frappe.listview_settings["Workforce Statutory Print Layout"] = {
    onload(listview) {
        if (!frappe.model.can_create("Workforce Statutory Print Layout")) return;
        listview.page.add_menu_item(__("Prepare Draft Layout"), () => {
            const dialog = new frappe.ui.Dialog({
                title: __("Prepare Draft Layout"),
                fields: [
                    {fieldname: "company", fieldtype: "Link", options: "Company", label: __("Company"), reqd: 1},
                    {fieldname: "branch", fieldtype: "Link", options: "Branch", label: __("Establishment / Branch"),
                        get_query: () => ({filters: {company: dialog.get_value("company")}})},
                    {fieldname: "form_code", fieldtype: "Select", label: __("DIFE Source Entry"), reqd: 1,
                        options: frappe.get_meta("Workforce Statutory Print Layout").fields.find(f => f.fieldname === "form_code").options},
                    {fieldname: "effective_from", fieldtype: "Date", label: __("Draft Effective From"), reqd: 1},
                    {fieldname: "notice", fieldtype: "HTML", options: `<p>${__("Creates an internal draft only. Existing layouts and administrator edits are retained. Establishment profile, translations, legal evidence and salary mappings still require review.")}</p>`}
                ],
                primary_action_label: __("Prepare Draft"),
                async primary_action(values) {
                    dialog.disable_primary_action();
                    try {
                        const result = await frappe.call({
                            method: "workforce_suite.workforce_suite.statutory_setup.prepare_draft_layout",
                            args: values, freeze: true
                        });
                        dialog.hide();
                        const layouts = result.message.layouts;
                        if (layouts.length === 1) frappe.set_route("Form", "Workforce Statutory Print Layout", layouts[0]);
                        else {
                            frappe.msgprint(__("Existing layouts were preserved. Select one from the list."));
                            listview.filter_area.add([["Workforce Statutory Print Layout", "company", "=", values.company],
                                ["Workforce Statutory Print Layout", "form_code", "=", values.form_code]]);
                            listview.refresh();
                        }
                    } finally { dialog.enable_primary_action(); }
                }
            });
            dialog.show();
        });
    }
};
