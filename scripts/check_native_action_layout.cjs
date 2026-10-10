"use strict";

/**
 * Native Frappe action-placement contract.
 *
 * Runs without Frappe or a database. Exercises the actual report/form JS
 * onload/refresh handlers in a minimal, explicit host so CI detects missing
 * actions, misplaced controls, accidental permission changes and ordering.
 * It verifies registrations, NOT a real browser's dropdown rendering.
 */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const ROOT = path.resolve(__dirname, "..");
let checked = 0;

function host(roles = []) {
    const calls = { actions: [], forms: {}, routes: [], newDocs: [], messages: [] };
    const frappe = {
        query_reports: {},
        model: {can_read: () => true, can_write: () => true, can_create: () => true},
        ui: { form: {
            on(doctype, handlers) { calls.forms[doctype] = handlers; },
        }},
        user: { has_role: (name) => roles.includes(name) },
        session: { user: "synthetic@example.com" },
        defaults: { get_user_default: () => "Synthetic Company" },
        datetime: { get_today: () => "2026-10-08", month_start: () => "2026-10-01" },
        utils: { escape_html: (value) => String(value) },
        route_options: null,
        set_route: (...args) => calls.routes.push(args),
        new_doc: (...args) => calls.newDocs.push(args),
        msgprint: (value) => calls.messages.push(value),
    };
    function button(label, action, group = "") {
        calls.actions.push({ label, action, group, kind: "toolbar" });
        return { addClass() { return this; }, prop() { return this; } };
    }
    const page = {
        add_inner_button: button,
        set_primary_action(label, action) {
            calls.actions.push({ label, action, group: "", kind: "primary" });
            return { prop() { return this; } };
        },
    };
    const report = {
        page, data: [{ employee: "SYN-EMP-1" }],
        get_filter_value(name) {
            return { company: "Synthetic Company", branch: "Synthetic Branch", department: "HR" }[name] || "";
        },
        $report: {
            off() { return this; },
            on() { return this; },
        },
    };
    const workforce_suite = {report_actions: {begin(report) {report.workforce_actions = {add: (...args) => report.page.add_inner_button(...args), primary: (...args) => report.page.set_primary_action(...args), is_current: () => true};}}};
    const context = vm.createContext({ frappe, workforce_suite, __: (value) => value, console });
    function load(relpath) {
        const fullpath = path.join(ROOT, relpath);
        const source = fs.readFileSync(fullpath, "utf8");
        new vm.Script(source, { filename: relpath }).runInContext(context);
    }
    return { calls, frappe, report, load };
}
function verifyActions(actual, expected, label) {
    assert.deepEqual(
        actual.map(({ label, group, kind }) => ({ label, group, kind })),
        expected.map(([label, group = "", kind = "toolbar"]) => ({ label, group, kind })),
        label
    );
    checked++;
}
function reportCase(reportPath, reportName, roles) {
    const h = host(roles);
    h.load(reportPath);
    h.frappe.query_reports[reportName].onload(h.report);
    return h;
}
function formCase(formPath, doctype) {
    const h = host();
    h.load(formPath);
    assert.ok(h.calls.forms[doctype]?.refresh, `Missing refresh handler for ${doctype}`);
    return h;
}

