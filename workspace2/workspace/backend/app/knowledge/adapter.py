"""KnowledgeInterface adapter for the in-process KnowledgeGraph."""

from __future__ import annotations

import threading

from .graph import KnowledgeGraph
from .graph_models import (
    GraphAttribute,
    GraphEdge,
    GraphNode,
    GraphQuery,
    GraphSubgraph,
    GraphTraversal,
    GraphUpdate,
    GraphUpdateKind,
    RelationshipType,
    TraversalDirection,
)
from .interface import (
    EntityUpdateRequest,
    KnowledgeAttribute,
    KnowledgeBatchResult,
    KnowledgeBatchUpdate,
    KnowledgeEntity,
    KnowledgeEntityDraft,
    KnowledgeInterface,
    KnowledgeItemKind,
    KnowledgeRelationship,
    KnowledgeRelationshipDraft,
    KnowledgeSearchMatch,
    KnowledgeSubgraph,
    KnowledgeTraversal,
    RelationshipUpdateRequest,
)


class KnowledgeGraphAdapter(KnowledgeInterface):
    """Maps the stable knowledge interface onto the current in-process graph."""

    def __init__(self, graph: KnowledgeGraph) -> None:
        self._graph = graph
        self._lock = threading.RLock()

    def create_entity(self, entity: KnowledgeEntityDraft) -> KnowledgeEntity:
        node = GraphNode.create(
            entity.entity_type,
            entity.label,
            attributes=self._graph_attributes(entity.attributes),
            weight=entity.weight,
            confidence=entity.confidence,
            importance=entity.importance,
            embedding=entity.embedding,
            tags=entity.tags,
            metadata=self._graph_attributes(entity.metadata),
        )
        return self._entity(self._graph.create_node(node))

    def update_entity(self, entity_id: str, update: EntityUpdateRequest) -> KnowledgeEntity:
        result = self._graph.update(
            GraphUpdate(
                GraphUpdateKind.NODE,
                entity_id,
                update.expected_version,
                attributes=self._graph_attributes(update.attributes) if update.attributes is not None else None,
                tags=update.tags,
                weight=update.weight,
                confidence=update.confidence,
                importance=update.importance,
                metadata=self._graph_attributes(update.metadata) if update.metadata is not None else None,
                embedding=update.embedding,
            )
        )
        return self._entity(result)

    def delete_entity(self, entity_id: str, *, expected_version: int | None = None) -> KnowledgeEntity:
        return self._entity(self._graph.delete_node(entity_id, expected_version=expected_version))

    def create_relationship(self, relationship: KnowledgeRelationshipDraft) -> KnowledgeRelationship:
        edge = GraphEdge.create(
            relationship.source_entity_id,
            relationship.target_entity_id,
            relationship.relationship_type,
            attributes=self._graph_attributes(relationship.attributes),
            weight=relationship.weight,
            confidence=relationship.confidence,
            importance=relationship.importance,
            tags=relationship.tags,
            metadata=self._graph_attributes(relationship.metadata),
        )
        return self._relationship(self._graph.create_edge(edge))

    def update_relationship(self, relationship_id: str, update: RelationshipUpdateRequest) -> KnowledgeRelationship:
        result = self._graph.update(
            GraphUpdate(
                GraphUpdateKind.EDGE,
                relationship_id,
                update.expected_version,
                attributes=self._graph_attributes(update.attributes) if update.attributes is not None else None,
                tags=update.tags,
                weight=update.weight,
                confidence=update.confidence,
                importance=update.importance,
                metadata=self._graph_attributes(update.metadata) if update.metadata is not None else None,
            )
        )
        return self._relationship(result)

    def delete_relationship(self, relationship_id: str, *, expected_version: int | None = None) -> KnowledgeRelationship:
        return self._relationship(self._graph.delete_edge(relationship_id, expected_version=expected_version))

    def get_entity(self, entity_id: str) -> KnowledgeEntity:
        return self._entity(self._graph.node(entity_id))

    def get_neighbors(
        self,
        entity_id: str,
        *,
        direction: TraversalDirection = TraversalDirection.BOTH,
    ) -> KnowledgeSubgraph:
        return self._subgraph(self._graph.neighbors(entity_id, direction=direction))

    def find_related(
        self,
        entity_id: str,
        relationship_types: tuple[RelationshipType, ...] = (),
    ) -> tuple[KnowledgeRelationship, ...]:
        graph = self._graph.neighbors(entity_id, relationships=relationship_types)
        return tuple(self._relationship(edge) for edge in graph.edges)

    def traverse(self, traversal: KnowledgeTraversal) -> KnowledgeSubgraph:
        return self._subgraph(
            self._graph.traverse(
                GraphTraversal(
                    traversal.start_entity_id,
                    traversal.max_depth,
                    traversal.direction,
                    traversal.relationship_types,
                )
            )
        )

    def semantic_search(self, query: str, *, limit: int = 10) -> tuple[KnowledgeSearchMatch, ...]:
        terms = tuple(term for term in query.lower().split() if term)
        if not terms:
            return ()
        candidates = self._graph.query(GraphQuery(limit=10_000)).nodes
        matches = []
        for node in candidates:
            searchable = " ".join(
                (node.label, *node.tags, *(item.key for item in node.attributes), *(item.value for item in node.attributes))
            ).lower()
            score = sum(term in searchable for term in terms) / len(terms)
            if score:
                matches.append((self._entity(node), score))
        return tuple(
            KnowledgeSearchMatch(entity, score)
            for entity, score in sorted(matches, key=lambda item: (-item[1], -item[0].importance, item[0].label))[:max(0, limit)]
        )

    def similarity_search(self, entity_id: str, *, limit: int = 10) -> tuple[KnowledgeSearchMatch, ...]:
        return tuple(KnowledgeSearchMatch(self._entity(node), score) for node, score in self._graph.similar_nodes(entity_id, limit=limit))

    def merge_entities(
        self,
        primary_entity_id: str,
        duplicate_entity_id: str,
        *,
        primary_version: int,
        duplicate_version: int,
    ) -> KnowledgeEntity:
        with self._lock:
            primary = self._graph.node(primary_entity_id)
            duplicate = self._graph.node(duplicate_entity_id)
            if primary.version != primary_version or duplicate.version != duplicate_version:
                raise ValueError("Entity merge requires current versions for both entities.")
            merged = self.update_entity(
                primary_entity_id,
                EntityUpdateRequest(
                    primary_version,
                    attributes=self._knowledge_attributes((*primary.attributes, *duplicate.attributes)),
                    tags=tuple(dict.fromkeys((*primary.tags, *duplicate.tags))),
                    weight=max(primary.weight, duplicate.weight),
                    confidence=max(primary.confidence, duplicate.confidence),
                    importance=max(primary.importance, duplicate.importance),
                    embedding=primary.embedding or duplicate.embedding,
                    metadata=self._knowledge_attributes((*primary.metadata, *duplicate.metadata)),
                ),
            )
            for edge in self._graph.neighbors(duplicate_entity_id).edges:
                source = primary_entity_id if edge.source_node_id == duplicate_entity_id else edge.source_node_id
                target = primary_entity_id if edge.target_node_id == duplicate_entity_id else edge.target_node_id
                self.create_relationship(
                    KnowledgeRelationshipDraft(
                        source,
                        target,
                        edge.relationship,
                        self._knowledge_attributes(edge.attributes),
                        edge.weight,
                        edge.confidence,
                        edge.importance,
                        edge.tags,
                        self._knowledge_attributes(edge.metadata),
                    )
                )
                self._graph.delete_edge(edge.edge_id, expected_version=edge.version)
            self.delete_entity(duplicate_entity_id, expected_version=duplicate_version)
            return merged

    def split_entity(
        self,
        entity_id: str,
        replacements: tuple[KnowledgeEntityDraft, ...],
        *,
        expected_version: int,
    ) -> tuple[KnowledgeEntity, ...]:
        with self._lock:
            source = self._graph.node(entity_id)
            if source.version != expected_version:
                raise ValueError("Entity split requires the current entity version.")
            created = tuple(self.create_entity(item) for item in replacements)
            self.delete_entity(entity_id, expected_version=expected_version)
            return created

    def version_check(self, kind: KnowledgeItemKind, identifier: str, expected_version: int) -> bool:
        item = self._graph.node(identifier) if kind is KnowledgeItemKind.ENTITY else self._graph.edge(identifier)
        return item.version == expected_version

    def batch_update(self, batch: KnowledgeBatchUpdate) -> KnowledgeBatchResult:
        with self._lock:
            for identifier, update in batch.entity_updates:
                if not self.version_check(KnowledgeItemKind.ENTITY, identifier, update.expected_version):
                    raise ValueError(f"Stale entity version in batch: {identifier}")
            for identifier, update in batch.relationship_updates:
                if not self.version_check(KnowledgeItemKind.RELATIONSHIP, identifier, update.expected_version):
                    raise ValueError(f"Stale relationship version in batch: {identifier}")
            entities = tuple(self.update_entity(identifier, update) for identifier, update in batch.entity_updates)
            relationships = tuple(self.update_relationship(identifier, update) for identifier, update in batch.relationship_updates)
            return KnowledgeBatchResult(entities, relationships)

    @staticmethod
    def _graph_attributes(attributes: tuple[KnowledgeAttribute, ...]) -> tuple[GraphAttribute, ...]:
        return tuple(GraphAttribute(item.key, item.value) for item in attributes)

    @staticmethod
    def _knowledge_attributes(attributes: tuple[GraphAttribute, ...]) -> tuple[KnowledgeAttribute, ...]:
        return tuple(KnowledgeAttribute(item.key, item.value) for item in attributes)

    @classmethod
    def _entity(cls, node: GraphNode) -> KnowledgeEntity:
        return KnowledgeEntity(
            entity_type=node.entity_type,
            label=node.label,
            attributes=cls._knowledge_attributes(node.attributes),
            weight=node.weight,
            confidence=node.confidence,
            importance=node.importance,
            embedding=node.embedding,
            tags=node.tags,
            metadata=cls._knowledge_attributes(node.metadata),
            entity_id=node.node_id,
            version=node.version,
        )

    @classmethod
    def _relationship(cls, edge: GraphEdge) -> KnowledgeRelationship:
        return KnowledgeRelationship(
            source_entity_id=edge.source_node_id,
            target_entity_id=edge.target_node_id,
            relationship_type=edge.relationship,
            attributes=cls._knowledge_attributes(edge.attributes),
            weight=edge.weight,
            confidence=edge.confidence,
            importance=edge.importance,
            tags=edge.tags,
            metadata=cls._knowledge_attributes(edge.metadata),
            relationship_id=edge.edge_id,
            version=edge.version,
        )

    @classmethod
    def _subgraph(cls, graph: GraphSubgraph) -> KnowledgeSubgraph:
        return KnowledgeSubgraph(tuple(cls._entity(node) for node in graph.nodes), tuple(cls._relationship(edge) for edge in graph.edges))


# Retains a descriptive legacy name for integrations that name the backend.
GraphCompatibilityAdapter = KnowledgeGraphAdapter
