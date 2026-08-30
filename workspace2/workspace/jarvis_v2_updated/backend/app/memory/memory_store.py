"""
memory/memory_store.py

Implements JARVIS Section 2.2 -- the three-tier memory system.

Tier 1 (short-term):  last N turns of the current session, in-memory only.
Tier 2 (long-term):   durable facts/preferences, persisted + encrypted in SQLite.
Tier 3 (predictive):  lightweight (action, hour, weekday) counts used to power
                      proactive suggestions like "you usually check email at 9am".
"""

from __future__ import annotations

import base64
import json
import os
import sqlite3
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class LocalEncryptor:
    """AES-256-GCM at rest. In a real deployment the key belongs in the OS
    keychain (e.g. via the `keyring` package) -- it's written to a local file
    here only so this scaffold runs standalone."""

    def __init__(self, key_path: Path):
        self.key_path = key_path
        if key_path.exists():
            self.key = key_path.read_bytes()
        else:
            self.key = AESGCM.generate_key(bit_length=256)
            key_path.parent.mkdir(parents=True, exist_ok=True)
            key_path.write_bytes(self.key)
        self.aead = AESGCM(self.key)

    def encrypt(self, plaintext: str) -> str:
        nonce = os.urandom(12)
        ct = self.aead.encrypt(nonce, plaintext.encode("utf-8"), None)
        return base64.b64encode(nonce + ct).decode("ascii")

    def decrypt(self, token: str) -> str:
        raw = base64.b64decode(token)
        nonce, ct = raw[:12], raw[12:]
        return self.aead.decrypt(nonce, ct, None).decode("utf-8")


@dataclass
class Turn:
    role: str
    content: str
    timestamp: float


class ShortTermMemory:
    """Tier 1 -- session context. Not persisted across restarts by design."""

    def __init__(self, max_turns: int = 20):
        self._turns: deque = deque(maxlen=max_turns)
        self.active_task: Optional[str] = None

    def add(self, role: str, content: str) -> None:
        self._turns.append(Turn(role, content, time.time()))

    def recent(self) -> list:
        return list(self._turns)


class LongTermMemory:
    """Tier 2 -- durable facts & preferences, encrypted at rest in SQLite.

    check_same_thread=False + an RLock matter here specifically: this object
    is built once at import time (main thread), but FastAPI runs sync route
    handlers in a worker threadpool -- a different thread on every request.
    Without both, the first real HTTP request throws
    sqlite3.ProgrammingError."""

    def __init__(self, db_path: Path, encryptor: LocalEncryptor):
        self.encryptor = encryptor
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS facts (
                key TEXT PRIMARY KEY,
                value_enc TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'general',
                updated_at TEXT NOT NULL
            )"""
        )
        self.conn.commit()

    def remember(self, key: str, value: str, category: str = "general") -> None:
        enc = self.encryptor.encrypt(value)
        with self._lock:
            self.conn.execute(
                """INSERT INTO facts (key, value_enc, category, updated_at) VALUES (?, ?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET
                     value_enc=excluded.value_enc,
                     category=excluded.category,
                     updated_at=excluded.updated_at""",
                (key, enc, category, datetime.now(timezone.utc).isoformat()),
            )
            self.conn.commit()

    def recall(self, key: str) -> Optional[str]:
        with self._lock:
            row = self.conn.execute("SELECT value_enc FROM facts WHERE key = ?", (key,)).fetchone()
        return self.encryptor.decrypt(row[0]) if row else None

    def forget(self, key: str) -> bool:
        with self._lock:
            cur = self.conn.execute("DELETE FROM facts WHERE key = ?", (key,))
            self.conn.commit()
        return cur.rowcount > 0

    def wipe_all(self) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM facts")
            self.conn.commit()

    def all_facts(self, category: Optional[str] = None) -> dict:
        with self._lock:
            if category:
                rows = self.conn.execute(
                    "SELECT key, value_enc FROM facts WHERE category = ?", (category,)
                ).fetchall()
            else:
                rows = self.conn.execute("SELECT key, value_enc FROM facts").fetchall()
        return {k: self.encryptor.decrypt(v) for k, v in rows}


class PredictiveMemory:
    """Tier 3 -- logs (action, hour, weekday) so JARVIS can learn routines and
    proactively suggest things, e.g. 'you usually check email around 9am'.
    Same check_same_thread=False + lock reasoning as LongTermMemory above."""

    def __init__(self, db_path: Path):
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS action_log (
                action TEXT NOT NULL,
                hour INTEGER NOT NULL,
                weekday INTEGER NOT NULL,
                ts TEXT NOT NULL
            )"""
        )
        self.conn.commit()

    def log_action(self, action: str, when: Optional[datetime] = None) -> None:
        when = when or datetime.now()
        with self._lock:
            self.conn.execute(
                "INSERT INTO action_log (action, hour, weekday, ts) VALUES (?, ?, ?, ?)",
                (action, when.hour, when.weekday(), when.isoformat()),
            )
            self.conn.commit()

    def routine_for_hour(self, hour: int, weekday: Optional[int] = None, min_occurrences: int = 3) -> list:
        with self._lock:
            if weekday is not None:
                rows = self.conn.execute(
                    """SELECT action, COUNT(*) c FROM action_log
                       WHERE hour = ? AND weekday = ?
                       GROUP BY action HAVING c >= ? ORDER BY c DESC""",
                    (hour, weekday, min_occurrences),
                ).fetchall()
            else:
                rows = self.conn.execute(
                    """SELECT action, COUNT(*) c FROM action_log
                       WHERE hour = ?
                       GROUP BY action HAVING c >= ? ORDER BY c DESC""",
                    (hour, min_occurrences),
                ).fetchall()
        return [r[0] for r in rows]


