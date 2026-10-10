frappe.query_reports["Daily Attendance Summary"] = {
    filters: [
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
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            default: (frappe.defaults && frappe.defaults.get_user_default && frappe.defaults.get_user_default("Company")) || "",
            reqd: 1,
        },
        {
            fieldname: "branch",
            label: __("Branch"),
            fieldtype: "Link",
            options: "Branch",
            default: "",
        },
        {
            fieldname: "department",
            label: __("Department"),
            fieldtype: "Link",
            options: "Department",
            default: "",
        },
        {
            fieldname: "status",
            label: __("Status"),
            fieldtype: "Select",
            options: "\nPresent\nAbsent\nOn Leave\nHalf Day\nWork From Home\nNot Marked\nHoliday\nNot Started",
            default: "",
        },
    ],
    onload(report) {
        report.page.add_inner_button(__("Form 34 weekly draft"), () => {
            const filters = report.get_values ? report.get_values() : {};
            window.workforceStatutoryExport("form_34", filters || {});
        }, __("Registers"));
    },
};
