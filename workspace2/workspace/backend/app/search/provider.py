"""Search provider contract and per-search cancellation signal."""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from typing import Any

from .models import SearchCapability, SearchProviderStatus, SearchQuery, SearchResult


class SearchCancellationToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()


class SearchProviderContext:
    def __init__(self, services: dict[str, Any] | None = None) -> None:
        self._services = dict(services or {})

    def require(self, name: str) -> Any:
        try:
            return self._services[name]
        except KeyError as exc:
            raise LookupError(f"Search provider dependency is unavailable: {name}") from exc


class SearchProvider(ABC):
    @abstractmethod
    def initialize(self, context: SearchProviderContext) -> None: ...
    @abstractmethod
    def shutdown(self) -> None: ...
    @abstractmethod
    def search(self, query: SearchQuery, cancellation: SearchCancellationToken) -> tuple[SearchResult, ...]: ...
    @abstractmethod
    def health(self) -> SearchProviderStatus: ...
    @abstractmethod
    def capabilities(self) -> tuple[SearchCapability, ...]: ...
    @abstractmethod
    def priority(self) -> int: ...
    @abstractmethod
    def supports(self, query: SearchQuery) -> bool: ...
    @abstractmethod
    def cancel(self, cancellation: SearchCancellationToken) -> None: ...
