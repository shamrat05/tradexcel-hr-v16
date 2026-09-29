frappe.query_reports["Workforce Anomaly Radar"] = {
	filters: [
		{fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: (frappe.defaults && frappe.defaults.get_user_default && frappe.defaults.get_user_default("Company")) || "", reqd: 1},
		{fieldname: "from_date", label: __("From Date"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1},
		{fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1},
		{fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Branch", default: "", get_query: function() { var c = frappe.query_report.get_filter_value('company'); return c ? {filters: {company: c}} : {}; }},
		{fieldname: "department", label: __("Department"), fieldtype: "Link", options: "Department", default: "", get_query: function() { var company = frappe.query_report.get_filter_value('company'); var branch = frappe.query_report.get_filter_value('branch'); if (!branch) { return company ? {filters: {company: company}} : {}; } return {query: 'tradex_hr.link_filters.departments_used_by_branch', filters: {company: company, branch: branch}}; }},
		{fieldname: "category", label: __("Category"), fieldtype: "Select", options: "All\nCheckin\nAttendance\nPayroll\nLeave\nTax", default: "All"},
		{fieldname: "severity", label: __("Severity"), fieldtype: "Select", options: "All\nHigh\nMedium\nLow", default: "All"},
		{fieldname: "z_threshold", label: __("Outlier Z Threshold"), fieldtype: "Float", default: 3.5, description: __("Modified z-score cutoff for cohort outliers (standard practice: 3.5)")},
		{fieldname: "min_cohort", label: __("Minimum Cohort Size"), fieldtype: "Int", default: 5, description: __("Groups smaller than this are skipped so statistics stay meaningful")}
	]
};
