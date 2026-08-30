"""Dependency-injected registration point for swappable knowledge providers."""

from __future__ import annotations

import threading
from collections.abc import Callable

from .interface import KnowledgeInterface, KnowledgeInterfaceContext

KnowledgeFactory = Callable[[KnowledgeInterfaceContext], KnowledgeInterface]


class KnowledgeInterfaceFactory:
    """Instance-scoped factory registry; suitable for local or remote backends."""

    def __init__(self) -> None:
        self._factories: dict[str, KnowledgeFactory] = {}
        self._lock = threading.RLock()

    def register(self, name: str, factory: KnowledgeFactory) -> None:
        if not name:
            raise ValueError("Knowledge factory name cannot be empty.")
        with self._lock:
            if name in self._factories:
                raise ValueError(f"Knowledge factory is already registered: {name}")
            self._factories[name] = factory

    def create(self, name: str, context: KnowledgeInterfaceContext | None = None) -> KnowledgeInterface:
        with self._lock:
            try:
                factory = self._factories[name]
            except KeyError as exc:
                raise KeyError(f"Unknown knowledge factory: {name}") from exc
        instance = factory(context or KnowledgeInterfaceContext())
        if not isinstance(instance, KnowledgeInterface):
            raise TypeError(f"Knowledge factory '{name}' returned an invalid interface.")
        return instance
