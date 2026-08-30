"""Provider-neutral semantic knowledge contract for future Memory consumers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .graph_models import EntityType, RelationshipType, TraversalDirection


class KnowledgeItemKind(str, Enum):
    ENTITY = "entity"
    RELATIONSHIP = "relationship"


@dataclass(frozen=True)
class KnowledgeAttribute:
    key: str
    value: str


@dataclass(frozen=True)
class KnowledgeEntityDraft:
    entity_type: EntityType
    label: str
    attributes: tuple[KnowledgeAttribute, ...] = ()
    weight: float = 1.0
    confidence: float = 1.0
    importance: float = 0.5
    embedding: tuple[float, ...] = ()
    tags: tuple[str, ...] = ()
    metadata: tuple[KnowledgeAttribute, ...] = ()


@dataclass(frozen=True)
class KnowledgeEntity(KnowledgeEntityDraft):
    entity_id: str = ""
    version: int = 1


@dataclass(frozen=True)
class KnowledgeRelationshipDraft:
    source_entity_id: str
    target_entity_id: str
    relationship_type: RelationshipType
    attributes: tuple[KnowledgeAttribute, ...] = ()
    weight: float = 1.0
    confidence: float = 1.0
    importance: float = 0.5
    tags: tuple[str, ...] = ()
    metadata: tuple[KnowledgeAttribute, ...] = ()


@dataclass(frozen=True)
class KnowledgeRelationship(KnowledgeRelationshipDraft):
    relationship_id: str = ""
    version: int = 1


@dataclass(frozen=True)
class EntityUpdateRequest:
    expected_version: int
    attributes: tuple[KnowledgeAttribute, ...] | None = None
    tags: tuple[str, ...] | None = None
    weight: float | None = None
    confidence: float | None = None
    importance: float | None = None
    embedding: tuple[float, ...] | None = None
    metadata: tuple[KnowledgeAttribute, ...] | None = None


@dataclass(frozen=True)
class RelationshipUpdateRequest:
    expected_version: int
    attributes: tuple[KnowledgeAttribute, ...] | None = None
    tags: tuple[str, ...] | None = None
    weight: float | None = None
    confidence: float | None = None
    importance: float | None = None
    metadata: tuple[KnowledgeAttribute, ...] | None = None


@dataclass(frozen=True)
class KnowledgeTraversal:
    start_entity_id: str
    max_depth: int = 1
    direction: TraversalDirection = TraversalDirection.OUTBOUND
    relationship_types: tuple[RelationshipType, ...] = ()


@dataclass(frozen=True)
class KnowledgeSubgraph:
    entities: tuple[KnowledgeEntity, ...]
    relationships: tuple[KnowledgeRelationship, ...]


@dataclass(frozen=True)
class KnowledgeSearchMatch:
    entity: KnowledgeEntity
    score: float


@dataclass(frozen=True)
class KnowledgeBatchUpdate:
    entity_updates: tuple[tuple[str, EntityUpdateRequest], ...] = ()
    relationship_updates: tuple[tuple[str, RelationshipUpdateRequest], ...] = ()


@dataclass(frozen=True)
class KnowledgeBatchResult:
    entities: tuple[KnowledgeEntity, ...]
    relationships: tuple[KnowledgeRelationship, ...]


class KnowledgeInterfaceContext:
    """Dependency injection context used by swappable knowledge factories."""

    def __init__(self, services: dict[str, Any] | None = None) -> None:
        self._services = dict(services or {})

    def require(self, name: str) -> Any:
        try:
            return self._services[name]
        except KeyError as exc:
            raise LookupError(f"Knowledge dependency is unavailable: {name}") from exc


class KnowledgeInterface(ABC):
    """Stable boundary that prevents consumers from depending on graph storage."""

    @abstractmethod
    def create_entity(self, entity: KnowledgeEntityDraft) -> KnowledgeEntity: ...
    @abstractmethod
    def update_entity(self, entity_id: str, update: EntityUpdateRequest) -> KnowledgeEntity: ...
    @abstractmethod
    def delete_entity(self, entity_id: str, *, expected_version: int | None = None) -> KnowledgeEntity: ...
    @abstractmethod
    def create_relationship(self, relationship: KnowledgeRelationshipDraft) -> KnowledgeRelationship: ...
    @abstractmethod
    def update_relationship(self, relationship_id: str, update: RelationshipUpdateRequest) -> KnowledgeRelationship: ...
    @abstractmethod
    def delete_relationship(self, relationship_id: str, *, expected_version: int | None = None) -> KnowledgeRelationship: ...
    @abstractmethod
    def get_entity(self, entity_id: str) -> KnowledgeEntity: ...
    @abstractmethod
    def get_neighbors(self, entity_id: str, *, direction: TraversalDirection = TraversalDirection.BOTH) -> KnowledgeSubgraph: ...
    @abstractmethod
    def find_related(self, entity_id: str, relationship_types: tuple[RelationshipType, ...] = ()) -> tuple[KnowledgeRelationship, ...]: ...
    @abstractmethod
    def traverse(self, traversal: KnowledgeTraversal) -> KnowledgeSubgraph: ...
    @abstractmethod
    def semantic_search(self, query: str, *, limit: int = 10) -> tuple[KnowledgeSearchMatch, ...]: ...
    @abstractmethod
    def similarity_search(self, entity_id: str, *, limit: int = 10) -> tuple[KnowledgeSearchMatch, ...]: ...
    @abstractmethod
    def merge_entities(self, primary_entity_id: str, duplicate_entity_id: str, *, primary_version: int, duplicate_version: int) -> KnowledgeEntity: ...
    @abstractmethod
    def split_entity(self, entity_id: str, replacements: tuple[KnowledgeEntityDraft, ...], *, expected_version: int) -> tuple[KnowledgeEntity, ...]: ...
    @abstractmethod
    def version_check(self, kind: KnowledgeItemKind, identifier: str, expected_version: int) -> bool: ...
    @abstractmethod
    def batch_update(self, batch: KnowledgeBatchUpdate) -> KnowledgeBatchResult: ...
