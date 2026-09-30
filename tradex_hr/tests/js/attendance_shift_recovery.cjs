/*
 * TXUX-260930-006 offline UI contract for attendance/shift recovery.
 *
 * Loads the candidate client scripts in a VM with explicit native mocks and
 * exercises presentation + routing only. No server calls, no business logic.
 */
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..', '..');
const DAILY = path.join(ROOT, 'tradexcel_hr/report/tradexcel_daily_attendance_board/tradexcel_daily_attendance_board.js');
const COVERAGE = path.join(ROOT, 'tradexcel_hr/report/tradexcel_shift_coverage/tradexcel_shift_coverage.js');
const CHECKIN = path.join(ROOT, 'public/js/employee_checkin_review.js');
const PERIOD = path.join(ROOT, 'public/js/tradexcel_attendance_period.js');
const TOOL = path.join(ROOT, 'public/js/shift_assignment_tool.js');

const tick = () => new Promise((resolve) => setImmediate(resolve));

// Mirrors frappe.__ placeholder substitution for {0}-style arguments.
const __ = (text, args) => args === undefined || args === null
	? text
	: String(text).replace(/\{(\d+)\}/g, (match, index) => (args[index] !== undefined ? String(args[index]) : match));

function baseMock() {
	const state = { calls: [], prints: [], prompts: [], routes: [], confirms: [], intros: {}, values: {} };
	const frappe = {
		query_reports: {},
		user: { has_role: () => false },
		session: { user: 'tester@example.test' },
		model: { can_read: () => false },
		defaults: { get_user_default: () => '' },
		datetime: { get_today: () => '2026-09-30', str_to_user: (v) => String(v) },
		utils: { escape_html: (v) => (v == null ? '' : String(v)) },
		call: (options) => new Promise((resolve, reject) => state.calls.push({ options, resolve, reject })),
		msgprint: (options) => state.prints.push(options),
		prompt: (fields, callback, title, primary) => state.prompts.push({ fields, callback, title, primary }),
		confirm: (message, onConfirm) => state.confirms.push({ message, onConfirm }),
		set_route: (...args) => state.routes.push(args),
		ui: { form: { on: (doctype, handlers) => { state.form = { doctype, handlers }; } } },
		route_options: null,
	};
	return { frappe, state };
}

function lastCall(state) { return state.calls[state.calls.length - 1]; }

function loadDailyBoard() {
	const { frappe, state } = baseMock();
	frappe.user.has_role = () => true;
	const values = { action: 'Present', explanation: 'Synthetic reviewed correction' };
	const events = {};
	frappe.ui = {
		Dialog: class {
			constructor() {
				this.fields_dict = {};
				this.fields_dict.preview = { $wrapper: { html: (html) => { this.preview_html = html; } } };
				for (const key of ['action', 'explanation']) {
					this.fields_dict[key] = { $input: { on: (evt, fn) => { events[key] = fn; } } };
				}
				state.dialog = this;
			}
			get_value(k) { return values[k]; }
			get_values() { return values; }
			set_primary_action(label, fn) { this.label = label; this.primary = fn; }
			show() { this.shown = true; }
			hide() { this.hidden = true; }
		},
	};
	vm.runInNewContext(fs.readFileSync(DAILY, 'utf8'), { frappe, __ });
	let button = null;
	frappe.query_reports['Tradexcel Daily Attendance Board'].onload({
		page: { add_inner_button: (_label, fn) => { button = fn; } },
		get_checked_items: () => [{ employee: 'EMP-ONE' }, { employee: 'EMP-TWO' }, { employee: 'EMP-THREE' }],
		get_filter_values: () => ({ company: 'Synthetic Co', attendance_date: '2026-09-30', branch: 'B1', department: 'D1' }),
		refresh: () => { state.refreshed = (state.refreshed || 0) + 1; },
	});
	button();
	return { frappe, state, dialog: state.dialog, events, values };
}

