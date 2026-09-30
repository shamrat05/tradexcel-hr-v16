frappe.query_reports["Employee Data Gaps"] = {
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
            fieldname: "status",
            label: __("Employee Status"),
            fieldtype: "Select",
            options: "Active\nInactive\nLeft\nAll",
            default: "Active",
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
                if (!branch) return company ? { filters: { company } } : {};
                return { query: "tradex_hr.link_filters.departments_used_by_branch", filters: { company, branch } };
            },
        },
        {
            fieldname: "employee",
            label: __("Employee"),
            fieldtype: "Link",
            options: "Employee",
            default: "",
            get_query() {
                const company = frappe.query_report.get_filter_value("company");
                const branch = frappe.query_report.get_filter_value("branch");
                const department = frappe.query_report.get_filter_value("department");
                const filters = {};
                if (company) filters.company = company;
                if (branch) filters.branch = branch;
                if (department) filters.department = department;
                return { filters };
            },
        },
        {
            fieldname: "employment_type",
            label: __("Employment Type"),
            fieldtype: "Link",
            options: "Employment Type",
            default: "",
        },
        {
            fieldname: "gap_type",
            label: __("Gap"),
            fieldtype: "Select",
            options: "All\nMissing Department\nMissing Employee Number\nNo Active Salary Assignment\nNo Shift Assignment\nConflicting Salary Assignments\nPay Basis Needs Review\nFuture Joining Date With Punches\nMissing Designation\nMissing Date of Birth\nMissing Holiday List",
            default: "All",
        },
        {
            fieldname: "priority",
            label: __("Priority"),
            fieldtype: "Select",
            options: "All\nHigh\nMedium\nLow",
            default: "All",
        },
    ],
    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (column.fieldname === "priority") {
            if (data.priority === "High") {
                value = `<span class="indicator-pill red font-weight-bold">${value}</span>`;
            } else if (data.priority === "Medium") {
                value = `<span class="indicator-pill orange font-weight-bold">${value}</span>`;
            } else if (data.priority === "Low") {
                value = `<span class="indicator-pill blue">${value}</span>`;
            }
        }
        return value;
    },
    onload(report) {
        report.page.add_inner_button(__("Review Matching Employees"), () => {
            const names = (report.data || []).map((row) => row.employee).filter(Boolean);
            if (!names.length) {
                frappe.msgprint(__("No matching Employees need review."));
                return;
            }
            frappe.route_options = { name: ["in", names] };
            frappe.set_route("List", "Employee");
        });

        const shift_maker = ["Tradexcel HR Manager", "Tradexcel HR/Attendance Officer", "HR User", "HR Manager"]
            .some((role) => frappe.user.has_role(role));
        if (shift_maker) {
            report.page.add_inner_button(__("Open Bulk Shift Assignment"), () => {
                const route_options = { start_date: frappe.datetime.get_today() };
                for (const fieldname of ["company", "branch", "department"]) {
                    const value = report.get_filter_value(fieldname);
                    if (value) route_options[fieldname] = value;
                }
                frappe.route_options = route_options;
                frappe.set_route("Form", "Shift Assignment Tool");
            });
        }

        const hr_maker = ["Tradexcel HR Manager", "HR User", "HR Manager"]
            .some((role) => frappe.user.has_role(role));
        if (!hr_maker) return;

        report.page.add_inner_button(__("Open Salary Assignment Tool"), () => {
            frappe.route_options = { company: report.get_filter_value("company") };
            frappe.set_route("Form", "Bulk Salary Structure Assignment");
        });

        report.page.add_inner_button(__("Create Employee Transfer"), () => {
            const rows = report.data || [];
            if (rows.length !== 1) {
                frappe.msgprint(__("Filter this report to one Employee before opening a Transfer."));
                return;
            }
            frappe.new_doc("Employee Transfer", { employee: rows[0].employee });
        });

        report.page.add_inner_button(__("Create Employee Promotion"), () => {
            const rows = report.data || [];
            if (rows.length !== 1) {
                frappe.msgprint(__("Filter this report to one Employee before opening a Promotion."));
                return;
            }
            frappe.new_doc("Employee Promotion", { employee: rows[0].employee });
        });

        report.page.add_inner_button(__("View Employee Onboardings"), () => {
            frappe.set_route("List", "Employee Onboarding");
        });
    },
};
