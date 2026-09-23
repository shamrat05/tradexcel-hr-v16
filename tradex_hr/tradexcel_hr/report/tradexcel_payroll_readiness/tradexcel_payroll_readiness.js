function payroll_month_default() {
    return frappe.datetime.get_today().slice(0, 7) + "-01";
}

function readiness_route(report, action, employee, start, end) {
    const filters = { employee };
    if (action === "attendance") {
        frappe.route_options = { ...filters, attendance_date: ["between", [start, end]] };
        frappe.set_route("List", "Attendance");
    } else if (action === "attendance_requests") {
        frappe.route_options = { ...filters, from_date: start, to_date: end };
        frappe.set_route("List", "Attendance Request");
    } else if (action === "salary_assignments") {
        frappe.route_options = filters;
        frappe.set_route("List", "Salary Structure Assignment");
    } else if (action === "migration") {
        show_daily_wage_migration_preview(report);
    }
}

function financial_readiness_route(action, company, employee, slip, component, account) {
    const routes = {
        tax_slabs: ["List", "Income Tax Slab", {company}],
        payroll_periods: ["List", "Payroll Period", {company}],
        salary_assignments: ["List", "Salary Structure Assignment", {company}],
        salary_components: ["List", "Salary Component", component ? {name: component} : {}],
        policy_exceptions: ["List", "Tradexcel Policy Exception", {company}],
        accounting_dimensions: ["List", "Accounting Dimension", {}],
        cost_centers: ["List", "Cost Center", {company}],
        payroll_payable: account
            ? ["Form", "Account", account]
            : ["Form", "Company", company],
        salary_slip: slip
            ? ["Form", "Salary Slip", slip]
            : ["List", "Salary Slip", {employee}],
    };
    const route = routes[action];
    if (!route) return;
    frappe.route_options = typeof route[2] === "object" ? {...route[2]} : null;
    frappe.set_route(...route);
}

function show_daily_wage_migration_preview(report) {
    const dialog = new frappe.ui.Dialog({
        title: __("Review Daily Wage Structure Migration"),
        fields: [
            {
                fieldname: "effective_date",
                label: __("Proposed Effective Date"),
                fieldtype: "Date",
                description: __("Choose an approved business date. No date is selected automatically."),
            },
            { fieldname: "preview", fieldtype: "HTML" },
        ],
        primary_action_label: __("Preview"),
        primary_action(values) {
            frappe.call({
                method: "tradex_hr.tradexcel_hr.report.tradexcel_payroll_readiness.tradexcel_payroll_readiness.get_daily_wage_migration_preview",
                args: {
                    company: report.get_filter_value("company"),
                    payroll_month: report.get_filter_value("payroll_month"),
                    effective_date: values.effective_date || null,
                },
                freeze: true,
                freeze_message: __("Checking assignments and conflicts"),
                callback(response) {
                    const result = response.message;
                    if (!result) return;
                    const escape = frappe.utils.escape_html;
                    const status = result.status === "DECISION_REQUIRED"
                        ? __("Decision required: select an approved effective date before planning assignments.")
                        : __("Read-only preview for {0}.", [escape(result.effective_date)]);
                    const rows = result.rows.map((row) =>
                        "<tr><td>" + escape(row.employee_name || row.employee) + "</td>" +
                        "<td>" + escape(row.current_assignment || __("Missing")) + "</td>" +
                        "<td>" + escape(row.current_structure || __("Missing")) + "</td>" +
                        "<td>" + (row.current_rate == null ? __("—") : escape(String(row.current_rate))) + "</td>" +
                        "<td>" + escape(row.current_basis) + "</td>" +
                        "<td>" + escape(row.conflicts || __("No conflict found")) + "</td></tr>"
                    ).join("");
                    const components = result.proposed_structure.components.map((item) =>
                        escape(item.component) + ": " + escape(String(item.amount)) + ", " +
                        __("prorated by payment days") + ": " + escape(String(item.depends_on_payment_days))
                    ).join("<br>");
                    dialog.fields_dict.preview.$wrapper.html(
                        "<p role=\"status\">" + status + "</p>" +
                        "<p>" + __("Employees") + ": " + result.employee_count + " · " +
                        __("Conflicts or missing data") + ": " + result.conflict_count + "</p>" +
                        "<p>" + escape(result.proposed_structure.name) + "<br>" + components + "</p>" +
                        "<div style=\"max-height: 50vh; overflow: auto\" tabindex=\"0\" aria-label=\"" +
                        __("Daily Wage migration preview rows") + "\">" +
                        "<table class=\"table table-bordered\"><thead><tr>" +
                        "<th>" + __("Employee") + "</th><th>" + __("Current SSA") + "</th>" +
                        "<th>" + __("Current Structure") + "</th><th>" + __("Current Rate") + "</th>" +
                        "<th>" + __("Pay Basis") + "</th><th>" + __("Conflicts / Missing Data") +
                        "</th></tr></thead><tbody>" + rows + "</tbody></table></div>"
                    );
                },
            });
        },
    });
    dialog.show();
}

