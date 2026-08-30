"""Pluggable search-cache boundary with in-memory implementation."""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod

from .models import SearchResponse


class SearchCache(ABC):
    @abstractmethod
    def lookup(self, key: str) -> SearchResponse | None: ...
    @abstractmethod
    def insert(self, key: str, value: SearchResponse, ttl_seconds: float) -> None: ...


class InMemorySearchCache(SearchCache):
    def __init__(self) -> None:
        self._entries: dict[str, tuple[float, SearchResponse]] = {}
        self._lock = threading.RLock()

    def lookup(self, key: str) -> SearchResponse | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            expires, value = entry
            if time.monotonic() >= expires:
                del self._entries[key]
                return None
            return value

    def insert(self, key: str, value: SearchResponse, ttl_seconds: float) -> None:
        with self._lock:
            self._entries[key] = (time.monotonic() + max(0.0, ttl_seconds), value)
