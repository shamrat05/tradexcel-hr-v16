/*
 * TXUX-260930-007 offline UI contract for payroll/finance recovery.
 *
 * Loads the candidate client scripts with explicit native mocks. No money is
 * calculated here; every asserted value comes from the mocked server payload.
 */
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..', '..');
const READINESS = path.join(ROOT, 'tradexcel_hr/report/tradexcel_payroll_readiness/tradexcel_payroll_readiness.js');
const OVERTIME = path.join(ROOT, 'public/js/overtime_bulk_list.js');
const TAX = path.join(ROOT, 'public/js/income_tax_slab.js');

const tick = () => new Promise((resolve) => setImmediate(resolve));
const __ = (text, args) => args === undefined || args === null
	? text
	: String(text).replace(/\{(\d+)\}/g, (match, index) => (args[index] !== undefined ? String(args[index]) : match));

function baseMock() {
	const state = { calls: [], prints: [], routes: [], confirms: [], prompts: [], values: {} };
	const frappe = {
		query_reports: {},
		listview_settings: {},
		user: { has_role: () => false },
		session: { user: 'payroll@example.test' },
		defaults: { get_user_default: () => '' },
		datetime: { get_today: () => '2026-09-30' },
		utils: { escape_html: (v) => (v == null ? '' : String(v)) },
		call: (options) => new Promise((resolve, reject) => state.calls.push({
			options,
			resolve: (value) => { if (options && options.callback) options.callback(value); resolve(value); },
			reject,
		})),
		msgprint: (options) => state.prints.push(options),
		prompt: (fields, callback, title, primary) => state.prompts.push({ fields, callback, title, primary }),
		confirm: (message, onConfirm) => state.confirms.push({ message, onConfirm }),
		set_route: (...args) => state.routes.push(args),
		route_options: null,
		ui: { Dialog: null, form: { on: (doctype, handlers) => { state.form = { doctype, handlers }; } } },
	};
	return { frappe, state };
}

function makeDialog(state) {
	frappeDialog.prototype.fields_dict = null;
	const fields = state.dialog_fields || {};
	const dialog = {
		fields: [],
		fields_dict: {},
		display: false,
		set_value: (name, value) => { state.values[name] = value; return Promise.resolve(); },
		get_value: (name) => state.values[name],
		get_values: () => ({ ...state.values }),
		set_primary_action: (label, fn) => { dialog.primary_label = label; dialog.primary = fn; },
		set_primary_action_label: (label) => { dialog.primary_label = label; },
		show: () => { dialog.display = true; },
		hide: () => {},
	};
	for (const name of ['company', 'from_date', 'to_date', 'effective_date', 'preview', 'action']) {
		dialog.fields_dict[name] = { $input: { on: () => {} }, $wrapper: { html: (html) => { state.rendered = html; } }, set_value: dialog.set_value };
	}
	state.dialogs = state.dialogs || [];
	state.dialogs.push(dialog);
	return dialog;
}

function frappeDialog() {}
frappeDialog.prototype.fields_dict = null;

function loadReadiness() {
	const { frappe, state } = baseMock();
	frappe.user.has_role = () => true;
	frappe.ui.Dialog = class {
		constructor(options = {}) {
			const dialog = makeDialog(state);
			dialog.primary = options.primary_action;
			dialog.primary_label = options.primary_action_label;
			return dialog;
		}
	};
	const sandbox = { frappe, __ };
	vm.runInNewContext(fs.readFileSync(READINESS, 'utf8'), sandbox);
	return { frappe, state, sandbox };
}

