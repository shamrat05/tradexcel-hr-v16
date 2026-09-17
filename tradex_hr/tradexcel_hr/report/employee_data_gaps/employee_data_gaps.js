frappe.query_reports["Employee Data Gaps"] = {
	filters: [
		{fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: "Tradexcel Ceramics Ltd.", reqd: 1},
		{fieldname: "status", label: __("Employee Status"), fieldtype: "Select", options: "Active\nInactive\nLeft\nAll", default: "Active"},
		{fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Branch", default: "", get_query: function() { var c = frappe.query_report.get_filter_value('company'); return c ? {filters: {company: c}} : {}; }},
		{fieldname: "department", label: __("Department"), fieldtype: "Link", options: "Department", default: "", get_query: function() { var company = frappe.query_report.get_filter_value('company'); var branch = frappe.query_report.get_filter_value('branch'); if (!branch) { return company ? {filters: {company: company}} : {}; } return {query: 'tradex_hr.link_filters.departments_used_by_branch', filters: {company: company, branch: branch}}; }},
		{fieldname: "employment_type", label: __("Employment Type"), fieldtype: "Select", options: "All\nWorker\nNon Worker", default: "All"},
		{fieldname: "gap_type", label: __("Gap"), fieldtype: "Select", options: "All\nMissing Department\nMissing Employee Number\nNo Active Salary Assignment\nMultiple Active Salary Assignments\nLatest Structure Is a Wage Structure\nWorker Without Wage Structure\nFuture Joining Date With Punches\nMissing Designation\nMissing Date of Birth\nMissing Holiday List", default: "All"},
		{fieldname: "priority", label: __("Priority"), fieldtype: "Select", options: "All\nHigh\nMedium\nLow", default: "All"}
	],
	onload: function(report) {
		report.page.add_inner_button(__("Open Employee List for Bulk Fix"), function() {
			frappe.route_options = {
				company: report.get_filter_value("company"),
				status: report.get_filter_value("status")
			};
			frappe.set_route("List", "Employee");
		});
	}
};
