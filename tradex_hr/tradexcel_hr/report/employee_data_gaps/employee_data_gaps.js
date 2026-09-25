frappe.query_reports["Employee Data Gaps"] = {
	filters: [
		{fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: (frappe.defaults && frappe.defaults.get_user_default && frappe.defaults.get_user_default("Company")) || "", reqd: 1},
		{fieldname: "status", label: __("Employee Status"), fieldtype: "Select", options: "Active\nInactive\nLeft\nAll", default: "Active"},
		{fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Branch", default: "", get_query: function() { var c = frappe.query_report.get_filter_value('company'); return c ? {filters: {company: c}} : {}; }},
		{fieldname: "department", label: __("Department"), fieldtype: "Link", options: "Department", default: "", get_query: function() { var company = frappe.query_report.get_filter_value('company'); var branch = frappe.query_report.get_filter_value('branch'); if (!branch) { return company ? {filters: {company: company}} : {}; } return {query: 'tradex_hr.link_filters.departments_used_by_branch', filters: {company: company, branch: branch}}; }},
		{fieldname: "employment_type", label: __("Employment Type"), fieldtype: "Select", options: "All\nWorker\nNon Worker", default: "All"},
		{fieldname: "gap_type", label: __("Gap"), fieldtype: "Select", options: "All\nMissing Department\nMissing Employee Number\nNo Active Salary Assignment\nNo Shift Assignment\nMultiple Active Salary Assignments\nLatest Structure Is a Wage Structure\nWorker Without Wage Structure\nFuture Joining Date With Punches\nMissing Designation\nMissing Date of Birth\nMissing Holiday List", default: "All"},
		{fieldname: "priority", label: __("Priority"), fieldtype: "Select", options: "All\nHigh\nMedium\nLow", default: "All"}
	],
	onload: function(report) {
		// Gap -> list filter that isolates employees with that gap (fallback: flagged employee IDs).
		const GAP_FIX_FILTERS = {
			"Missing Department": {department: ["is", "not set"]},
			"Missing Employee Number": {employee_number: ["is", "not set"]},
			"Missing Designation": {designation: ["is", "not set"]},
			"Missing Date of Birth": {date_of_birth: ["is", "not set"]},
			"Missing Holiday List": {holiday_list: ["is", "not set"]}
		};

		// Gap -> in-place resolver fields. Any gap added here becomes resolvable from this dialog.
		const GAP_RESOLVERS = {
			"Missing Department": [
				{fieldname: "department", label: __("Department"), fieldtype: "Link", options: "Department", reqd: 1}
			],
			"Missing Designation": [
				{fieldname: "designation", label: __("Designation"), fieldtype: "Link", options: "Designation", reqd: 1}
			],
			"Missing Holiday List": [
				{fieldname: "holiday_list", label: __("Holiday List"), fieldtype: "Link", options: "Holiday List", reqd: 1}
			]
		};

		function open_preview(gap, employees, values) {
			const action = __("Set the missing value to <b>{0}</b>", [values[Object.keys(values).find(function(k) { return values[k]; })] || ""]);
			const rows_html = employees.map(function(emp) {
				return `<tr><td style="padding:4px 8px">${frappe.utils.escape_html(emp.employee_name || emp.employee)}</td>
					<td style="padding:4px 8px" class="text-muted">${emp.employee}</td>
					<td style="padding:4px 8px">${emp.department || "—"}</td></tr>`;
			}).join("");
			const html = `<div class="mb-2">${action} — <b>${employees.length}</b> ${__("employee(s)")}</div>
				<table class="table table-bordered" style="font-size:12px">
				<thead><tr><th style="padding:4px 8px">${__("Employee")}</th><th style="padding:4px 8px">${__("ID")}</th><th style="padding:4px 8px">${__("Department")}</th></tr></thead>
				<tbody>${rows_html}</tbody></table>`;

			const confirm = new frappe.ui.Dialog({
				title: __("Preview: {0}", [gap]),
				fields: [{fieldname: "preview", fieldtype: "HTML", options: html}],
				primary_action_label: __("Confirm & Apply to {0}", [employees.length]),
				primary_action: function() {
					frappe.call({
						method: "tradex_hr.tradexcel_hr.bulk_fix.resolve_gap",
						args: {gap: gap, employees: employees.map(function(e) { return e.employee; }), values: values},
						freeze: true,
						freeze_message: __("Applying to {0} employee(s)...", [employees.length]),
						callback: function(r) {
							if (!r.message) return;
							confirm.hide();
							const msg = __("{0} updated, {1} skipped", [r.message.updated, r.message.skipped])
								+ (r.message.exceptions ? __(", {0} exception(s) applied", [r.message.exceptions]) : "")
								+ (r.message.errors && r.message.errors.length ? __(", {0} row(s) failed — see Error Log", [r.message.errors.length]) : "");
							frappe.show_alert({message: msg, indicator: r.message.errors && r.message.errors.length ? "orange" : (r.message.updated ? "green" : "orange")});
							report.refresh();
						}
					});
				}
			});
			confirm.show();
		}

		report.page.add_inner_button(__("Bulk Fix Flagged Employees"), function() {
			const rows = report.data || [];
			if (!rows.length) {
				frappe.msgprint(__("No flagged employees in the current view — adjust the filters first."));
				return;
			}
			const gap = report.get_filter_value("gap_type");

			if (gap && gap !== "All" && GAP_RESOLVERS[gap]) {
				const checklist = rows.map(function(row, index) {
					return `<label class="d-flex align-items-center mb-1" style="gap:6px">
						<input type="checkbox" class="bulk-fix-emp" data-employee="${row.employee}" checked>
						<b>${frappe.utils.escape_html(row.employee_name || row.employee)}</b>
						<span class="text-muted">${row.employee}</span>
						<span class="text-muted">${row.department || ""}</span></label>`;
				}).join("");
				const dialog = new frappe.ui.Dialog({
					title: __("Bulk Fix: {0}", [gap]),
					fields: GAP_RESOLVERS[gap].concat([
						{fieldname: "selection", fieldtype: "HTML",
						 options: `<div class="mb-1"><b>${__("Select employees to fix")}</b>
							<button class="btn btn-xs btn-default ml-2" data-toggle-all="1">${__("Toggle all")}</button></div>
							<div style="max-height:200px;overflow:auto">${checklist}</div>`}
					]),
					primary_action_label: __("Preview Changes"),
					primary_action: function(values) {
						const selected = dialog.$wrapper.find(".bulk-fix-emp:checked").map(function() {
							return $(this).attr("data-employee");
						}).get();
						if (!selected.length) {
							frappe.msgprint(__("Select at least one employee."));
							return;
						}
						const chosen = rows.filter(function(row) { return selected.includes(row.employee); });
						dialog.hide();
						open_preview(gap, chosen, values);
					}
				});
				dialog.show();
				dialog.$wrapper.on("click", "[data-toggle-all]", function() {
					const boxes = dialog.$wrapper.find(".bulk-fix-emp");
					const turn_on = boxes.filter(":checked").length !== boxes.length;
					boxes.prop("checked", turn_on);
				});
				return;
			}

			if (gap === "No Shift Assignment") {
				frappe.msgprint(__("Use Open Bulk Shift Assignment. The native tool will refresh and validate the eligible Employee list."));
				return;
			}
			const employees = rows.map(function(row) { return row.employee; }).filter(Boolean);
			const options = {
				company: report.get_filter_value("company"),
				status: report.get_filter_value("status"),
				name: ["in", employees]
			};
			if (gap && gap !== "All" && GAP_FIX_FILTERS[gap]) {
				Object.assign(options, GAP_FIX_FILTERS[gap]);
			}
			frappe.route_options = options;
			frappe.set_route("List", "Employee");
		});
		if (["Tradexcel HR Manager", "Tradexcel HR/Attendance Officer", "HR User", "HR Manager"].some((role) => frappe.user.has_role(role))) {
			report.page.add_inner_button(__("Open Bulk Shift Assignment"), function() {
				const route_options = {start_date: frappe.datetime.get_today()};
				for (const fieldname of ["company", "branch", "department"]) {
					const value = report.get_filter_value(fieldname);
					if (value) route_options[fieldname] = value;
				}
				// Do not pass report row Employee IDs: the native tool rebuilds its
				// permission-aware preview and revalidates selected rows at apply.
				frappe.route_options = route_options;
				frappe.set_route("Form", "Shift Assignment Tool");
			});
		}
	}
};
