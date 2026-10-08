"""Truthful worker-facing labels based on Checkin evidence, not Attendance."""
from pathlib import Path
import subprocess

SOURCE = Path(__file__).parents[1] / 'workforce_suite/page/workforce_mobile_attendance/workforce_mobile_attendance.js'


def test_evidence_state_mapping():
    source = SOURCE.read_text().split('frappe.pages[')[0]
    program = r'''
const assert=require('node:assert/strict');const __=x=>x;
SOURCE
assert.equal(workforceMobileEvidenceState('IN',{},true).kind,'queued');
assert.match(workforceMobileEvidenceState('IN',{},true).detail,/sync or confirm/);
assert.equal(workforceMobileEvidenceState('IN',{custom_workforce_time_status:'Trusted',custom_workforce_review_status:'Not Required'}).title,'Check-in saved');
assert.equal(workforceMobileEvidenceState('OUT',{}).title,'Check-out saved');
assert.equal(workforceMobileEvidenceState('OUT',{custom_workforce_review_status:'Pending'}).title,'Check-out received — needs review');
for(const row of [{custom_workforce_review_status:'Pending'},{custom_workforce_time_status:'Flagged'},{skip_auto_attendance:1},{skip_auto_attendance:'1'},{custom_workforce_location_status:'Time Review Required'}]) assert.equal(workforceMobileEvidenceState('IN',row).kind,'review');
assert.equal(workforceMobileEvidenceState('OUT',{custom_workforce_review_status:'Approved',custom_workforce_time_status:'Flagged',skip_auto_attendance:0}).kind,'saved');
assert.equal(workforceMobileEvidenceState('IN',{custom_workforce_review_status:'Rejected',skip_auto_attendance:1}).kind,'review_rejected');
assert.equal(workforceMobileEvidenceState('IN',{custom_workforce_review_status:'Approved',skip_auto_attendance:1}).kind,'review');
assert.equal(workforceMobileEvidenceState('IN',{custom_workforce_time_status:'Blocked'}).kind,'rejected');
'''.replace('SOURCE', source)
    subprocess.run(['node','-e',program],check=True,capture_output=True,text=True)


def test_context_failure_retry_and_replay_use_backend_truth():
    source=SOURCE.read_text()
    assert 'Attendance recorded' not in source
    assert 'Recording attendance' not in source
    assert 'Retry loading' in source
    assert 'if (!context) return loadPageContext()' in source
    assert 'return checkin;' in source
    assert 'const checkin = await replayQueuedCheckin(item)' in source
    assert 'showSuccessState(item.log_type, checkin)' in source
    assert 'aria-live="polite"' in source


def test_replay_displays_review_truth_and_does_not_retry_rejection():
    source=SOURCE.read_text()
    replay=source[source.index('  async function finishSelfieAttachment'):source.index('  function refreshButton')]
    program=r'''
const assert=require('node:assert/strict');
const __=x=>x;const navigator={onLine:true};let offlineFlushInProgress=false;
let context={next_action:'OUT'};let calls=0;const shown=[];
const rows=new Map([['pending',{sync_id:'pending',log_type:'IN'}],['blocked',{sync_id:'blocked',log_type:'OUT'}]]);
const queuedCheckins=async()=>[...rows.values()];
const cleanupOfflineEvidence=async()=>{};
const deleteQueuedCheckin=async id=>rows.delete(id);
const discardQueuedEvidence=async(item,message)=>rows.set(item.sync_id,{sync_id:item.sync_id,retryable:false,last_error:message});
const isNetworkError=e=>(e.cause||e).status===0;
const updateQueueStatus=async()=>{};const refreshButton=()=>{};
const showSuccessState=(log,doc)=>shown.push(doc);
const frappe={call:async({args})=>{
 calls++;
 if(args.sync_id==='blocked') throw {status:417};
 return {message:{name:'synthetic',custom_workforce_review_status:'Pending',skip_auto_attendance:1}};
}};
REPLAY
(async()=>{
 await flushOfflineQueue();
 assert.equal(calls,2);assert.equal(shown[0].custom_workforce_review_status,'Pending');
 assert.equal(shown[0].skip_auto_attendance,1);
 assert.equal(shown[1].custom_workforce_review_status,undefined);
 assert.equal(rows.get('blocked').retryable,false);assert.equal(rows.has('pending'),false);
 await flushOfflineQueue();assert.equal(calls,2);
})().catch(e=>{console.error(e);process.exit(1)});
'''.replace('REPLAY',replay)
    subprocess.run(['node','-e',program],check=True,capture_output=True,text=True)


