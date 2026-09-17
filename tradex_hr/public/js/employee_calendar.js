frappe.ui.form.on('Employee', {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__('Calendar'), () => show_employee_calendar(frm));
	}
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
	const parsed = new Date(month + '-01T00:00:00');
	parsed.setMonth(parsed.getMonth() + delta);
	return parsed.toISOString().slice(0, 7);
}

function show_employee_calendar(frm) {
	frm.doc.__calendar_month = frappe.datetime.get_today().slice(0, 7);
	const dialog = new frappe.ui.Dialog({ title: __('{0} Calendar', [frm.doc.employee_name || frm.doc.name]), size: 'extra-large' });

	const render = () => {
		const month = frm.doc.__calendar_month;
		frappe.call({
			method: 'tradex_hr.tradexcel_hr.employee_calendar.get_employee_calendar',
			args: { employee: frm.doc.name, month },
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
				html += `<td style="background:${color};${outline}height:86px;vertical-align:top;color:#1f2933;padding:6px">
					<div style="font-size:15px;font-weight:700">${entry.day}</div>
					<div style="font-size:12px;font-weight:600">${__(entry.category)}</div>
					${detailLine ? `<div style="font-size:11px;line-height:1.4">${frappe.utils.escape_html(detailLine)}</div>` : ''}
					${entry.checkins ? `<div style="font-size:11px;color:#4b5563">${entry.checkins} ${__('punch(es)')}</div>` : ''}</td>`;
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
				frm.doc.__calendar_month = nav === 'today'
					? frappe.datetime.get_today().slice(0, 7)
					: shift_calendar_month(month, nav === 'next' ? 1 : -1);
				render();
			});
		});
	};

	dialog.show();
	render();
}
