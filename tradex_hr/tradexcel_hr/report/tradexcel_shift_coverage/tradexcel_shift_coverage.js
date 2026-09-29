frappe.query_reports["Tradexcel Shift Coverage"] = {
    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            default: (frappe.defaults && frappe.defaults.get_user_default && frappe.defaults.get_user_default("Company")) || "",
            reqd: 1,
        },
        {
            fieldname: "as_of_date",
            label: __("As Of Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
            reqd: 1,
        },
        {
            fieldname: "branch",
            label: __("Branch"),
            fieldtype: "Link",
            options: "Branch",
            default: "",
            get_query() {
                const company = frappe.query_report.get_filter_value("company");
                return company ? { filters: { company } } : {};
            },
        },
        {
            fieldname: "department",
            label: __("Department"),
            fieldtype: "Link",
            options: "Department",
            default: "",
            get_query() {
                const company = frappe.query_report.get_filter_value("company");
                const branch = frappe.query_report.get_filter_value("branch");
                if (branch) {
                    return {
                        query: "tradex_hr.link_filters.departments_used_by_branch",
                        filters: { company, branch },
                    };
                }
                return company ? { filters: { company } } : {};
            },
        },
        {
            fieldname: "coverage",
            label: __("Coverage"),
            fieldtype: "Select",
            options: "All\nOverlap\nMissing\nAssigned\nDefault only",
            default: "All",
        },
    ],
};
