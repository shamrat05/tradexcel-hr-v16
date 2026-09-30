frappe.query_reports["Tradexcel Shift Coverage"] = {
    get_datatable_options(options) {
        return { ...options, checkboxColumn: true };
    },
    onload(report) {
        // Row actions only for users who can open the installed single tool.
        if (!(frappe.model.can_read && frappe.model.can_read("Shift Assignment Tool"))) return;
        const escape = frappe.utils.escape_html;
        const stateOf = (row) => String(row.coverage || "");
        const names = (rows) => rows.map((row) => row.employee).filter(Boolean);
        const openTool = (rows) => {
            // The native tool rebuilds its own permission-aware eligible list.
            // No Employee IDs are passed so its preview stays authoritative.
            const route_options = { action: "Assign Shift", start_date: report.get_filter_value("as_of_date") };
            for (const fieldname of ["company", "branch", "department"]) {
                const value = report.get_filter_value(fieldname);
                if (value) route_options[fieldname] = value;
            }
            frappe.route_options = route_options;
            frappe.set_route("Form", "Shift Assignment Tool");
        };
        const openAssignments = (rows) => {
            // Native Shift Assignment is a submittable DocType. Shift Coverage
            // calculations only consider submitted assignments (docstatus 1).
            // List route options can only express AND filters, so an exact
            // "active on the selected day" filter (End Date blank OR End Date
            // on/after the day) is not available here. Filter submitted records
            // for selected employees starting on or before the review day, and
            // guide the operator to inspect End Date without inferring historical
            // validity solely from cached status.
            frappe.route_options = {
                docstatus: 1,
                employee: ["in", names(rows)],
                start_date: ["<=", report.get_filter_value("as_of_date")],
            };
            frappe.set_route("List", "Shift Assignment", "List");
        };
        report.page.add_inner_button(__("Review / Assign Shift"), () => {
            const rows = report.get_checked_items();
            if (!rows.length) {
                frappe.msgprint(__("Select one or more Employees in the report first."));
                return;
            }
            const missing = rows.filter((row) => stateOf(row).startsWith("No shift assigned"));
            const overlap = rows.filter((row) => stateOf(row).startsWith("Multiple active"));
            const default_only = rows.filter((row) => stateOf(row) === "Default shift only");
            const assigned = rows.filter((row) => stateOf(row) === "Assigned");
            let html = `<p class="small">${escape(report.get_filter_value("as_of_date"))} · ${rows.length} ${__("selected Employee(s)")}</p>`;
            if (missing.length) {
                html += `<p><b>${__("No shift assigned")} (${missing.length})</b></p>
                    <p class="small">${__("Use the native Shift Assignment Tool: choose the Shift Type and this date, review the eligible list, select the Employee(s), then confirm Assign Shift. Nothing is assigned before the native confirmation.")}</p>
                    <ul>${missing.map((row) => `<li>${escape(row.employee_name || row.employee || "")}</li>`).join("")}</ul>`;
            }
            if (overlap.length) {
                html += `<p><b>${__("Multiple active assignments")} (${overlap.length})</b></p>
                    <p class="small">${__("The app never chooses between assignments. Review opens the native Shift Assignment list filtered to submitted records (docstatus 1) for these Employees with Start Date on or before the selected day. Check each row's End Date: an assignment is active on that day only when End Date is blank or on/after it — previously ended assignments are retained in the broader results. Do not infer historical validity solely from cached assignment status; inspect and correct the conflicting assignment there.")}</p>
                    <ul>${overlap.map((row) => `<li>${escape(row.employee_name || row.employee || "")} — ${escape(row.assigned_shifts || "")}</li>`).join("")}</ul>`;
            }
            if (default_only.length) {
                html += `<p><b>${__("Default shift only")} (${default_only.length})</b></p>
                    <p class="small">${__("The Employee default shift applies. Use the native tool only if a dated assignment is actually required; the default is not assumed to be wrong.")}</p>`;
            }
            if (assigned.length) {
                html += `<p><b>${__("Already assigned")} (${assigned.length})</b></p>
                    <p class="small">${__("One active assignment covers this date. No action is needed.")}</p>`;
            }
            frappe.msgprint({
                title: __("Shift coverage next step"),
                message: html,
                primary_action: (missing.length || default_only.length) ? {
                    label: __("Open Shift Assignment Tool"),
                    action: () => openTool(rows.filter((row) => stateOf(row).startsWith("No shift assigned") || stateOf(row) === "Default shift only")),
                } : undefined,
                secondary_action: overlap.length ? {
                    label: __("Review Shift Assignments"),
                    action: () => openAssignments(overlap),
                } : undefined,
            });
        });
    },
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
