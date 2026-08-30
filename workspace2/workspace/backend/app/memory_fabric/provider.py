"""Swappable persistence boundary for local, vector, cloud, or distributed memory."""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any

from .models import MemoryDraft, MemoryEntry, MemoryMatch, MemoryQuery, MemoryStatus, MemoryUpdate, memory_id


@dataclass(frozen=True)
class MemoryProviderMetadata:
    provider_id: str
    display_name: str
    priority: int = 0
    capabilities: tuple[str, ...] = ("memory",)


class MemoryProviderContext:
    """Small DI container intentionally owned by each registry instance."""

    def __init__(self, services: dict[str, Any] | None = None) -> None:
        self._services = dict(services or {})

    def require(self, name: str) -> Any:
        try:
            return self._services[name]
        except KeyError as exc:
            raise LookupError(f"Memory dependency is unavailable: {name}") from exc


class MemoryProvider(ABC):
    @abstractmethod
    def initialize(self, context: MemoryProviderContext) -> None: ...
    @abstractmethod
    def shutdown(self) -> None: ...
    @abstractmethod
    def store(self, draft: MemoryDraft) -> MemoryEntry: ...
    @abstractmethod
    def retrieve(self, memory_id: str) -> MemoryEntry | None: ...
    @abstractmethod
    def update(self, memory_id: str, update: MemoryUpdate) -> MemoryEntry: ...
    @abstractmethod
    def delete(self, memory_id: str, *, expected_version: int | None = None) -> MemoryEntry: ...
    @abstractmethod
    def archive(self, memory_id: str, *, expected_version: int | None = None) -> MemoryEntry: ...
    @abstractmethod
    def restore(self, memory_id: str, *, expected_version: int | None = None) -> MemoryEntry: ...
    @abstractmethod
    def search(self, query: MemoryQuery) -> tuple[MemoryMatch, ...]: ...


class MemoryVersionConflict(RuntimeError):
    """A write targeted an out-of-date immutable memory entry."""


