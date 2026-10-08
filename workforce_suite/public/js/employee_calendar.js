// doctype -> how to get the employee to show the calendar for
const WORKFORCE_CALENDAR_FORMS = {
	'Employee': (frm) => ({ employee: frm.doc.name, name: frm.doc.employee_name }),
	'Attendance': (frm) => ({ employee: frm.doc.employee, name: frm.doc.employee_name }),
};

Object.keys(WORKFORCE_CALENDAR_FORMS).forEach((doctype) => {
	frappe.ui.form.on(doctype, {
		refresh(frm) {
			if (frm.is_new()) return;
			const target = WORKFORCE_CALENDAR_FORMS[doctype](frm);
			if (!target.employee) return;
            if (doctype === "Employee") {
                frm.add_custom_button(__("Worker ID draft"), () =>
                    window.workforceStatutoryExport("form_6", {
                        company: frm.doc.company, branch: frm.doc.branch,
                        employee: frm.doc.name,
                    }), __("Statutory drafts"));
            }
			frm.add_custom_button(__('Calendar'), () => show_employee_calendar(target.employee, target.name));
		},
	});
});

const EMPLOYEE_CALENDAR_COLORS = {
	'Present': '#c6efce',
	'Present (Late)': '#fff2cc',
	'Present (Early exit)': '#fed9cc',
	'Half Day': '#ffe699',
	'Absent': '#ffc7ce',
	'On Leave': '#bdd7ee',
	'Leave': '#bdd7ee',
	'Holiday': '#d9d2e9',
	'Weekly Off': '#e8eaed',
	'Punched Only': '#ffe0b2',
	'Future': '#fbfbfb',
	'No Record': '#ffffff'
};

function shift_calendar_month(month, delta) {
	const parts = month.split('-');
	const total = Number(parts[0]) * 12 + (Number(parts[1]) - 1) + delta;
	const year = Math.floor(total / 12);
	const month_index = (total % 12) + 1;
	return `${year}-${String(month_index).padStart(2, '0')}`;
}

