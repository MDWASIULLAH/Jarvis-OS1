"""Capability discovery, lifecycle management, and selection.

The registry owns metadata and lazy factories only. It does not make routing
or planning decisions; later layers consume this neutral inventory.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from .contracts import (
    Capability,
    CapabilityContext,
    CapabilityMetadata,
    CapabilityRequest,
    CapabilityResult,
    HealthReport,
    HealthStatus,
    ValidationResult,
)

CapabilityFactory = Callable[[CapabilityContext], Capability]


@dataclass
class _Registration:
    metadata: CapabilityMetadata
    factory: CapabilityFactory
    instance: Capability | None = None
    health: HealthReport | None = None
    initialized_at: float | None = None


class CapabilityRegistry:
    """Single source of truth for registered JARVIS capabilities.

    Registration and discovery are metadata-only operations. A factory is not
    invoked until ``get``, ``initialize_capability``, ``validate``, ``health``,
    ``execute``, or a health-aware ranking requests that specific capability.
    """

    def __init__(self) -> None:
        self._registrations: dict[str, _Registration] = {}
        self._aliases: dict[str, str] = {}
        self._context: CapabilityContext | None = None
        self._lock = threading.RLock()
        self._load_order: list[str] = []

    def register(self, metadata: CapabilityMetadata, factory: CapabilityFactory) -> None:
        if not metadata.name or not metadata.name.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Capability names must contain letters, numbers, underscores, or hyphens.")
        with self._lock:
            if metadata.name in self._registrations:
                raise ValueError(f"Capability is already registered: {metadata.name}")
            aliases = (metadata.name, *metadata.legacy_ids)
            conflicts = [alias for alias in aliases if alias in self._aliases]
            if conflicts:
                raise ValueError(f"Capability alias is already registered: {conflicts[0]}")
            self._registrations[metadata.name] = _Registration(metadata=metadata, factory=factory)
            for alias in aliases:
                self._aliases[alias] = metadata.name

    def initialize(self, context: CapabilityContext) -> None:
        """Make dependencies available without eagerly loading any capability."""
        with self._lock:
            self._context = context

    def discover(
        self,
        *,
        intent: str | None = None,
        permission: str | None = None,
        tag: str | None = None,
    ) -> list[CapabilityMetadata]:
        with self._lock:
            metadata = [registration.metadata for registration in self._registrations.values()]
        return sorted(
            [
                item
                for item in metadata
                if (intent is None or intent in item.supported_intents)
                and (permission is None or permission in item.permissions)
                and (tag is None or tag in item.tags)
            ],
            key=lambda item: (-item.priority, item.name),
        )

    def metadata(self, name: str) -> CapabilityMetadata:
        with self._lock:
            try:
                return self._registrations[self._resolve_name(name)].metadata
            except KeyError as exc:
                raise KeyError(f"Unknown capability: {name}") from exc

    def resolve_name(self, name: str) -> str:
        """Resolve a canonical name or a preserved legacy capability ID."""
        with self._lock:
            try:
                return self._resolve_name(name)
            except KeyError as exc:
                raise KeyError(f"Unknown capability: {name}") from exc

    def registered_names(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._registrations))

    def get(self, name: str) -> Capability:
        with self._lock:
            registration = self._registration(name)
            if registration.instance is not None:
                return registration.instance
            context = self._require_context()
            if not context.dependencies_available(registration.metadata.dependencies):
                missing = [item for item in registration.metadata.dependencies if not context.has(item)]
                raise LookupError(f"Capability '{name}' is missing dependencies: {', '.join(missing)}")
            instance = registration.factory(context)
            if not isinstance(instance, Capability):
                raise TypeError(f"Capability factory for '{name}' returned an invalid implementation.")
            instance.initialize(context)
            registration.instance = instance
            registration.initialized_at = time.time()
            self._load_order.append(name)
            return instance

    def initialize_capability(self, name: str) -> Capability:
        return self.get(name)

    def validate(self, name: str, request: CapabilityRequest) -> ValidationResult:
        return self.get(name).validate(request)

    def health(self, name: str, *, refresh: bool = True) -> HealthReport:
        with self._lock:
            registration = self._registration(name)
            if registration.health is not None and not refresh:
                return registration.health
        try:
            report = self.get(name).health()
        except Exception as exc:  # A health probe must never make discovery fail.
            report = HealthReport(HealthStatus.UNHEALTHY, str(exc), checked_at=time.time())
        if report.checked_at is None:
            report = HealthReport(report.status, report.detail, checked_at=time.time())
        with self._lock:
            self._registration(name).health = report
        return report

    def health_snapshot(self, *, refresh: bool = False) -> dict[str, HealthReport]:
        """Monitor registered capabilities on demand without a background worker."""
        return {name: self.health(name, refresh=refresh) for name in self.registered_names()}

    def rank(
        self,
        *,
        intent: str | None = None,
        required_permissions: tuple[str, ...] = (),
        require_healthy: bool = False,
    ) -> list[CapabilityMetadata]:
        """Rank capabilities by declared priority, intent match, and health."""
        candidates = []
        for metadata in self.discover(intent=intent):
            if not set(required_permissions).issubset(metadata.permissions):
                continue
            score = metadata.priority + (100 if intent and intent in metadata.supported_intents else 0)
            if require_healthy:
                health = self.health(metadata.name)
                if health.status != HealthStatus.HEALTHY:
                    continue
                score += 10
            candidates.append((score, metadata))
        return [metadata for _, metadata in sorted(candidates, key=lambda item: (-item[0], item[1].name))]

    def execute(self, name: str, request: CapabilityRequest) -> CapabilityResult:
        capability = self.get(name)
        validation = capability.validate(request)
        if not validation.valid:
            return CapabilityResult(False, message=validation.reason)
        return capability.execute(request)

    def rollback(self, name: str, rollback_token: str) -> CapabilityResult:
        return self.get(name).rollback(rollback_token)

    def shutdown(self) -> None:
        """Shutdown only loaded capabilities, in reverse initialization order."""
        with self._lock:
            names = list(reversed(self._load_order))
            self._load_order.clear()
        for name in names:
            with self._lock:
                registration = self._registration(name)
                instance, registration.instance = registration.instance, None
                registration.initialized_at = None
                registration.health = None
            if instance is not None:
                instance.shutdown()

    def _registration(self, name: str) -> _Registration:
        try:
            return self._registrations[self._resolve_name(name)]
        except KeyError as exc:
            raise KeyError(f"Unknown capability: {name}") from exc

    def _resolve_name(self, name: str) -> str:
        return self._aliases[name]

    def _require_context(self) -> CapabilityContext:
        if self._context is None:
            raise RuntimeError("Capability registry has not been initialized by Runtime.")
        return self._context
