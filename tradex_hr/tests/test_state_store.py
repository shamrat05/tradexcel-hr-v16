import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from tradex_hr.tradexcel_hr.biometric.state_store import SyncStateStore


def test_cursors_are_monotonic_and_separate():
    with tempfile.TemporaryDirectory() as directory:
        with SyncStateStore(str(Path(directory) / "state.sqlite3")) as store:
            assert store.advance_cursor("senseface", "SN1", 10) == 10
            assert store.advance_cursor("senseface", "SN1", 7) == 10
            assert store.get_cursor("senseface", "SN1") == 10
            assert store.get_cursor("senseface", "SN2") == 0


def test_failed_event_blocks_contiguous_success_cursor():
    with tempfile.TemporaryDirectory() as directory:
        with SyncStateStore(str(Path(directory) / "state.sqlite3")) as store:
            for source_id, status in [(1, "inserted"), (2, "failed"), (3, "inserted")]:
                store.record_event(f"SN1:{source_id}", "senseface", "SN1", source_id,
                                   {"id": source_id}, status=status)
            assert store.advance_success_cursor("senseface", "SN1") == 1
            assert store.get_cursor("senseface", "SN1", "success") == 1


def test_retryable_events_include_unmapped_and_failed_only():
    with tempfile.TemporaryDirectory() as directory:
        with SyncStateStore(str(Path(directory) / "state.sqlite3")) as store:
            for source_id, status in [(1, "inserted"), (2, "unmapped"), (3, "failed"), (4, "duplicate")]:
                store.record_event(f"SN1:{source_id}", "senseface", "SN1", source_id,
                                   {"id": source_id}, status=status)
            assert [row["source_id"] for row in store.retryable_events("senseface", "SN1")] == [2, 3]


def test_success_cursor_allows_global_id_gaps_between_devices():
    with tempfile.TemporaryDirectory() as directory:
        with SyncStateStore(str(Path(directory) / "state.sqlite3")) as store:
            for source_id in (10, 12):
                store.record_event(f"SN1:{source_id}", "senseface", "SN1", source_id,
                                   {"id": source_id}, status="inserted")
            assert store.advance_success_cursor("senseface", "SN1") == 12
