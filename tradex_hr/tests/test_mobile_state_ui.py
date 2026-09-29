"""Truthful worker-facing labels based on Checkin evidence, not Attendance."""
from pathlib import Path
import subprocess

SOURCE = Path(__file__).parents[1] / 'tradexcel_hr/page/tradexcel_mobile_attendance/tradexcel_mobile_attendance.js'


def test_evidence_state_mapping():
    source = SOURCE.read_text().split('frappe.pages[')[0]
    program = r'''
const assert=require('node:assert/strict');const __=x=>x;
SOURCE
assert.equal(tradexMobileEvidenceState('IN',{},true).kind,'queued');
assert.match(tradexMobileEvidenceState('IN',{},true).detail,/not yet been received/);
assert.equal(tradexMobileEvidenceState('IN',{custom_tradex_time_status:'Trusted',custom_tradex_review_status:'Not Required'}).title,'Check-in saved');
assert.equal(tradexMobileEvidenceState('OUT',{}).title,'Check-out saved');
assert.equal(tradexMobileEvidenceState('OUT',{custom_tradex_review_status:'Pending'}).title,'Check-out received — needs review');
for(const row of [{custom_tradex_review_status:'Pending'},{custom_tradex_time_status:'Flagged'},{skip_auto_attendance:1},{skip_auto_attendance:'1'},{custom_tradex_location_status:'Time Review Required'}]) assert.equal(tradexMobileEvidenceState('IN',row).kind,'review');
assert.equal(tradexMobileEvidenceState('OUT',{custom_tradex_review_status:'Approved',custom_tradex_time_status:'Flagged',skip_auto_attendance:0}).kind,'saved');
assert.equal(tradexMobileEvidenceState('IN',{custom_tradex_review_status:'Rejected',skip_auto_attendance:1}).kind,'rejected');
assert.equal(tradexMobileEvidenceState('IN',{custom_tradex_review_status:'Approved',skip_auto_attendance:1}).kind,'review');
assert.equal(tradexMobileEvidenceState('IN',{custom_tradex_time_status:'Blocked'}).kind,'rejected');
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
    replay=source[source.index('  async function replayQueuedCheckin'):source.index('  function refreshButton')]
    program=r'''
const assert=require('node:assert/strict');
const __=x=>x;const navigator={onLine:true};let offlineFlushInProgress=false;
let context={next_action:'OUT'};let calls=0;const shown=[];
const rows=new Map([['pending',{sync_id:'pending',log_type:'IN'}],['blocked',{sync_id:'blocked',log_type:'OUT'}]]);
const queuedCheckins=async()=>[...rows.values()];
const cleanupOfflineEvidence=async()=>{};
const deleteQueuedCheckin=async id=>rows.delete(id);
const discardQueuedEvidence=async(item,message)=>rows.set(item.sync_id,{sync_id:item.sync_id,retryable:false,last_error:message});
const isNetworkError=e=>e.status===0;
const updateQueueStatus=async()=>{};const refreshButton=()=>{};
const showSuccessState=(log,doc)=>shown.push(doc);
const frappe={call:async({args})=>{
 calls++;
 if(args.sync_id==='blocked') throw {status:417};
 return {message:{name:'synthetic',custom_tradex_review_status:'Pending',skip_auto_attendance:1}};
}};
REPLAY
(async()=>{
 await flushOfflineQueue();
 assert.equal(calls,2);assert.equal(shown[0].custom_tradex_review_status,'Pending');
 assert.equal(shown[0].skip_auto_attendance,1);
 assert.equal(shown[1].custom_tradex_review_status,'Rejected');
 assert.equal(rows.get('blocked').retryable,false);assert.equal(rows.has('pending'),false);
 await flushOfflineQueue();assert.equal(calls,2);
})().catch(e=>{console.error(e);process.exit(1)});
'''.replace('REPLAY',replay)
    subprocess.run(['node','-e',program],check=True,capture_output=True,text=True)
