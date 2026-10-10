"use strict";
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../workforce_suite/public/js/native_announcements.bundle.js'),'utf8');
function run(notice,old,dismissed,tag='DIV',present=true){
 const store=new Map([['announcement_widget',old],['dismissed_announcement_widget',dismissed]]);let ready,keys,clicks=0;
 const attrs={};const close={tagName:tag,tabIndex:tag==='BUTTON'?0:-1,setAttribute:(k,v)=>attrs[k]=v,addEventListener:(e,fn)=>keys=fn,click:()=>clicks++};
 vm.runInNewContext(code,{frappe:{boot:{navbar_settings:{announcement_widget:notice}}},localStorage:{getItem:k=>store.get(k),removeItem:k=>store.delete(k)},document:{querySelector:()=>present?close:null},$:()=>({on:(e,fn)=>ready=fn}),__:x=>x});
 ready();return{store,attrs,keys,clicks:()=>clicks};
}
let a=run('new','old','true');assert(!a.store.has('dismissed_announcement_widget'));assert.equal(a.attrs.role,'button');assert.equal(a.attrs.tabindex,'0');assert.equal(a.attrs['aria-label'],'Dismiss site announcement');
for(const key of ['Enter',' ']){let prevented=false;a.keys({key,preventDefault:()=>prevented=true});assert(prevented);}
assert.equal(a.clicks(),2);a.keys({key:'Escape'});assert.equal(a.clicks(),2);
assert.equal(run('same','same','true').store.get('dismissed_announcement_widget'),'true');
assert.equal(run('','old','true').store.get('dismissed_announcement_widget'),'true');
assert.deepEqual(run('new','old','true','BUTTON').attrs,{});
assert.deepEqual(run('new','old','true','DIV',false).attrs,{});
console.log('Native announcement compatibility: 6 scenarios passed');
