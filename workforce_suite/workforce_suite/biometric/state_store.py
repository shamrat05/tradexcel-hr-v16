"""Durable, replay-safe state for incremental synchronizers.

The store is intentionally independent of Frappe. It records what was seen,
what succeeded, and what needs retrying so a process crash cannot turn a
partial batch into an apparently complete sync.
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, Self


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SyncStateStore:
    def __init__(self, path: str):
        self.path = os.path.abspath(os.path.expanduser(path))
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.con = sqlite3.connect(self.path, timeout=30)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA busy_timeout=30000")
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.execute("PRAGMA synchronous=FULL")
        self.con.executescript("""
        CREATE TABLE IF NOT EXISTS sync_cursors(
          source TEXT NOT NULL, scope TEXT NOT NULL, cursor_type TEXT NOT NULL,
          cursor_value INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL,
          PRIMARY KEY(source, scope, cursor_type));
        CREATE TABLE IF NOT EXISTS sync_events(
          event_key TEXT PRIMARY KEY, source TEXT NOT NULL, scope TEXT NOT NULL,
          source_id INTEGER, payload_json TEXT NOT NULL, status TEXT NOT NULL,
          attempts INTEGER NOT NULL DEFAULT 0, error TEXT, first_seen TEXT NOT NULL,
          updated_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS sync_events_retry_idx
          ON sync_events(source, scope, status, updated_at);
        """)
        self.con.commit()

    def get_cursor(self, source: str, scope: str, cursor_type: str = "scan") -> int:
        row = self.con.execute(
            "SELECT cursor_value FROM sync_cursors WHERE source=? AND scope=? AND cursor_type=?",
            (source, scope, cursor_type),
        ).fetchone()
        return int(row["cursor_value"]) if row else 0

    def advance_cursor(self, source: str, scope: str, value: int, cursor_type: str = "scan") -> int:
        """Advance monotonically; a retry can never move a cursor backward."""
        current = self.get_cursor(source, scope, cursor_type)
        if value <= current:
            return current
        self.con.execute(
            """INSERT INTO sync_cursors(source,scope,cursor_type,cursor_value,updated_at)
               VALUES(?,?,?,?,?) ON CONFLICT(source,scope,cursor_type) DO UPDATE SET
               cursor_value=excluded.cursor_value, updated_at=excluded.updated_at""",
            (source, scope, cursor_type, value, utc_now()),
        )
        self.con.commit()
        return value

    def record_event(
        self, event_key: str, source: str, scope: str, source_id: int | None,
        payload: Mapping[str, Any], status: str = "pending", error: str | None = None,
    ) -> None:
        now = utc_now()
        self.con.execute(
            """INSERT INTO sync_events(event_key,source,scope,source_id,payload_json,status,
               attempts,error,first_seen,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(event_key) DO UPDATE SET payload_json=excluded.payload_json,
               status=excluded.status, error=excluded.error,
               updated_at=excluded.updated_at""",
            (event_key, source, scope, source_id, json.dumps(payload, sort_keys=True, default=str),
             status, 0, error, now, now),
        )
        self.con.commit()

    def set_event_status(self, event_key: str, status: str, error: str | None = None) -> None:
        self.con.execute(
            """UPDATE sync_events SET status=?,error=?,attempts=attempts+1,updated_at=?
               WHERE event_key=?""",
            (status, error, utc_now(), event_key),
        )
        self.con.commit()

    def get_event(self, event_key: str) -> sqlite3.Row | None:
        return self.con.execute(
            "SELECT * FROM sync_events WHERE event_key=?", (event_key,)
        ).fetchone()

    def retryable_events(self, source: str, scope: str, limit: int = 500) -> list[sqlite3.Row]:
        return self.con.execute(
            """SELECT * FROM sync_events WHERE source=? AND scope=?
               AND status IN ('pending','failed','unmapped')
               ORDER BY COALESCE(source_id, 0), first_seen LIMIT ?""",
            (source, scope, limit),
        ).fetchall()

    def advance_success_cursor(self, source: str, scope: str) -> int:
        """Move the contiguous successful high-water mark only.

        A later successful event cannot hide an earlier failed event. This is
        the integrity property missing from the legacy worker.
        """
        current = self.get_cursor(source, scope, "success")
        rows = self.con.execute(
            """SELECT source_id,status FROM sync_events WHERE source=? AND scope=?
               AND source_id>? ORDER BY source_id ASC""",
            (source, scope, current),
        ).fetchall()
        next_value = current
        if current == 0 and rows:
            # Device databases commonly use one global AUTOINCREMENT across
            # all terminals. Per-device IDs therefore have legitimate gaps.
            next_value = int(rows[0]["source_id"]) - 1
        for row in rows:
            source_id = row["source_id"]
            if source_id is None:
                break
            if row["status"] not in ("inserted", "duplicate"):
                break
            next_value = int(source_id)
        return self.advance_cursor(source, scope, next_value, "success")

    def close(self) -> None:
        self.con.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
