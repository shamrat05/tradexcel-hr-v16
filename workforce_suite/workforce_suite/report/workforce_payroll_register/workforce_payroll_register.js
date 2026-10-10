frappe.query_reports["Workforce Payroll Register"] = {
	filters: [
		{fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: (frappe.defaults && frappe.defaults.get_user_default && frappe.defaults.get_user_default("Company")) || "", reqd: 1},
		{fieldname: "from_date", label: __("From Date"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1},
		{fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1}
	],
    onload(report) {
        report.page.add_inner_button(__("Form 38 wage register draft"), () => {
            const filters = report.get_values ? report.get_values() : {};
            window.workforceStatutoryExport("form_38", filters || {});
        }, __("Registers"));
    },
};
