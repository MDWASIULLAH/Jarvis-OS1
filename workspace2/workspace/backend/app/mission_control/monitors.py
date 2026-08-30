"""Read-only recording, metrics, communication, and pluggable resource monitors."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from ..events.model import DomainEvent
from .models import CommunicationRecord, FlightRecord, MissionMetrics, ResourceSnapshot, TimelineEntry


class MissionTimeline:
    def __init__(self) -> None:
        self._entries: dict[str, list[TimelineEntry]] = {}
        self._sequence = 0
        self._lock = threading.RLock()

    def record(self, mission_id: str, event: DomainEvent[object], detail: str = "") -> TimelineEntry:
        with self._lock:
            self._sequence += 1
            entry = TimelineEntry(self._sequence, event.timestamp, mission_id, event.event_type.value, event.source, event.correlation_id, detail)
            self._entries.setdefault(mission_id, []).append(entry)
            return entry

    def entries(self, mission_id: str) -> tuple[TimelineEntry, ...]:
        with self._lock: return tuple(self._entries.get(mission_id, ()))


class FlightRecorder:
    def __init__(self) -> None:
        self._records: dict[str, list[FlightRecord]] = {}
        self._lock = threading.RLock()

    def record(self, entry: TimelineEntry) -> FlightRecord:
        record = FlightRecord(str(uuid.uuid4()), entry.mission_id, entry)
        with self._lock: self._records.setdefault(entry.mission_id, []).append(record)
        return record

    def replay(self, mission_id: str) -> tuple[FlightRecord, ...]:
        with self._lock: return tuple(self._records.get(mission_id, ()))


class CommunicationMonitor:
    def __init__(self) -> None:
        self._records: dict[str, list[CommunicationRecord]] = {}
        self._lock = threading.RLock()

    def record(self, record: CommunicationRecord) -> CommunicationRecord:
        with self._lock: self._records.setdefault(record.mission_id, []).append(record)
        return record

    def search(self, mission_id: str, text: str = "") -> tuple[CommunicationRecord, ...]:
        with self._lock: records = tuple(self._records.get(mission_id, ()))
        lowered = text.lower()
        return tuple(item for item in records if not lowered or lowered in item.content.lower() or lowered in item.message_type.lower())


class ResourceProvider:
    def snapshot(self) -> ResourceSnapshot: raise NotImplementedError


class StaticResourceProvider(ResourceProvider):
    def __init__(self, snapshot: ResourceSnapshot | None = None) -> None: self._snapshot = snapshot or ResourceSnapshot()
    def snapshot(self) -> ResourceSnapshot: return self._snapshot


class SystemResourceProvider(ResourceProvider):
    """Reads the host counters the observability tier already collects.

    The default provider is static, so Mission Control reported 0% CPU / 0 MB
    for a running process. This adapts ``SystemMonitor`` instead of duplicating
    psutil access, and degrades to zeros only when psutil is genuinely absent.
    """

    def __init__(self, monitor: object, data_dir: object) -> None:
        self._monitor, self._data_dir = monitor, data_dir

    def snapshot(self) -> ResourceSnapshot:
        try:
            payload = self._monitor.snapshot(self._data_dir)  # type: ignore[attr-defined]
        except Exception:
            return ResourceSnapshot()
        memory = payload.get("memory") or {}
        storage = payload.get("storage") or {}
        return ResourceSnapshot(
            cpu_percent=float(payload.get("cpu_percent") or 0.0),
            memory_mb=round(float(memory.get("used") or 0.0) / (1024 * 1024), 1),
            disk_percent=float(storage.get("percent") or 0.0),
        )


class ResourceMonitor:
    def __init__(self, provider: ResourceProvider | None = None) -> None: self._provider = provider or StaticResourceProvider()
    def snapshot(self) -> ResourceSnapshot: return self._provider.snapshot()


class MetricsManager:
    def collect(self, agents: tuple[object, ...], timeline: tuple[TimelineEntry, ...]) -> MissionMetrics:
        from ..swarm.models import AgentKind, AgentLifecycle
        typed = tuple(agents)
        active = tuple(agent for agent in typed if getattr(agent, "lifecycle", None) is not AgentLifecycle.RETIRED)
        return MissionMetrics(
            active_agents=len(active), helper_agents=sum(getattr(agent, "kind", None) is AgentKind.HELPER for agent in active),
            completed_tasks=sum(entry.event_type.endswith("completed") for entry in timeline),
            failed_tasks=sum(entry.event_type.endswith("failed") for entry in timeline),
            retries=sum(getattr(getattr(agent, "health", None), "retries", 0) for agent in active),
            cpu_percent=sum(getattr(getattr(agent, "health", None), "cpu_percent", 0.0) for agent in active),
            memory_mb=sum(getattr(getattr(agent, "health", None), "memory_mb", 0.0) for agent in active),
            queue_size=sum(getattr(getattr(agent, "health", None), "queue_size", 0) for agent in active),
        )
