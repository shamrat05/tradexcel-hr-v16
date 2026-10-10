frappe.query_reports["Workforce Leave Balance Board"] = {
	filters: [
		{fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: (frappe.defaults && frappe.defaults.get_user_default && frappe.defaults.get_user_default("Company")) || "", reqd: 1},
		{fieldname: "as_of_date", label: __("As Of Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1}
	],
    onload(report) {
        report.page.add_inner_button(__("Form 9 leave register draft"), () => {
            const values = report.get_values ? report.get_values() : {};
            const scope = {...(values || {})};
            // An as-of snapshot is not a selected leave-history period.
            // The export asks for dates rather than reusing this as a range.
            delete scope.as_of_date;
            window.workforceStatutoryExport("form_9", scope);
        }, __("Registers"));
    },
};
