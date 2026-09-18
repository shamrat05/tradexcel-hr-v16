import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from tradex_hr.tradexcel_hr.biometric.worker import event_key, normalise_log_type, process_punches
from tradex_hr.tradexcel_hr.biometric.state_store import SyncStateStore


def test_log_type_mapping_is_explicit():
    assert normalise_log_type("0") == "IN"
    assert normalise_log_type("checkout") == "OUT"
    assert normalise_log_type("unexpected") is None


def test_event_key_uses_device_and_source_id():
    punch = {"id": 12, "serial_number": "SN-A", "employee_id": "7"}
    assert event_key(punch) == "SN-A:12"
    assert event_key({"serial_number": "SN-A", "employee_id": "7", "event_time": "t"}).startswith("SN-A:hash:")


def test_unmapped_punch_does_not_advance_success_cursor():
    with tempfile.TemporaryDirectory() as directory:
        with SyncStateStore(str(Path(directory) / "state.sqlite3")) as state:
            result = process_punches([
                {"id": 1, "serial_number": "SN-A", "employee_id": "7", "event_time": "t", "status": "0"},
                {"id": 2, "serial_number": "SN-A", "employee_id": "8", "event_time": "t", "status": "0"},
            ], state=state, source="senseface", scope="SN-A",
                employee_map={("SN-A", "7"): {"name": "EMP-1"}, ("SN-A", "8"): None},
                insert_checkin=lambda employee, punch, log_type: "inserted")

            assert result == {"inserted": 1, "unmapped": 1}
            assert state.get_cursor("senseface", "SN-A", "success") == 1
            assert state.get_event("SN-A:2")["status"] == "unmapped"


def test_failed_punch_can_be_retried_without_duplicate_insert():
    with tempfile.TemporaryDirectory() as directory:
        with SyncStateStore(str(Path(directory) / "state.sqlite3")) as state:
            calls = []
            punch = {"id": 1, "serial_number": "SN-A", "employee_id": "7", "event_time": "t", "status": "0"}
            def fail_once(employee, value, log_type):
                calls.append(value["id"])
                if len(calls) == 1:
                    raise RuntimeError("temporary database failure")
                return "inserted"

            process_punches([punch], state=state, source="senseface", scope="SN-A",
                            employee_map={("SN-A", "7"): {"name": "EMP-1"}}, insert_checkin=fail_once)
            assert state.get_cursor("senseface", "SN-A", "success") == 0
            process_punches([punch], state=state, source="senseface", scope="SN-A",
                            employee_map={("SN-A", "7"): {"name": "EMP-1"}}, insert_checkin=fail_once)
            assert state.get_cursor("senseface", "SN-A", "success") == 1
            assert calls == [1, 1]


def test_same_pin_is_resolved_per_device_not_globally():
    with tempfile.TemporaryDirectory() as directory:
        with SyncStateStore(str(Path(directory) / "state.sqlite3")) as state:
            seen = []
            result = process_punches([
                {"id": 1, "serial_number": "SN-HO", "employee_id": "7",
                 "event_time": "2026-09-17 08:00:00", "status": "0"},
                {"id": 1, "serial_number": "SN-FACTORY", "employee_id": "7",
                 "event_time": "2026-09-17 08:01:00", "status": "0"},
            ], state=state, source="senseface", scope="SN-HO",
                employee_map={
                    ("SN-HO", "7"): {"name": "EMP-HO"},
                    ("SN-FACTORY", "7"): {"name": "EMP-FACTORY"},
                },
                insert_checkin=lambda employee, punch, log_type: (
                    seen.append((employee["name"], punch["serial_number"])) or "inserted"
                ))

            assert result == {"inserted": 2}
            assert seen == [("EMP-HO", "SN-HO"), ("EMP-FACTORY", "SN-FACTORY")]


def test_unassigned_device_pin_is_not_guessed_from_another_device():
    with tempfile.TemporaryDirectory() as directory:
        with SyncStateStore(str(Path(directory) / "state.sqlite3")) as state:
            result = process_punches([
                {"id": 1, "serial_number": "SN-NEW", "employee_id": "7",
                 "event_time": "2026-09-17 08:00:00", "status": "0"},
            ], state=state, source="senseface", scope="SN-NEW",
                employee_map={("SN-HO", "7"): {"name": "EMP-HO"}},
                insert_checkin=lambda employee, punch, log_type: "inserted")

            assert result == {"unmapped": 1}
            assert state.get_event("SN-NEW:1")["status"] == "unmapped"
