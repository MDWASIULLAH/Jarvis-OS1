"""Immutable, transport-neutral contracts for coordinated agent work."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum


class AgentKind(str, Enum):
    EXECUTIVE = "executive"
    DEPARTMENT_MANAGER = "department_manager"
    WORKER = "worker"
    HELPER = "helper"
    OBSERVER = "observer"
    RECOVERY = "recovery"


class AgentLifecycle(str, Enum):
    CREATED = "created"
    INITIALIZING = "initializing"
    READY = "ready"
    BUSY = "busy"
    WAITING = "waiting"
    BLOCKED = "blocked"
    RECOVERING = "recovering"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    RETIRED = "retired"


class AgentMessageType(str, Enum):
    REQUEST = "request"
    RESPONSE = "response"
    BROADCAST = "broadcast"
    DELEGATION = "delegation"
    ESCALATION = "escalation"
    ACKNOWLEDGEMENT = "acknowledgement"
    HEARTBEAT = "heartbeat"
    CANCELLATION = "cancellation"


class TaskLifecycle(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


class HardwareProfile(str, Enum):
    LOW_END_PC = "low_end_pc"
    MID_RANGE_PC = "mid_range_pc"
    HIGH_END_WORKSTATION = "high_end_workstation"
    SERVER = "server"


@dataclass(frozen=True)
class AgentCapability:
    capability_id: str


@dataclass(frozen=True)
class AgentHealth:
    heartbeat_at: float = 0.0
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    execution_seconds: float = 0.0
    failures: int = 0
    retries: int = 0
    queue_size: int = 0
    score: float = 1.0


@dataclass(frozen=True)
class SwarmAgent:
    agent_id: str
    kind: AgentKind
    name: str
    lifecycle: AgentLifecycle = AgentLifecycle.CREATED
    capabilities: tuple[AgentCapability, ...] = ()
    health: AgentHealth = field(default_factory=AgentHealth)
    context_id: str | None = None
    parent_agent_id: str | None = None
    version: int = 1


@dataclass(frozen=True)
class SwarmTask:
    task_id: str
    title: str
    description: str
    priority: int = 50
    dependencies: tuple[str, ...] = ()
    parent_task_id: str | None = None
    plan_id: str | None = None
    checkpoint_ids: tuple[str, ...] = ()
    rollback_prepared: bool = False
    lifecycle: TaskLifecycle = TaskLifecycle.PENDING

    @classmethod
    def create(cls, title: str, description: str, **values) -> "SwarmTask":
        return cls(str(uuid.uuid4()), title, description, **values)


@dataclass(frozen=True)
class AgentAssignment:
    agent_id: str
    task_id: str
    assigned_at: float


@dataclass(frozen=True)
class AgentMessage:
    message_id: str
    message_type: AgentMessageType
    sender_agent_id: str
    recipient_agent_id: str | None
    content: str
    correlation_id: str
    task_id: str | None = None

    @classmethod
    def create(cls, message_type: AgentMessageType, sender_agent_id: str, content: str, correlation_id: str, **values) -> "AgentMessage":
        recipient_agent_id = values.pop("recipient_agent_id", None)
        task_id = values.pop("task_id", None)
        return cls(str(uuid.uuid4()), message_type, sender_agent_id, recipient_agent_id, content, correlation_id, task_id)


@dataclass(frozen=True)
class TaskResult:
    task_id: str
    agent_id: str
    content: str
    successful: bool = True


@dataclass(frozen=True)
class RecoveryRecord:
    agent_id: str
    reason: str
    action: str


@dataclass(frozen=True)
class HelperPoolConfiguration:
    minimum_active: int = 0
    maximum_active: int | None = 300
    idle_retirement_seconds: float = 60.0
    cpu_budget_percent: float = 80.0
    memory_budget_mb: float = 4096.0
    concurrency_limit: int | None = 300

    @classmethod
    def for_profile(cls, profile: HardwareProfile, *, server_limit: int | None = None) -> "HelperPoolConfiguration":
        maximum = {HardwareProfile.LOW_END_PC: 100, HardwareProfile.MID_RANGE_PC: 300, HardwareProfile.HIGH_END_WORKSTATION: 1000, HardwareProfile.SERVER: server_limit}[profile]
        return cls(maximum_active=maximum, concurrency_limit=maximum)


@dataclass(frozen=True)
class SwarmResult:
    task_id: str
    content: str
    results: tuple[TaskResult, ...]
