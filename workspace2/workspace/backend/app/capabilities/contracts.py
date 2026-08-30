"""Stable contracts for JARVIS capabilities.

Capabilities are deliberately synchronous today because the existing backend
surface is synchronous. The contract isolates that implementation detail so an
async executor can be introduced later without changing capability metadata or
the registry API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class HealthStatus(str, Enum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass(frozen=True)
class CapabilityMetadata:
    """Describes a capability without loading its implementation."""

    name: str
    description: str
    display_name: str = ""
    category: str = "General"
    version: str = "1.0.0"
    supported_intents: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    legacy_ids: tuple[str, ...] = ()
    priority: int = 0


@dataclass(frozen=True)
class CapabilityRequest:
    """Implementation-neutral invocation request.

    ``arguments`` is intentionally a dictionary so compatibility adapters can
    preserve existing function signatures while future native capabilities can
    define stricter request types behind the same interface.
    """

    operation: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    reason: str = ""


@dataclass(frozen=True)
class HealthReport:
    status: HealthStatus
    detail: str = ""
    checked_at: float | None = None


@dataclass(frozen=True)
class CapabilityResult:
    ok: bool
    data: Any = None
    message: str = ""
    rollback_token: str | None = None


class CapabilityContext:
    """Dependency-injection boundary supplied by the Runtime composition root."""

    def __init__(self, services: dict[str, Any] | None = None):
        self._services = dict(services or {})

    def require(self, name: str) -> Any:
        try:
            return self._services[name]
        except KeyError as exc:
            raise LookupError(f"Capability dependency is unavailable: {name}") from exc

    def has(self, name: str) -> bool:
        return name in self._services

    def dependencies_available(self, dependencies: tuple[str, ...]) -> bool:
        return all(self.has(name) for name in dependencies)


@runtime_checkable
class Capability(Protocol):
    """Common lifecycle and execution contract for every registered capability."""

    metadata: CapabilityMetadata

    def initialize(self, context: CapabilityContext) -> None:
        """Initialize this capability after its dependencies are available."""

    def validate(self, request: CapabilityRequest) -> ValidationResult:
        """Validate a request without performing external work."""

    def health(self) -> HealthReport:
        """Return the current health of this capability."""

    def execute(self, request: CapabilityRequest) -> CapabilityResult:
        """Perform a validated operation."""

    def rollback(self, rollback_token: str) -> CapabilityResult:
        """Attempt to reverse a previously completed operation when supported."""

    def shutdown(self) -> None:
        """Release resources acquired during initialization."""
