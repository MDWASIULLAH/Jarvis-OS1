import tempfile
from pathlib import Path

from app.observability.audit import AuditLog
from app.tasks.store import TaskStatus, TaskStore


def test_task_lifecycle_persists_across_updates():
    with tempfile.TemporaryDirectory() as tmp:
        store = TaskStore(Path(tmp) / "tasks.db")
        try:
            task = store.create("summarize my inbox", ["email"])
            assert task["status"] == TaskStatus.QUEUED.value

            store.update(task["id"], TaskStatus.RUNNING)
            running = store.get(task["id"])
            assert running["status"] == TaskStatus.RUNNING.value

            done = store.update(task["id"], TaskStatus.COMPLETED, result={"summary": "3 unread"})
            assert done["status"] == TaskStatus.COMPLETED.value
            assert done["result"] == {"summary": "3 unread"}
        finally:
            store.close()


def test_task_list_orders_most_recent_first():
    with tempfile.TemporaryDirectory() as tmp:
        store = TaskStore(Path(tmp) / "tasks.db")
        try:
            first = store.create("first task", ["planning"])
            second = store.create("second task", ["planning"])
            listed = store.list(limit=10)
            assert listed[0]["id"] == second["id"]
            assert listed[1]["id"] == first["id"]
        finally:
            store.close()


def test_audit_log_redacts_secrets():
    with tempfile.TemporaryDirectory() as tmp:
        audit = AuditLog(Path(tmp) / "audit.db")
        try:
            audit.record("login", "success", {"api_key": "sk-should-not-appear", "user": "local"})
            entries = audit.recent(limit=1)
            assert entries[0]["detail"]["api_key"] == "[redacted]"
            assert entries[0]["detail"]["user"] == "local"
        finally:
            audit.close()


def test_audit_log_recent_respects_limit():
    with tempfile.TemporaryDirectory() as tmp:
        audit = AuditLog(Path(tmp) / "audit.db")
        try:
            for i in range(5):
                audit.record("event", "ok", {"i": i})
            assert len(audit.recent(limit=2)) == 2
        finally:
            audit.close()
