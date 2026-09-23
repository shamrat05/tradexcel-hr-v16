// doctype -> how to get the employee to show the calendar for
const TRADEX_CALENDAR_FORMS = {
	'Employee': (frm) => ({ employee: frm.doc.name, name: frm.doc.employee_name }),
	'Attendance': (frm) => ({ employee: frm.doc.employee, name: frm.doc.employee_name }),
};

Object.keys(TRADEX_CALENDAR_FORMS).forEach((doctype) => {
	frappe.ui.form.on(doctype, {
		refresh(frm) {
			if (frm.is_new()) return;
			const target = TRADEX_CALENDAR_FORMS[doctype](frm);
			if (!target.employee) return;
			frm.add_custom_button(__('Calendar'), () => show_employee_calendar(target.employee, target.name));
		},
	});
});

const EMPLOYEE_CALENDAR_COLORS = {
	'Present': '#c6efce',
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
	const dialog = new frappe.ui.Dialog({ title: __('{0} Calendar', [employee_name || employee]), size: 'extra-large' });

	const render = () => {
		frappe.call({
			method: 'tradex_hr.tradexcel_hr.employee_calendar.get_employee_calendar',
			args: { employee: employee, month },
		}).then((response) => {
			const data = response.message;
			if (!data) return;
			const month_label = frappe.datetime.str_to_user(month + '-01').slice(3);
			let html = `<div class="d-flex justify-content-between align-items-center mb-2">
				<button class="btn btn-xs btn-default" data-nav="prev">&#8249; ${__('Prev')}</button>
				<b>${month_label}</b>
				<span>
					<button class="btn btn-xs btn-default" data-nav="today">${__('Today')}</button>
					<button class="btn btn-xs btn-default" data-nav="next">${__('Next')} &#8250;</button>
				</span></div>`;
			const first_dow = new Date(month + '-01T00:00:00').getDay();
			html += '<table class="table table-bordered" style="table-layout:fixed;text-align:left;font-size:12px">';
			html += '<thead><tr>' + ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((day) => `<th style="font-size:12px;background:#f4f6f9;color:#34495e;text-align:center;padding:6px">${__(day)}</th>`).join('') + '</tr></thead><tbody><tr>';
			for (let i = 0; i < first_dow; i++) html += '<td></td>';
			data.days.forEach((entry, index) => {
				const color = entry.color || '#ffffff';
				const outline = entry.date === data.today ? 'outline:2px solid #2490ef;' : '';
				const detailLine = [entry.detail, entry.shift].filter(Boolean).join(' · ');
				html += `<td style="background:${color};${outline}height:92px;vertical-align:top;color:#1f2933;padding:6px">
					<div style="font-size:15px;font-weight:700">${entry.day}</div>
					<div style="font-size:12px;font-weight:600">${__(entry.label || entry.category)}</div>
					${entry.in_time ? `<div style="font-size:12px;color:#14532d"><b>${entry.in_time}</b> – ${entry.out_time || '…'}</div>` : ''}
					${detailLine && !entry.in_time ? `<div style="font-size:11px;line-height:1.4">${frappe.utils.escape_html(detailLine)}</div>` : ''}
					${entry.checkins ? `<div style="font-size:10px;color:#4b5563">${entry.checkins} ${__('punch(es)')}</div>` : ''}</td>`;
				if ((first_dow + index + 1) % 7 === 0) html += '</tr><tr>';
			});
			html += '</tr></tbody></table>';
			html += `<div class="text-muted">${__('Holiday list')}: ${data.holiday_list || '-'} &middot; ${__('Weekly off')}: ${data.weekly_off || '-'}</div>`;
			html += `<div class="mt-2">` + Object.entries(data.legend || {})
				.map(([name, color]) => `<span class="badge mr-2" style="background:${color};color:#333;border:1px solid #ccc">${__(name)}</span>`)
				.join('') + `</div>`;
			dialog.$body.html(html);
			dialog.$body.find('[data-nav]').on('click', (event) => {
				const nav = event.currentTarget.dataset.nav;
				month = nav === 'today'
					? frappe.datetime.get_today().slice(0, 7)
					: shift_calendar_month(month, nav === 'next' ? 1 : -1);
				render();
			});
		});
	};

	dialog.show();
	render();
}


frappe.ui.form.on("Employee", {
	refresh(frm) {
		if (frm.is_new() || !frm.doc.name) return;
		frm.add_custom_button(__("Check Exit Readiness"), () => {
			frappe.call({
				method: "tradex_hr.tradexcel_hr.employee_separation.inspect_employee_exit_readiness",
				args: { employee_name: frm.doc.name },
			}).then(({ message }) => show_exit_readiness(message));
		}, __("Separation"));
		if (["Active", "Left"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Finalize Exit Access"), () => {
				frappe.confirm(__("This disables the employee's dedicated application and biometric access. Financial settlement remains separate."), () => {
					frappe.call({
						method: "tradex_hr.tradexcel_hr.employee_separation.finalize_employee_exit_access",
						args: { employee_name: frm.doc.name },
					}).then(() => frm.reload_doc());
				});
			}, __("Separation"));
		}
		frm.add_custom_button(__("Check Full & Final Readiness"), () => {
			frappe.call({
				method: "tradex_hr.tradexcel_hr.employee_separation.inspect_full_and_final_readiness",
				args: { employee_name: frm.doc.name },
			}).then(({ message }) => show_exit_readiness(message));
		}, __("Separation"));
	},
});

function show_exit_readiness(result) {
	if (!result) return;
	const messages = {
		LEGAL_CLASSIFICATION_REVIEW_REQUIRED: __("Legal or statutory classification needs review."),
		GRATUITY_RULE_DECISION_REQUIRED: __("No approved gratuity rule is configured."),
		LEAVE_ENCASHMENT_CONFIGURATION_REQUIRED: __("Leave encashment configuration needs review."),
		FINAL_PAYROLL_PENDING: __("Final regular salary is not finalized through payroll."),
		PAYROLL_ADJUSTMENT_PENDING: __("Approved payroll adjustments remain unconsumed."),
		NATIVE_SETTLEMENT_ITEMS_PENDING: __("Native Full & Final payables, receivables, or asset actions need review."),
	};
	const lines = [...(result.blockers || []), ...(result.findings || [])]
		.map((item) => `<li>${frappe.utils.escape_html(item.message || messages[item.code] || item.code)}${item.count ? ` (${item.count})` : ""}</li>`)
		.join("");
	frappe.msgprint({
		title: __(result.status || "Readiness"),
		message: lines ? `<ul>${lines}</ul>` : __("No outstanding operational findings."),
	});
}
