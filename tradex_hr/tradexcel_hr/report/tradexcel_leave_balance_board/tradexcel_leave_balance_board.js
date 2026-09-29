frappe.query_reports["Tradexcel Leave Balance Board"] = {
	filters: [
		{fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: (frappe.defaults && frappe.defaults.get_user_default && frappe.defaults.get_user_default("Company")) || "", reqd: 1},
		{fieldname: "as_of_date", label: __("As Of Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1}
	]
};
