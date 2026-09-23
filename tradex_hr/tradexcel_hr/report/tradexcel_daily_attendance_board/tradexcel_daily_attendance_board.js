frappe.query_reports["Tradexcel Daily Attendance Board"] = {
	filters: [
		{fieldname: "attendance_date", label: __("Attendance Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1},
		{fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: (frappe.defaults && frappe.defaults.get_user_default && frappe.defaults.get_user_default("Company")) || "", reqd: 1}
	]
};