function show_employee_calendar(employee, employee_name) {
	let month = frappe.datetime.get_today().slice(0, 7);
	let current_request_id = 0;
	const dialog = new frappe.ui.Dialog({
		title: __('{0} Calendar', [frappe.utils.escape_html(employee_name || employee)]),
		size: 'extra-large'
	});

	const show_unavailable = (message) => {
		dialog.$body.html(`<div role="status" aria-live="polite" class="p-3">${frappe.utils.escape_html(message)}</div><button class="btn btn-default" data-retry>${__('Retry calendar')}</button>`);
		dialog.$body.find('[data-retry]').on('click', render);
	};
	const render = () => {
		const req_id = ++current_request_id;
		dialog.$body.find('[data-nav]').prop('disabled', true);
		frappe.call({
			method: 'workforce_suite.workforce_suite.employee_calendar.get_employee_calendar',
			args: { employee: employee, month },
		}).then((response) => {
			if (req_id !== current_request_id) return;
			const data = response.message;
			if (!data) {
				show_unavailable(__("No calendar data available. Try again."));
				return;
			}
			const month_label = frappe.datetime.str_to_user(month + '-01').slice(3);
			const safe_month_label = frappe.utils.escape_html(month_label);
			let html = `<div class="d-flex justify-content-between align-items-center mb-2">
				<button class="btn btn-xs btn-default" data-nav="prev">&#8249; ${__('Prev')}</button>
				<b>${safe_month_label}</b>
				<span>
					<button class="btn btn-xs btn-default" data-nav="today">${__('Today')}</button>
					<button class="btn btn-xs btn-default" data-nav="next">${__('Next')} &#8250;</button>
				</span></div>`;
			html += `<div class="small text-muted mb-2">${frappe.utils.escape_html(__('Operational calendar: Approved Attendance · Approved Leave · Scheduled Off / Holiday · Raw Check-in Evidence'))}</div>`;

			const first_dow = new Date(month + '-01T00:00:00').getDay();
			html += '<div class="workforce-calendar-scroll" style="overflow-x:auto;-webkit-overflow-scrolling:touch;width:100%;margin-bottom:12px;">';
			html += '<table class="table table-bordered mb-0" style="min-width:540px;table-layout:fixed;text-align:left;font-size:12px">';
			html += '<thead><tr>' + ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((day) => `<th style="font-size:12px;background:#f4f6f9;color:#34495e;text-align:center;padding:6px">${__(day)}</th>`).join('') + '</tr></thead><tbody><tr>';
			for (let i = 0; i < first_dow; i++) html += '<td></td>';
			data.days.forEach((entry, index) => {
				const color = entry.color || '#ffffff';
				const outline = entry.date === data.today ? 'outline:2px solid #2490ef;' : '';
				const safe_day = frappe.utils.escape_html(String(entry.day));
				const safe_detail = entry.detail ? frappe.utils.escape_html(entry.detail) : '';
				const safe_shift = entry.shift ? frappe.utils.escape_html(entry.shift) : '';
				const safe_in_time = entry.in_time ? frappe.utils.escape_html(entry.in_time) : '';
				const safe_out_time = entry.out_time ? frappe.utils.escape_html(entry.out_time) : '…';

				let status_markup = '';
				if (entry.category === 'Punched Only') {
					status_markup = `<span class="badge" style="background:#ffe0b2;color:#7c2d12;font-size:10px;font-weight:600">${frappe.utils.escape_html(__('Punched Only (Raw)'))}</span>`;
				} else if (entry.category === 'Holiday') {
					status_markup = `<span class="badge" style="background:#d9d2e9;color:#432874;font-size:10px;font-weight:600">${frappe.utils.escape_html(__('Holiday'))}</span>`;
				} else if (entry.category === 'Weekly Off') {
					status_markup = `<span class="badge" style="background:#e8eaed;color:#374151;font-size:10px;font-weight:600">${frappe.utils.escape_html(__('Weekly Off'))}</span>`;
				} else if (entry.category === 'No Record' && entry.date < data.today) {
					status_markup = `<span class="text-danger" style="font-size:11px;font-weight:600">${frappe.utils.escape_html(__('No submitted Attendance — review may be required'))}</span>`;
				} else {
					status_markup = `<div style="font-size:12px;font-weight:600">${frappe.utils.escape_html(__(entry.label || entry.category))}</div>`;
				}

				const details = [safe_detail, safe_shift].filter(Boolean).join(' &middot; ');

				html += `<td style="background:${color};${outline}height:92px;vertical-align:top;color:#1f2933;padding:6px">
					<div style="font-size:15px;font-weight:700">${safe_day}</div>
					${status_markup}
					${safe_in_time ? `<div style="font-size:12px;color:#14532d"><b>${safe_in_time}</b> &ndash; ${safe_out_time}</div>` : ''}
					${details ? `<div style="font-size:11px;line-height:1.3;color:#4b5563;margin-top:2px;">${details}</div>` : ''}
					${entry.checkins ? `<div style="font-size:10px;color:#6b7280;margin-top:2px;">${frappe.utils.escape_html(String(entry.checkins))} ${frappe.utils.escape_html(__('punch(es)'))}</div>` : ''}</td>`;
				if ((first_dow + index + 1) % 7 === 0) html += '</tr><tr>';
			});
			html += '</tr></tbody></table></div>';
			html += `<div class="text-muted small">${frappe.utils.escape_html(__('Holiday list'))}: ${frappe.utils.escape_html(data.holiday_list || '-')} &middot; ${frappe.utils.escape_html(__('Weekly off'))}: ${frappe.utils.escape_html(data.weekly_off || '-')}</div>`;
			html += `<div class="mt-2">` + Object.entries(data.legend || {})
				.map(([name, color]) => `<span class="badge mr-2 mb-1" style="background:${color};color:#333;border:1px solid #ccc">${frappe.utils.escape_html(__(name))}</span>`)
				.join('') + `</div>`;
			dialog.$body.html(html);
			dialog.$body.find('[data-nav]').on('click', (event) => {
				const nav = event.currentTarget.dataset.nav;
				month = nav === 'today'
					? frappe.datetime.get_today().slice(0, 7)
					: shift_calendar_month(month, nav === 'next' ? 1 : -1);
				render();
			});
		}).catch(() => {
			if (req_id !== current_request_id) return;
			show_unavailable(__("Unable to load employee calendar. Please check permissions or try again."));
		});
	};

	dialog.show();
	render();
}