async function run() {
	// 1) Every blocker family keeps its canonical destination (no invented money).
	{
		const { frappe, state, sandbox } = loadReadiness();
		sandbox.financial_readiness_route('payroll_entry', 'Synthetic Co', 'EMP-1', '', '', '', 'PAY-1');
		assert.deepEqual(JSON.parse(JSON.stringify(state.routes[0])), ['Form', 'Payroll Entry', 'PAY-1']);
		sandbox.financial_readiness_route('salary_slip', 'Synthetic Co', 'EMP-1', 'SS-1', '', '', '');
		assert.deepEqual(JSON.parse(JSON.stringify(state.routes[1])), ['Form', 'Salary Slip', 'SS-1']);
		sandbox.financial_readiness_route('tax_slabs', 'Synthetic Co', 'EMP-1', '', '', '', '');
		assert.deepEqual(JSON.parse(JSON.stringify(state.routes[2])), ['List', 'Income Tax Slab', { company: 'Synthetic Co' }]);
		assert.equal(JSON.parse(JSON.stringify(frappe.route_options)).company, 'Synthetic Co');
	}

	// 2) The prepare action never sends a client "ready" flag and is server-authoritative.
	{
		const { frappe, state } = loadReadiness();
		let clicked = null;
		const button = { prop: (name, value) => { button[name] = value; return button; } };
		let inner_buttons = [];
		const report = {
			filter_values: { company: 'Synthetic Co', payroll_month: '2026-09-01' },
			get_filter_value(name) { return this.filter_values[name]; },
			page: {
				set_primary_action: (label, fn) => { clicked = fn; return button; },
				add_inner_button: (label, fn) => { inner_buttons.push(label); },
			},
			$report: { off: () => report.$report, on: () => report.$report },
		};
		frappe.query_reports['Tradexcel Payroll Readiness'].onload(report);
		frappe.query_report = {
			get_filter_value: (name) => report.filter_values[name],
			raw_data: { report_summary: [
				{ label: 'Ready', value: 0 },
				{ label: 'Need attention', value: 2 },
				{ label: 'Salary Slip creation', value: 'Not started' },
				{ label: 'Managed Payroll Entry', value: 'Not prepared' },
			] },
		};
		frappe.query_report.$prepare_payroll_button = button;
		frappe.query_reports['Tradexcel Payroll Readiness'].after_datatable_render();
		assert.equal(button.disabled, true, 'blocked employees must disable preparation');
		frappe.query_report.raw_data.report_summary = [
			{ label: 'Ready', value: 3 },
			{ label: 'Need attention', value: 0 },
			{ label: 'Salary Slip creation', value: 'Not started' },
			{ label: 'Managed Payroll Entry', value: 'Not prepared' },
		];
		frappe.query_reports['Tradexcel Payroll Readiness'].after_datatable_render();
		assert.equal(button.disabled, false);
		clicked();
		const call = state.calls[state.calls.length - 1].options;
		assert.match(call.method, /prepare_payroll$/);
		assert.deepEqual(JSON.parse(JSON.stringify(Object.keys(call.args).sort())), ['company', 'payroll_month']);
		assert.equal('ready' in call.args, false);
	}

	// 3) Daily Wage migration dialog is preview-only with an explicit date.
	{
		const { frappe, state, sandbox } = loadReadiness();
		const report = { get_filter_value: (name) => ({ company: 'Synthetic Co', payroll_month: '2026-09-01' }[name]) };
		sandbox.show_daily_wage_migration_preview(report);
		const dialog = state.dialogs[state.dialogs.length - 1];
		state.values.effective_date = null;
		dialog.primary(dialog.get_values());
		const call = state.calls[state.calls.length - 1].options;
		assert.match(call.method, /get_daily_wage_migration_preview$/);
		assert.equal(call.args.effective_date, null, 'no effective date may be invented');
		state.calls[state.calls.length - 1].resolve({ message: {
			status: 'DECISION_REQUIRED', effective_date: null, employee_count: 0, conflict_count: 0,
			proposed_structure: { name: 'New effective-dated Daily Wage structure', components: [], guidance: 'Native guidance' },
			rows: [],
		} });
		await tick();
		await tick();
		if (!state.rendered) console.error('DEBUG migration state:', JSON.stringify(Object.keys(state)), state.calls.length);
		assert.ok(state.rendered && state.rendered.includes('creates nothing'));
		assert.ok(state.rendered.includes('native Bulk Salary Structure Assignment'));
	}

	// 4) Overtime results group exact backend statuses and reaffirm draft-only.
	{
		const { frappe, state } = baseMock();
		frappe.user.has_role = () => true;
		frappe.ui.Dialog = class {
			constructor(options = {}) {
				const dialog = makeDialog(state);
				dialog.primary = options.primary_action;
				dialog.primary_label = options.primary_action_label;
				return dialog;
			}
		};
		vm.runInNewContext(fs.readFileSync(OVERTIME, 'utf8'), { frappe, __ });
		let button = null;
		const listview = {
			page: { add_inner_button: (_label, fn) => { button = fn; } },
			refresh: () => { state.refreshed = true; },
		};
		frappe.listview_settings['Overtime Slip'].onload(listview);
		button();
		const dialog = state.dialogs[state.dialogs.length - 1];
		state.values = { company: 'Synthetic Co', from_date: '2026-09-01', to_date: '2026-09-30' };
		dialog.primary(dialog.get_values());
		state.calls[state.calls.length - 1].resolve({ message: {
			company: 'Synthetic Co', from_date: '2026-09-01', to_date: '2026-09-30',
			rows: [
				{ employee: 'EMP-1', employee_name: 'One', eligible: true, attendance_count: 3 },
				{ employee: 'EMP-2', employee_name: 'Two', eligible: false, reason: 'Salary authority needs review' },
			],
		} });
		await tick();
		dialog.fields_dict.preview.$wrapper.find = () => ({ map: () => ({ get: () => ['EMP-1', 'EMP-2'] }) });
		dialog.primary(dialog.get_values());
		state.confirms[0].onConfirm();
		state.calls[state.calls.length - 1].resolve({ message: { status: 'Completed', rows: [
			{ employee: 'EMP-1', status: 'Draft', overtime_slip: 'OT-1' },
			{ employee: 'EMP-2', status: 'Blocked', reason: 'Salary authority needs review' },
			{ employee: 'EMP-3', status: 'Failed', reason: 'Review submitted Attendance and Overtime Type, then retry this Employee.' },
		] } });
		await tick();
		const message = state.prints[state.prints.length - 1].message;
		for (const label of ['Draft created', 'Not eligible — salary authority needs review', 'Could not be prepared — review the Employee']) {
			assert.ok(message.includes(label), label);
		}
		assert.ok(message.includes('do not create pay'));
		assert.ok(!message.includes('Drafts created: 1. Needs review: 2.'));
	}

	// 5) Unreviewed tax configuration is labelled truthfully and approval stays role-gated.
	{
		const scenarios = [
			{ doc: { docstatus: 0 }, roles: true, intro: 'blue', button: false },
			{ doc: { docstatus: 1, custom_tradex_review_status: 'Pending' }, roles: true, intro: 'orange', button: true },
			{ doc: { docstatus: 1, custom_tradex_review_status: 'Pending' }, roles: false, intro: 'orange', button: false },
			{ doc: { docstatus: 1, custom_tradex_review_status: 'Approved' }, roles: true, intro: null, button: false },
		];
		for (const scenario of scenarios) {
			const { frappe, state } = baseMock();
			frappe.user.has_role = () => scenario.roles;
			vm.runInNewContext(fs.readFileSync(TAX, 'utf8'), { frappe, __ });
			let buttons = 0;
			const frm = {
				doc: { name: 'TAX-1', ...scenario.doc },
				set_intro: (text, color) => { state.intro = { text, color }; },
				add_custom_button: () => { buttons += 1; },
				reload_doc: () => {},
			};
			state.form.handlers.refresh(frm);
			assert.equal(buttons, scenario.button ? 1 : 0, JSON.stringify(scenario.doc));
			if (scenario.intro) {
				assert.equal(state.intro.color, scenario.intro);
			} else {
				assert.equal(state.intro, undefined);
			}
		}
	}

	console.log('Payroll/finance recovery UI contracts passed (routes, prepare authority, preview-only migration, overtime grouping, tax review gating)');
}

run().catch((error) => {
	console.error(error);
	process.exit(1);
});
