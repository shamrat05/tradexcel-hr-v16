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


def test_live_locations_script_registers_with_frappe_page_name():
    page = json.loads((ROOT / "tradex_live_locations" / "tradex_live_locations.json").read_text())
    script = (ROOT / "tradex_live_locations" / "tradex_live_locations.js").read_text()
    assert f'frappe.pages["{page["page_name"]}"]' in script
