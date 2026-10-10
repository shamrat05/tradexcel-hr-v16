"use strict";
// Deterministic lifecycle test; actual native Page/menus are also tested in Desk.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
let route = ['query-report', 'First'];
let changed;
let called = 0;
const nodes = [];
const buttons = new Map();
let primary;
function node(label) {
 const n = {label, remove() {const i=nodes.indexOf(n);if(i>=0)nodes.splice(i,1);}};
 nodes.push(n); return n;
}
const native = node('Print');
const other = node('Other app export');
const page = {
 menu: {children: () => ({toArray: () => [...nodes], each: fn => [...nodes].forEach((n,i)=>fn(i,n))})},
 add_inner_button(label, callback, group) {node(label); buttons.set(label,callback);return {label};},
 remove_inner_button(label) {buttons.delete(label);},
 set_primary_action(label, callback) {primary={label,callback};return primary;},
 clear_primary_action() {primary=null;},
 btn_primary: {attr: () => primary && encodeURIComponent(primary.label)},
};
const workforce_suite = {report_actions:{}};
const frappe = {provide() {},get_route:()=>route,router:{on:(event,cb)=>{assert.equal(event,'change');changed=cb;}}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../workforce_suite/public/js/report_actions.bundle.js'),'utf8'),{frappe,workforce_suite,Set});
const report={page,report_name:'First'};
let a=workforce_suite.report_actions.begin(report);
a.add('First action',()=>called++,'More actions');
a.primary('Prepare Payroll',()=>called++);
const stale = buttons.get('First action');
stale();assert.equal(called,1);
// Ordinary refresh recreates owned controls exactly once, preserves foreign/native items.
a=workforce_suite.report_actions.begin(report);
a.add('First action',()=>called++,'More actions');
assert.equal(nodes.filter(n=>n.label==='First action').length,1);
assert.equal(primary,null);
a.primary('Prepare Payroll',()=>called++);
// Navigation to ANY report, including an upstream report without our helper.
route=['query-report','Native upstream report'];changed();
assert.equal(buttons.size,0);assert.equal(primary,null);assert.deepEqual(nodes,[native,other]);
stale();assert.equal(called,1,'stale callback cannot run on another report');
// Native Form/List navigation hides, then reuses the same report without onload.
route=['query-report','First'];a=workforce_suite.report_actions.begin(report);
a.add('First action',()=>called++);a.primary('Prepare Payroll',()=>called++);
route=['Form','Employee','Synthetic'];changed();
buttons.get('First action')();assert.equal(called,1,'hidden report callback is inert');
route=['query-report','First'];changed();
buttons.get('First action')();assert.equal(called,2,'back navigation retains the action');
assert.equal(nodes.filter(n=>n.label==='First action').length,1);
// Do not clear a primary action replaced by native or another app.
route=['query-report','First'];a=workforce_suite.report_actions.begin(report);a.primary('Prepare Payroll',()=>{});
page.set_primary_action('Native Save',()=>{});route=['query-report','Second'];changed();assert.equal(primary.label,'Native Save');
console.log('Report action lifecycle: refresh, route change, back navigation and foreign-action preservation passed');