class PreferenceMemory:
    """Tier 4 -- user preferences store (voice settings, theme, behavior prefs)."""

    def __init__(self, db_path: Path):
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'general',
                updated_at TEXT NOT NULL
            )"""
        )
        self.conn.commit()

    def set(self, key: str, value: str, category: str = "general") -> None:
        with self._lock:
            self.conn.execute(
                """INSERT INTO preferences (key, value, category, updated_at) VALUES (?, ?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value, category=excluded.category, updated_at=excluded.updated_at""",
                (key, value, category, datetime.now(timezone.utc).isoformat()),
            )
            self.conn.commit()

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            row = self.conn.execute("SELECT value FROM preferences WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def get_all(self, category: Optional[str] = None) -> dict:
        with self._lock:
            if category:
                rows = self.conn.execute("SELECT key, value FROM preferences WHERE category = ?", (category,)).fetchall()
            else:
                rows = self.conn.execute("SELECT key, value FROM preferences").fetchall()
        return {r[0]: r[1] for r in rows}

    def delete(self, key: str) -> bool:
        with self._lock:
            cur = self.conn.execute("DELETE FROM preferences WHERE key = ?", (key,))
            self.conn.commit()
        return cur.rowcount > 0


class ConversationSummaries:
    """Tier 5 -- auto-generated summaries of past conversation turns."""

    def __init__(self, db_path: Path):
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS summaries (
                id TEXT PRIMARY KEY,
                user_text TEXT NOT NULL,
                jarvis_reply TEXT NOT NULL,
                intent TEXT NOT NULL DEFAULT '',
                summary TEXT NOT NULL DEFAULT '',
                tools_used TEXT NOT NULL DEFAULT '[]',
                ts TEXT NOT NULL
            )"""
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_summaries_ts ON summaries(ts)"
        )
        self.conn.commit()

    def record(
        self,
        session_id: str,
        user_text: str,
        jarvis_reply: str,
        intent: str = "",
        summary: str = "",
        tools_used: list = None,
    ) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO summaries (id, user_text, jarvis_reply, intent, summary, tools_used, ts) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    user_text[:2000],
                    jarvis_reply[:4000],
                    intent[:200],
                    summary[:1000],
                    json.dumps(tools_used or []),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            self.conn.commit()

    def recent(self, limit: int = 20) -> list[dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT id, intent, summary, tools_used, ts FROM summaries ORDER BY ts DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": r[0],
                "intent": r[1],
                "summary": r[2],
                "tools_used": json.loads(r[3]) if r[3] else [],
                "ts": r[4],
            }
            for r in rows
        ]

    def search(self, query: str, limit: int = 10) -> list[dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT id, user_text, jarvis_reply, intent, summary FROM summaries WHERE user_text LIKE ? OR jarvis_reply LIKE ? OR summary LIKE ? ORDER BY ts DESC LIMIT ?",
                (f"%{query}%", f"%{query}%", f"%{query}%", limit),
            ).fetchall()
        return [
            {"id": r[0], "user_text": r[1], "jarvis_reply": r[2], "intent": r[3], "summary": r[4]}
            for r in rows
        ]

    def count(self) -> int:
        with self._lock:
            return self.conn.execute("SELECT COUNT(*) FROM summaries").fetchone()[0]


class MemorySystem:
    """Facade wiring all five tiers together -- this is what the rest of the
    app talks to."""

    def __init__(self, data_dir: Path):
        data_dir = Path(data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        encryptor = LocalEncryptor(data_dir / "jarvis.key")
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory(data_dir / "long_term.db", encryptor)
        self.predictive = PredictiveMemory(data_dir / "predictive.db")
        self.preferences = PreferenceMemory(data_dir / "preferences.db")
        self.summaries = ConversationSummaries(data_dir / "summaries.db")
