"""Knowledge assets and semantic-relationship contracts, independent of Memory."""

from .graph import GraphVersionConflict, KnowledgeGraph
from .adapter import GraphCompatibilityAdapter, KnowledgeGraphAdapter
from .factory import KnowledgeInterfaceFactory
from .graph_models import (
    EntityType,
    GraphAttribute,
    GraphEdge,
    GraphNode,
    GraphQuery,
    GraphQueryResult,
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
    KnowledgeInterfaceContext,
    KnowledgeItemKind,
    KnowledgeRelationship,
    KnowledgeRelationshipDraft,
    KnowledgeSearchMatch,
    KnowledgeSubgraph,
    KnowledgeTraversal,
    RelationshipUpdateRequest,
)

__all__ = [
    "EntityType", "GraphAttribute", "GraphEdge", "GraphNode", "GraphQuery", "GraphQueryResult", "GraphSubgraph",
    "GraphTraversal", "GraphUpdate", "GraphUpdateKind", "GraphVersionConflict", "KnowledgeGraph", "RelationshipType",
    "TraversalDirection", "EntityUpdateRequest", "GraphCompatibilityAdapter", "KnowledgeAttribute", "KnowledgeBatchResult",
    "KnowledgeBatchUpdate", "KnowledgeEntity", "KnowledgeEntityDraft", "KnowledgeGraphAdapter", "KnowledgeInterface",
    "KnowledgeInterfaceContext", "KnowledgeInterfaceFactory", "KnowledgeItemKind", "KnowledgeRelationship",
    "KnowledgeRelationshipDraft", "KnowledgeSearchMatch", "KnowledgeSubgraph", "KnowledgeTraversal", "RelationshipUpdateRequest",
]
