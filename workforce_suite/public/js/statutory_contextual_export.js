/* Standard Frappe navigation to versioned, permission-scoped statutory drafts.
 * The selected report context is reused; only missing/meaningful choices
 * appear. Backend validation controls company and employee visibility.
 */
window.workforceStatutoryDownload = async function (method, args) {
    // POST keeps worker/financial filters out of URLs and commits the server
    // generation audit through Frappe's normal CSRF-protected request lifecycle.
    const response = await fetch("/api/method/" + method, {
        method: "POST", credentials: "same-origin",
        headers: {"Content-Type": "application/x-www-form-urlencoded",
                  "X-Frappe-CSRF-Token": frappe.csrf_token},
        body: new URLSearchParams(args),
    });
    if (!response.ok) {
        frappe.msgprint(__("Export could not be generated. Review source permissions, required values and the selected template."));
        return;
    }
    const blob = await response.blob();
    const filename = (response.headers.get("Content-Disposition") || "").match(/filename="?([^";]+)/);
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename ? filename[1] : "statutory-working-copy";
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 30000);
};

window.workforceStatutoryExport = async function (formCode, context) {
    if (!frappe.model.can_read("Workforce Statutory Print Layout")) {
        frappe.msgprint(__("You need authorized statutory-layout access to use this export."));
        return;
    }
    const safeContext = {...(context || {})};
    if (!safeContext.company) {
        frappe.msgprint(__("Select a Company first."));
        return;
    }
    const {message: records} = await frappe.call({
        method: "workforce_suite.workforce_suite.statutory_forms.available_print_layouts",
        args: {
            form_code: formCode,
            company: safeContext.company,
            branch: safeContext.branch || "",
        },
    });
    if (!records || !records.length) {
        frappe.msgprint(__("No saved template is available for this Company and branch. An authorized HR administrator can configure a draft in Statutory Form Layouts."));
        return;
    }
    const choose = (item) => {
        // Pass only the source filter keys expected by the backend.
        const allowed = ["employee", "branch", "department", "employment_type",
                         "from_date", "to_date"];
        const scoped = Object.fromEntries(
            allowed.filter((key) => safeContext[key]).map((key) => [key, safeContext[key]])
        );
        return window.workforceStatutoryPrintLayout(item.name, scoped);
    };
    if (records.length === 1) {
        return choose(records[0]);
    }
    frappe.prompt([{
        fieldname: "layout_name", fieldtype: "Select", reqd: 1,
        label: __("Saved draft layout"),
        options: records.map((item) => ({
            label: item.title + " · " + item.version + " · " + item.status,
            value: item.name,
        })),
        default: records[0].name,
    }], (values) => {
        const item = records.find((entry) => entry.name === values.layout_name);
        if (item) return choose(item);
    }, __("Select printing layout"), __("Continue"));
};

