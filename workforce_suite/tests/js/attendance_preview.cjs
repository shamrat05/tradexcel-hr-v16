const workforce_suite = {report_actions: {begin(report) {report.workforce_actions = {add: (...args) => report.page.add_inner_button(...args), primary: (...args) => report.page.set_primary_action(...args), is_current: () => true};}}};
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
let dialog, button, resolvePreview;
const values = {action: 'Present', explanation: 'Synthetic reviewed correction'};
const events = {};
const calls = [];
const frappe = {
 query_reports: {}, user: {has_role: () => true},
 defaults: {get_user_default: () => ''}, datetime: {get_today: () => '2026-09-01'},
 utils: {escape_html: String}, msgprint: () => {},
 call: options => { calls.push(options); return new Promise(resolve => {resolvePreview = resolve;}); },
 ui: {Dialog: class { constructor() {dialog=this; this.fields_dict={}; for(const key of ['action','explanation']) this.fields_dict[key]={$input:{on:(_,fn)=>{events[key]=fn;}}};this.fields_dict.preview={$wrapper:{html:()=>{}}};}get_value(k){return values[k];}get_values(){return values;}set_primary_action(label,fn){this.label=label;this.primary=fn;}show(){}hide(){} }}
};
vm.runInNewContext(fs.readFileSync(process.argv[2], 'utf8'), {frappe, workforce_suite, __: x=>x});
frappe.query_reports['Workforce Daily Attendance Board'].onload({
 page:{add_inner_button:(_,fn)=>{button=fn;}}, get_checked_items:()=>[{employee:'SYNTHETIC'}],
 get_filter_values:()=>({company:'Synthetic',attendance_date:'2026-09-01'}), refresh:()=>{}
});
button();dialog.primary();
values.action='Work From Home';events.action();
resolvePreview({message:{rows:[{proposed_status:'Present',outcome:'Will create'}]}});
setImmediate(async () => {
 assert.equal(dialog.label, 'Preview', 'An obsolete preview must not offer Apply');
 assert.equal(calls.length, 1);
 dialog.primary();
 resolvePreview({message:{rows:[]}});
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(dialog.label, 'Create draft requests');
 // A stale callback cannot apply even if input changes without a DOM event.
 values.explanation='A different synthetic explanation';
 dialog.primary();
 assert.equal(calls.length, 2);
 events.explanation();
 dialog.primary();
 resolvePreview({message:{rows:[]}});
 await new Promise(resolve=>setImmediate(resolve));
 dialog.primary();
 assert.equal(calls.length, 4);
 assert.equal(calls[3].args.action, 'Work From Home');
 assert.equal(calls[3].args.explanation, values.explanation);
 assert.match(calls[3].method, /prepare_attendance_corrections$/);
 // Repeated clicks while applying never send another mutation.
 dialog.primary();
 assert.equal(calls.length, 4);
 console.log('Stale preview, fresh confirmation and duplicate-click checks passed');
});