frappe.ui.form.on("Employee", {
	refresh(frm) {
		if (frm.is_new() || !frm.doc.name) return;

		const has_hr_role = ["Administrator", "System Manager", "Workforce Suite Manager", "Workforce Suite/Attendance Officer", "HR Manager", "HR User"]
			.some((role) => frappe.user.has_role(role));
		const has_manager_role = ["Administrator", "System Manager", "Workforce Suite Manager", "Workforce Owner/Director"]
			.some((role) => frappe.user.has_role(role));
		const has_finance_role = ["Administrator", "System Manager", "Workforce Finance/Accounts Officer", "Workforce Payroll Manager", "Accounts Manager", "Accounts User"]
			.some((role) => frappe.user.has_role(role));

		if (has_hr_role) {
			frm.add_custom_button(__("Check Joiner Readiness"), () => {
				frappe.call({
					method: "workforce_suite.workforce_suite.joiner_readiness.inspect_joiner_readiness",
					args: { employee_name: frm.doc.name },
				}).then(({ message }) => show_joiner_readiness(message));
			}, __("Onboarding"));
		}

		if (has_hr_role || has_manager_role) {
			frm.add_custom_button(__("Check Exit Readiness"), () => {
				frappe.call({
					method: "workforce_suite.workforce_suite.employee_separation.inspect_employee_exit_readiness",
					args: { employee_name: frm.doc.name },
				}).then(({ message }) => show_exit_readiness(message));
			}, __("Separation"));
		}

		if ((frappe.session.user === "Administrator" || ["Workforce Suite Manager", "Workforce Owner/Director"].some(role => frappe.user.has_role(role))) && ["Active", "Left"].includes(frm.doc.status) && frm.doc.relieving_date) {
			frm.add_custom_button(__("Finalize Exit Access"), () => {
				frappe.confirm(
					__("This disables the employee's dedicated application and biometric access on or after the relieving date. Financial settlement and Full & Final remain completely separate."),
					() => {
						frappe.call({
							method: "workforce_suite.workforce_suite.employee_separation.finalize_employee_exit_access",
							args: { employee_name: frm.doc.name },
						}).then(() => frm.reload_doc());
					}
				);
			}, __("Separation"));
		}

		if (has_manager_role || has_finance_role) {
			frm.add_custom_button(__("Check Full & Final Readiness"), () => {
				frappe.call({
					method: "workforce_suite.workforce_suite.employee_separation.inspect_full_and_final_readiness",
					args: { employee_name: frm.doc.name },
				}).then(({ message }) => show_full_and_final_readiness(message));
			}, __("Separation"));
		}
	},
});