frappe.query_reports["Tradexcel Payroll Readiness"] = {
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
            fieldname: "payroll_month",
            label: __("Payroll Month"),
            fieldtype: "Date",
            default: payroll_month_default(),
            reqd: 1,
        },
    ],
    onload(report) {
        report.$prepare_payroll_button = null;
        if (!frappe.user.has_role("Tradexcel Payroll Manager")) return;

        report.$prepare_payroll_button = report.page.set_primary_action(
            __("Prepare Payroll"),
            () => {
                frappe.call({
                    method: "tradex_hr.tradexcel_hr.report.tradexcel_payroll_readiness.tradexcel_payroll_readiness.prepare_payroll",
                    args: {
                        company: report.get_filter_value("company"),
                        payroll_month: report.get_filter_value("payroll_month"),
                    },
                    freeze: true,
                    freeze_message: __("Rechecking payroll readiness"),
                    callback(response) {
                        const result = response.message;
                        if (result && result.status === "PREPARED" && result.payroll_entry) {
                            frappe.set_route("Form", "Payroll Entry", result.payroll_entry);
                        } else {
                            frappe.msgprint({
                                title: __("Payroll was not prepared"),
                                message: __("Readiness changed or payroll needs attention. Refresh this report and review the current findings."),
                                indicator: "orange",
                            });
                        }
                    },
                });
            }
        );
        report.$prepare_payroll_button.prop("disabled", true);
        report.page.add_inner_button(
            __("Review Structure Migration"),
            () => show_daily_wage_migration_preview(report)
        );

        report.$report
            .off("click.tradexcelPayrollReadiness")
            .on("click.tradexcelPayrollReadiness", ".payroll-readiness-action", (event) => {
                event.preventDefault();
                const button = $(event.currentTarget);
                readiness_route(
                    report,
                    button.attr("data-action"),
                    button.attr("data-employee"),
                    button.attr("data-start"),
                    button.attr("data-end")
                );
            });
        report.$report
            .off("click.tradexcelFinancialReadiness")
            .on("click.tradexcelFinancialReadiness", ".financial-readiness-action", (event) => {
                event.preventDefault();
                const button = $(event.currentTarget);
                financial_readiness_route(
                    button.attr("data-action"), button.attr("data-company"),
                    button.attr("data-employee"), button.attr("data-slip"),
                    button.attr("data-component"), button.attr("data-account")
                );
            });
    },
    after_datatable_render() {
        const report = frappe.query_report;
        if (!report.$prepare_payroll_button || !report.raw_data?.report_summary) return;
        const summary = Object.fromEntries(
            report.raw_data.report_summary.map((item) => [item.label, item.value])
        );
        const ready = Number(summary[__("Ready")]) || 0;
        const blocked = Number(summary[__("Need attention")]) || 0;
        const slipStatus = summary[__("Salary Slip creation")];
        const entryStatus = summary[__("Managed Payroll Entry")];
        const hasEntryName = entryStatus && ![
            __("Not prepared"),
            __("Cancelled"),
            __("Unmanaged entry needs review"),
        ].includes(entryStatus);

        report.$prepare_payroll_button.prop(
            "disabled",
            !report.get_filter_value("company") ||
                ready === 0 ||
                blocked > 0 ||
                ["Queued", "Failed"].includes(slipStatus) ||
                entryStatus === __("Cancelled") ||
                entryStatus === __("Unmanaged entry needs review")
        );

        if (slipStatus === "Failed" && hasEntryName && !report.$open_payroll_entry_button) {
            report.$open_payroll_entry_button = report.page.add_inner_button(
                __("Open Payroll Entry for retry"),
                () => frappe.set_route("Form", "Payroll Entry", entryStatus)
            );
        }
    },
    formatter(value, row, column, data, default_formatter) {
        if (column.fieldname === "financial_action_kinds" && data?.financial_action_kinds) {
            const escape = frappe.utils.escape_html;
            const labels = {
                tax_slabs: __("Income Tax Slabs"),
                payroll_periods: __("Payroll Periods"),
                salary_assignments: __("Salary Assignments"),
                salary_components: __("Salary Components"),
                policy_exceptions: __("Tax Exceptions"),
                accounting_dimensions: __("Accounting Dimensions"),
                cost_centers: __("Cost Centers"),
                payroll_payable: __("Payroll Payable Account"),
                salary_slip: __("Salary Slip"),
            };
            return "<div class=\"text-nowrap\">" + data.financial_action_kinds.split("|").map((action) =>
                "<button type=\"button\" class=\"btn btn-link btn-xs financial-readiness-action\" " +
                "data-action=\"" + escape(action) + "\" data-company=\"" + escape(data.company || "") + "\" " +
                "data-employee=\"" + escape(data.employee || "") + "\" " +
                "data-slip=\"" + escape(data.financial_salary_slip || "") + "\" " +
                "data-component=\"" + escape(data.financial_component || "") + "\" " +
                "data-account=\"" + escape(data.financial_account || "") + "\">" +
                escape(labels[action] || action) + "</button>"
            ).join("") + "</div>";
        }
        if (column.fieldname !== "actions" || !data?.action_kinds) {
            return default_formatter(value, row, column, data);
        }
        const escape = frappe.utils.escape_html;
        const labels = {
            attendance: __("Attendance"),
            attendance_requests: __("Requests"),
            salary_assignments: __("Salary Assignments"),
            migration: __("Review Structure Migration"),
        };
        const actions = data.action_kinds.split("|").map((action) =>
            "<button type=\"button\" class=\"btn btn-link btn-xs payroll-readiness-action\" " +
            "data-action=\"" + escape(action) + "\" " +
            "data-employee=\"" + escape(data.employee) + "\" " +
            "data-start=\"" + escape(data.period_start) + "\" " +
            "data-end=\"" + escape(data.period_end) + "\">" +
            escape(labels[action] || action) + "</button>"
        ).join("");
        return "<div class=\"text-nowrap\">" + actions + "</div>";
    },
};
