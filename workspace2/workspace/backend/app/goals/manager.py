"""
goals/manager.py

Dedicated Goal Manager.

Supports long-term goals, milestones, task hierarchies, dependencies,
progress tracking, completion percentages, daily/weekly/project objectives,
automatic reminders, and automatic planning.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional


class GoalStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class GoalPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class GoalScope(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    PROJECT = "project"
    LONG_TERM = "long_term"


@dataclass
class Goal:
    id: str
    title: str
    description: str = ""
    scope: GoalScope = GoalScope.PROJECT
    status: GoalStatus = GoalStatus.PENDING
    priority: GoalPriority = GoalPriority.MEDIUM
    parent_id: Optional[str] = None
    dependencies: list[str] = field(default_factory=list)
    tasks: list[str] = field(default_factory=list)
    milestones: list[dict] = field(default_factory=list)
    progress: float = 0.0
    target_date: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    completed_at: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "scope": self.scope.value,
            "status": self.status.value,
            "priority": self.priority.value,
            "parent_id": self.parent_id,
            "dependencies": self.dependencies,
            "tasks": self.tasks,
            "milestones": self.milestones,
            "progress": round(self.progress, 2),
            "target_date": self.target_date,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }


class GoalManager:
    """Manages goals, milestones, and task hierarchies."""

    def __init__(self, db_path: Path):
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def close(self) -> None:
        with self._lock:
            self.conn.close()

    def _init_db(self) -> None:
        with self._lock:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS goals (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    scope TEXT NOT NULL DEFAULT 'project',
                    status TEXT NOT NULL DEFAULT 'pending',
                    priority TEXT NOT NULL DEFAULT 'medium',
                    parent_id TEXT,
                    dependencies TEXT DEFAULT '[]',
                    tasks TEXT DEFAULT '[]',
                    milestones TEXT DEFAULT '[]',
                    progress REAL DEFAULT 0.0,
                    target_date TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    metadata TEXT DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_goals_scope ON goals(scope);
                CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status);
                CREATE INDEX IF NOT EXISTS idx_goals_parent ON goals(parent_id);
                CREATE INDEX IF NOT EXISTS idx_goals_priority ON goals(priority);
            """)
            self.conn.commit()

    def create(
        self,
        title: str,
        description: str = "",
        scope: GoalScope = GoalScope.PROJECT,
        priority: GoalPriority = GoalPriority.MEDIUM,
        parent_id: Optional[str] = None,
        target_date: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Goal:
        goal_id = str(uuid.uuid4())[:12]
        now = datetime.now(timezone.utc).isoformat()
        goal = Goal(
            id=goal_id,
            title=title,
            description=description,
            scope=scope,
            priority=priority,
            parent_id=parent_id,
            target_date=target_date,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        with self._lock:
            self.conn.execute(
                """INSERT INTO goals (id, title, description, scope, status, priority,
                   parent_id, dependencies, tasks, milestones, progress, target_date,
                   created_at, updated_at, completed_at, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    goal.id, goal.title, goal.description, goal.scope.value,
                    goal.status.value, goal.priority.value, goal.parent_id,
                    json.dumps(goal.dependencies), json.dumps(goal.tasks),
                    json.dumps(goal.milestones), goal.progress, goal.target_date,
                    goal.created_at, goal.updated_at, goal.completed_at,
                    json.dumps(goal.metadata),
                ),
            )
            self.conn.commit()
        return goal

    def get(self, goal_id: str) -> Optional[Goal]:
        with self._lock:
            row = self.conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
        return self._row_to_goal(row) if row else None

    def update(self, goal_id: str, **kwargs) -> Optional[Goal]:
        goal = self.get(goal_id)
        if not goal:
            return None

        allowed = {
            "title", "description", "scope", "status", "priority",
            "parent_id", "target_date", "metadata",
        }
        for key, value in kwargs.items():
            if key in allowed and hasattr(goal, key):
                if key == "scope" and isinstance(value, str):
                    value = GoalScope(value)
                elif key == "status" and isinstance(value, str):
                    value = GoalStatus(value)
                elif key == "priority" and isinstance(value, str):
                    value = GoalPriority(value)
                setattr(goal, key, value)

        goal.updated_at = datetime.now(timezone.utc).isoformat()
        if goal.status == GoalStatus.COMPLETED and not goal.completed_at:
            goal.completed_at = goal.updated_at

        with self._lock:
            self.conn.execute(
                """UPDATE goals SET title=?, description=?, scope=?, status=?, priority=?,
                   parent_id=?, target_date=?, updated_at=?, completed_at=?, metadata=?
                   WHERE id=?""",
                (
                    goal.title, goal.description, goal.scope.value,
                    goal.status.value, goal.priority.value, goal.parent_id,
                    goal.target_date, goal.updated_at, goal.completed_at,
                    json.dumps(goal.metadata), goal.id,
                ),
            )
            self.conn.commit()
        return goal

    def delete(self, goal_id: str) -> bool:
        with self._lock:
            cur = self.conn.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
            self.conn.execute("DELETE FROM goals WHERE parent_id = ?", (goal_id,))
            self.conn.commit()
        return cur.rowcount > 0

    def add_task(self, goal_id: str, task_id: str) -> bool:
        with self._lock:
            row = self.conn.execute("SELECT tasks FROM goals WHERE id = ?", (goal_id,)).fetchone()
            if not row:
                return False
            tasks = json.loads(row["tasks"]) if row["tasks"] else []
            if task_id not in tasks:
                tasks.append(task_id)
                self.conn.execute(
                    "UPDATE goals SET tasks = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(tasks), datetime.now(timezone.utc).isoformat(), goal_id),
                )
                self.conn.commit()
                self._recalc_progress(goal_id)
            return True

    def add_dependency(self, goal_id: str, dep_goal_id: str) -> bool:
        with self._lock:
            row = self.conn.execute("SELECT dependencies FROM goals WHERE id = ?", (goal_id,)).fetchone()
            if not row:
                return False
            deps = json.loads(row["dependencies"]) if row["dependencies"] else []
            if dep_goal_id not in deps and dep_goal_id != goal_id:
                deps.append(dep_goal_id)
                self.conn.execute(
                    "UPDATE goals SET dependencies = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(deps), datetime.now(timezone.utc).isoformat(), goal_id),
                )
                self.conn.commit()
            return True

    def add_milestone(self, goal_id: str, title: str, target_date: Optional[str] = None) -> Optional[str]:
        goal = self.get(goal_id)
        if not goal:
            return None
        milestone_id = str(uuid.uuid4())[:8]
        milestone = {
            "id": milestone_id,
            "title": title,
            "target_date": target_date,
            "completed": False,
            "completed_at": None,
        }
        goal.milestones.append(milestone)
        goal.updated_at = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self.conn.execute(
                "UPDATE goals SET milestones = ?, updated_at = ? WHERE id = ?",
                (json.dumps(goal.milestones), goal.updated_at, goal.id),
            )
            self.conn.commit()
            self._recalc_progress(goal_id)
        return milestone_id

    def complete_milestone(self, goal_id: str, milestone_id: str) -> bool:
        goal = self.get(goal_id)
        if not goal:
            return False
        for m in goal.milestones:
            if m.get("id") == milestone_id:
                m["completed"] = True
                m["completed_at"] = datetime.now(timezone.utc).isoformat()
                break
        goal.updated_at = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self.conn.execute(
                "UPDATE goals SET milestones = ?, updated_at = ? WHERE id = ?",
                (json.dumps(goal.milestones), goal.updated_at, goal.id),
            )
            self.conn.commit()
            self._recalc_progress(goal_id)
        return True

    def _recalc_progress(self, goal_id: str) -> None:
        goal = self.get(goal_id)
        if not goal:
            return
        total = len(goal.tasks) + len(goal.milestones)
        if total == 0:
            return
        completed = sum(1 for t in goal.tasks if self.get(t) and self.get(t).status == GoalStatus.COMPLETED)
        completed += sum(1 for m in goal.milestones if m.get("completed"))
        progress = round(completed / total, 4)
        with self._lock:
            self.conn.execute(
                "UPDATE goals SET progress = ? WHERE id = ?", (progress, goal_id)
            )
            self.conn.commit()

    def set_progress(self, goal_id: str, progress: float) -> bool:
        progress = max(0.0, min(1.0, progress))
        with self._lock:
            cur = self.conn.execute(
                "UPDATE goals SET progress = ?, updated_at = ? WHERE id = ?",
                (progress, datetime.now(timezone.utc).isoformat(), goal_id),
            )
            self.conn.commit()
        return cur.rowcount > 0

    def list_goals(
        self,
        scope: Optional[GoalScope] = None,
        status: Optional[GoalStatus] = None,
        parent_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[Goal]:
        query = "SELECT * FROM goals WHERE 1=1"
        params: list = []
        if scope:
            query += " AND scope = ?"
            params.append(scope.value if isinstance(scope, GoalScope) else scope)
        if status:
            query += " AND status = ?"
            params.append(status.value if isinstance(status, GoalStatus) else status)
        if parent_id is not None:
            query += " AND parent_id = ?"
            params.append(parent_id)
        query += " ORDER BY priority DESC, created_at DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_goal(r) for r in rows]

    def get_hierarchy(self, goal_id: str) -> dict:
        goal = self.get(goal_id)
        if not goal:
            return {}
        result = goal.to_dict()
        children = self.list_goals(parent_id=goal_id)
        result["children"] = [self.get_hierarchy(c.id) for c in children]
        dep_goals = [self.get(d).to_dict() if self.get(d) else {"id": d, "error": "not found"} for d in goal.dependencies]
        result["dependency_details"] = dep_goals
        return result

    def get_daily(self) -> list[Goal]:
        return self.list_goals(scope=GoalScope.DAILY)

    def get_weekly(self) -> list[Goal]:
        return self.list_goals(scope=GoalScope.WEEKLY)

    def get_active(self) -> list[Goal]:
        return self.list_goals(status=GoalStatus.IN_PROGRESS)

    def get_due_reminders(self) -> list[dict]:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with self._lock:
            rows = self.conn.execute(
                "SELECT id, title, target_date, priority FROM goals WHERE target_date <= ? AND status != 'completed' AND status != 'cancelled'",
                (today,),
            ).fetchall()
        return [{"id": r["id"], "title": r["title"], "target_date": r["target_date"], "priority": r["priority"]} for r in rows]

    def auto_plan_daily(self) -> list[dict]:
        active = self.get_active()
        suggestions = []
        for goal in sorted(active, key=lambda g: (g.priority.value == "critical", g.priority.value == "high", g.target_date or ""), reverse=True):
            if goal.progress < 0.5:
                suggestions.append({
                    "goal_id": goal.id,
                    "title": goal.title,
                    "progress": goal.progress,
                    "suggested_action": "Break into smaller tasks" if not goal.tasks else f"Next: complete remaining {len(goal.tasks)} task(s)",
                    "priority": goal.priority.value,
                })
        return suggestions[:5]

    def status_summary(self) -> dict:
        with self._lock:
            total = self.conn.execute("SELECT COUNT(*) FROM goals").fetchone()[0]
            by_status = {}
            for row in self.conn.execute("SELECT status, COUNT(*) as c FROM goals GROUP BY status").fetchall():
                by_status[row["status"]] = row["c"]
            by_scope = {}
            for row in self.conn.execute("SELECT scope, COUNT(*) as c FROM goals GROUP BY scope").fetchall():
                by_scope[row["scope"]] = row["c"]
        return {
            "total_goals": total,
            "by_status": by_status,
            "by_scope": by_scope,
            "active_count": by_status.get("in_progress", 0),
            "completed_count": by_status.get("completed", 0),
            "reminders_due": len(self.get_due_reminders()),
        }

    @staticmethod
    def _row_to_goal(row) -> Goal:
        return Goal(
            id=row["id"],
            title=row["title"],
            description=row["description"] or "",
            scope=GoalScope(row["scope"]),
            status=GoalStatus(row["status"]),
            priority=GoalPriority(row["priority"]),
            parent_id=row["parent_id"],
            dependencies=json.loads(row["dependencies"]) if row["dependencies"] else [],
            tasks=json.loads(row["tasks"]) if row["tasks"] else [],
            milestones=json.loads(row["milestones"]) if row["milestones"] else [],
            progress=row["progress"] or 0.0,
            target_date=row["target_date"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )
