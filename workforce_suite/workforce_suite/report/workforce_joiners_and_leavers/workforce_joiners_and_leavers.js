frappe.query_reports["Workforce Joiners and Leavers"] = {
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
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            default: frappe.datetime.month_start(),
            reqd: 1,
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
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
                        query: "workforce_suite.link_filters.departments_used_by_branch",
                        filters: { company, branch },
                    };
                }
                return company ? { filters: { company } } : {};
            },
        },
    ],
    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (column.fieldname === "movement") {
            if (data.movement === "Joined") {
                value = `<span class="indicator-pill green font-weight-bold">${value}</span>`;
            } else if (data.movement === "Left") {
                value = `<span class="indicator-pill orange font-weight-bold">${value}</span>`;
            }
        }
        return value;
    },
    onload(report) {
        const hr_maker = ["Workforce Suite Manager", "HR User", "HR Manager"]
            .some((role) => frappe.user.has_role(role));
        if (hr_maker) {
            report.page.add_inner_button(__("View Employee Onboardings"), () => {
                frappe.set_route("List", "Employee Onboarding");
            });
            report.page.add_inner_button(__("View Employee Separations"), () => {
                frappe.set_route("List", "Employee Separation");
            });
        }
    },
};
