import json
from pathlib import Path


ROOT = Path(__file__).parents[1] / "tradexcel_hr" / "page"


def test_mobile_attendance_script_registers_with_frappe_page_name():
    page = json.loads(
        (ROOT / "tradexcel_mobile_attendance" / "tradexcel_mobile_attendance.json").read_text()
    )
    script = (ROOT / "tradexcel_mobile_attendance" / "tradexcel_mobile_attendance.js").read_text()
    assert f'frappe.pages["{page["page_name"]}"]' in script
    assert 'accept="image/*" capture="user"' in script
    assert 'data-selfie-preview' in script
    assert 'URL.createObjectURL' in script
    assert 'data-attendance-form' in script
    assert 'data-success-state' in script
    assert 'showSuccessState' in script
    assert 'showCheckoutForm' in script
    assert 'selfieInput.val("")' in script
    assert 'const completedAction = context.next_action' in script
    assert 'showSuccessState(completedAction, checkin)' in script


def test_mobile_attendance_has_durable_offline_queue_contract():
    script = (ROOT / "tradexcel_mobile_attendance" / "tradexcel_mobile_attendance.js").read_text()
    assert "indexedDB" in script
    assert "tradex_mobile_attendance" in script
    assert "flushOfflineQueue" in script
    assert "sync_id" in script
    assert "queueOfflineCheckin" in script


def test_live_locations_script_registers_with_frappe_page_name():
    page = json.loads((ROOT / "tradex_live_locations" / "tradex_live_locations.json").read_text())
    script = (ROOT / "tradex_live_locations" / "tradex_live_locations.js").read_text()
    assert f'frappe.pages["{page["page_name"]}"]' in script


def test_offline_selfie_cleanup_executes_on_reject_expiry_and_replay():
    """Execute production functions with a deterministic in-memory IDB boundary."""
    import shutil
    import subprocess
    script = (ROOT / 'tradexcel_mobile_attendance/tradexcel_mobile_attendance.js').read_text()
    cleanup = script[script.index('  function offlineEventExpired'):script.index('  function isNetworkError')]
    replay = script[script.index('  async function replayQueuedCheckin'):script.index('  async function flushOfflineQueue')]
    node = shutil.which('node')
    assert node, 'Node is required for the offline evidence contract'
    program = '''
const assert = require('node:assert/strict');
let context = {offline_max_age_hours: 72};
const __ = x => x;
const rows = new Map();
const navigator = {onLine: true};
const withOfflineStore = async (_, action) => action({put: x => rows.set(x.sync_id, x)});
const queuedCheckins = async () => [...rows.values()];
const deleteQueuedCheckin = async id => rows.delete(id);
const frappe = {call: async () => ({message: {name: 'synthetic'}})};
''' + cleanup + replay + '''
(async () => {
 const payload = {sync_id:'expired', queued_at:new Date().toISOString(), time:new Date(Date.now()-73*3600000).toISOString(), selfie_blob:'sensitive', employee:'synthetic', latitude:23};
 rows.set(payload.sync_id, payload);
 await cleanupOfflineEvidence();
 assert.deepEqual(Object.keys(rows.get('expired')).sort(), ['last_error','queued_at','retryable','sync_id']);
 const rejected = {...payload, sync_id:'rejected', time:new Date().toISOString(), retryable:false};
 rows.set(rejected.sync_id, rejected);
 await cleanupOfflineEvidence();
 assert.equal(rows.get('rejected').selfie_blob, undefined);
 const success = {...payload, sync_id:'success', selfie_blob:null, time:new Date().toISOString()};
 rows.set(success.sync_id, success);
 assert.equal(await replayQueuedCheckin(success), true);
 assert.equal(rows.has('success'), false);
 const retained = {...payload, sync_id:'retry', time:new Date().toISOString(), retryable:true};
 rows.set(retained.sync_id, retained);
 await cleanupOfflineEvidence();
 assert.equal(rows.get('retry').selfie_blob, 'sensitive');
})().catch(e => {console.error(e); process.exit(1)});
'''
    subprocess.run([node, '-e', program], check=True, capture_output=True, text=True)