async function run() {
	// 1) Mixed batch presentation keeps each backend outcome distinct.
	{
		const { state, dialog } = loadDailyBoard();
		dialog.primary(); // Preview
		lastCall(state).resolve({ message: { rows: [] } });
		await tick();
		assert.equal(dialog.label, 'Create draft requests');
		dialog.primary(); // Create drafts
		lastCall(state).resolve({
			message: {
				created: [{ employee: 'EMP-ONE', attendance_request: 'ATT-REQ-1', outcome: 'Draft request created' }],
				results: [
					{ employee: 'EMP-TWO', outcome: 'Skipped', message: 'Skipped — the requested attendance status is already in place' },
					{ employee: 'EMP-THREE', outcome: 'Blocked — existing request', message: 'An existing Attendance Request already covers this date.' },
					{ employee: 'EMP-FOUR', outcome: 'Blocked — outside permitted scope', message: 'The selected employee is outside your permitted scope.' },
					{ employee: 'EMP-FIVE', outcome: 'Blocked', message: 'This request could not be prepared.' },
				],
			},
		});
		await tick();
		assert.equal(state.prints.length, 1);
		const message = state.prints[0].message;
		for (const outcome of ['Skipped', 'Blocked — existing request', 'Blocked — outside permitted scope', 'Blocked']) {
			assert.ok(message.includes(outcome), `missing backend outcome label: ${outcome}`);
		}
		assert.ok(message.includes('Draft Attendance Requests created: 1'));
		assert.ok(message.includes('ATT-REQ-1'));
		assert.ok(!message.includes('Skipped or blocked'), 'non-created rows must not be merged into one ambiguous summary');
		assert.ok(message.includes('cannot duplicate a request'));
		assert.equal(state.prints[0].primary_action.label, 'Review draft requests');
		assert.ok(dialog.hidden);
		assert.equal(state.refreshed, 1);
	}

	// 2) Preview failure shows a truthful recoverable state; nothing is created.
	{
		const { state, dialog } = loadDailyBoard();
		dialog.primary();
		lastCall(state).reject(new Error('network down'));
		await tick();
		assert.equal(dialog.label, 'Preview');
		assert.ok(dialog.preview_html.includes('Preview could not be loaded'));
		assert.ok(dialog.preview_html.includes('Nothing was created'));
		assert.equal(state.calls.length, 1);
	}

	// 3) Shift coverage routes to the native tool/list without Employee IDs.
	{
		const { frappe, state } = baseMock();
		frappe.model.can_read = (doctype) => doctype === 'Shift Assignment Tool';
		vm.runInNewContext(fs.readFileSync(COVERAGE, 'utf8'), { frappe, __ });
		const def = frappe.query_reports['Tradexcel Shift Coverage'];
		assert.equal(def.get_datatable_options({}).checkboxColumn, true);
		let button = null;
		const rows = [
			{ employee: 'EMP-MISS', employee_name: 'Missing One', coverage: 'No shift assigned — review', assigned_shifts: '' },
			{ employee: 'EMP-OVER', employee_name: 'Overlap One', coverage: 'Multiple active assignments — review', assigned_shifts: 'Day, Night' },
			{ employee: 'EMP-OK', employee_name: 'Assigned One', coverage: 'Assigned', assigned_shifts: 'Day' },
			{ employee: 'EMP-DEF', employee_name: 'Default One', coverage: 'Default shift only', assigned_shifts: '' },
		];
		def.onload({
			page: { add_inner_button: (_label, fn) => { button = fn; } },
			get_checked_items: () => rows,
			get_filter_value: (name) => ({ company: 'Synthetic Co', as_of_date: '2026-09-30', branch: 'B1', department: 'D1' }[name]),
		});
		assert.ok(button, 'eligible role must receive the native next-step button');
		button();
		assert.equal(state.prints.length, 1);
		const print = state.prints[0];
		for (const label of ['No shift assigned', 'Multiple active assignments', 'Default shift only', 'Already assigned']) {
			assert.ok(print.message.includes(label), `missing coverage state: ${label}`);
		}
		assert.equal(print.primary_action.label, 'Open Shift Assignment Tool');
		assert.equal(print.secondary_action.label, 'Review Shift Assignments');
		print.primary_action.action();
		const options = frappe.route_options;
		assert.equal(options.action, 'Assign Shift');
		assert.equal(options.start_date, '2026-09-30');
		assert.equal(options.company, 'Synthetic Co');
		assert.equal(options.branch, 'B1');
		assert.equal(options.department, 'D1');
		assert.ok(!('employee' in options) && !('employee_names' in options), 'native tool must rebuild its own eligible preview');
		assert.deepEqual(state.routes[0], ['Form', 'Shift Assignment Tool']);
		print.secondary_action.action();
		const review_options = JSON.parse(JSON.stringify(frappe.route_options));
		assert.deepEqual(review_options.employee, ['in', ['EMP-OVER']]);
		assert.deepEqual(review_options.from_date, ['<=', '2026-09-30']);
		assert.deepEqual(review_options.to_date, ['>=', '2026-09-30']);
		assert.deepEqual(state.routes[1], ['List', 'Shift Assignment', 'List']);

		// A role without tool read gets no button.
		const denied = baseMock();
		vm.runInNewContext(fs.readFileSync(COVERAGE, 'utf8'), { frappe: denied.frappe, __ });
		let denied_button = null;
		denied.frappe.query_reports['Tradexcel Shift Coverage'].onload({
			page: { add_inner_button: (_l, fn) => { denied_button = fn; } },
			get_checked_items: () => [], get_filter_value: () => '',
		});
		assert.equal(denied_button, null);
	}

	// 4) Employee Checkin evidence review states and reviewer gating.
	{
		const scenarios = [
			{ doc: { custom_tradex_source: 'Mobile', custom_tradex_time_status: 'Flagged', custom_tradex_review_status: 'Pending' }, reviewer: true, intro: 'orange', buttons: 2 },
			{ doc: { custom_tradex_source: 'Mobile', custom_tradex_time_status: 'Flagged', custom_tradex_review_status: 'Pending' }, reviewer: false, intro: 'orange', buttons: 0 },
			{ doc: { custom_tradex_source: 'Mobile', custom_tradex_time_status: 'Trusted', custom_tradex_review_status: 'Approved' }, reviewer: true, intro: 'green', buttons: 0 },
			{ doc: { custom_tradex_source: 'Mobile', custom_tradex_time_status: 'Flagged', custom_tradex_review_status: 'Rejected' }, reviewer: true, intro: 'red', buttons: 0 },
			{ doc: { custom_tradex_source: 'Mobile', custom_tradex_time_status: 'Trusted', custom_tradex_review_status: 'Not Required' }, reviewer: true, intro: 'blue', buttons: 0 },
			{ doc: { custom_tradex_source: 'Terminal', custom_tradex_time_status: 'Trusted', custom_tradex_review_status: 'Not Required' }, reviewer: true, intro: null, buttons: 0 },
		];
		for (const scenario of scenarios) {
			const { frappe, state } = baseMock();
			frappe.user.has_role = () => scenario.reviewer;
			vm.runInNewContext(fs.readFileSync(CHECKIN, 'utf8'), { frappe, __ });
			const added = [];
			state.form.handlers.refresh({
				doc: { name: 'CHK-1', ...scenario.doc },
				is_new: () => false,
				has_perm: () => true,
				set_intro: (text, color) => { state.intro = { text, color }; },
				add_custom_button: (label, fn) => added.push({ label, fn }),
				reload_doc: () => { state.reloaded = true; },
				set_value: () => { state.value_set = true; },
			});
			assert.equal(added.length, scenario.buttons, JSON.stringify(scenario.doc));
			if (scenario.intro) {
				assert.equal(state.intro.color, scenario.intro);
			} else {
				assert.equal(state.intro, undefined);
			}
			assert.ok(!state.value_set, 'no client-side checkin state may be written');
			if (added.length === 2) {
				assert.deepEqual(added.map((b) => b.label), ['Approve Evidence', 'Reject Evidence']);
				added[0].fn();
				assert.equal(state.prompts.length, 1);
				assert.equal(state.prompts[0].fields[0].fieldname, 'review_note');
				state.prompts[0].callback({ review_note: 'Synthetic evidence review' });
				await tick();
				assert.match(lastCall(state).options.method, /approve_mobile_checkin$/);
				assert.deepEqual(JSON.parse(JSON.stringify(lastCall(state).options.args)), { checkin: 'CHK-1', review_note: 'Synthetic evidence review' });
				assert.equal(lastCall(state).options.type, 'POST');
			}
		}
	}

	// 5) Attendance Period state guidance; reopening requires native confirmation.
	{
		const scenarios = [
			{ status: 'Open', write: true, expected_buttons: ['Finalize Attendance'], intro: 'blue' },
			{ status: 'Reopened', write: true, expected_buttons: ['Finalize Attendance'], intro: 'orange' },
			{ status: 'Finalized', write: true, expected_buttons: ['Reopen Attendance'], intro: 'green' },
			{ status: 'Finalized', write: false, expected_buttons: [], intro: 'green' },
		];
		for (const scenario of scenarios) {
			const { frappe, state } = baseMock();
			vm.runInNewContext(fs.readFileSync(PERIOD, 'utf8'), { frappe, __ });
			const buttons = [];
			state.form.handlers.refresh({
				doc: { name: 'PER-1', status: scenario.status, revision: 2, finalized_by: 'lead@example.test', finalized_at: '2026-09-29 10:00:00' },
				is_new: () => false,
				has_perm: (p) => p === 'write' && scenario.write,
				set_intro: (text, color) => { state.intro = { text, color }; },
				add_custom_button: (label, fn) => buttons.push({ label, fn }),
				reload_doc: () => { state.reloaded = true; },
				set_value: () => { state.value_set = true; },
			});
			assert.deepEqual(buttons.map((b) => b.label), scenario.expected_buttons);
			assert.equal(state.intro.color, scenario.intro);
			assert.ok(!state.value_set, 'status must change only through server actions');
			if (buttons.length) {
				buttons[0].fn();
				if (scenario.status === 'Finalized') {
					assert.equal(state.confirms.length, 1, 'reopen must be confirmed before the server call');
					assert.equal(state.calls.length, 0);
					state.confirms[0].onConfirm();
				}
				await tick();
				assert.equal(state.calls.length, 1);
				assert.match(lastCall(state).options.method, scenario.status === 'Finalized' ? /reopen_attendance_period$/ : /finalize_attendance_period$/);
			}
		}
	}

	// 6) Shift Assignment Tool intro only narrows the Tradexcel-only operator.
	{
		const { frappe, state } = baseMock();
		frappe.user.has_role = (role) => role === 'Tradexcel HR Manager';
		vm.runInNewContext(fs.readFileSync(TOOL, 'utf8'), { frappe, __ });
		const props = [];
		const frm = {
			doc: { action: 'Process Shift Requests' },
			set_df_property: (field, prop, value) => props.push([field, prop, value]),
			set_value: (field, value) => { state.value_set = [field, value]; },
			set_intro: (text, color) => { state.intro = { text, color }; },
		};
		state.form.handlers.onload(frm);
		state.form.handlers.refresh(frm);
		assert.deepEqual(JSON.parse(JSON.stringify(props)), [['action', 'options', 'Assign Shift']]);
		assert.deepEqual(JSON.parse(JSON.stringify(state.value_set)), ['action', 'Assign Shift']);
		assert.equal(state.intro.color, 'blue');

		const native = baseMock();
		native.frappe.user.has_role = (role) => role === 'Tradexcel HR Manager' || role === 'HR User';
		vm.runInNewContext(fs.readFileSync(TOOL, 'utf8'), { frappe: native.frappe, __ });
		const native_props = [];
		native.state.form.handlers.onload({
			doc: { action: 'Assign Shift' },
			set_df_property: (...args) => native_props.push(args),
			set_value: () => { throw new Error('native HR User action must not be rewritten'); },
		});
		native.state.form.handlers.refresh({ set_intro: () => { throw new Error('native HR User form must not receive Tradexcel intro'); } });
		assert.equal(native_props.length, 0);
	}

	console.log('Attendance/shift recovery UI contracts passed (mixed results, retry messaging, shift routing, evidence review, period states, tool narrowing)');
}

run().catch((error) => {
	console.error(error);
	process.exit(1);
});
