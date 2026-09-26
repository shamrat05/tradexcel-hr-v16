frappe.query_reports["Tradexcel Daily Attendance Board"] = {
	formatter(value, row, column, data, default_formatter) {
		if (["status", "attendance_state"].includes(column.fieldname)) value = __(value || "");
		return default_formatter(value, row, column, data);
	},
	get_datatable_options(options) {
		return { ...options, checkboxColumn: true };
	},
	onload(report) {
		const roles = ["Tradexcel HR Manager", "Tradexcel HR/Attendance Officer"];
		if (!roles.some((role) => frappe.user.has_role(role))) return;

	report.page.add_inner_button(__("Prepare Attendance Corrections"), () => {
		const selected = report.get_checked_items().map((row) => row.employee).filter(Boolean);
		if (!selected.length) {
			frappe.msgprint(__("Select one or more Employees in the report first."));
			return;
		}
		const values = report.get_filter_values();
		const dialog = new frappe.ui.Dialog({
			title: __("Prepare Attendance Corrections"),
			fields: [
				{ fieldname: "scope", fieldtype: "HTML", options: `<p>${frappe.utils.escape_html(values.company)} · ${frappe.utils.escape_html(values.attendance_date)}</p>` },
				{ fieldname: "action", label: __("Correction"), fieldtype: "Select", reqd: 1,
					options: ["Present", "Half Day", "Work From Home"].join("\n") },
				{ fieldname: "explanation", label: __("Explanation"), fieldtype: "Small Text", reqd: 1 },
				{ fieldname: "preview", fieldtype: "HTML" },
			],
		});
		let previewReady = false;
		let previewGeneration = 0;
		const args = () => ({
			company: values.company,
			attendance_date: values.attendance_date,
			branch: values.branch || "",
			department: values.department || "",
			employee_names: selected,
			action: dialog.get_value("action"),
			explanation: dialog.get_value("explanation"),
		});
		const render = (rows) => {
			const escape = frappe.utils.escape_html;
			const body = rows.map((row) => `<tr><td>${escape(row.employee_name || row.employee || "")}</td>
				<td>${escape(__(row.current_state || ""))}${row.current_attendance ? `: ${escape(row.current_attendance)}` : ""}</td>
				<td>${escape(__(row.current_status || ""))}</td><td>${escape(row.active_shift || "")}</td>
				<td>${escape(row.checkin_count ?? "")}</td><td>${escape(row.in_time || "")}</td><td>${escape(row.out_time || "")}</td>
				<td>${escape(__(row.proposed_status || ""))}</td>
				<td>${escape(__(row.outcome || ""))}</td><td>${escape((row.native_warnings || []).map((item) => `${item.reason} — ${item.action}`).join("; "))}</td>
				<td>${escape(row.message || "")}</td></tr>`).join("");
			dialog.fields_dict.preview.$wrapper.html(`<div class="small text-muted">${__("Punches are evidence only. No Attendance changes until an approver submits the native request.")}</div>
				<div class="table-responsive"><table class="table table-bordered"><thead><tr>
				<th>${__("Employee")}</th><th>${__("Current record")}</th><th>${__("Current status")}</th><th>${__("Active Shift")}</th>
				<th>${__("Punches")}</th><th>${__("First IN")}</th><th>${__("Last OUT")}</th>
				<th>${__("Proposed")}</th><th>${__("Result")}</th><th>${__("Native warning")}</th><th>${__("Review note")}</th>
				</tr></thead><tbody>${body}</tbody></table></div>`);
		};
		const prepareArgs = (reviewed) => ({ method: "tradex_hr.tradexcel_hr.attendance_corrections.prepare_attendance_corrections", args: reviewed });
		const preview = () => {
			if (!dialog.get_values()) return;
			const request = ++previewGeneration;
			const reviewed = args();
			previewReady = false;
			frappe.call({ method: "tradex_hr.tradexcel_hr.attendance_corrections.preview_attendance_corrections", args: reviewed })
				.then((response) => {
					if (request !== previewGeneration || JSON.stringify(reviewed) !== JSON.stringify(args())) return;
					render(response.message.rows || []);
					previewReady = true;
					dialog.set_primary_action(__("Create draft requests"), () => {
						if (!previewReady || request !== previewGeneration || JSON.stringify(reviewed) !== JSON.stringify(args())) return;
						previewReady = false;
						frappe.call(prepareArgs(reviewed)).then((result) => {
							const message = result.message || {};
							const created = (message.created || []).length;
							const blocked = (message.results || []).length;
							const names = (message.created || []).map((row) => row.attendance_request).filter(Boolean);
							frappe.msgprint({
								title: __("Draft correction results"),
								message: __("Draft requests created: {0}. Skipped or blocked: {1}.", [created, blocked]) +
									(message.results || []).map((row) => `<p>${frappe.utils.escape_html(row.employee || "")}: ${frappe.utils.escape_html(row.message || row.outcome || "")}</p>`).join(""),
								primary_action: names.length ? {
									label: __("Review draft requests"),
									action: () => {
										frappe.route_options = {name: ["in", names]};
										frappe.set_route("List", "Attendance Request", "List");
									},
								} : undefined,
							});
							dialog.hide();
							report.refresh();
						}).catch(() => invalidatePreview());
					});
				});
		};
		const invalidatePreview = () => {
			previewGeneration++;
			previewReady = false;
			dialog.set_primary_action(__("Preview"), preview);
		};
		dialog.fields_dict.action.$input.on("change", invalidatePreview);
		dialog.fields_dict.explanation.$input.on("input", invalidatePreview);
		dialog.set_primary_action(__("Preview"), () => {
			preview();
		});
		dialog.show();
	});
	},
	filters: [
		{fieldname: "attendance_date", label: __("Attendance Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1},
		{fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: (frappe.defaults && frappe.defaults.get_user_default && frappe.defaults.get_user_default("Company")) || "", reqd: 1},
		{fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Branch", get_query: () => ({ filters: { company: frappe.query_report.get_filter_value("company") } })},
		{fieldname: "department", label: __("Department"), fieldtype: "Link", options: "Department", get_query: () => ({ filters: { company: frappe.query_report.get_filter_value("company") } })}
	]
};
