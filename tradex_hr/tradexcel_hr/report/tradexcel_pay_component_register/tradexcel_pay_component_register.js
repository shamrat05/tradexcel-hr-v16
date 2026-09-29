frappe.query_reports["Tradexcel Pay Component Register"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: (frappe.defaults && frappe.defaults.get_user_default && frappe.defaults.get_user_default("Company")) || "",
			reqd: 1,
		},
		{ fieldname: "from_date", label: __("Period From"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1 },
		{ fieldname: "to_date", label: __("Period To"), fieldtype: "Date", default: frappe.datetime.month_end(), reqd: 1 },
		{ fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Branch", default: "" },
		{ fieldname: "department", label: __("Department"), fieldtype: "Link", options: "Department", default: "" },
		{ fieldname: "component_type", label: __("Type"), fieldtype: "Select", options: "All\nEarning\nDeduction", default: "All" },
		{ fieldname: "component", label: __("Salary Component"), fieldtype: "Link", options: "Salary Component", default: "" },
	],
};
