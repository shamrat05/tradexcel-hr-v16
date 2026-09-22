frappe.query_reports["Tradexcel Salary Coverage Board"] = {
	filters: [
		{fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: (frappe.defaults && frappe.defaults.get_user_default && frappe.defaults.get_user_default("Company")) || "", reqd: 1},
		{fieldname: "as_of_date", label: __("As Of Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1},
		{fieldname: "employee_status", label: __("Employee Status"), fieldtype: "Select", options: "All\nActive\nInactive\nLeft", default: "Active"},
		{fieldname: "assignment_status", label: __("Assignment Status"), fieldtype: "Select", options: "All\nAssigned\nMissing\nCompany Mismatch", default: "All"},
		{fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Branch", default: "", get_query: function() { var c = frappe.query_report.get_filter_value('company'); return c ? {filters: {company: c}} : {}; }},
		{fieldname: "department", label: __("Department"), fieldtype: "Link", options: "Department", default: "", get_query: function() { var company = frappe.query_report.get_filter_value('company'); var branch = frappe.query_report.get_filter_value('branch'); if (!branch) { return company ? {filters: {company: company}} : {}; } return {query: 'tradex_hr.link_filters.departments_used_by_branch', filters: {company: company, branch: branch}}; }}
	]
};