const reports = "workforce_suite/workforce_suite/report/";
{
    const h = reportCase(
        reports + "employee_data_gaps/employee_data_gaps.js",
        "Employee Data Gaps", ["HR Manager"]
    );
    verifyActions(h.calls.actions, [
        ["Review Employees"],
        ["Open Salary Assignment Tool", "More actions"],
        ["Open Bulk Shift Assignment", "More actions"],
        ["Create Employee Transfer", "More actions"],
        ["Create Employee Promotion", "More actions"],
        ["View Employee Onboardings", "More actions"],
    ], "HR actions and order on Employee Data Gaps");
    assert.equal(h.calls.actions.filter(a => !a.group).length, 1);
    h.calls.actions[0].action();
    assert.deepEqual(h.calls.routes.at(-1), ["List", "Employee"]);
    assert.equal(h.frappe.route_options.name[0], "in");
    assert.deepEqual(Array.from(h.frappe.route_options.name[1]), ["SYN-EMP-1"]);
    h.calls.actions[1].action();
    assert.deepEqual(h.calls.routes.at(-1), ["Form", "Bulk Salary Structure Assignment"]);
    h.calls.actions[2].action();
    assert.deepEqual(h.calls.routes.at(-1), ["Form", "Shift Assignment Tool"]);
    assert.equal(h.frappe.route_options.branch, "Synthetic Branch");
    h.report.data.push({employee: "SYN-EMP-2"});
    h.calls.actions[3].action();
    assert.equal(h.calls.newDocs.length, 0, "Transfer must require exactly one Employee");
    assert.ok(h.calls.messages.length > 0);
    checked++;
}
{
    const h = reportCase(
        reports + "employee_data_gaps/employee_data_gaps.js",
        "Employee Data Gaps", ["Workforce Suite/Attendance Officer"]
    );
    verifyActions(h.calls.actions, [
        ["Review Employees"], ["Open Bulk Shift Assignment", "More actions"]
    ], "Attendance officer sees only permitted action groups");
}
{
    const h = reportCase(
        reports + "employee_data_gaps/employee_data_gaps.js",
        "Employee Data Gaps", []
    );
    verifyActions(h.calls.actions, [
        ["Review Employees"]
    ], "Read-only user sees no HR mutations");
}
{
    const h = reportCase(
        reports + "biometric_id_audit/biometric_id_audit.js",
        "Biometric ID Audit", []
    );
    verifyActions(h.calls.actions, [
        ["Assign Biometric ID"], ["Copy Biometric to Device", "Device actions"]
    ], "Biometric audit separates frequent assignment from transfer");
}
{
    const h = reportCase(
        reports + "workforce_joiners_and_leavers/workforce_joiners_and_leavers.js",
        "Workforce Joiners and Leavers", ["HR Manager"]
    );
    verifyActions(h.calls.actions, [
        ["View Employee Onboardings", "Employee workflows"],
        ["View Employee Separations", "Employee workflows"],
    ], "Equal-priority lifecycle workflows share one labeled native group");
    h.calls.actions[1].action();
    assert.deepEqual(h.calls.routes.at(-1), ["List", "Employee Separation"]);
    checked++;
}
{
    const h = reportCase(
        reports + "workforce_joiners_and_leavers/workforce_joiners_and_leavers.js",
        "Workforce Joiners and Leavers", []
    );
    verifyActions(h.calls.actions, [], "No unpermitted workflow links");
}
{
    const h = reportCase(
        reports + "workforce_payroll_readiness/workforce_payroll_readiness.js",
        "Workforce Payroll Readiness", ["Workforce Payroll Manager"]
    );
    verifyActions(h.calls.actions, [
        ["Prepare Payroll", "", "primary"],
        ["Review Structure Migration", "More actions"],
    ], "Payroll primary action remains primary and review remains discoverable");
    assert.ok(h.report.$prepare_payroll_button);
}
{
    const h = reportCase(
        reports + "workforce_payroll_readiness/workforce_payroll_readiness.js",
        "Workforce Payroll Readiness", []
    );
    verifyActions(h.calls.actions, [], "No payroll preparation action for other roles");
}
{
    const h = formCase("workforce_suite/public/js/workforce_biometric_device.js", "Workforce Biometric Device");
    const frm = {
        is_new: () => false,
        has_perm: () => true,
        doc: {name: "SYN-DEVICE-1"},
        add_custom_button: (label, action, group = "") => {
            h.calls.actions.push({label, action, group, kind: "toolbar"});
        },
    };
    h.calls.forms["Workforce Biometric Device"].refresh(frm);
    verifyActions(h.calls.actions, [
        ["Check Bridge Health"], ["Push Configuration to Bridge", "Device actions"]
    ], "Health first; configuration write in explicit device group");
}
async function payrollForm(status, payment, write = true, read = true) {
    const h = formCase("workforce_suite/public/js/payroll_entry.js", "Payroll Entry");
    const frm = {
        doc: { custom_workforce_run_key: "SYN-RUN", docstatus: 1, name: "SYN-PAYROLL", status: "Submitted" },
        has_perm: () => write,
        dashboard: { set_headline() {} },
        remove_custom_button() {},
        add_custom_button(label, action, group = "") {
            h.calls.actions.push({label, action, group, kind: "toolbar"});
            return { addClass() {return this;} };
        },
    };
    h.frappe.model.can_read = () => read;
    h.frappe.call = ({method}) => Promise.resolve({
        message: method.endsWith("get_payroll_accrual_reconciliation") ? status : payment,
    });
    h.calls.forms["Payroll Entry"].refresh(frm);
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
    return h;
}
(async () => {
    const ready = await payrollForm({status:"READY",safe_to_retry:false}, {status:"READY_TO_PREPARE_PAYMENT"});
    verifyActions(ready.calls.actions, [
        ["Prepare Payment"]
    ], "Payment preparation stays one click away when ready");

    const records = await payrollForm({status:"READY",safe_to_retry:false}, {
        status:"AWAITING_BANK_RECONCILIATION",
        payment_journal_entry:"SYN-JE-1", bank_transactions:[{name:"SYN-BANK-1"}],
    });
    verifyActions(records.calls.actions, [
        ["Open Journal Entry", "Payment records"],
        ["Open Bank Transaction", "Payment records"],
    ], "Related payment records share a group rather than two toolbar buttons");
    records.calls.actions[0].action();
    assert.deepEqual(records.calls.routes.at(-1), ["Form", "Journal Entry", "SYN-JE-1"]);
    checked++;

    const retry = await payrollForm({
        status:"PARTIAL_SUBMISSION",safe_to_retry:true,submitted_slip_count:2,draft_slip_count:3,
    }, null);
    verifyActions(retry.calls.actions, [
        ["Retry Unsubmitted Salary Slips"]
    ], "Urgent payroll retry remains visible");

    const denied = await payrollForm({status:"READY",safe_to_retry:false}, {
        status:"READY_TO_PREPARE_PAYMENT"}, false, false);
    verifyActions(denied.calls.actions, [], "Read-only users cannot prepare payment");
    const hidden = await payrollForm({status:"READY",safe_to_retry:false}, {
        status:"AWAITING_BANK_RECONCILIATION", payment_journal_entry:"SYN-JE",
        bank_transactions:[{name:"SYN-BANK"}]}, false, false);
    verifyActions(hidden.calls.actions, [], "Accounting routes require native read permission");
    const device = formCase("workforce_suite/public/js/workforce_biometric_device.js", "Workforce Biometric Device");
    device.calls.forms["Workforce Biometric Device"].refresh({is_new:()=>false,has_perm:()=>false});
    verifyActions(device.calls.actions, [], "Read-only device user has no write-backed diagnostics");
    // Delayed responses must not add actions for an earlier refresh/document.
    const stale = formCase("workforce_suite/public/js/payroll_entry.js", "Payroll Entry");
    const pending = [];
    stale.frappe.call = () => new Promise(resolve => pending.push(resolve));
    const form = {
        doc: {name:"SYN-ONE",docstatus:1,custom_workforce_run_key:"SYN-RUN"},
        has_perm: () => true,
        remove_custom_button() {}, dashboard: {set_headline() {}},
        add_custom_button(label) {stale.calls.actions.push(label);return {addClass() {}};},
    };
    const refresh = stale.calls.forms["Payroll Entry"].refresh;
    refresh(form); refresh(form);
    pending[0]({message:{safe_to_retry:true,draft_slip_count:1}});
    await Promise.resolve();
    assert.deepEqual(stale.calls.actions, [], "out-of-order refresh cannot add a stale finalize action"); checked++;
    pending[1]({message:{status:"READY"}});
    await Promise.resolve();
    assert.equal(pending.length,3);
    refresh(form);
    pending[2]({message:{status:"READY_TO_PREPARE_PAYMENT"}});
    await Promise.resolve();
    assert.deepEqual(stale.calls.actions, [], "out-of-order payment response cannot add Prepare Payment"); checked++;
    form.doc.name = "SYN-TWO";
    pending[3]({message:{safe_to_retry:true,draft_slip_count:1}});
    await Promise.resolve();
    assert.deepEqual(stale.calls.actions, [], "old document response cannot add an action to a different document"); checked++;

    for (const [user,roles,status,visible] of [
        ["Administrator",[],1,true],
        ["synthetic@example.test",["Workforce Payroll Manager"],1,true],
        ["synthetic@example.test",["Workforce Employee/Worker"],1,false],
        ["synthetic@example.test",["Workforce Payroll Manager"],0,false],
    ]) {
        const slip = host(roles);
        slip.frappe.session.user = user;
        slip.load("workforce_suite/public/js/salary_slip_adjustments.js");
        slip.calls.forms["Salary Slip"].refresh({doc:{docstatus:status},add_custom_button:label=>slip.calls.actions.push(label)});
        assert.equal(slip.calls.actions.includes("Review Payroll Adjustment"),visible);
        checked++;
    }
    console.log(`Native action placement: ${checked} checks passed`);
})().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});