function show_joiner_readiness(result) {
	if (!result) return;

	const section_titles = {
		employment: __("Employment Details"),
		payroll: __("Salary & Payroll Assignment"),
		wage_floor: __("Wage Floor Compliance"),
		statutory_benefits: __("Statutory Benefits"),
		attendance: __("Attendance & Shift Setup"),
		payment: __("Salary Payment Setup"),
		access: __("System Access"),
	};

	const destination_links = {
		SALARY_ASSIGNMENT_REQUIRED: `<a class="btn btn-xs btn-default ml-2" href="/app/salary-structure-assignment/new-salary-structure-assignment-1?employee=${encodeURIComponent(result.employee)}">${__("Create Salary Assignment")}</a>`,
		SALARY_STRUCTURE_REVIEW_REQUIRED: `<a class="btn btn-xs btn-default ml-2" href="/app/salary-structure">${__("View Salary Structures")}</a>`,
		SHIFT_SETUP_REVIEW: `<a class="btn btn-xs btn-default ml-2" href="/app/shift-assignment-tool">${__("Open Shift Tool")}</a>`,
		HOLIDAY_LIST_REQUIRED: `<a class="btn btn-xs btn-default ml-2" href="/app/holiday-list">${__("Assign Holiday List")}</a>`,
		BIOMETRIC_SETUP_REVIEW: `<a class="btn btn-xs btn-default ml-2" href="/app/workforce-employee-biometric">${__("Biometric Setup")}</a>`,
		ACCESS_SHARED_USER_REVIEW: `<a class="btn btn-xs btn-default ml-2" href="/app/user">${__("Review Users")}</a>`,
		USER_ACCESS_REVIEW: `<a class="btn btn-xs btn-default ml-2" href="/app/user">${__("Review Users")}</a>`,
	};

	let sections_html = "";
	Object.entries(result.sections || {}).forEach(([key, section]) => {
		const title = section_titles[key] || __(key);
		const status_badge = section.status === "READY"
			? `<span class="badge badge-success ml-2" style="background:#c6efce;color:#14532d">${__("Ready")}</span>`
			: `<span class="badge badge-danger ml-2" style="background:#ffc7ce;color:#991b1b">${__("Needs Configuration")}</span>`;

		const findings_html = (section.findings || []).map((item) => {
			const action_link = destination_links[item.code] || "";
			const severity_label = item.severity === "review" ? __("Requires Authorized Review") : __("Missing Information");
			return `<li class="mb-1">
				<span>${frappe.utils.escape_html(item.message || item.code)}</span>
				<span class="text-muted small ml-1">(${severity_label})</span>
				${action_link}
			</li>`;
		}).join("");

		const detail = section.message ? `<div class="text-muted small mt-1">${frappe.utils.escape_html(section.message)}</div>` : "";
		sections_html += `<div class="card p-2 mb-2" style="border:1px solid #e2e8f0;border-radius:4px;">
			<div class="d-flex justify-content-between align-items-center">
				<b>${frappe.utils.escape_html(title)}</b>
				${status_badge}
			</div>
			${detail}
			${findings_html ? `<ul class="mt-2 mb-1 pl-3">${findings_html}</ul>` : ""}
		</div>`;
	});

	const overall_badge = result.status === "READY"
		? `<span class="indicator-pill green font-weight-bold">${__("Ready")}</span>`
		: `<span class="indicator-pill red font-weight-bold">${__("Needs Attention")}</span>`;

	const hire_source_note = result.hire_source === "Direct Hire"
		? __("Direct Hire (Recruitment and onboarding workflows not required)")
		: __("Recruitment Workflow (Linked applicant / onboarding required)");

	const content = `<div class="mb-3">
		<div class="d-flex justify-content-between align-items-center mb-2">
			<div><b>${__("Status")}:</b> ${overall_badge}</div>
			<div><b>${__("Hire Source")}:</b> ${frappe.utils.escape_html(hire_source_note)}</div>
		</div>
		<div class="text-muted small mb-2">${frappe.utils.escape_html(__("Independent pay approval is preserved. Wage and salary structures must be assigned via native records."))}</div>
		${sections_html}
	</div>`;

	frappe.msgprint({
		title: __("Joiner Readiness — {0}", [frappe.utils.escape_html(result.employee)]),
		message: content,
	});
}