class InMemoryMemoryProvider(MemoryProvider):
    """Thread-safe reference provider used by default and in isolated deployments."""

    def __init__(self) -> None:
        self._entries: dict[str, MemoryEntry] = {}
        self._lock = threading.RLock()

    def initialize(self, context: MemoryProviderContext) -> None:
        del context

    def shutdown(self) -> None:
        return None

    def store(self, draft: MemoryDraft) -> MemoryEntry:
        now = datetime.now(timezone.utc)
        entry = MemoryEntry(
            memory_id=memory_id(), memory_type=draft.memory_type, title=draft.title, content=draft.content,
            summary=draft.summary, embedding=draft.embedding, tags=draft.tags, metadata=draft.metadata,
            created_at=now, updated_at=now, source=draft.source, confidence=draft.confidence,
            importance=draft.importance, expiration=draft.expiration, owner_id=draft.owner_id,
            permissions=draft.permissions, references=draft.references, knowledge_entity_id=draft.knowledge_entity_id,
        )
        with self._lock:
            self._entries[entry.memory_id] = entry
        return entry

    def retrieve(self, memory_id: str) -> MemoryEntry | None:
        with self._lock:
            entry = self._entries.get(memory_id)
            if entry is None or entry.status is MemoryStatus.DELETED:
                return None
            updated = replace(entry, access_frequency=entry.access_frequency + 1, updated_at=datetime.now(timezone.utc))
            self._entries[memory_id] = updated
            return updated

    def update(self, memory_id: str, update: MemoryUpdate) -> MemoryEntry:
        with self._lock:
            current = self._require(memory_id)
            if current.version != update.expected_version:
                raise MemoryVersionConflict(f"Expected version {update.expected_version}, found {current.version}.")
            changes = {name: value for name, value in (
                ("title", update.title), ("content", update.content), ("summary", update.summary),
                ("embedding", update.embedding), ("tags", update.tags), ("metadata", update.metadata),
                ("confidence", update.confidence), ("importance", update.importance),
                ("expiration", update.expiration), ("owner_id", update.owner_id), ("permissions", update.permissions),
                ("references", update.references),
            ) if value is not None}
            updated = replace(current, **changes, version=current.version + 1, updated_at=datetime.now(timezone.utc))
            self._entries[memory_id] = updated
            return updated

    def delete(self, memory_id: str, *, expected_version: int | None = None) -> MemoryEntry:
        with self._lock:
            current = self._require(memory_id)
            if expected_version is not None and current.version != expected_version:
                raise MemoryVersionConflict(f"Expected version {expected_version}, found {current.version}.")
            deleted = replace(current, status=MemoryStatus.DELETED, version=current.version + 1, updated_at=datetime.now(timezone.utc))
            self._entries[memory_id] = deleted
            return deleted

    def archive(self, memory_id: str, *, expected_version: int | None = None) -> MemoryEntry:
        with self._lock:
            current = self._require(memory_id)
            if expected_version is not None and current.version != expected_version:
                raise MemoryVersionConflict(f"Expected version {expected_version}, found {current.version}.")
            archived = replace(current, status=MemoryStatus.ARCHIVED, archived_at=datetime.now(timezone.utc), version=current.version + 1, updated_at=datetime.now(timezone.utc))
            self._entries[memory_id] = archived
            return archived

    def restore(self, memory_id: str, *, expected_version: int | None = None) -> MemoryEntry:
        with self._lock:
            current = self._require(memory_id)
            if expected_version is not None and current.version != expected_version:
                raise MemoryVersionConflict(f"Expected version {expected_version}, found {current.version}.")
            restored = replace(current, status=MemoryStatus.ACTIVE, archived_at=None, version=current.version + 1, updated_at=datetime.now(timezone.utc))
            self._entries[memory_id] = restored
            return restored

    def search(self, query: MemoryQuery) -> tuple[MemoryMatch, ...]:
        with self._lock:
            entries = tuple(self._entries.values())
        matches = [MemoryMatch(entry, self._score(entry, query)) for entry in entries if self._matches(entry, query)]
        return tuple(sorted(matches, key=lambda item: (-item.score, item.memory.created_at), reverse=False)[:max(0, query.limit)])

    def _require(self, memory_id: str) -> MemoryEntry:
        entry = self._entries.get(memory_id)
        if entry is None:
            raise KeyError(f"Unknown memory: {memory_id}")
        return entry

    @staticmethod
    def _matches(entry: MemoryEntry, query: MemoryQuery) -> bool:
        if entry.status is MemoryStatus.DELETED or (entry.status is MemoryStatus.ARCHIVED and not query.include_archived):
            return False
        if query.memory_types and entry.memory_type not in query.memory_types:
            return False
        if query.tags and not set(query.tags).issubset(entry.tags):
            return False
        metadata = {item.key: item.value for item in entry.metadata}
        if any(metadata.get(item.key) != item.value for item in query.metadata):
            return False
        if query.project_id and metadata.get("project_id") != query.project_id:
            return False
        if query.workspace_id and metadata.get("workspace_id") != query.workspace_id:
            return False
        if query.user_id and entry.owner_id != query.user_id:
            return False
        if query.created_after and entry.created_at < query.created_after:
            return False
        if query.created_before and entry.created_at > query.created_before:
            return False
        if not query.text:
            return True
        corpus = " ".join((entry.title, entry.content, entry.summary, *entry.tags)).lower()
        terms = tuple(term for term in query.text.lower().split() if term)
        # Keyword queries match their meaningful terms, not only one exact phrase.
        return all(term in corpus for term in terms) or query.semantic

    @staticmethod
    def _score(entry: MemoryEntry, query: MemoryQuery) -> float:
        text = query.text.lower().strip()
        corpus = " ".join((entry.title, entry.content, entry.summary, *entry.tags)).lower()
        keyword_score = (sum(1 for token in text.split() if token in corpus) / max(1, len(text.split()))) if text else 0.0
        semantic_score = 1.0 if query.semantic and text and any(token in corpus for token in text.split()) else 0.0
        return round(keyword_score + semantic_score + entry.importance + entry.confidence + min(entry.access_frequency, 10) / 100, 6)


MemoryProviderFactory = Callable[[MemoryProviderContext], MemoryProvider]


@dataclass
class _Registration:
    metadata: MemoryProviderMetadata
    factory: MemoryProviderFactory
    instance: MemoryProvider | None = None


class MemoryProviderRegistry:
    """Lazy, DI-friendly provider registry; no process-global memory state."""

    def __init__(self, context: MemoryProviderContext | None = None) -> None:
        self._context = context or MemoryProviderContext()
        self._registrations: dict[str, _Registration] = {}
        self._lock = threading.RLock()

    def register(self, metadata: MemoryProviderMetadata, factory: MemoryProviderFactory) -> None:
        with self._lock:
            if not metadata.provider_id or metadata.provider_id in self._registrations:
                raise ValueError(f"Memory provider is already registered: {metadata.provider_id}")
            self._registrations[metadata.provider_id] = _Registration(metadata, factory)

    def discover(self) -> tuple[MemoryProviderMetadata, ...]:
        with self._lock:
            return tuple(sorted((item.metadata for item in self._registrations.values()), key=lambda item: (-item.priority, item.provider_id)))

    def get(self, provider_id: str) -> MemoryProvider:
        with self._lock:
            try:
                registration = self._registrations[provider_id]
            except KeyError as exc:
                raise KeyError(f"Unknown memory provider: {provider_id}") from exc
            if registration.instance is None:
                instance = registration.factory(self._context)
                if not isinstance(instance, MemoryProvider):
                    raise TypeError("Memory provider factory returned an invalid provider.")
                instance.initialize(self._context)
                registration.instance = instance
            return registration.instance

    def shutdown(self) -> None:
        with self._lock:
            instances = tuple(item.instance for item in self._registrations.values() if item.instance is not None)
            for registration in self._registrations.values():
                registration.instance = None
        for provider in instances:
            provider.shutdown()
