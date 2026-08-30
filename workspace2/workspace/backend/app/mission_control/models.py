"""Immutable operational-awareness contracts for Mission Control and Neural Nexus."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class MissionLifecycle(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class NexusNodeKind(str, Enum):
    MISSION = "mission"
    EXECUTIVE_AGENT = "executive_agent"
    DEPARTMENT_MANAGER = "department_manager"
    WORKER_AGENT = "worker_agent"
    HELPER_AGENT = "helper_agent"
    TASK = "task"
    MEMORY = "memory"
    SEARCH = "search"
    PLANNER = "planner"
    EXECUTOR = "executor"
    REFLECTION = "reflection"
    EVOLUTION = "evolution"


class NexusRelationship(str, Enum):
    PARENT = "parent"
    CHILD = "child"
    COMMUNICATES_WITH = "communicates_with"
    DEPENDS_ON = "depends_on"
    CREATED = "created"
    ASSIGNED = "assigned"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class MissionAttribute:
    key: str
    value: str


@dataclass(frozen=True)
class Mission:
    mission_id: str
    title: str
    description: str
    lifecycle: MissionLifecycle = MissionLifecycle.CREATED
    context_id: str | None = None
    correlation_id: str = ""
    metadata: tuple[MissionAttribute, ...] = ()
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(cls, title: str, description: str, **values) -> "Mission":
        return cls(str(uuid.uuid4()), title, description, **values)


@dataclass(frozen=True)
class MissionFilter:
    lifecycle: MissionLifecycle | None = None
    text: str = ""


@dataclass(frozen=True)
class TimelineEntry:
    sequence: int
    timestamp: datetime
    mission_id: str
    event_type: str
    source: str
    correlation_id: str
    detail: str = ""


@dataclass(frozen=True)
class FlightRecord:
    record_id: str
    mission_id: str
    timeline_entry: TimelineEntry


@dataclass(frozen=True)
class CommunicationRecord:
    mission_id: str
    message_id: str
    message_type: str
    sender_agent_id: str
    recipient_agent_id: str | None
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class MissionMetrics:
    active_agents: int = 0
    helper_agents: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    retries: int = 0
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    execution_latency_seconds: float = 0.0
    queue_size: int = 0
    throughput: float = 0.0


@dataclass(frozen=True)
class ResourceSnapshot:
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    disk_percent: float = 0.0
    gpu_percent: float | None = None
    network_bytes_per_second: float | None = None


@dataclass(frozen=True)
class AgentInspection:
    agent_id: str
    name: str
    parent_agent_id: str | None
    child_agent_ids: tuple[str, ...]
    state: str
    assigned_task_ids: tuple[str, ...]
    capabilities: tuple[str, ...]
    health_score: float
    cpu_percent: float
    memory_mb: float
    message_count: int
    timeline: tuple[TimelineEntry, ...]


@dataclass(frozen=True)
class NexusNode:
    node_id: str
    kind: NexusNodeKind
    label: str
    metadata: tuple[MissionAttribute, ...] = ()


@dataclass(frozen=True)
class NexusEdge:
    edge_id: str
    source_id: str
    target_id: str
    relationship: NexusRelationship


@dataclass(frozen=True)
class NexusFilter:
    kinds: tuple[NexusNodeKind, ...] = ()
    text: str = ""


@dataclass(frozen=True)
class NexusSnapshot:
    snapshot_id: str
    mission_id: str
    nodes: tuple[NexusNode, ...]
    edges: tuple[NexusEdge, ...]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class MissionReplay:
    mission_id: str
    timeline: tuple[TimelineEntry, ...]
    snapshots: tuple[NexusSnapshot, ...] = ()
