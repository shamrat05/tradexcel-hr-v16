frappe.ui.form.on('Tradexcel Payroll Policy', {
	refresh(frm) {
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
		frm.set_query('salary_structure', () => frm.doc.company ? {filters: {company: frm.doc.company}} : {});
	},
	company(frm) {
		frm.set_value('branch', '');
		frm.set_value('department', '');
	},
	branch(frm) {
		frm.set_value('department', '');
	},
});
