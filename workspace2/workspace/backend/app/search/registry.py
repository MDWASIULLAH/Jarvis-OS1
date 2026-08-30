"""Lazy provider registry for Search Intelligence."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass

from .models import SearchCapability, SearchProviderHealth, SearchProviderMetadata, SearchProviderStatus, SearchQuery
from .provider import SearchProvider, SearchProviderContext

SearchProviderFactory = Callable[[SearchProviderContext], SearchProvider]


@dataclass
class _Registration:
    metadata: SearchProviderMetadata
    factory: SearchProviderFactory
    enabled: bool = True
    instance: SearchProvider | None = None
    health: SearchProviderStatus | None = None


class SearchProviderRegistry:
    def __init__(self, context: SearchProviderContext | None = None) -> None:
        self._context = context or SearchProviderContext()
        self._registrations: dict[str, _Registration] = {}
        self._aliases: dict[str, str] = {}
        self._lock = threading.RLock()

    def register(self, metadata: SearchProviderMetadata, factory: SearchProviderFactory) -> None:
        with self._lock:
            aliases = (metadata.provider_id, *metadata.legacy_ids)
            if not metadata.provider_id or any(alias in self._aliases for alias in aliases):
                raise ValueError(f"Search provider is already registered: {metadata.provider_id}")
            self._registrations[metadata.provider_id] = _Registration(metadata, factory)
            for alias in aliases:
                self._aliases[alias] = metadata.provider_id

    def discover(self, *, capability: SearchCapability | None = None, enabled_only: bool = True) -> tuple[SearchProviderMetadata, ...]:
        with self._lock:
            registrations = tuple(self._registrations.values())
        return tuple(sorted(
            (item.metadata for item in registrations if (not enabled_only or item.enabled) and (capability is None or capability in item.metadata.capabilities)),
            key=lambda item: (-item.priority, item.provider_id),
        ))

    def get(self, provider_id: str) -> SearchProvider:
        with self._lock:
            registration = self._registration(provider_id)
            if not registration.enabled:
                raise RuntimeError("Search provider is disabled.")
            if registration.instance is None:
                instance = registration.factory(self._context)
                if not isinstance(instance, SearchProvider):
                    raise TypeError("Search provider factory returned an invalid provider.")
                instance.initialize(self._context)
                registration.instance = instance
            return registration.instance

    def set_enabled(self, provider_id: str, enabled: bool) -> None:
        with self._lock:
            self._registration(provider_id).enabled = enabled

    def health(self, provider_id: str, *, refresh: bool = True) -> SearchProviderStatus:
        with self._lock:
            registration = self._registration(provider_id)
            if registration.health is not None and not refresh:
                return registration.health
        try:
            status = self.get(provider_id).health()
        except Exception:
            status = SearchProviderStatus(SearchProviderHealth.UNHEALTHY, "provider unavailable")
        with self._lock:
            self._registration(provider_id).health = status
        return status

    def rank(self, query: SearchQuery) -> tuple[SearchProviderMetadata, ...]:
        required = set(query.required_capabilities)
        preferred = {value: index for index, value in enumerate(query.preferred_provider_ids)}
        ranked = []
        for metadata in self.discover():
            if not required.issubset(metadata.capabilities):
                continue
            score = metadata.priority + (1_000_000 - preferred[metadata.provider_id] * 10_000 if metadata.provider_id in preferred else 0)
            ranked.append((score, metadata))
        return tuple(item for _, item in sorted(ranked, key=lambda item: (-item[0], item[1].provider_id)))

    def shutdown(self) -> None:
        with self._lock:
            instances = tuple(item.instance for item in self._registrations.values() if item.instance is not None)
            for item in self._registrations.values():
                item.instance = None
                item.health = None
        for instance in instances:
            instance.shutdown()

    def _registration(self, provider_id: str) -> _Registration:
        try:
            return self._registrations[self._aliases[provider_id]]
        except KeyError as exc:
            raise KeyError(f"Unknown search provider: {provider_id}") from exc
