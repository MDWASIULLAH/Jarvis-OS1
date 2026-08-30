"""Strongly typed contracts for JARVIS's semantic Knowledge Graph."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class EntityType(str, Enum):
    USER = "user"
    PROJECT = "project"
    FILE = "file"
    TECHNOLOGY = "technology"
    GOAL = "goal"
    TASK = "task"
    PERSON = "person"
    REPOSITORY = "repository"
    GENERIC = "generic"


class RelationshipType(str, Enum):
    CONTAINS = "contains"
    OWNS = "owns"
    USES = "uses"
    DEPENDS_ON = "depends_on"
    REFERENCES = "references"
    ASSIGNED_TO = "assigned_to"
    RELATED_TO = "related_to"


class TraversalDirection(str, Enum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"
    BOTH = "both"


class GraphUpdateKind(str, Enum):
    NODE = "node"
    EDGE = "edge"


@dataclass(frozen=True)
class GraphAttribute:
    key: str
    value: str


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    entity_type: EntityType
    label: str
    attributes: tuple[GraphAttribute, ...] = ()
    weight: float = 1.0
    confidence: float = 1.0
    importance: float = 0.5
    embedding: tuple[float, ...] = ()
    tags: tuple[str, ...] = ()
    metadata: tuple[GraphAttribute, ...] = ()
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(cls, entity_type: EntityType, label: str, **values) -> "GraphNode":
        return cls(node_id=str(uuid.uuid4()), entity_type=entity_type, label=label, **values)


@dataclass(frozen=True)
class GraphEdge:
    edge_id: str
    source_node_id: str
    target_node_id: str
    relationship: RelationshipType
    attributes: tuple[GraphAttribute, ...] = ()
    weight: float = 1.0
    confidence: float = 1.0
    importance: float = 0.5
    tags: tuple[str, ...] = ()
    metadata: tuple[GraphAttribute, ...] = ()
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(
        cls,
        source_node_id: str,
        target_node_id: str,
        relationship: RelationshipType,
        **values,
    ) -> "GraphEdge":
        return cls(str(uuid.uuid4()), source_node_id, target_node_id, relationship, **values)


@dataclass(frozen=True)
class GraphQuery:
    entity_types: tuple[EntityType, ...] = ()
    relationships: tuple[RelationshipType, ...] = ()
    tags: tuple[str, ...] = ()
    minimum_confidence: float = 0.0
    minimum_importance: float = 0.0
    label_contains: str | None = None
    limit: int = 100


@dataclass(frozen=True)
class GraphTraversal:
    start_node_id: str
    max_depth: int = 1
    direction: TraversalDirection = TraversalDirection.OUTBOUND
    relationships: tuple[RelationshipType, ...] = ()


@dataclass(frozen=True)
class GraphSubgraph:
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]


@dataclass(frozen=True)
class GraphQueryResult:
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...] = ()


@dataclass(frozen=True)
class GraphUpdate:
    kind: GraphUpdateKind
    identifier: str
    expected_version: int
    attributes: tuple[GraphAttribute, ...] | None = None
    tags: tuple[str, ...] | None = None
    weight: float | None = None
    confidence: float | None = None
    importance: float | None = None
    metadata: tuple[GraphAttribute, ...] | None = None
    embedding: tuple[float, ...] | None = None
