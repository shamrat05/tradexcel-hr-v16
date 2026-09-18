"""Contract test: the bridge worker's resolver and its check-in writer must agree.

This exists because they did not. `_employee_map()` selects
`a.name AS assignment, a.employee, ...` while `_insert_checkin()` read
`employee["name"]`, so every punch raised `KeyError: 'name'` and no Employee
Check-in could ever be created. Neither side was wrong on its own — only their
contract was, and nothing tested it.

The test is the guard for that contract: it fails loudly if either side changes
its keys without the other.

Run:
    cd ~/frappe-bench && env/bin/python \
        apps/tradex_hr/tradex_hr/tests/test_biometric_worker_contract.py

It never writes to Frappe: the check-in writer is stubbed and the worker's state
store is pointed at a throwaway database.
"""

from __future__ import annotations

import os
import sys
import tempfile

BENCH = os.environ.get("FRAPPE_BENCH", os.path.expanduser("~/frappe-bench"))
SYNC_DIR = os.path.join(BENCH, "sync")
SITE = os.environ.get("FRAPPE_SITE", "hrms.localhost")

if not os.path.isdir(SYNC_DIR):
    print(f"SKIP: runtime not present at {SYNC_DIR}")
    sys.exit(0)

sys.path.insert(0, SYNC_DIR)

import frappe  # noqa: E402
import reliable_bridge_worker as W  # noqa: E402

# Keys `_insert_checkin` needs from a resolver value. If the resolver's SQL
# projection changes, this list must change with it — that is the point.
REQUIRED_KEYS = {"employee"}

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{(' — ' + detail) if detail else ''}")
    if not ok:
        failures.append(name)


def main() -> int:
    frappe.init(site=SITE, sites_path=os.path.join(BENCH, "sites"))
    frappe.connect()
    frappe.set_user("Administrator")

    with tempfile.TemporaryDirectory() as tmp:
        worker = W.ReliableBiometricWorker(
            state_path=os.path.join(tmp, "state.sqlite3"), frappe_module=frappe
        )
        try:
            emap = worker._employee_map()

            # 1. resolver value carries every key the writer needs
            sample = next(iter(emap.values()), None)
            check("resolver returns at least one assignment", sample is not None)
            if sample is not None:
                missing = REQUIRED_KEYS - set(sample)
                check(
                    "resolver value exposes the keys _insert_checkin reads",
                    not missing,
                    f"missing {sorted(missing)}" if missing else f"keys={sorted(sample)}",
                )

            # 2. no ambiguous keys — a duplicate (serial, PIN) must read as None
            ambiguous = [k for k, v in emap.items() if v is None]
            check("no ambiguous (serial, PIN) keys", not ambiguous,
                  f"{len(ambiguous)} ambiguous" if ambiguous else f"{len(emap)} keys")

            # 3. the real writer path runs without KeyError, with the DB stubbed
            if emap:
                serial, pin = next(iter(emap))
                seen = []
                # call the REAL _insert_checkin but stop before it touches Frappe
                original_sql = worker.frappe.db.sql
                original_get_doc = worker.frappe.get_doc
                worker.frappe.db.sql = lambda *a, **k: []          # "no existing checkin"
                worker.frappe.get_doc = lambda d: seen.append(d) or _FakeDoc()
                try:
                    result = worker._insert_checkin(
                        emap[(serial, pin)],
                        {"serial_number": serial, "event_time": "2026-01-01 09:00:00"},
                        "IN",
                    )
                    check("_insert_checkin runs against the real resolver shape",
                          result == "inserted", f"result={result}")
                    check("the check-in it builds names a real Employee",
                          bool(seen) and seen[0].get("employee"),
                          str(seen[0].get("employee")) if seen else "nothing built")
                except Exception as exc:  # noqa: BLE001
                    check("_insert_checkin runs against the real resolver shape", False,
                          f"{type(exc).__name__}: {exc}")
                finally:
                    worker.frappe.db.sql = original_sql
                    worker.frappe.get_doc = original_get_doc
        finally:
            worker.close()

    print()
    if failures:
        print(f"FAILED: {len(failures)} contract check(s): {failures}")
        return 1
    print("OK: resolver and writer agree.")
    return 0


class _FakeDoc:
    def insert(self, **kwargs) -> None:  # noqa: D401
        return None


if __name__ == "__main__":
    sys.exit(main())