window.workforceStatutoryPrintLayout = async function (layoutName, context = {}) {
    const {message: options} = await frappe.call({
        method: "workforce_suite.workforce_suite.statutory_forms.export_options",
        args: {layout_name: layoutName}
    });
    if (!options.languages || !options.languages.length) {
        frappe.msgprint(__("This layout requires complete English labels before printing."));
        return;
    }
    const current = {...context};
    const fields = [];
    if (options.languages.includes("bn")) {
        fields.push({
            fieldname: "language", fieldtype: "Select", label: __("Language"),
            options: "English\nবাংলা", default: "English", reqd: 1
        });
    }
    const period = options.period_mode;
    if (period === "none") {
        delete current.from_date;
        delete current.to_date;
    } else if (period === "week") {
        const start = current.from_date ? new Date(current.from_date + "T12:00:00") : null;
        const end = current.to_date ? new Date(current.to_date + "T12:00:00") : null;
        const isWeek = start && end && start.getDay() === 5 &&
            Math.round((end.getTime() - start.getTime()) / 86400000) === 6;
        if (!isWeek) {
            const today = frappe.datetime.get_today();
            const weekday = new Date(today + "T12:00:00").getDay();
            fields.push({
                fieldname: "week_start", fieldtype: "Date", reqd: 1,
                label: __("Week beginning (Friday)"),
                default: frappe.datetime.add_days(today, -((weekday + 2) % 7)),
                description: __("Official-style Form 34 uses one Friday–Thursday week; monthly analysis remains in the attendance report.")
            });
        }
    } else if (period === "half-year" || period === "year") {
        const today = frappe.datetime.get_today();
        const year = today.slice(0, 4);
        const valid = current.from_date && current.to_date &&
            current.from_date.slice(0, 4) === current.to_date.slice(0, 4) &&
            (period === "year" ? current.from_date.endsWith("-01-01") && current.to_date.endsWith("-12-31") :
                (current.from_date.endsWith("-01-01") && current.to_date.endsWith("-06-30")) ||
                (current.from_date.endsWith("-07-01") && current.to_date.endsWith("-12-31")));
        if (!valid) {
            const secondHalf = Number(today.slice(5, 7)) > 6 && period === "half-year";
            fields.push(
                {fieldname: "from_date", fieldtype: "Date", label: __("Reporting period starts"), reqd: 1,
                    default: year + (secondHalf ? "-07-01" : "-01-01"),
                    description: period === "year" ? __("Form 81 requires a full calendar year.") : __("Form 80 requires January–June or July–December.")},
                {fieldname: "to_date", fieldtype: "Date", label: __("Reporting period ends"), reqd: 1,
                    default: year + (period === "year" || secondHalf ? "-12-31" : "-06-30")}
            );
        }
    } else if (!(current.from_date && current.to_date)) {
        fields.push(
            {fieldname: "from_date", fieldtype: "Date", label: __("From Date"),
                reqd: 1, default: frappe.datetime.month_start()},
            {fieldname: "to_date", fieldtype: "Date", label: __("To Date"),
                reqd: 1, default: frappe.datetime.get_today()}
        );
    }
    if (options.employee_required && !current.employee) {
        fields.push({
            fieldname: "employee", fieldtype: "Link", options: "Employee",
            label: __("Employee"), get_query: () => ({filters: {company: options.company}})
        });
        fields.push({
            fieldname: "include_all", fieldtype: "Check",
            label: __("All matching employees (up to 50)"), default: 0
        });
    }
    if (options.allow_worker_filters) {
        const optional = [];
        if (!current.employee && !options.employee_required) {
            optional.push({fieldname: "employee", fieldtype: "Link", options: "Employee",
                label: __("Employee (optional)"), get_query: () => ({filters: {company: options.company}})});
        }
        for (const [key, doctype] of [["branch", "Branch"], ["department", "Department"]]) {
            if (!current[key] && !(key === "branch" && options.branch)) {
                optional.push({fieldname: key, fieldtype: "Link", options: doctype,
                    label: __(doctype + " (optional)"), get_query: () => ({filters: {company: options.company}})});
            }
        }
        if (options.data_source === "Employee" && !current.employment_type) {
            optional.push({fieldname: "employment_type", fieldtype: "Link", options: "Employment Type",
                label: __("Employment type (optional)")});
        }
        if (optional.length) fields.push({fieldname: "scope_break", fieldtype: "Section Break",
            label: __("Narrow results"), collapsible: 1}, ...optional);
    }
    const preview = async (values = {}) => {
        const args = {...current, layout_name: layoutName};
        if (values.week_start) {
            const d = new Date(values.week_start + "T12:00:00");
            if (d.getDay() !== 5) {
                frappe.msgprint(__("Select a Friday for Form 34.")); return;
            }
            args.from_date = values.week_start;
            args.to_date = frappe.datetime.add_days(values.week_start, 6);
        }
        if (values.from_date) args.from_date = values.from_date;
        if (values.to_date) args.to_date = values.to_date;
        for (const key of ["employee", "branch", "department", "employment_type"]) {
            if (values[key]) args[key] = values[key];
        }
        if (values.include_all) args.include_all = 1;
        if (options.employee_required && !args.employee && !args.include_all) {
            frappe.msgprint(__("Choose an Employee or explicitly select all matching employees."));
            return;
        }
        args.language = values.language === "বাংলা" ? "bn" : "en";
        const response = await frappe.call({
            method: "workforce_suite.workforce_suite.statutory_forms.preview_a4",
            args, freeze: true,
            freeze_message: __("Preparing A4 draft preview")
        });
        const dialog = new frappe.ui.Dialog({
            title: __("Statutory working draft"), size: "extra-large",
            fields: [{fieldname: "findings", fieldtype: "HTML"}, {fieldname: "page", fieldtype: "HTML"}],
            primary_action_label: __("Download A4 PDF"),
            primary_action() {
                return window.workforceStatutoryDownload("workforce_suite.workforce_suite.statutory_forms.download_a4", args);
            },
        });
        dialog.add_custom_action(__("Editable DOCX working copy"), () => {
            return window.workforceStatutoryDownload("workforce_suite.workforce_suite.statutory_forms.download_docx", args);
        });
        const findings = response.message.findings || [];
        if (findings.length) {
            const escape = frappe.utils.escape_html;
            dialog.fields_dict.findings.$wrapper.html(
                "<p role='status'>" + escape(__("Draft only. Resolve missing data and review findings before official use.")) + "</p>" +
                "<details><summary>" + escape(__("Review findings")) + " (" + findings.length + ")</summary><ul>" +
                findings.map((finding) => "<li>" + escape((finding.row ? __("Row") + " " + finding.row + ": " : "") + finding.message) + "</li>").join("") + "</ul></details>");
        }
        const frame = document.createElement("iframe");
        frame.title = __("Draft A4 print");
        frame.setAttribute("sandbox", "allow-same-origin");
        frame.style.cssText = "width:100%;height:65vh;border:1px solid var(--border-color,#ddd)";
        frame.srcdoc = response.message.html;
        dialog.fields_dict.page.$wrapper.append(frame);
        dialog.show();
    };
    if (!fields.length) return preview();
    frappe.prompt(fields, preview, __("Print settings"), __("Preview A4"));
};
