"""Thread-safe context registration and adapter discovery."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from .contracts import Context, ContextCreateRequest, ContextDependencies, ContextKind

ContextFactory = Callable[[ContextCreateRequest, ContextDependencies], Context]
ContextAdapter = Callable[[Any, ContextDependencies], Context]


class ContextRegistry:
    """Registry for lazy Fabric context creation and legacy-context adapters."""

    def __init__(self, dependencies: ContextDependencies | None = None) -> None:
        self._dependencies = dependencies or ContextDependencies()
        self._factories: dict[ContextKind, ContextFactory] = {}
        self._adapters: dict[type[Any], ContextAdapter] = {}
        self._lock = threading.RLock()

    def register(self, kind: ContextKind, factory: ContextFactory) -> None:
        with self._lock:
            if kind in self._factories:
                raise ValueError(f"Context factory is already registered: {kind.value}")
            self._factories[kind] = factory

    def register_adapter(self, source_type: type[Any], adapter: ContextAdapter) -> None:
        with self._lock:
            if source_type in self._adapters:
                raise ValueError(f"Context adapter is already registered: {source_type.__name__}")
            self._adapters[source_type] = adapter

    def discover(self) -> tuple[ContextKind, ...]:
        with self._lock:
            return tuple(sorted(self._factories, key=lambda item: item.value))

    def has_factory(self, kind: ContextKind) -> bool:
        with self._lock:
            return kind in self._factories

    def has_adapter(self, source_type: type[Any]) -> bool:
        with self._lock:
            return source_type in self._adapters

    def create(self, request: ContextCreateRequest) -> Context:
        with self._lock:
            try:
                factory = self._factories[request.kind]
            except KeyError as exc:
                raise KeyError(f"No context factory registered for: {request.kind.value}") from exc
        return factory(request, self._dependencies)

    def adapt(self, source: Any) -> Context:
        with self._lock:
            adapter = next((handler for source_type, handler in self._adapters.items() if isinstance(source, source_type)), None)
        if adapter is None:
            raise TypeError(f"No context adapter registered for: {type(source).__name__}")
        return adapter(source, self._dependencies)
