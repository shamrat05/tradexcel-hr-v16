function refresh_child_scope(frm) {
	if (!['Component', 'Attendance'].includes(frm.doc.exception_type)
			|| (!frm.doc.branch && !frm.doc.department)) {
		frm.toggle_display('include_child_scope', false);
		return;
	}
	frappe.call({
		method: 'tradex_hr.link_filters.scope_has_children',
		args: {branch: frm.doc.branch, department: frm.doc.department},
	}).then((response) => {
		const info = response.message || {};
		frm.toggle_display('include_child_scope', !!(info.branch_has_children || info.department_has_children));
	});
}

frappe.ui.form.on('Tradexcel Policy Exception', {
	onload(frm) {
		if (frm.is_new() && !frm.doc.effective_from) {
			frm.set_value('effective_from', frappe.datetime.add_days(frappe.datetime.get_today(), 1));
		}
	},
	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__('Preview Impact'), async () => {
				if (frm.is_dirty() || frm.is_new()) await frm.save();
				const response = await frappe.call({
					method: 'tradex_hr.tradexcel_hr.doctype.tradexcel_policy_exception.tradexcel_policy_exception.preview_impact',
					args: {name: frm.doc.name},
					freeze: true,
					freeze_message: __('Checking affected employees and dates...'),
				});
				await frm.reload_doc();
				const result = response.message;
				const warning = result.submitted_slips.length
					? __('Submitted salary slips are affected. Reconciliation is required before activation.')
					: result.draft_slips.length
						? __('Existing draft salary slips must be repriced and reviewed before activation.')
						: __('No existing salary slips need reconciliation.');
				frappe.msgprint({
					title: __('Policy impact preview'),
					message: [frappe.utils.escape_html(result.summary), frappe.utils.escape_html(warning)].join('<br>'),
					indicator: result.submitted_slips.length || result.draft_slips.length ? 'orange' : 'blue',
				});
			});
		}
		frm.set_query('branch', () => frm.doc.company ? {filters: {company: frm.doc.company}} : {});
		frm.set_query('department', () => {
			if (!frm.doc.branch) {
				return frm.doc.company ? {filters: {company: frm.doc.company}} : {};
			}
			return {
				query: 'tradex_hr.link_filters.departments_used_by_branch',
				filters: {company: frm.doc.company, branch: frm.doc.branch},
			};
		});
		frm.set_query('designation', () => {
			const filters = {};
			if (frm.doc.company) filters.company = frm.doc.company;
			if (frm.doc.branch) filters.branch = frm.doc.branch;
			if (frm.doc.department) filters.department = frm.doc.department;
			if (!frm.doc.branch && !frm.doc.department) {
				return frm.doc.company ? {filters: {company: frm.doc.company}} : {};
			}
			return {
				query: 'tradex_hr.link_filters.designations_used_by_scope',
				filters,
			};
		});
		frm.set_query('employee', () => {
			const filters = {status: 'Active'};
			if (frm.doc.company) filters.company = frm.doc.company;
			if (frm.doc.branch) filters.branch = frm.doc.branch;
			if (frm.doc.department) filters.department = frm.doc.department;
			if (frm.doc.designation) filters.designation = frm.doc.designation;
			if (frm.doc.exception_type === 'Payroll') {
				if (frm.doc.employee_category === 'Worker') filters.employment_type = 'Worker';
				else if (frm.doc.employee_category === 'Staff') filters.employment_type = ['!=', 'Worker'];
			}
			return {filters};
		});
		refresh_child_scope(frm);
	},
	company(frm) {
		frm.set_value('branch', '');
		frm.set_value('department', '');
		frm.set_value('designation', '');
		frm.set_value('employee', '');
		refresh_child_scope(frm);
	},
	branch(frm) {
		frm.set_value('department', '');
		frm.set_value('designation', '');
		frm.set_value('employee', '');
		refresh_child_scope(frm);
	},
	department(frm) {
		frm.set_value('designation', '');
		frm.set_value('employee', '');
		refresh_child_scope(frm);
	},
	designation(frm) {
		frm.set_value('employee', '');
	},
	employee_category(frm) {
		frm.set_value('employee', '');
	},
});
