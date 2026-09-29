frappe.listview_settings["Overtime Slip"] = {
    onload(listview) {
        if (!frappe.user.has_role("Tradexcel HR Manager")) return;
        listview.page.add_inner_button(__("Prepare Overtime Drafts"), () => {
            const today = frappe.datetime.get_today();
            const first = today.slice(0, 7) + "-01";
            const [year, month] = today.slice(0, 7).split("-").map(Number);
            const last = today.slice(0, 7) + "-" + String(new Date(year, month, 0).getDate()).padStart(2, "0");
            const dialog = new frappe.ui.Dialog({
                title: __("Prepare Overtime Drafts"),
                fields: [
                    {fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company",
                        default: frappe.defaults.get_user_default("Company") || "", reqd: 1},
                    {fieldname: "from_date", label: __("From Date"), fieldtype: "Date", default: first, reqd: 1},
                    {fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: last, reqd: 1},
                    {fieldname: "preview", fieldtype: "HTML"},
                ],
            });
            let preview = null;
            const escaped = (value) => frappe.utils.escape_html(String(value || ""));
            const preview_action = () => {
                const values = dialog.get_values();
                if (!values) return;
                frappe.call({
                    method: "tradex_hr.tradexcel_hr.overtime_bulk.preview_overtime_drafts",
                    args: {company: values.company, from_date: values.from_date, to_date: values.to_date},
                    freeze: true,
                    callback(response) {
                        preview = response.message;
                        const rows = (preview?.rows || []).map((row) =>
                            `<tr><td><input type="checkbox" class="tradex-ot-select" data-employee="${escaped(row.employee)}" ${row.eligible ? "" : "disabled"}></td>` +
                            `<td>${escaped(row.employee_name || row.employee)}</td><td>${escaped(row.branch)}</td>` +
                            `<td>${escaped(row.department)}</td><td>${escaped(row.attendance_count)}</td>` +
                            `<td>${row.eligible ? __("Ready for draft") : escaped(row.reason || __("Salary authority needs review"))}</td></tr>`
                        ).join("");
                        dialog.fields_dict.preview.$wrapper.html(
                            `<p role="status">${__("Select Employees after reviewing their submitted overtime Attendance. Drafts do not create pay.")}</p>` +
                            `<div style="max-height:45vh;overflow:auto" tabindex="0"><table class="table table-bordered">` +
                            `<thead><tr><th>${__("Select")}</th><th>${__("Employee")}</th><th>${__("Branch")}</th>` +
                            `<th>${__("Department")}</th><th>${__("Attendance days")}</th><th>${__("Review")}</th></tr></thead>` +
                            `<tbody>${rows || `<tr><td colspan="6">${__("No matching overtime needs a draft.")}</td></tr>`}</tbody></table></div>`
                        );
                        dialog.set_primary_action(__("Create Selected Drafts"), () => {
                            const current = dialog.get_values();
                            if (!current) return;
                            if (current.company !== preview.company || current.from_date !== preview.from_date || current.to_date !== preview.to_date) {
                                frappe.msgprint(__("Filters changed. Preview again before creating drafts."));
                                return;
                            }
                            const employees = dialog.fields_dict.preview.$wrapper.find(".tradex-ot-select:checked")
                                .map((_, input) => input.dataset.employee).get();
                            if (!employees.length) {
                                frappe.msgprint(__("Select at least one Employee."));
                                return;
                            }
                            frappe.confirm(__("Create draft Overtime Slips for {0} selected Employee(s)? An independent Payroll Approver must submit them.", [employees.length]), () => {
                                frappe.call({
                                    method: "tradex_hr.tradexcel_hr.overtime_bulk.prepare_overtime_drafts",
                                    args: {...current, employees},
                                    freeze: true,
                                    callback(result) {
                                        const outcome = result.message;
                                        if (outcome?.status === "Queued") {
                                            frappe.msgprint(__("Draft preparation was queued. Review Overtime Slip List when it finishes."));
                                        } else {
                                            const created = (outcome?.rows || []).filter((row) => row.status === "Draft").length;
                                            const other = (outcome?.rows || []).length - created;
                                            frappe.msgprint(__("Drafts created: {0}. Needs review: {1}.", [created, other]));
                                        }
                                        dialog.hide();
                                        listview.refresh();
                                    },
                                });
                            });
                        });
                    },
                });
            };
            dialog.set_primary_action(__("Preview Eligible Employees"), preview_action);
            dialog.show();
        });
    },
};