function show_exit_readiness(result) {
	if (!result) return;

	const blockers = (result.blockers || []).map((item) => {
		const count_str = item.count ? ` (${frappe.utils.escape_html(String(item.count))})` : "";
		return `<li class="text-danger mb-1 font-weight-bold">${frappe.utils.escape_html(item.message || item.code)}${count_str}</li>`;
	}).join("");

	const findings = (result.findings || []).map((item) => {
		const count_str = item.count ? ` (${frappe.utils.escape_html(String(item.count))})` : "";
		return `<li class="text-muted mb-1">${frappe.utils.escape_html(item.message || item.code)}${count_str}</li>`;
	}).join("");

	const ready_banner = result.ready_for_access_finalization
		? `<div class="alert alert-success p-2 mb-2" style="font-size:12px;">${frappe.utils.escape_html(__("Operational exit checks passed. Ready for access finalization on or after the relieving date."))}</div>`
		: `<div class="alert alert-warning p-2 mb-2" style="font-size:12px;">${frappe.utils.escape_html(__("Operational blockers must be resolved before employee access can be finalized."))}</div>`;

	const content = `<div>
		<div class="alert alert-info p-2 mb-2" style="font-size:11px;">
			${frappe.utils.escape_html(__("Operational exit readiness validates operational closure (relieving date, submitted separation, attendance cutoff, shift closure). Legal statutory review, final regular payroll, and Full & Final financial settlement remain completely separate."))}
		</div>
		<div class="mb-2">
			<b>${__("Relieving Date")}:</b> ${frappe.utils.escape_html(result.relieving_date ? frappe.datetime.str_to_user(result.relieving_date) : __("Not Set"))}
			&middot; <b>${__("Separation Document")}:</b> ${frappe.utils.escape_html(result.separation || __("None Submitted"))}
		</div>
		${ready_banner}
		${blockers ? `<div class="mt-2"><b>${__("Operational Blockers")}:</b><ul class="pl-3 mt-1">${blockers}</ul></div>` : ""}
		${findings ? `<div class="mt-2"><b>${__("Operational Findings")}:</b><ul class="pl-3 mt-1">${findings}</ul></div>` : ""}
		${!blockers && !findings ? `<div class="text-success">${frappe.utils.escape_html(__("No outstanding operational exit blockers found."))}</div>` : ""}
	</div>`;

	frappe.msgprint({
		title: __("Operational Exit Readiness — {0}", [frappe.utils.escape_html(result.employee || "")]),
		message: content,
	});
}

