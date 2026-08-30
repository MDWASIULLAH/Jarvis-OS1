from __future__ import annotations

import pytest

from app.knowledge import (
    EntityType,
    EntityUpdateRequest,
    KnowledgeAttribute,
    KnowledgeBatchUpdate,
    KnowledgeEntityDraft,
    KnowledgeGraph,
    KnowledgeGraphAdapter,
    KnowledgeInterface,
    KnowledgeInterfaceContext,
    KnowledgeInterfaceFactory,
    KnowledgeItemKind,
    KnowledgeRelationshipDraft,
    KnowledgeTraversal,
    RelationshipType,
    RelationshipUpdateRequest,
    TraversalDirection,
)


def _knowledge() -> tuple[KnowledgeGraphAdapter, str, str, str]:
    adapter = KnowledgeGraphAdapter(KnowledgeGraph())
    project = adapter.create_entity(KnowledgeEntityDraft(EntityType.PROJECT, "JARVIS", embedding=(1.0, 0.0), tags=("assistant",)))
    source = adapter.create_entity(KnowledgeEntityDraft(EntityType.FILE, "app/main.py", embedding=(0.9, 0.1), tags=("python",)))
    technology = adapter.create_entity(KnowledgeEntityDraft(EntityType.TECHNOLOGY, "FastAPI", embedding=(0.0, 1.0), tags=("python",)))
    adapter.create_relationship(KnowledgeRelationshipDraft(project.entity_id, source.entity_id, RelationshipType.CONTAINS))
    adapter.create_relationship(KnowledgeRelationshipDraft(source.entity_id, technology.entity_id, RelationshipType.USES))
    return adapter, project.entity_id, source.entity_id, technology.entity_id


def test_interface_compliance_and_entity_version_delegation():
    adapter, project_id, _, _ = _knowledge()

    assert isinstance(adapter, KnowledgeInterface)
    updated = adapter.update_entity(project_id, EntityUpdateRequest(1, attributes=(KnowledgeAttribute("status", "active"),)))

    assert updated.version == 2
    assert adapter.get_entity(project_id).attributes == (KnowledgeAttribute("status", "active"),)
    assert adapter.version_check(KnowledgeItemKind.ENTITY, project_id, 2) is True


def test_relationship_queries_and_traversal_remain_backend_neutral():
    adapter, project_id, source_id, technology_id = _knowledge()

    neighbors = adapter.get_neighbors(project_id)
    related = adapter.find_related(source_id, (RelationshipType.USES,))
    traversed = adapter.traverse(KnowledgeTraversal(project_id, max_depth=2, direction=TraversalDirection.OUTBOUND))

    assert {entity.entity_id for entity in neighbors.entities} == {project_id, source_id}
    assert len(related) == 1 and related[0].target_entity_id == technology_id
    assert {entity.entity_id for entity in traversed.entities} == {project_id, source_id, technology_id}


def test_semantic_and_similarity_search_return_interface_dtos_not_graph_objects():
    adapter, project_id, source_id, _ = _knowledge()

    semantic = adapter.semantic_search("python main")
    similar = adapter.similarity_search(project_id)

    assert semantic[0].entity.entity_id == source_id
    assert similar[0].entity.entity_id == source_id
    assert similar[0].score > 0.9


def test_batch_updates_are_preflight_version_checked_and_factory_supports_dependency_injection():
    graph = KnowledgeGraph()
    factory = KnowledgeInterfaceFactory()
    factory.register("in_memory", lambda context: KnowledgeGraphAdapter(context.require("graph")))
    adapter = factory.create("in_memory", KnowledgeInterfaceContext({"graph": graph}))
    entity = adapter.create_entity(KnowledgeEntityDraft(EntityType.GOAL, "Ship graph"))
    relationship_target = adapter.create_entity(KnowledgeEntityDraft(EntityType.TASK, "Write tests"))
    relationship = adapter.create_relationship(KnowledgeRelationshipDraft(entity.entity_id, relationship_target.entity_id, RelationshipType.CONTAINS))

    result = adapter.batch_update(
        KnowledgeBatchUpdate(
            ((entity.entity_id, EntityUpdateRequest(1, importance=1.0)),),
            ((relationship.relationship_id, RelationshipUpdateRequest(1, confidence=0.8)),),
        )
    )

    assert result.entities[0].version == 2 and result.relationships[0].version == 2
    with pytest.raises(ValueError, match="Stale entity"):
        adapter.batch_update(KnowledgeBatchUpdate(((entity.entity_id, EntityUpdateRequest(1, importance=0.2)),)))


def test_merge_split_and_delete_preserve_interface_compatibility():
    adapter, project_id, source_id, _ = _knowledge()
    duplicate = adapter.create_entity(KnowledgeEntityDraft(EntityType.PROJECT, "JARVIS project", tags=("duplicate",)))
    adapter.create_relationship(KnowledgeRelationshipDraft(duplicate.entity_id, source_id, RelationshipType.CONTAINS))

    merged = adapter.merge_entities(project_id, duplicate.entity_id, primary_version=1, duplicate_version=1)
    replacements = adapter.split_entity(merged.entity_id, (KnowledgeEntityDraft(EntityType.PROJECT, "JARVIS Core"),), expected_version=2)

    assert "duplicate" in merged.tags
    assert replacements[0].label == "JARVIS Core"
    with pytest.raises(KeyError):
        adapter.get_entity(project_id)
