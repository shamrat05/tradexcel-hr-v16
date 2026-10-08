"""Candidate DOM interactions. Run using uv pytest with playwright; no site writes."""
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
JQUERY=Path('/home/sanchita/frappe-bench-v16/apps/frappe/frappe/public/js/lib/jquery/jquery.min.js')

HARNESS=r'''
window.__ = (text,args=[]) => text.replace(/\{(\d+)\}/g,(_,i)=>args[i]||'');
window.responses=[];window.calls=[];window.dialogs=[];window.messages=[];window.roles=[];window.handlers={};
window.frappe={session:{user:'reviewer@test'},user:{has_role:r=>roles.includes(r)},
utils:{escape_html:x=>String(x).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')},
datetime:{get_today:()=> '2026-09-30',str_to_user:x=>x},
ui:{form:{on:(dt,handler)=>handlers[dt]=handler},Dialog:class {
 constructor(options){this.options=options;this.values={};this.properties={};this.$body=$('<section role="dialog" tabindex="-1"></section>').appendTo('body');dialogs.push(this)}
 show(){this.$body[0].focus()}; hide(){this.$body.hide()};
 get_value(name){return this.values[name]};set_value(name,value){this.values[name]=value};
 set_df_property(name,key,value){(this.properties[name]??={})[key]=value}
}},
call:request=>{calls.push(request);let next=responses.shift();return next instanceof Error?Promise.reject(next):Promise.resolve({message:next})},
msgprint:message=>{messages.push(message);$('#result').html(message.message)},confirm:()=>{}};
'''

@pytest.mark.parametrize('width',[375,1365])
@pytest.mark.parametrize('theme',['light','dark'])
def test_calendar_retry_legal_dialog_exit_visibility_and_fnf(width,theme):
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True)
  page=browser.new_page(viewport={'width':width,'height':900})
  page.set_content('<div id="result"></div><style>section{max-width:100%;padding:8px;box-sizing:border-box}body{margin:8px}button{padding:8px}</style>')
  page.add_script_tag(path=str(JQUERY));page.add_script_tag(content=HARNESS)
  page.add_script_tag(content=(ROOT/'public/js/employee_calendar.js').read_text())
  page.add_script_tag(content=(ROOT/'public/js/employee_separation.js').read_text())
  page.evaluate("document.body.style.background='%s';document.body.style.color='%s'" % (('#fff','#222') if theme=='light' else ('#222','#fff')))
  # Failed -> empty -> retry -> real calendar payload, using actual click handlers.
  page.evaluate("responses.push(new Error('Transport'),null,{today:'2026-09-30',days:[{date:'2026-09-01',day:1,category:'No Record'}],legend:{}});show_employee_calendar('Synthetic','Synthetic')")
  retry=page.get_by_role('button',name='Retry calendar');retry.wait_for();retry.focus();page.keyboard.press('Enter')
  page.wait_for_function('calls.length===2');retry.wait_for();retry.click()
  page.wait_for_function('calls.length===3')
  assert 'No submitted Attendance' in page.locator('body').inner_text()
  assert 'No Record / Absent' not in page.locator('body').inner_text()
  assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
  # Earliest backend blocker is displayed without invented downstream progress.
  page.evaluate("show_full_and_final_readiness({status:'BLOCKED',employee:'Synthetic',findings:[{code:'RELIEVING_DATE_MISSING'}]})")
  assert 'RELIEVING_DATE_MISSING' in page.locator('#result').inner_text()
  assert 'Pending Submission' not in page.locator('#result').inner_text()
  page.evaluate("show_full_and_final_readiness({status:'REVIEW_REQUIRED',employee:'Synthetic',native_outstanding_sources:{},findings:[{message:'Resolve blocker'},{severity:'info',message:'Informational finding'}]})")
  assert 'Resolve blocker' in page.locator('#result').inner_text()
  assert 'Information' in page.locator('#result').inner_text()
  # Real form refresh callback role visibility, with no endpoint invocation.
  for role,expected in [('System Manager',False),('Workforce Suite Manager',True),('Workforce Owner/Director',True)]:
   result=page.evaluate("""([role])=>{roles=[role];let buttons=[];handlers.Employee.refresh({is_new:()=>false,doc:{name:'Synthetic',status:'Left',relieving_date:'2026-09-01'},add_custom_button:label=>buttons.push(label)});return buttons.includes('Finalize Exit Access')}""",[role])
   assert result is expected
  # Native dialog callbacks enforce exact Not Applicable payload and clear rule.
  page.evaluate("roles=['Workforce Owner/Director'];handlers['Employee Separation'].refresh({is_new:()=>false,doc:{name:'Synthetic',owner:'maker@test',docstatus:1,company:'Synthetic'},add_custom_button:(label,fn)=>fn(),reload_doc:()=>{}})")
  result=page.evaluate("""()=>{let d=dialogs.at(-1);d.values={status:'Not Applicable',rule_set:'Old rule',classification:'Worker under selected regime'};d.options.fields.find(f=>f.fieldname==='status').change();return {values:d.values,properties:d.properties}}""")
  assert result['values']['rule_set']=='' and result['values']['classification']=='Outside worker scope'
  assert result['properties']['classification']['reqd']==1
  page.evaluate("responses.push({status:'Not Applicable'});dialogs.at(-1).options.primary_action({...dialogs.at(-1).values,notes:'Synthetic review'})")
  args=page.evaluate('calls.at(-1).args');assert args['classification']=='Outside worker scope' and args['rule_set']==''
  page.evaluate("dialogs.at(-1).values.status='Approved';dialogs.at(-1).options.fields.find(f=>f.fieldname==='status').change()")
  assert page.evaluate('dialogs.at(-1).properties.rule_set.reqd')==1
  assert page.evaluate('dialogs.at(-1).properties.classification.read_only')==0
  browser.close()
