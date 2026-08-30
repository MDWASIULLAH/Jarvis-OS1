"""Companion pairing and event inbox.

The native Android/iOS app is intentionally outside this Python backend. This
module gives it a secure, local protocol without storing raw device tokens.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CompanionService:
    def __init__(self, db_path: Path):
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(str(db_path), check_same_thread=False)
        self._connection.execute(
            """CREATE TABLE IF NOT EXISTS pairing_codes (
               code_hash TEXT PRIMARY KEY, expires_at TEXT NOT NULL
            )"""
        )
        self._connection.execute(
            """CREATE TABLE IF NOT EXISTS companion_devices (
               id TEXT PRIMARY KEY, label TEXT NOT NULL, platform TEXT NOT NULL,
               token_hash TEXT NOT NULL, created_at TEXT NOT NULL, last_seen TEXT NOT NULL,
               capabilities_json TEXT NOT NULL
            )"""
        )
        self._connection.execute(
            """CREATE TABLE IF NOT EXISTS companion_events (
               id TEXT PRIMARY KEY, device_id TEXT NOT NULL, created_at TEXT NOT NULL,
               event_type TEXT NOT NULL, payload_json TEXT NOT NULL
            )"""
        )
        self._connection.commit()

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def create_pairing_code(self, ttl_seconds: int = 300) -> dict[str, Any]:
        code = f"{secrets.randbelow(1_000_000):06d}"
        expires_at = _now() + timedelta(seconds=max(30, min(ttl_seconds, 900)))
        with self._lock:
            self._connection.execute("DELETE FROM pairing_codes WHERE expires_at < ?", (_now().isoformat(),))
            self._connection.execute(
                "INSERT INTO pairing_codes (code_hash, expires_at) VALUES (?, ?)",
                (self._hash(code), expires_at.isoformat()),
            )
            self._connection.commit()
        return {"code": code, "expires_at": expires_at.isoformat()}

    def pair(self, code: str, label: str, platform: str, capabilities: list[str] | None = None) -> dict[str, Any] | None:
        code_hash = self._hash(code.strip())
        with self._lock:
            row = self._connection.execute(
                "SELECT expires_at FROM pairing_codes WHERE code_hash = ?", (code_hash,)
            ).fetchone()
            self._connection.execute("DELETE FROM pairing_codes WHERE code_hash = ?", (code_hash,))
            self._connection.commit()
        if row is None or row[0] < _now().isoformat():
            return None
        device_id = str(uuid.uuid4())
        token = secrets.token_urlsafe(32)
        now = _now().isoformat()
        with self._lock:
            self._connection.execute(
                """INSERT INTO companion_devices
                   (id, label, platform, token_hash, created_at, last_seen, capabilities_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (device_id, label.strip() or "Unnamed device", platform.strip().lower(), self._hash(token), now, now, json.dumps(capabilities or [])),
            )
            self._connection.commit()
        return {"device_id": device_id, "access_token": token, "paired_at": now}

    def authenticate(self, access_token: str) -> dict[str, Any] | None:
        token_hash = self._hash(access_token)
        with self._lock:
            row = self._connection.execute(
                """SELECT id, label, platform, created_at, last_seen, capabilities_json
                   FROM companion_devices WHERE token_hash = ?""",
                (token_hash,),
            ).fetchone()
            if row:
                self._connection.execute("UPDATE companion_devices SET last_seen = ? WHERE id = ?", (_now().isoformat(), row[0]))
                self._connection.commit()
        return self._device_dict(row) if row else None

    def devices(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT id, label, platform, created_at, last_seen, capabilities_json FROM companion_devices ORDER BY last_seen DESC"
            ).fetchall()
        return [self._device_dict(row) for row in rows]

    def record_event(self, device_id: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        event = {"id": str(uuid.uuid4()), "device_id": device_id, "created_at": _now().isoformat(), "event_type": event_type}
        with self._lock:
            self._connection.execute(
                "INSERT INTO companion_events (id, device_id, created_at, event_type, payload_json) VALUES (?, ?, ?, ?, ?)",
                (event["id"], device_id, event["created_at"], event_type, json.dumps(payload)),
            )
            self._connection.commit()
        return event | {"payload": payload}

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    @staticmethod
    def _device_dict(row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "id": row[0],
            "label": row[1],
            "platform": row[2],
            "created_at": row[3],
            "last_seen": row[4],
            "capabilities": json.loads(row[5]),
        }
