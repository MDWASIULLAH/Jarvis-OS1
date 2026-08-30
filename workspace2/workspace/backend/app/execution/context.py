"""Stable execution context and compatibility bridge for capabilities.

The context is intentionally owned by the execution layer.  It contains the
per-request state that can safely travel to in-process, remote, streamed, or
agent-backed capabilities without making those capabilities depend on the
ToolExecutor implementation.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from ..capabilities.contracts import Capability, CapabilityRequest, CapabilityResult

if TYPE_CHECKING:
    from ..planning.models import ExecutionPlan, PlanStep


class CapabilityInvocationStyle(str, Enum):
    """Invocation contracts supported during the capability migration."""

    CONTEXT = "context"
    LEGACY_REQUEST = "legacy_request"


class CancellationToken:
    """Thread-safe, per-execution cancellation signal."""

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
class ContextAttribute:
    key: str
    value: str


class SharedExecutionState:
    """The explicit, synchronized mutable portion of an ExecutionContext."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._values: dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._values[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._values.get(key, default)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._values)


class ExecutionMetricsTracker:
    """Thread-safe, extensible execution counters available to capabilities."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, int] = {}

    def increment(self, name: str, amount: int = 1) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + amount

    def snapshot(self) -> tuple[ContextAttribute, ...]:
        with self._lock:
            return tuple(ContextAttribute(name, str(value)) for name, value in sorted(self._counters.items()))


@dataclass(frozen=True)
class TimeoutManager:
    """Immutable deadline view that can be carried into local or remote work."""

    deadline_monotonic: float | None = None

    @classmethod
    def for_duration(cls, timeout_seconds: float | None) -> "TimeoutManager":
        return cls(None if timeout_seconds is None else time.monotonic() + timeout_seconds)

    def remaining_seconds(self) -> float | None:
        return None if self.deadline_monotonic is None else max(0.0, self.deadline_monotonic - time.monotonic())

    @property
    def expired(self) -> bool:
        remaining = self.remaining_seconds()
        return remaining is not None and remaining <= 0


@dataclass(frozen=True, kw_only=True)
class ExecutionContext:
    """The preferred capability contract for one execution request.

    Identity, plan, metadata, and the current step are immutable values.  The
    intentionally mutable collaborators are ``shared_state`` and ``metrics``;
    both provide their own synchronization for concurrent plan branches.
    """

    execution_id: str
    correlation_id: str
    execution_plan: "ExecutionPlan"
    conversation_id: str | None = None
    session_id: str | None = None
    user_id: str | None = None
    current_step: "PlanStep | None" = None
    shared_state: SharedExecutionState = field(default_factory=SharedExecutionState)
    cancellation_token: CancellationToken = field(default_factory=CancellationToken)
    timeout_manager: TimeoutManager = field(default_factory=TimeoutManager)
    logger: Any | None = None
    telemetry: Any | None = None
    metrics: ExecutionMetricsTracker = field(default_factory=ExecutionMetricsTracker)
    metadata: tuple[ContextAttribute, ...] = ()
    memory: Any | None = None

    @classmethod
    def create(
        cls,
        execution_plan: "ExecutionPlan",
        *,
        execution_id: str | None = None,
        correlation_id: str | None = None,
        conversation_id: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        cancellation_token: CancellationToken | None = None,
        timeout_manager: TimeoutManager | None = None,
        logger: Any | None = None,
        telemetry: Any | None = None,
        metadata: tuple[ContextAttribute, ...] = (),
        memory: Any | None = None,
    ) -> "ExecutionContext":
        identifier = execution_id or str(uuid.uuid4())
        return cls(
            execution_id=identifier,
            correlation_id=correlation_id or identifier,
            execution_plan=execution_plan,
            conversation_id=conversation_id,
            session_id=session_id,
            user_id=user_id,
            cancellation_token=cancellation_token or CancellationToken(),
            timeout_manager=timeout_manager or TimeoutManager(),
            logger=logger,
            telemetry=telemetry,
            metadata=metadata,
            memory=memory,
        )

    def for_step(self, step: "PlanStep") -> "ExecutionContext":
        """Create an immutable step view while retaining shared request state."""
        return replace(self, current_step=step)


@runtime_checkable
class ContextCapability(Protocol):
    """Native capability shape for the ExecutionContext contract."""

    metadata: Any
    execution_interface: CapabilityInvocationStyle

    def execute(self, context: ExecutionContext) -> CapabilityResult:
        """Execute using the shared execution context."""


class CapabilityCompatibilityAdapter:
    """Invokes native context capabilities and preserves legacy request ones."""

    def execute(self, capability: Capability, context: ExecutionContext) -> CapabilityResult:
        if getattr(capability, "execution_interface", None) is CapabilityInvocationStyle.CONTEXT:
            return capability.execute(context)  # type: ignore[arg-type]
        request = self._legacy_request(context)
        validation = capability.validate(request)
        if not validation.valid:
            return CapabilityResult(False, message=validation.reason)
        return capability.execute(request)

    @staticmethod
    def _legacy_request(context: ExecutionContext) -> CapabilityRequest:
        step = context.current_step
        if step is None:
            raise ValueError("A capability can only be invoked for a plan step.")
        metadata = {field.name: field.value for field in step.metadata}
        return CapabilityRequest(
            operation=metadata.get("operation", ""),
            arguments={"args": [], "kwargs": {field.name: field.value for field in step.inputs}},
            correlation_id=context.correlation_id,
        )
