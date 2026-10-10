frappe.query_reports["Workforce Daily Attendance Board"] = {
	formatter(value, row, column, data, default_formatter) {
		if (["status", "attendance_state"].includes(column.fieldname)) value = __(value || "");
		return default_formatter(value, row, column, data);
	},
	get_datatable_options(options) {
		return { ...options, checkboxColumn: true };
	},
	onload(report) {
        workforce_suite.report_actions.begin(report);
		const roles = ["Workforce Suite Manager", "Workforce Suite/Attendance Officer"];
		if (!roles.some((role) => frappe.user.has_role(role))) return;

	report.workforce_actions.add(__("Prepare Attendance Corrections"), () => {
		const selected = report.get_checked_items().map((row) => row.employee).filter(Boolean);
		if (!selected.length) {
			frappe.msgprint(__("Select one or more Employees in the report first."));
			return;
		}
		const values = report.get_filter_values();
		const escape = frappe.utils.escape_html;
		const dialog = new frappe.ui.Dialog({
			title: __("Prepare Attendance Corrections"),
			fields: [
				{ fieldname: "steps", fieldtype: "HTML", options: `<div class="small">
					<p class="text-muted">${escape(values.company)} · ${escape(values.attendance_date)} · ${selected.length} ${__("selected Employee(s)")}</p>
					<ol>
						<li><b>${__("Evidence")}</b> — ${__("punches, device/mobile records and the active Shift are evidence only.")}</li>
						<li><b>${__("Current Attendance")}</b> — ${__("the native record that exists today.")}</li>
						<li><b>${__("Problem")}</b> — ${__("the preview Result states what is missing, conflicting, already resolved or blocked.")}</li>
						<li><b>${__("Proposed correction")}</b> — ${__("the action you choose for the reviewed date.")}</li>
						<li><b>${__("Now")}</b> — ${__("only draft Attendance Requests are created. Attendance does not change.")}</li>
						<li><b>${__("Later")}</b> — ${__("an independent Attendance Correction Approver must submit each request.")}</li>
					</ol></div>` },
				{ fieldname: "action", label: __("Correction"), fieldtype: "Select", reqd: 1,
					options: ["Present", "Half Day", "Work From Home"].join("\n") },
				{ fieldname: "explanation", label: __("Explanation"), fieldtype: "Small Text", reqd: 1,
					description: __("Explain the dates and why this request is needed. A draft is not approved Attendance.") },
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
		const renderNotice = (text, indicator) => {
			dialog.fields_dict.preview.$wrapper.html(
				`<div class="small ${indicator === "red" ? "text-danger" : "text-muted"}">${escape(text)}</div>`);
		};
		const render = (rows) => {
			const body = rows.map((row) => {
				const current = [escape(__(row.current_state || "")),
					row.current_attendance ? `: ${escape(row.current_attendance)}` : "",
					row.current_status ? ` (${escape(__(row.current_status))})` : ""].join("");
				const evidence = `<details><summary>${__("Show evidence")}</summary>
					<div>${__("Active Shift")}: ${escape(row.active_shift || "")}</div>
					<div>${__("Punches")}: ${escape(row.checkin_count ?? "")}</div>
					<div>${__("First IN")}: ${escape(row.in_time || "")}</div>
					<div>${__("Last OUT")}: ${escape(row.out_time || "")}</div>
					${row.existing_request ? `<div>${__("Existing request")}: ${escape(row.existing_request)}</div>` : ""}</details>`;
				const warnings = (row.native_warnings || []).map((item) => `${escape(item.reason || "")} — ${escape(item.action || "")}`).join("; ");
				return `<tr><td>${escape(row.employee_name || row.employee || "")}
					<div class="text-muted small">${escape(row.employee || "")}</div></td>
					<td>${current}</td><td>${evidence}</td>
					<td>${escape(__(row.proposed_status || ""))}</td>
					<td>${escape(__(row.outcome || ""))}${row.message ? `<div class="text-muted small">${escape(row.message)}</div>` : ""}</td>
					<td>${warnings}</td></tr>`;
			}).join("");
			dialog.fields_dict.preview.$wrapper.html(`<div class="small text-muted">${__("Punches are evidence only. No Attendance changes until an approver submits the native request.")}</div>
				<div class="table-responsive"><table class="table table-bordered"><thead><tr>
				<th>${__("Employee")}</th><th>${__("Current Attendance")}</th><th>${__("Evidence")}</th>
				<th>${__("Proposed")}</th><th>${__("Problem / Result")}</th><th>${__("Native warning")}</th>
				</tr></thead><tbody>${body}</tbody></table></div>`);
		};
		const prepareArgs = (reviewed) => ({ method: "workforce_suite.workforce_suite.attendance_corrections.prepare_attendance_corrections", args: reviewed });
		const showResults = (message) => {
			const created = message.created || [];
			const names = created.map((row) => row.attendance_request).filter(Boolean);
			const groups = new Map();
			for (const row of message.results || []) {
				const key = row.outcome || __("Needs review");
				if (!groups.has(key)) groups.set(key, []);
				groups.get(key).push(row);
			}
			let html = created.length
				? `<p><b>${__("Draft Attendance Requests created: {0}", [created.length])}</b></p>`
				: `<p><b>${__("No draft Attendance Requests were created.")}</b></p>`;
			if (names.length) html += `<p>${names.map(escape).join(", ")}</p>`;
			for (const [outcome, rows] of groups) {
				html += `<p class="small"><b>${escape(__(outcome))} (${rows.length})</b></p><ul>` +
					rows.map((row) => `<li>${escape(row.employee || "")} — ${escape(row.message || row.outcome || "")}</li>`).join("") +
					`</ul>`;
			}
			html += `<p class="small text-muted">${__("Draft requests are not approved Attendance. An independent Attendance Correction Approver must submit them. Running the same selection again cannot duplicate a request; it is reported as an existing request instead.")}</p>`;
			frappe.msgprint({
				title: __("Draft correction results"),
				message: html,
				primary_action: names.length ? {
					label: __("Review draft requests"),
					action: () => {
						frappe.route_options = {name: ["in", names]};
						frappe.set_route("List", "Attendance Request", "List");
					},
				} : undefined,
			});
		};
		const apply = (reviewed) => {
			previewReady = false;
			frappe.call(prepareArgs(reviewed)).then((result) => {
				showResults(result.message || {});
				dialog.hide();
				report.refresh();
			}).catch(() => {
				invalidatePreview();
				renderNotice(__("The result could not be confirmed. Run Preview again: already-created requests are reported as existing requests, so drafts are never duplicated."), "red");
			});
		};
		const preview = () => {
			if (!dialog.get_values()) return;
			const request = ++previewGeneration;
			const reviewed = args();
			previewReady = false;
			frappe.call({ method: "workforce_suite.workforce_suite.attendance_corrections.preview_attendance_corrections", args: reviewed })
				.then((response) => {
					if (request !== previewGeneration || JSON.stringify(reviewed) !== JSON.stringify(args())) return;
					render((response.message || {}).rows || []);
					previewReady = true;
					dialog.set_primary_action(__("Create draft requests"), () => {
						if (!previewReady || request !== previewGeneration || JSON.stringify(reviewed) !== JSON.stringify(args())) return;
						apply(reviewed);
					});
				})
				.catch(() => {
					if (request !== previewGeneration) return;
					invalidatePreview();
					renderNotice(__("Preview could not be loaded. Nothing was created. Check the message, then try Preview again."), "red");
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
