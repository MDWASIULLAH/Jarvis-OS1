"""Lazy, metadata-first registry for language-model providers."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass

from .contracts import (
    ModelProvider,
    ModelProviderContext,
    ModelCapability,
    ModelRequest,
    ProviderHealth,
    ProviderHealthStatus,
    ProviderKind,
    ProviderMetadata,
)

ProviderFactory = Callable[[ModelProviderContext], ModelProvider]


@dataclass
class _ProviderRegistration:
    metadata: ProviderMetadata
    factory: ProviderFactory
    instance: ModelProvider | None = None
    health: ProviderHealth | None = None


class ModelProviderRegistry:
    """Single source of truth for provider metadata and lazy instances."""

    def __init__(self) -> None:
        self._registrations: dict[str, _ProviderRegistration] = {}
        self._aliases: dict[str, str] = {}
        self._context: ModelProviderContext | None = None
        self._lock = threading.RLock()
        self._load_order: list[str] = []

    def initialize(self, context: ModelProviderContext | None = None) -> None:
        with self._lock:
            self._context = context or ModelProviderContext()

    def register(self, metadata: ProviderMetadata, factory: ProviderFactory) -> None:
        if not metadata.provider_id:
            raise ValueError("Model provider ID cannot be empty.")
        with self._lock:
            aliases = (metadata.provider_id, *metadata.legacy_ids)
            if metadata.provider_id in self._registrations or any(alias in self._aliases for alias in aliases):
                raise ValueError(f"Model provider is already registered: {metadata.provider_id}")
            self._registrations[metadata.provider_id] = _ProviderRegistration(metadata, factory)
            for alias in aliases:
                self._aliases[alias] = metadata.provider_id

    def discover(
        self,
        *,
        capability: ModelCapability | None = None,
        kind: ProviderKind | None = None,
    ) -> tuple[ProviderMetadata, ...]:
        with self._lock:
            providers = tuple(item.metadata for item in self._registrations.values())
        return tuple(
            sorted(
                (item for item in providers if (capability is None or capability in item.capabilities) and (kind is None or item.kind is kind)),
                key=lambda item: (-item.priority, item.provider_id),
            )
        )

    def metadata(self, provider_id: str) -> ProviderMetadata:
        with self._lock:
            return self._registration(provider_id).metadata

    def get(self, provider_id: str) -> ModelProvider:
        with self._lock:
            registration = self._registration(provider_id)
            if registration.instance is not None:
                return registration.instance
            if self._context is None:
                raise RuntimeError("Model provider registry has not been initialized.")
            instance = registration.factory(self._context)
            if not isinstance(instance, ModelProvider):
                raise TypeError(f"Model provider factory for '{provider_id}' returned an invalid provider.")
            instance.initialize(self._context)
            registration.instance = instance
            self._load_order.append(registration.metadata.provider_id)
            return instance

    def rank(self, request: ModelRequest) -> tuple[ProviderMetadata, ...]:
        required = set(request.all_required_capabilities)
        preferred = {provider_id: index for index, provider_id in enumerate(request.preferred_provider_ids)}
        fallback = {provider_id: index for index, provider_id in enumerate(request.fallback_provider_ids)}
        candidates = []
        for metadata in self.discover():
            if not required.issubset(metadata.capabilities):
                continue
            score = metadata.priority
            if request.prefer_local and metadata.kind in {ProviderKind.LOCAL, ProviderKind.EMBEDDED}:
                score += 100
            if metadata.provider_id in preferred:
                # Explicit preference order must dominate generic priority and
                # locality scores while still allowing deterministic fallbacks.
                score += 1_000_000 - (preferred[metadata.provider_id] * 10_000)
            elif metadata.provider_id in fallback:
                score += 100_000 - (fallback[metadata.provider_id] * 10_000)
            candidates.append((score, metadata))
        return tuple(item for _, item in sorted(candidates, key=lambda item: (-item[0], item[1].provider_id)))

    def health(self, provider_id: str, *, refresh: bool = True) -> ProviderHealth:
        with self._lock:
            registration = self._registration(provider_id)
            if registration.health is not None and not refresh:
                return registration.health
        try:
            health = self.get(provider_id).health()
        except Exception as exc:
            health = ProviderHealth(ProviderHealthStatus.UNHEALTHY, str(exc))
        with self._lock:
            self._registration(provider_id).health = health
        return health

    def health_snapshot(self, *, refresh: bool = False) -> tuple[tuple[str, ProviderHealth], ...]:
        with self._lock:
            identifiers = tuple(self._registrations)
        return tuple((identifier, self.health(identifier, refresh=refresh)) for identifier in identifiers)

    def shutdown(self) -> None:
        with self._lock:
            identifiers = tuple(reversed(self._load_order))
            self._load_order.clear()
        for identifier in identifiers:
            with self._lock:
                registration = self._registration(identifier)
                instance, registration.instance = registration.instance, None
                registration.health = None
            if instance is not None:
                instance.shutdown()

    def _registration(self, provider_id: str) -> _ProviderRegistration:
        try:
            return self._registrations[self._aliases[provider_id]]
        except KeyError as exc:
            raise KeyError(f"Unknown model provider: {provider_id}") from exc
