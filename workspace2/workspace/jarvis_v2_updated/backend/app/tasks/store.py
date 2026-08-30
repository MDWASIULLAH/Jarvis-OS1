"""A small durable task queue used by the multi-agent orchestrator."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStore:
    """SQLite task persistence; it does not start any autonomous background work."""

    def __init__(self, db_path: Path):
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(str(db_path), check_same_thread=False)
        self._connection.execute(
            """CREATE TABLE IF NOT EXISTS agent_tasks (
               id TEXT PRIMARY KEY,
               created_at TEXT NOT NULL,
               updated_at TEXT NOT NULL,
               status TEXT NOT NULL,
               request_text TEXT NOT NULL,
               agents_json TEXT NOT NULL,
               result_json TEXT,
               error TEXT
            )"""
        )
        self._connection.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def create(self, request_text: str, agents: list[str]) -> dict[str, Any]:
        task_id = str(uuid.uuid4())
        now = self._now()
        with self._lock:
            self._connection.execute(
                """INSERT INTO agent_tasks
                   (id, created_at, updated_at, status, request_text, agents_json) VALUES (?, ?, ?, ?, ?, ?)""",
                (task_id, now, now, TaskStatus.QUEUED.value, request_text, json.dumps(agents)),
            )
            self._connection.commit()
        return self.get(task_id)  # type: ignore[return-value]

    def update(
        self,
        task_id: str,
        status: TaskStatus,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> dict[str, Any] | None:
        with self._lock:
            self._connection.execute(
                """UPDATE agent_tasks SET status = ?, updated_at = ?, result_json = ?, error = ? WHERE id = ?""",
                (status.value, self._now(), json.dumps(result) if result is not None else None, error, task_id),
            )
            self._connection.commit()
        return self.get(task_id)

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute(
                """SELECT id, created_at, updated_at, status, request_text, agents_json, result_json, error
                   FROM agent_tasks WHERE id = ?""",
                (task_id,),
            ).fetchone()
        return self._to_dict(row) if row else None

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 250))
        with self._lock:
            rows = self._connection.execute(
                """SELECT id, created_at, updated_at, status, request_text, agents_json, result_json, error
                   FROM agent_tasks ORDER BY created_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [self._to_dict(row) for row in rows]

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    @staticmethod
    def _to_dict(row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "id": row[0],
            "created_at": row[1],
            "updated_at": row[2],
            "status": row[3],
            "request_text": row[4],
            "agents": json.loads(row[5]),
            "result": json.loads(row[6]) if row[6] else None,
            "error": row[7],
        }
