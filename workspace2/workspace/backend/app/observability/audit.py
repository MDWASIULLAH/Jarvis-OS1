"""Append-only, redacted audit log for security-relevant JARVIS actions."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_SENSITIVE_PARTS = ("secret", "token", "password", "authorization", "api_key", "credential")


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[redacted]" if any(part in key.lower() for part in _SENSITIVE_PARTS) else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


class AuditLog:
    """Stores local audit entries without ever persisting secret material."""

    def __init__(self, db_path: Path):
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(str(db_path), check_same_thread=False)
        self._connection.execute(
            """CREATE TABLE IF NOT EXISTS audit_log (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               created_at TEXT NOT NULL,
               event_type TEXT NOT NULL,
               actor TEXT NOT NULL,
               outcome TEXT NOT NULL,
               detail_json TEXT NOT NULL
            )"""
        )
        self._connection.commit()

    def record(self, event_type: str, outcome: str, detail: dict[str, Any] | None = None, actor: str = "local-user") -> None:
        payload = json.dumps(_redact(detail or {}), ensure_ascii=False, sort_keys=True)
        with self._lock:
            self._connection.execute(
                "INSERT INTO audit_log (created_at, event_type, actor, outcome, detail_json) VALUES (?, ?, ?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(), event_type, actor, outcome, payload),
            )
            self._connection.commit()

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 500))
        with self._lock:
            rows = self._connection.execute(
                "SELECT id, created_at, event_type, actor, outcome, detail_json FROM audit_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": row[0],
                "created_at": row[1],
                "event_type": row[2],
                "actor": row[3],
                "outcome": row[4],
                "detail": json.loads(row[5]),
            }
            for row in rows
        ]

    def close(self) -> None:
        with self._lock:
            self._connection.close()
