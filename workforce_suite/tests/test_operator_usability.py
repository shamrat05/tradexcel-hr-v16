"""Operator contract: stale previews cannot authorize a different correction."""
import csv
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_attendance_preview_rejects_changed_inputs_and_requires_fresh_confirmation():
    subprocess.run(['node', str(Path(__file__).parent / 'js' / 'attendance_preview.cjs'),
                    str(ROOT / 'workforce_suite/report/workforce_daily_attendance_board/workforce_daily_attendance_board.js')], check=True)


def test_bangla_catalog_uses_frappe_and_preserves_placeholders():
    from frappe.translate import get_translations_from_csv
    rows = list(csv.reader((ROOT / 'translations/bn.csv').open()))
    assert len({row[0] for row in rows}) == len(rows)
    for source, translated in rows:
        assert translated and re.search(r'[\u0980-\u09ff]', translated)
        assert re.findall(r'\{\d+\}', source) == re.findall(r'\{\d+\}', translated)
    actual = get_translations_from_csv('bn', 'workforce_suite')
    assert actual['Create draft requests'] == dict(rows)['Create draft requests']


def test_bundled_attendance_ui_and_stored_metadata_agree():
    path = ROOT / 'workforce_suite/report/workforce_daily_attendance_board/workforce_daily_attendance_board'
    assert json.loads(path.with_suffix('.json').read_text())['javascript'] == path.with_suffix('.js').read_text()