def test_partial_acceptance_keeps_retry_and_backend_truth():
    """P01: production replay/online shared attachment/error handlers, real row boundary."""
    source = SOURCE.read_text()
    helpers = source[source.index('  async function finishSelfieAttachment'):source.index('  function refreshButton')]
    program = r'''
const assert=require('node:assert/strict');const __=x=>x;
const navigator={onLine:true};let offlineFlushInProgress=false,context={next_action:'IN'};
const rows=new Map(),shown=[],ids=[],files=[];let uploads=0,attachFailure=0,rejectBefore=false;
const saved={name:'same-canonical-checkin',custom_workforce_review_status:'Pending',skip_auto_attendance:1};
const withOfflineStore=async(_,fn)=>fn({put:x=>rows.set(x.sync_id,{...x})});
const queueOfflineCheckin=async item=>rows.set(item.sync_id,{...item,retryable:true});
const queuedCheckins=async()=>[...rows.values()];
const deleteQueuedCheckin=async id=>rows.delete(id);
const discardQueuedEvidence=async(item,message)=>rows.set(item.sync_id,{sync_id:item.sync_id,queued_at:item.queued_at,retryable:false,last_error:message});
const cleanupOfflineEvidence=async()=>{},updateQueueStatus=async()=>{},refreshButton=()=>{};
const showSuccessState=(log,doc,queued,warning,ingestion)=>shown.push({doc,queued,warning,ingestion});
const isNetworkError=e=>(e.cause||e).status===0;
const File=function(){};
const uploadSelfie=async()=>{uploads++;return '/private/files/synthetic.jpg'};
const frappe={call:async({method,args})=>{
 if(method.endsWith('attach_selfie')){files.push(args.file_url);if(attachFailure)throw {status:attachFailure};return {message:{}};}
 ids.push(args.sync_id);if(rejectBefore)throw {status:417};return {message:saved};
}};
HELPERS
(async()=>{
 // P01-1: uploaded once, accepted, attachment lost; same row/ID/private URL survives.
 const item={sync_id:'same',log_type:'IN',selfie_blob:'sensitive',latitude:23,queued_at:'synthetic',retryable:true};
 rows.set(item.sync_id,item);attachFailure=0;
 // Force only secondary transport to fail, never the ingestion call.
 attachFailure=0;const originalCall=frappe.call;
 frappe.call=async o=>{if(o.method.endsWith('attach_selfie'))throw {status:0};return originalCall(o)};
 await flushOfflineQueue();
 assert.equal(rows.get('same').retryable,true);assert.equal(rows.get('same').sync_id,'same');
 assert.equal(rows.get('same').selfie_url,'/private/files/synthetic.jpg');assert.equal(uploads,1);
 assert.equal(shown.at(-1).doc,saved);assert.equal(shown.at(-1).queued,true);assert.notEqual(shown.at(-1).ingestion,true);
 frappe.call=originalCall;await flushOfflineQueue();
 assert.equal(rows.has('same'),false);assert.equal(uploads,1);assert.deepEqual(ids,['same','same']);
 assert.equal(shown.at(-1).doc,saved);assert.equal(files.at(-1),'/private/files/synthetic.jpg');
 // P01-2: exact helper used by direct online click annotates accepted response.
 const direct={sync_id:'direct',log_type:'OUT',selfie_url:'/private/files/owned.jpg',selfie_blob:'private',latitude:23};
 frappe.call=async o=>{if(o.method.endsWith('attach_selfie'))throw {status:0};return originalCall(o)};
 try{await finishSelfieAttachment(saved,direct.selfie_url);assert.fail('expected transport failure')}catch(e){assert.equal(e.acceptedCheckin,saved);await handleSyncFailure(direct,e);}
 assert.equal(rows.get('direct').retryable,true);assert.equal(rows.get('direct').selfie_url,direct.selfie_url);assert.equal(shown.at(-1).queued,true);
 // P01-3: permanent secondary validation is a warning, not Checkin rejection.
 frappe.call=originalCall;attachFailure=417;await flushOfflineQueue();
 assert.equal(shown.at(-1).doc,saved);assert.equal(shown.at(-1).warning,true);assert.equal(shown.at(-1).ingestion,false);
 assert.deepEqual(Object.keys(rows.get('direct')).sort(),['last_error','queued_at','retryable','sync_id']);
 const calls=ids.length;await flushOfflineQueue();assert.equal(ids.length,calls);
 // P01-4: genuine rejection before Checkin creation has an explicit client error.
 rejectBefore=true;rows.set('before',{sync_id:'before',log_type:'IN',retryable:true});await flushOfflineQueue();
 assert.equal(shown.at(-1).ingestion,true);assert.equal(shown.at(-1).doc.custom_workforce_review_status,undefined);
})().catch(e=>{console.error(e);process.exit(1)});
'''.replace('HELPERS', helpers)
    subprocess.run(['node','-e',program],check=True,capture_output=True,text=True)
    click = source[source.index('  actionEl.on("click"'):source.index('  window.addEventListener("online"')]
    assert 'await finishSelfieAttachment(checkin, selfieUrl)' in click
    assert 'await handleSyncFailure(queuedPayload, error)' in click


def test_review_rejection_is_distinct_from_ingestion_failure():
    source=SOURCE.read_text().split('frappe.pages[')[0]
    program=r'''
const assert=require('node:assert/strict');const __=x=>x;
SOURCE
for(const log of ['IN','OUT']){
 const state=workforceMobileEvidenceState(log,{custom_workforce_review_status:'Rejected',skip_auto_attendance:1});
 assert.equal(state.kind,'review_rejected');assert.match(state.title,/rejected after review/);assert.match(state.detail,/received but rejected/);
 const failed=workforceMobileEvidenceState(log,{},false,true);assert.equal(failed.title,'Could not be accepted');assert.equal(failed.kind,'rejected');
}
'''.replace('SOURCE',source)
    subprocess.run(['node','-e',program],check=True,capture_output=True,text=True)
