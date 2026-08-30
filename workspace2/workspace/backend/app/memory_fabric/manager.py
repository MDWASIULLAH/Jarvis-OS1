"""The central, orchestration-only Memory Fabric entry point."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from ..contexts.contracts import Context
from ..events.bus import EventBus
from ..events.model import (
    MemoryArchived, MemoryCreated, MemoryDeleted, MemoryLifecyclePayload,
    MemoryMerged, MemoryRestored, MemoryRetrieved, MemoryUpdated,
)
from ..knowledge.graph_models import EntityType
from ..knowledge.interface import KnowledgeAttribute, KnowledgeEntityDraft, KnowledgeInterface
from ..search.manager import SearchManager
from ..search.models import SearchQuery
from .models import (
    MemoryAttribute, MemoryDraft, MemoryEntry, MemoryExpiration, MemoryMatch,
    MemoryQuery, MemoryReference, MemorySearchResponse, MemoryStatus, MemorySummary,
    MemoryUpdate, memory_type_id,
)
from .provider import InMemoryMemoryProvider, MemoryProvider, MemoryProviderMetadata, MemoryProviderRegistry


class MemoryManager:
    """Coordinates memory providers without owning another context or graph model.

    The manager only receives Fabric ``Context`` envelopes, delegates graph work
    solely to ``KnowledgeInterface``, and keeps storage implementation behind a
    lazy provider registry.
    """

    DEFAULT_PROVIDER_ID = "in_memory"

    def __init__(
        self,
        *,
        registry: MemoryProviderRegistry | None = None,
        provider_id: str = DEFAULT_PROVIDER_ID,
        event_bus: EventBus | None = None,
        knowledge: KnowledgeInterface | None = None,
        search_manager: SearchManager | None = None,
    ) -> None:
        self._registry = registry or MemoryProviderRegistry()
        self._provider_id = provider_id
        self._event_bus = event_bus
        self._knowledge = knowledge
        self._search_manager = search_manager
        if not self._registry.discover():
            self._registry.register(MemoryProviderMetadata(provider_id, "In-memory Memory Fabric"), lambda _: InMemoryMemoryProvider())

    @property
    def registry(self) -> MemoryProviderRegistry:
        return self._registry

    def store(self, draft: MemoryDraft, *, context: Context | None = None) -> MemoryEntry:
        prepared = self._with_context(draft, context)
        if self._knowledge is not None and prepared.knowledge_entity_id is None:
            entity = self._knowledge.create_entity(KnowledgeEntityDraft(
                entity_type=EntityType.GENERIC,
                label=prepared.title,
                attributes=(KnowledgeAttribute("memory_type", memory_type_id(prepared.memory_type)),),
                confidence=prepared.confidence,
                importance=prepared.importance,
                embedding=prepared.embedding,
                tags=prepared.tags,
                metadata=tuple(KnowledgeAttribute(item.key, item.value) for item in prepared.metadata),
            ))
            prepared = replace(prepared, knowledge_entity_id=entity.entity_id, references=(*prepared.references, MemoryReference(entity.entity_id, "knowledge_entity")))
        entry = self._provider.store(prepared)
        self._publish(MemoryCreated, entry, context)
        return entry

    def retrieve(self, memory_id: str, *, context: Context | None = None) -> MemoryEntry | None:
        entry = self._provider.retrieve(memory_id)
        if entry is not None:
            self._publish(MemoryRetrieved, entry, context)
        return entry

    def update(self, memory_id: str, update: MemoryUpdate, *, context: Context | None = None) -> MemoryEntry:
        entry = self._provider.update(memory_id, update)
        self._publish(MemoryUpdated, entry, context)
        return entry

    def delete(self, memory_id: str, *, expected_version: int | None = None, context: Context | None = None) -> MemoryEntry:
        entry = self._provider.delete(memory_id, expected_version=expected_version)
        self._publish(MemoryDeleted, entry, context)
        return entry

    def search(self, query: MemoryQuery, *, context: Context | None = None, use_search_intelligence: bool = False) -> MemorySearchResponse:
        matches = self._provider.search(query)
        external_used = False
        if use_search_intelligence and self._search_manager is not None and query.text:
            # Search Intelligence remains an independent source; its result is not persisted implicitly.
            self._search_manager.search(SearchQuery(query.text, correlation_id=self._correlation_id(context)))
            external_used = True
        return MemorySearchResponse(matches, external_used)

    def summarize(self, memory_id: str, *, context: Context | None = None) -> MemorySummary:
        entry = self._require(memory_id, context)
        summary = entry.summary or self._summary_for(entry.content)
        if summary != entry.summary:
            entry = self.update(memory_id, MemoryUpdate(expected_version=entry.version, summary=summary), context=context)
        return MemorySummary(entry.memory_id, summary)

    def consolidate(self, query: MemoryQuery, *, context: Context | None = None) -> tuple[MemoryEntry, ...]:
        """Merge exact-content duplicates, then archive inactive matching entries."""
        matches = self.search(query, context=context).matches
        grouped: dict[str, list[MemoryEntry]] = {}
        for match in matches:
            key = " ".join(match.memory.content.lower().split())
            grouped.setdefault(key, []).append(match.memory)
        consolidated: list[MemoryEntry] = []
        for duplicates in grouped.values():
            primary = duplicates[0]
            if len(duplicates) > 1:
                primary = self.merge(primary.memory_id, tuple(item.memory_id for item in duplicates[1:]), context=context)
            consolidated.append(primary)
        return tuple(consolidated)

    def archive(self, memory_id: str, *, expected_version: int | None = None, context: Context | None = None) -> MemoryEntry:
        entry = self._provider.archive(memory_id, expected_version=expected_version)
        self._publish(MemoryArchived, entry, context)
        return entry

    def expire(self, *, now: datetime | None = None, context: Context | None = None) -> tuple[MemoryEntry, ...]:
        now = now or datetime.now(timezone.utc)
        entries = self._provider.search(MemoryQuery(include_archived=True, limit=100_000))
        return tuple(self.archive(match.memory.memory_id, expected_version=match.memory.version, context=context) for match in entries if match.memory.expiration.expires_at and match.memory.expiration.expires_at <= now and match.memory.status is MemoryStatus.ACTIVE)

    def restore(self, memory_id: str, *, expected_version: int | None = None, context: Context | None = None) -> MemoryEntry:
        entry = self._provider.restore(memory_id, expected_version=expected_version)
        self._publish(MemoryRestored, entry, context)
        return entry

    def merge(self, primary_memory_id: str, duplicate_memory_ids: tuple[str, ...], *, context: Context | None = None) -> MemoryEntry:
        primary = self._require(primary_memory_id, context)
        duplicates = tuple(self._require(memory_id, context) for memory_id in duplicate_memory_ids)
        all_tags = tuple(dict.fromkeys((*primary.tags, *(tag for item in duplicates for tag in item.tags))))
        all_references = tuple(dict.fromkeys((*primary.references, *(reference for item in duplicates for reference in item.references))))
        content = "\n".join(dict.fromkeys((primary.content, *(item.content for item in duplicates))))
        updated = self.update(primary.memory_id, MemoryUpdate(expected_version=primary.version, content=content, tags=all_tags, references=all_references, importance=max(item.importance for item in (primary, *duplicates))), context=context)
        for duplicate in duplicates:
            self.archive(duplicate.memory_id, expected_version=duplicate.version, context=context)
        self._publish(MemoryMerged, updated, context, tuple(item.memory_id for item in duplicates))
        return updated

    def split(self, memory_id: str, parts: tuple[MemoryDraft, ...], *, context: Context | None = None) -> tuple[MemoryEntry, ...]:
        original = self._require(memory_id, context)
        created = tuple(self.store(part, context=context) for part in parts)
        self.archive(original.memory_id, expected_version=original.version, context=context)
        return created

    def prioritize(self, query: MemoryQuery, *, context: Context | None = None) -> tuple[MemoryMatch, ...]:
        return tuple(sorted(self.search(query, context=context).matches, key=lambda match: (-self.score(match.memory), match.memory.memory_id)))

    @staticmethod
    def score(entry: MemoryEntry) -> float:
        return round(entry.importance * 0.55 + entry.confidence * 0.35 + min(entry.access_frequency, 10) * 0.01, 6)

    def version(self, memory_id: str, *, context: Context | None = None) -> int:
        return self._require(memory_id, context).version

    def shutdown(self) -> None:
        self._registry.shutdown()

    @property
    def _provider(self) -> MemoryProvider:
        return self._registry.get(self._provider_id)

    def _require(self, memory_id: str, context: Context | None) -> MemoryEntry:
        entry = self.retrieve(memory_id, context=context)
        if entry is None:
            raise KeyError(f"Unknown memory: {memory_id}")
        return entry

    @staticmethod
    def _summary_for(content: str) -> str:
        normalized = " ".join(content.split())
        return normalized[:240] + ("…" if len(normalized) > 240 else "")

    @staticmethod
    def _with_context(draft: MemoryDraft, context: Context | None) -> MemoryDraft:
        if context is None:
            return draft
        metadata = {item.key: item.value for item in draft.metadata}
        metadata.setdefault("context_id", context.context_id)
        if context.identity.conversation_id:
            metadata.setdefault("conversation_id", context.identity.conversation_id)
        owner_id = draft.owner_id or context.identity.user_id
        return replace(draft, owner_id=owner_id, metadata=tuple(MemoryAttribute(key, value) for key, value in metadata.items()))

    @staticmethod
    def _correlation_id(context: Context | None) -> str | None:
        return context.identity.correlation_id if context is not None else None

    def _publish(self, event_type, entry: MemoryEntry, context: Context | None, related: tuple[str, ...] = ()) -> None:
        if self._event_bus is not None:
            self._event_bus.publish(event_type(
                source="memory_fabric",
                payload=MemoryLifecyclePayload(entry.memory_id, memory_type_id(entry.memory_type), related),
                correlation_id=self._correlation_id(context) or entry.memory_id,
            ))
