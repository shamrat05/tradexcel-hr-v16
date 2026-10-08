"""Lossless multi-device SenseFace → Frappe checkin synchronizer.

The legacy ``bridge_worker.py`` remains available for compatibility. This
worker is the production path: it treats delivery as at-least-once and makes
the Frappe side effect idempotent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime, timezone
from typing import Any

from .state_store import SyncStateStore

SOURCE = "senseface"
DEFAULT_BRIDGE_DB = os.getenv("SENSEFACE_BRIDGE_DB")
DEFAULT_STATE_FILE = os.getenv("WORKFORCE_SYNC_STATE_FILE")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalise_log_type(status: Any) -> str | None:
    value = str(status or "").strip().lower()
    if value in {"0", "in", "checkin", "check-in", "entry"}:
        return "IN"
    if value in {"1", "out", "checkout", "check-out", "exit"}:
        return "OUT"
    return None


def event_key(punch: Mapping[str, Any]) -> str:
    device = str(punch.get("serial_number") or "unknown-device")
    source_id = punch.get("id")
    if source_id not in (None, ""):
        return f"{device}:{source_id}"
    stable = "\0".join(str(punch.get(key, "")) for key in (
        "employee_id", "event_time", "status", "verify_mode", "work_code", "raw_line",
    ))
    digest = hashlib.sha256(stable.encode("utf-8")).hexdigest()
    return f"{device}:hash:{digest}"


def biometric_map_key(punch: Mapping[str, Any]) -> tuple[str, str]:
    """Return the device-scoped identity key carried by one punch."""
    return (
        str(punch.get("serial_number") or "unknown-device").strip(),
        str(punch.get("employee_id") or "").strip(),
    )


def _safe_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: {str(exc)[:240]}"


def process_punches(
    punches: Iterable[Mapping[str, Any]], *, state: SyncStateStore,
    source: str, scope: str,
    employee_map: Mapping[tuple[str, str], Mapping[str, Any] | None],
    insert_checkin: Callable[[Mapping[str, Any], Mapping[str, Any], str | None], str],
) -> dict[str, int]:
    """Process a batch without advancing past failed or unmapped events."""
    counts = defaultdict(int)
    for punch in punches:
        key = event_key(punch)
        existing = state.get_event(key)
        if existing and existing["status"] in {"inserted", "duplicate"}:
            counts["already_done"] += 1
            continue
        source_id = punch.get("id")
        try:
            source_id = int(source_id) if source_id not in (None, "") else None
        except (TypeError, ValueError):
            source_id = None
        if not existing:
            state.record_event(key, source, scope, source_id, dict(punch), status="pending")
        else:
            state.set_event_status(key, "pending")

        employee = employee_map.get(biometric_map_key(punch))
        if not employee:
            state.set_event_status(key, "unmapped", "No unique Employee matches the biometric PIN")
            counts["unmapped"] += 1
            continue
        try:
            result = insert_checkin(employee, punch, normalise_log_type(punch.get("status")))
            if result not in {"inserted", "duplicate"}:
                raise ValueError(f"Unexpected checkin result: {result}")
        except Exception as exc:  # noqa: BLE001 - isolate one bad punch for retry
            state.set_event_status(key, "failed", _safe_error(exc))
            counts["failed"] += 1
            continue
        state.set_event_status(key, result)
        counts[result] += 1

    state.advance_success_cursor(source, scope)
    return dict(counts)


class ReliableBiometricWorker:
    def __init__(
        self, *, bridge_url: str = "http://127.0.0.1:8090", sqlite_path: str | None = None,
        api_key: str | None = None, state_path: str | None = DEFAULT_STATE_FILE,
        site: str | None = None, sites_path: str | None = None,
        batch_size: int = 500, device_serials: Iterable[str] | None = None,
        frappe_module: Any | None = None,
    ):
        self.bridge_url = bridge_url.rstrip("/")
        self.sqlite_path = sqlite_path or DEFAULT_BRIDGE_DB
        self.api_key = api_key or os.getenv("SENSEFACE_API_KEY", "")
        self.site = site or os.getenv("FRAPPE_SITE")
        self.sites_path = sites_path or os.getenv(
            "FRAPPE_SITES_PATH", os.path.join(os.getcwd(), "sites")
        )
        self.batch_size = max(1, min(int(batch_size), 5000))
        self.device_serials = [str(value) for value in (device_serials or []) if str(value)]
        if not state_path:
            raise ValueError("Set --state-file or WORKFORCE_SYNC_STATE_FILE to a persistent path")
        self.state = SyncStateStore(state_path)
        self.frappe = frappe_module or self._load_frappe()

    def _load_frappe(self) -> Any:
        import frappe
        if not self.site:
            raise ValueError("Set --site or FRAPPE_SITE before starting biometric sync")
        if getattr(frappe.local, "site", None) != self.site:
            frappe.init(site=self.site, sites_path=self.sites_path, force=True)
        if not getattr(frappe.local, "db", None):
            frappe.connect()
        return frappe

    def close(self) -> None:
        self.state.close()

    def _sqlite(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.sqlite_path, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=30000")
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def _discover_devices(self) -> list[str]:
        if self.device_serials:
            return self.device_serials
        if not self.sqlite_path or not os.path.exists(self.sqlite_path):
            try:
                req = urllib.request.Request(f"{self.bridge_url}/health",
                                              headers={"X-API-Key": self.api_key})
                with urllib.request.urlopen(req, timeout=10) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                devices = [str(row.get("serial_number")) for row in payload.get("devices", [])
                           if row.get("serial_number")]
                if devices:
                    return devices
            except (OSError, ValueError, TypeError):
                pass
            raise RuntimeError("No devices were returned by the bridge. Configure a device or pass --device.")
        with self._sqlite() as con:
            rows = con.execute(
                "SELECT DISTINCT serial_number FROM attendance WHERE serial_number IS NOT NULL ORDER BY serial_number"
            ).fetchall()
        return [str(row[0]) for row in rows]

    def _fetch_sqlite(self, device: str) -> list[dict[str, Any]]:
        cursor = self.state.get_cursor(SOURCE, device, "scan")
        with self._sqlite() as con:
            rows = con.execute(
                """SELECT id,serial_number,employee_id,event_time,status,verify_mode,work_code,
                   reserved,raw_line,received_at FROM attendance
                   WHERE serial_number=? AND id>? ORDER BY id ASC LIMIT ?""",
                (device, cursor, self.batch_size),
            ).fetchall()
        return [dict(row) for row in rows]

    def _fetch_http(self, device: str) -> list[dict[str, Any]]:
        cursor = self.state.get_cursor(SOURCE, device, "scan")
        params = urllib.parse.urlencode({
            "after_id": cursor, "limit": self.batch_size, "serial_number": device,
        })
        req = urllib.request.Request(
            f"{self.bridge_url}/api/v1/attendance?{params}",
            headers={"X-API-Key": self.api_key}, method="GET",
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        rows = payload.get("data", payload) if isinstance(payload, dict) else payload
        return [dict(row) for row in rows if str(row.get("serial_number", device)) == device]

    def _fetch(self, device: str) -> list[dict[str, Any]]:
        if self.sqlite_path and os.path.exists(self.sqlite_path):
            return self._fetch_sqlite(device)
        return self._fetch_http(device)

    def _employee_map(self) -> dict[tuple[str, str], Mapping[str, Any] | None]:
        records = self.frappe.db.sql(
            """SELECT a.name AS assignment, a.employee, a.biometric_id,
                      d.device_serial, e.employee_name, e.company
                 FROM `tabWorkforce Employee Biometric` a
                 JOIN `tabWorkforce Biometric Device` d ON d.name=a.device
                 JOIN `tabEmployee` e ON e.name=a.employee
                WHERE a.enabled=1 AND d.enabled=1
                  AND d.device_serial IS NOT NULL AND d.device_serial != ''
                  AND a.biometric_id IS NOT NULL AND a.biometric_id != ''""",
            as_dict=True,
        )
        grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
        for record in records:
            key = (str(record["device_serial"]).strip(), str(record["biometric_id"]).strip())
            grouped[key].append(record)
        return {key: rows[0] if len(rows) == 1 else None for key, rows in grouped.items()}

    def _insert_checkin(
        self, employee: Mapping[str, Any], punch: Mapping[str, Any], log_type: str | None,
    ) -> str:
        employee_name = employee.get("employee_name") or ""
        device_id = str(punch.get("serial_number") or "SenseFace-2A")
        timestamp = punch.get("event_time")
        exists = self.frappe.db.sql(
            """SELECT name FROM `tabEmployee Checkin`
               WHERE employee=%s AND time=%s AND device_id=%s LIMIT 1""",
            (employee["employee"], timestamp, device_id),
        )
        if exists:
            return "duplicate"
        doc = self.frappe.get_doc({
            "doctype": "Employee Checkin", "employee": employee["employee"],
            "employee_name": employee_name, "time": timestamp, "device_id": device_id,
            "log_type": log_type, "skip_auto_attendance": 0,
        })
        doc.insert(ignore_permissions=True)
        self.frappe.db.commit()
        return "inserted"

    def _update_device_status(self, device: str, counts: Mapping[str, int]) -> None:
        """Reflect bridge delivery state in the Frappe-editable device record."""
        if not self.frappe.db.exists("DocType", "Workforce Biometric Device"):
            return
        status = "Error" if counts.get("failed") else "Warning" if counts.get("unmapped") else "Healthy"
        name = self.frappe.db.get_value("Workforce Biometric Device",
                                        {"device_serial": device}, "name")
        if name:
            values = {
                "last_seen": self.frappe.utils.now_datetime(),
                "last_sync_status": status,
                "last_successful_event_id": self.state.get_cursor(SOURCE, device, "success"),
                "last_sync_error": ("One or more punches need retry or PIN mapping." if status != "Healthy" else ""),
            }
            for fieldname, value in values.items():
                self.frappe.db.set_value("Workforce Biometric Device", name, fieldname, value,
                                         update_modified=False)

    def sync_once(self) -> dict[str, Any]:
        total = defaultdict(int)
        per_device: dict[str, dict[str, int]] = {}
        employee_map = self._employee_map()
        for device in self._discover_devices():
            try:
                retry_rows = self.state.retryable_events(SOURCE, device, self.batch_size)
                retry_punches = [json.loads(row["payload_json"]) for row in retry_rows]
                new_punches = self._fetch(device)
                if new_punches:
                    numeric_ids = [int(p["id"]) for p in new_punches if str(p.get("id", "")).isdigit()]
                    if numeric_ids:
                        self.state.advance_cursor(SOURCE, device, max(numeric_ids), "scan")
                counts = process_punches(
                    [*retry_punches, *new_punches], state=self.state, source=SOURCE,
                    scope=device, employee_map=employee_map, insert_checkin=self._insert_checkin,
                )
            except Exception as exc:  # noqa: BLE001 - isolate one device from the cycle
                counts = {"failed": 1}
                print(json.dumps({"at": utc_now(), "event": "device_sync_failed",
                                  "device": device, "error": _safe_error(exc)}, sort_keys=True))
            per_device[device] = counts
            try:
                self._update_device_status(device, counts)
            except Exception as exc:  # noqa: BLE001 - status must not hide punch delivery
                print(json.dumps({"at": utc_now(), "event": "device_status_update_failed",
                                  "device": device, "error": _safe_error(exc)}, sort_keys=True))
            for key, value in counts.items():
                total[key] += value
        result = {"at": utc_now(), "devices": per_device, "totals": dict(total)}
        print(json.dumps(result, sort_keys=True))
        return result

    def run_daemon(self, interval: int = 30) -> None:
        while True:
            try:
                self.sync_once()
            except Exception as exc:  # noqa: BLE001 - daemon must remain alive
                print(json.dumps({"at": utc_now(), "event": "sync_cycle_failed",
                                  "error": _safe_error(exc)}, sort_keys=True))
            time.sleep(max(5, interval))


def main() -> None:
    parser = argparse.ArgumentParser(description="Lossless multi-device SenseFace sync")
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument("--interval", type=int, default=30)
    parser.add_argument("--url", default="http://127.0.0.1:8090")
    parser.add_argument("--db", default=None)
    parser.add_argument("--site", default=None, help="Frappe site (or FRAPPE_SITE)")
    parser.add_argument("--sites-path", default=None, help="Frappe sites directory (or FRAPPE_SITES_PATH)")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--state-file", default=DEFAULT_STATE_FILE)
    parser.add_argument("--device", action="append", dest="devices", default=[])
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()
    worker = ReliableBiometricWorker(
        bridge_url=args.url, sqlite_path=args.db, api_key=args.api_key,
        state_path=args.state_file, batch_size=args.batch_size,
        device_serials=args.devices, site=args.site, sites_path=args.sites_path,
    )
    try:
        if args.daemon:
            worker.run_daemon(args.interval)
        else:
            worker.sync_once()
    finally:
        worker.close()


if __name__ == "__main__":
    main()