function show_full_and_final_readiness(result) {
	if (!result) return;

	const render_findings = (items) => items.map(item => `<li>${frappe.utils.escape_html(item.message || item.code || '')}${item.count ? ` (${frappe.utils.escape_html(String(item.count))})` : ''}</li>`).join('');
	const findings = result.findings || [];
	const informational = findings.filter(item => item.severity === "info");
	const unresolved = findings.filter(item => item.severity !== "info");
	const findings_html = `${unresolved.length ? `<h5>${__('Needs attention')}</h5><ul>${render_findings(unresolved)}</ul>` : ''}${informational.length ? `<h5>${__('Information')}</h5><ul>${render_findings(informational)}</ul>` : ''}`;
	// An early response does not establish downstream payroll/settlement progress.
	if (!Object.prototype.hasOwnProperty.call(result, "native_outstanding_sources")) {
		frappe.msgprint({title: __("Full & Final Readiness"), message: `<div role="status">${frappe.utils.escape_html(result.status || __('Unavailable'))}</div>${findings_html}`});
		return;
	}
	const slip_info = (result.final_salary_slips && result.final_salary_slips.length)
		? `<span class="badge badge-success" style="background:#c6efce;color:#14532d">${frappe.utils.escape_html(result.final_salary_slips[0].name)} (${frappe.utils.escape_html(result.final_salary_slips[0].status)})</span>`
		: `<span class="badge badge-danger" style="background:#ffc7ce;color:#991b1b">${__("Pending Submission")}</span> <a class="btn btn-xs btn-default ml-1" href="/app/salary-slip?employee=${encodeURIComponent(result.employee)}">${__("View Salary Slips")}</a>`;

	const statutory = result.statutory_review || {};
	const statutory_status_badge = statutory.status === "READY_FOR_STATUTORY_REVIEW" || statutory.status === "APPROVED"
		? `<span class="badge badge-success" style="background:#c6efce;color:#14532d">${frappe.utils.escape_html(statutory.status || __("Ready"))}</span>`
		: `<span class="badge badge-warning" style="background:#ffe699;color:#856404">${frappe.utils.escape_html(statutory.status || __("Review Required"))}</span>`;

	const fnf_docs = (result.full_and_final_statements && result.full_and_final_statements.length)
		? `<span class="font-weight-bold">${frappe.utils.escape_html(result.full_and_final_statements[0].name)} (${frappe.utils.escape_html(result.full_and_final_statements[0].status)})</span>`
		: `<span class="text-muted">${__("Not Created")}</span> <a class="btn btn-xs btn-default ml-1" href="/app/full-and-final-statement/new-full-and-final-statement-1?employee=${encodeURIComponent(result.employee)}">${__("Create F&F")}</a>`;

	const native_sources = result.native_outstanding_sources || {};
	const payables_count = (native_sources.payables || []).length;
	const receivables_count = (native_sources.receivables || []).length;
	const assets_count = (native_sources.assets || []).length;

	const payment_badge = result.payment_status === "CLEARED"
		? `<span class="badge badge-success" style="background:#c6efce;color:#14532d">${frappe.utils.escape_html(result.payment_status)}</span>`
		: `<span class="badge badge-info" style="background:#d1ecf1;color:#0c5460">${frappe.utils.escape_html(result.payment_status || __("Not Prepared"))}</span>`;

	const content = `<div>
		${findings_html}
		<div class="alert alert-info p-2 mb-2" style="font-size:11px;">
			${frappe.utils.escape_html(__("Full & Final Readiness inspects settlement prerequisites across final regular payroll, statutory review, native payables/receivables, and payment status. No money or statutory entitlements are calculated on the client."))}
		</div>
		<div class="card p-2 mb-2" style="border:1px solid #e2e8f0;">
			<b>1. ${__("Final Regular Payroll")}</b>
			<div class="mt-1">${slip_info}</div>
		</div>
		<div class="card p-2 mb-2" style="border:1px solid #e2e8f0;">
			<div class="d-flex justify-content-between align-items-center">
				<b>2. ${__("Statutory / Legal Review")}</b>
				${statutory_status_badge}
			</div>
			<div class="small text-muted mt-1">
				${__("Rule Set")}: ${frappe.utils.escape_html(statutory.rule_set || __("None"))} &middot;
				${__("Classification")}: ${frappe.utils.escape_html(statutory.classification || __("None"))}
			</div>
		</div>
		<div class="card p-2 mb-2" style="border:1px solid #e2e8f0;">
			<b>3. ${__("Native Full & Final Statement")}</b>
			<div class="mt-1">${fnf_docs}</div>
			<div class="small text-muted mt-1">
				${__("Outstanding Items")}: ${payables_count} ${__("payables")}, ${receivables_count} ${__("receivables")}, ${assets_count} ${__("assets")}
			</div>
		</div>
		<div class="card p-2 mb-2" style="border:1px solid #e2e8f0;">
			<div class="d-flex justify-content-between align-items-center">
				<b>4. ${__("Payment & Settlement Status")}</b>
				${payment_badge}
			</div>
			<div class="small text-muted mt-1">
				${__("Pending Adjustments")}: ${frappe.utils.escape_html(String(result.pending_adjustments || 0))} &middot;
				${__("Journal Entries")}: ${frappe.utils.escape_html((result.payment_journal_entries || []).map(j => j.name).join(", ") || __("None"))}
			</div>
		</div>
	</div>`;

	frappe.msgprint({
		title: __("Full & Final Readiness — {0}", [frappe.utils.escape_html(result.employee || "")]),
		message: content,
	});
}
