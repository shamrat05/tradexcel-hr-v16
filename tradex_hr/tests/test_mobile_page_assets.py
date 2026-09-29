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


def test_custom_field_pages_use_native_desk_theme_tokens():
    css = (ROOT.parents[2] / "tradex_hr" / "public" / "css" / "tradex_hr.bundle.css").read_text()
    mobile_script = (ROOT / "tradexcel_mobile_attendance" / "tradexcel_mobile_attendance.js").read_text()
    live_script = (ROOT / "tradex_live_locations" / "tradex_live_locations.js").read_text()
    assert 'class="tradex-mobile-attendance' in mobile_script
    assert 'class="container-fluid tradex-live-locations"' in live_script
    assert '<div class="card"><div class="table-responsive"><table class="table' in live_script
    assert ".tradex-live-locations .card," in css
    assert ".tradex-mobile-attendance .card" in css
    assert "background-color: var(--card-bg)" in css
    assert "color: var(--text-color)" in css
    assert "border-color: var(--border-color)" in css
    assert "--bs-table-" not in css


def test_offline_selfie_cleanup_waits_for_policy_and_reuses_partial_upload():
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
let uploadCount = 0;
let failNextCall = false;
const withOfflineStore = async (_, action) => action({put: x => rows.set(x.sync_id, x), delete: id => rows.delete(id)});
const queuedCheckins = async () => [...rows.values()];
const deleteQueuedCheckin = async id => rows.delete(id);
const uploadSelfie = async () => { uploadCount++; return '/private/files/synthetic.jpg'; };
const frappe = {call: async options => {
 if (failNextCall) { failNextCall = false; const error = new Error('offline'); error.status = 0; throw error; }
 if (options.method.endsWith('mobile_checkin')) assert.equal(rows.get(options.args.sync_id).selfie_url, options.args.selfie);
 return {message: {name: 'synthetic'}};
}};
''' + cleanup + replay + '''
(async () => {
 const old = {sync_id:'old', queued_at:new Date().toISOString(), time:new Date(Date.now()-80*3600000).toISOString(), selfie_blob:'sensitive', selfie_url:null, latitude:23, longitude:90, retryable:true};
 context = null;
 rows.set(old.sync_id, {...old});
 await cleanupOfflineEvidence();
 assert.equal(rows.get('old').selfie_blob, 'sensitive');
 context = {offline_max_age_hours:120};
 await cleanupOfflineEvidence({allowAgeExpiry:true});
 assert.equal(rows.get('old').selfie_blob, 'sensitive');
 context = {offline_max_age_hours:72};
 await cleanupOfflineEvidence({allowAgeExpiry:true});
 assert.deepEqual(Object.keys(rows.get('old')).sort(), ['last_error','queued_at','retryable','sync_id']);
 const rejected = {...old, sync_id:'rejected', time:new Date().toISOString(), retryable:false};
 context = null;
 rows.set(rejected.sync_id, rejected);
 await cleanupOfflineEvidence();
 assert.equal(rows.get('rejected').selfie_blob, undefined);
 const malformed = {...old, sync_id:'malformed', time:'not-a-date'};
 rows.set(malformed.sync_id, malformed);
 await cleanupOfflineEvidence();
 assert.equal(rows.get('malformed').selfie_blob, 'sensitive');
 context = {offline_max_age_hours:120};
 await cleanupOfflineEvidence({allowAgeExpiry:true});
 assert.equal(rows.get('malformed').selfie_blob, undefined);
 const retained = {...old, sync_id:'retry', time:new Date().toISOString(), retryable:true};
 rows.set(retained.sync_id, retained);
 await cleanupOfflineEvidence();
 assert.equal(rows.get('retry').selfie_blob, 'sensitive');
 failNextCall = true;
 await assert.rejects(replayQueuedCheckin(rows.get('retry')));
 assert.equal(rows.get('retry').selfie_url, '/private/files/synthetic.jpg');
 assert.equal(uploadCount, 1);
 assert.deepEqual(await replayQueuedCheckin(rows.get('retry')), {name:'synthetic'});
 assert.equal(uploadCount, 1);
 assert.equal(rows.has('retry'), false);
})().catch(e => {console.error(e); process.exit(1)});
'''
    subprocess.run([node, '-e', program], check=True, capture_output=True, text=True)
    click = script[script.index('  actionEl.on("click"'):script.index('  window.addEventListener("online"')]
    assert click.index("queuedPayload.selfie_url = selfieUrl") < click.index("method: \"tradex_hr.tradexcel_hr.field_attendance_service.mobile_checkin\"")
