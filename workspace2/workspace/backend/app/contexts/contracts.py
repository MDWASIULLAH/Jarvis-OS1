"""Typed context-fabric contracts, independent of all functional systems."""

from __future__ import annotations

import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ContextKind(str, Enum):
    CONVERSATION = "conversation"
    EXECUTION = "execution"
    RESPONSE = "response"
    SEARCH = "search"
    MEMORY = "memory"
    KNOWLEDGE = "knowledge"
    BROWSER = "browser"
    WORKSPACE = "workspace"
    AGENT = "agent"
    MISSION = "mission"
    USER = "user"
    SECURITY = "security"
    GENERIC = "generic"


@dataclass(frozen=True)
class ContextAttribute:
    key: str
    value: str


@dataclass(frozen=True)
class ContextIdentity:
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    execution_id: str | None = None
    conversation_id: str | None = None
    mission_id: str | None = None
    user_id: str | None = None
    session_id: str | None = None

    def inherit(self, child: "ContextIdentity") -> "ContextIdentity":
        return ContextIdentity(
            correlation_id=child.correlation_id or self.correlation_id,
            execution_id=child.execution_id or self.execution_id,
            conversation_id=child.conversation_id or self.conversation_id,
            mission_id=child.mission_id or self.mission_id,
            user_id=child.user_id or self.user_id,
            session_id=child.session_id or self.session_id,
        )


class ContextCancellationToken:
    """Thread-safe cancellation primitive owned by a fabric context."""

    def __init__(self) -> None:
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._reason = "Cancellation requested."

    def cancel(self, reason: str = "Cancellation requested.") -> None:
        with self._lock:
            self._reason = reason
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    @property
    def reason(self) -> str:
        with self._lock:
            return self._reason


@dataclass(frozen=True)
class ContextDeadline:
    deadline_monotonic: float | None = None

    @classmethod
    def for_timeout(cls, timeout_seconds: float | None) -> "ContextDeadline":
        return cls(None if timeout_seconds is None else time.monotonic() + max(0.0, timeout_seconds))

    def remaining_seconds(self) -> float | None:
        return None if self.deadline_monotonic is None else max(0.0, self.deadline_monotonic - time.monotonic())

    @property
    def expired(self) -> bool:
        remaining = self.remaining_seconds()
        return remaining is not None and remaining <= 0.0


@dataclass(frozen=True)
class ImmutableContextState:
    values: tuple[ContextAttribute, ...] = ()

    def value_for(self, key: str) -> str | None:
        return next((item.value for item in self.values if item.key == key), None)

    def with_value(self, key: str, value: str) -> "ImmutableContextState":
        retained = tuple(item for item in self.values if item.key != key)
        return ImmutableContextState((*retained, ContextAttribute(key, value)))

    def merge(self, other: "ImmutableContextState") -> "ImmutableContextState":
        state = self
        for item in other.values:
            state = state.with_value(item.key, item.value)
        return state


@dataclass(frozen=True)
class ContextTelemetry:
    trace_id: str = ""
    attributes: tuple[ContextAttribute, ...] = ()


@dataclass(frozen=True, kw_only=True)
class Context(ABC):
    """Common immutable envelope for every context managed by the Fabric."""

    context_id: str
    kind: ContextKind
    identity: ContextIdentity
    state: ImmutableContextState = field(default_factory=ImmutableContextState)
    parent_context_id: str | None = None
    deadline: ContextDeadline = field(default_factory=ContextDeadline)
    cancellation: ContextCancellationToken = field(default_factory=ContextCancellationToken)
    telemetry: ContextTelemetry = field(default_factory=ContextTelemetry)
    metadata: tuple[ContextAttribute, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1

    @abstractmethod
    def with_update(self, *, state: ImmutableContextState | None = None, metadata: tuple[ContextAttribute, ...] | None = None) -> "Context":
        ...


@dataclass(frozen=True, kw_only=True)
class FabricContext(Context):
    """Default serializable context envelope used by the manager and adapters."""

    def with_update(self, *, state: ImmutableContextState | None = None, metadata: tuple[ContextAttribute, ...] | None = None) -> "FabricContext":
        return replace(self, state=state or self.state, metadata=metadata if metadata is not None else self.metadata, version=self.version + 1)


@dataclass(frozen=True)
class ContextCreateRequest:
    kind: ContextKind
    identity: ContextIdentity = field(default_factory=ContextIdentity)
    state: ImmutableContextState = field(default_factory=ImmutableContextState)
    parent_context_id: str | None = None
    timeout_seconds: float | None = None
    telemetry: ContextTelemetry = field(default_factory=ContextTelemetry)
    metadata: tuple[ContextAttribute, ...] = ()


@dataclass(frozen=True)
class ContextUpdateRequest:
    expected_version: int
    state: ImmutableContextState | None = None
    metadata: tuple[ContextAttribute, ...] | None = None


class ContextDependencies:
    def __init__(self, services: dict[str, Any] | None = None) -> None:
        self._services = dict(services or {})

    def require(self, name: str) -> Any:
        try:
            return self._services[name]
        except KeyError as exc:
            raise LookupError(f"Context dependency is unavailable: {name}") from exc
