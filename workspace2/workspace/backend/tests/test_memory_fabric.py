from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from app.contexts import ContextCreateRequest, ContextIdentity, ContextKind, ContextManager
from app.events import EventBus, EventType
from app.knowledge import KnowledgeGraph, KnowledgeGraphAdapter
from app.memory_fabric import (
    InMemoryMemoryProvider, MemoryAttribute, MemoryDraft, MemoryExpiration,
    MemoryManager, MemoryProviderContext, MemoryProviderMetadata,
    MemoryProviderRegistry, MemoryQuery, MemoryStatus, MemoryType, MemoryUpdate,
    MemoryVersionConflict,
)


def _draft(title: str = "Weather", content: str = "The weather in Delhi is sunny.", **values) -> MemoryDraft:
    return MemoryDraft(memory_type=MemoryType.SEMANTIC, title=title, content=content, **values)


def test_memory_creation_retrieval_update_deletion_and_versioning():
    manager = MemoryManager()
    created = manager.store(_draft())
    retrieved = manager.retrieve(created.memory_id)
    updated = manager.update(created.memory_id, MemoryUpdate(expected_version=retrieved.version, summary="Sunny Delhi weather."))
    deleted = manager.delete(updated.memory_id, expected_version=updated.version)

    assert retrieved.access_frequency == 1
    assert updated.version == 2 and updated.summary == "Sunny Delhi weather."
    assert deleted.status is MemoryStatus.DELETED and manager.retrieve(created.memory_id) is None
    with pytest.raises(MemoryVersionConflict):
        manager.update(created.memory_id, MemoryUpdate(expected_version=1, title="stale"))


def test_keyword_semantic_tag_metadata_scope_time_and_hybrid_search():
    manager = MemoryManager()
    recent = manager.store(_draft(tags=("weather", "india"), metadata=(MemoryAttribute("project_id", "jarvis"), MemoryAttribute("workspace_id", "core")), owner_id="u1"))
    manager.store(_draft("Older", "Archived discussion", tags=("old",)))

    keyword = manager.search(MemoryQuery(text="Delhi sunny", tags=("weather",), project_id="jarvis", workspace_id="core", user_id="u1"))
    semantic = manager.search(MemoryQuery(text="sunshine", semantic=True))

    assert keyword.matches[0].memory.memory_id == recent.memory_id
    assert semantic.matches


def test_consolidation_duplicate_detection_merge_archive_restore_and_expire():
    manager = MemoryManager()
    first = manager.store(_draft("One", "same useful fact", tags=("one",)))
    second = manager.store(_draft("Two", "same useful fact", tags=("two",)))
    result = manager.consolidate(MemoryQuery(text="useful", limit=10))
    archived = manager.retrieve(second.memory_id)
    restored = manager.restore(second.memory_id, expected_version=archived.version)
    expiring = manager.store(_draft("Expire", "temporary", expiration=MemoryExpiration(datetime.now(timezone.utc) - timedelta(seconds=1))))
    expired = manager.expire()

    assert len(result) == 1 and first.memory_id == result[0].memory_id
    assert archived.status is MemoryStatus.ARCHIVED and restored.status is MemoryStatus.ACTIVE
    assert expiring.memory_id in {entry.memory_id for entry in expired}


def test_scoring_prioritization_context_and_knowledge_interface_integration():
    graph = KnowledgeGraphAdapter(KnowledgeGraph())
    manager = MemoryManager(knowledge=graph)
    context = ContextManager().create(ContextCreateRequest(ContextKind.CONVERSATION, ContextIdentity(conversation_id="c1", user_id="user-1")))
    high = manager.store(_draft("High", "important weather", importance=1.0), context=context)
    low = manager.store(_draft("Low", "important weather", importance=0.1), context=context)
    prioritized = manager.prioritize(MemoryQuery(text="important"), context=context)

    assert high.owner_id == "user-1"
    assert any(item.key == "context_id" and item.value == context.context_id for item in high.metadata)
    assert high.knowledge_entity_id and graph.get_entity(high.knowledge_entity_id).label == "High"
    assert prioritized[0].memory.memory_id == high.memory_id
    assert manager.score(high) > manager.score(low)


def test_memory_events_only_publish_lifecycle_events():
    bus = EventBus()
    observed = []
    bus.subscribe(None, lambda event: observed.append(event.event_type))
    manager = MemoryManager(event_bus=bus)
    entry = manager.store(_draft())
    current = manager.retrieve(entry.memory_id)
    updated = manager.update(entry.memory_id, MemoryUpdate(expected_version=current.version, title="Updated"))
    manager.archive(updated.memory_id, expected_version=updated.version)
    archived = manager.retrieve(updated.memory_id)
    manager.restore(updated.memory_id, expected_version=archived.version)
    manager.delete(updated.memory_id)

    assert EventType.MEMORY_CREATED in observed
    assert EventType.MEMORY_RETRIEVED in observed
    assert EventType.MEMORY_UPDATED in observed
    assert EventType.MEMORY_ARCHIVED in observed
    assert EventType.MEMORY_RESTORED in observed
    assert EventType.MEMORY_DELETED in observed


def test_registry_is_lazy_dependency_injected_and_thread_safe():
    registry = MemoryProviderRegistry(MemoryProviderContext({"region": "test"}))
    created = []
    registry.register(MemoryProviderMetadata("test", "Test"), lambda context: created.append(context.require("region")) or InMemoryMemoryProvider())
    manager = MemoryManager(registry=registry, provider_id="test")

    assert not created and registry.discover()[0].provider_id == "test"
    with ThreadPoolExecutor(max_workers=8) as executor:
        entries = list(executor.map(lambda index: manager.store(_draft(f"T{index}", f"content {index}")), range(20)))

    assert created == ["test"]
    assert len({entry.memory_id for entry in entries}) == 20
    assert len(manager.search(MemoryQuery(text="content", limit=100)).matches) == 20


def test_future_provider_defined_memory_types_remain_pluggable():
    manager = MemoryManager()
    entry = manager.store(MemoryDraft(memory_type="cloud_vector", title="Portable", content="Future backend memory"))

    assert entry.memory_type == "cloud_vector"
    assert manager.search(MemoryQuery(memory_types=("cloud_vector",))).matches[0].memory.memory_id == entry.memory_id


def test_legacy_memory_api_remains_independent_and_compatible(tmp_path):
    from app.memory.memory_store import MemorySystem

    legacy = MemorySystem(tmp_path)
    try:
        legacy.long_term.remember("name", "Jarvis")
        assert legacy.long_term.recall("name") == "Jarvis"
        assert MemoryManager().store(_draft()).memory_id
    finally:
        legacy.close()
