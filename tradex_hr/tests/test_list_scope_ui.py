"""Execute the production list extension; permissions stay server-owned."""
from pathlib import Path
import subprocess

SOURCE = Path(__file__).parents[1] / 'public/js/list_scope.js'


def test_list_settings_compose_scope_and_native_date_controls():
    program = r'''
const vm = require('node:vm'), assert = require('node:assert/strict');
let calls = [], rows = [['Attendance','company','=','Synthetic'],['Attendance','branch','=','Branch A']];
let loads=0, refreshes=0;
const priorFormatter = x => 'prior:'+x;
const ctx = {__:x=>x, setTimeout:fn=>fn(), moment:()=>({format:()=> '09:00 AM'}), frappe:{
 listview_settings: {Attendance:{onload:()=>loads++,refresh:()=>refreshes++,formatters:{custom:priorFormatter}}, 'Employee Checkin':{formatters:{custom:priorFormatter}}},
 meta:{has_field:()=>true}, datetime:{str_to_user:x=>'native date '+x}
}};
vm.createContext(ctx);vm.runInContext(SOURCE,ctx);
const fields = Object.fromEntries(['company','branch','department','designation','employee'].map(k=>[k,{}]));
const list = {page:{fields_dict:fields,add_inner_button:(label,fn,group)=>calls.push({label,fn,group})},filter_area:{get:()=>rows,clear:()=>rows=[],add:x=>rows=x}};
const settings=ctx.frappe.listview_settings.Attendance;
settings.onload(list);settings.refresh(list);settings.refresh(list);
assert.equal(loads,1);assert.equal(refreshes,2);assert.equal(settings.formatters.custom,priorFormatter);
assert.deepEqual(calls.map(x=>[x.group,x.label]),[['Date','Today'],['Date','This Week'],['Date','This Month']]);
assert.equal(fields.branch.get_query().filters.company,'Synthetic');
assert.equal(fields.department.get_query().filters.branch,'Branch A');
assert.equal(fields.employee.get_query().filters.branch,'Branch A');
rows.push(['Attendance','attendance_date','=','2026-01-01']);calls[0].fn();
assert.equal(rows.length,3);assert.equal(rows[0][1],'company');assert.equal(rows[1][1],'branch');
assert.equal(rows[2][2],'Timespan');assert.equal(rows[2][3],'today');
assert.equal(settings.formatters.in_time('x'),'09:00 AM');
const checkin=ctx.frappe.listview_settings['Employee Checkin'];
assert.equal(checkin.formatters.time('2026-09-30 09:00:00'),'native date 2026-09-30 09:00:00');
assert.equal(checkin.formatters.time(null),'');
assert.equal(checkin.formatters.custom,priorFormatter);
'''
    subprocess.run(['node', '-e', program.replace('SOURCE', repr(SOURCE.read_text()))], check=True, capture_output=True, text=True)


def test_no_duplicate_range_or_saved_filter_system():
    source = SOURCE.read_text()
    assert 'frappe.prompt' not in source
    assert 'Custom Range' not in source
    assert 'ignore_permissions' not in source
    assert 'frappe.call' not in source
    assert 'Native server permissions remain the access boundary' in source
