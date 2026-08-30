"""Thread-safe semantic relationship graph, intentionally independent of Memory."""

from __future__ import annotations

import math
import threading
from collections import deque
from dataclasses import replace
from datetime import datetime, timezone

from .graph_models import (
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


class GraphVersionConflict(RuntimeError):
    """A caller attempted to update a stale graph object version."""


class KnowledgeGraph:
    """An in-memory graph for semantic relationships, not user experiences."""

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: dict[str, GraphEdge] = {}
        self._outbound: dict[str, set[str]] = {}
        self._inbound: dict[str, set[str]] = {}
        self._lock = threading.RLock()

    def create_node(self, node: GraphNode) -> GraphNode:
        self._validate_scores(node.weight, node.confidence, node.importance)
        with self._lock:
            if node.node_id in self._nodes:
                raise ValueError(f"Graph node already exists: {node.node_id}")
            self._nodes[node.node_id] = node
            self._outbound.setdefault(node.node_id, set())
            self._inbound.setdefault(node.node_id, set())
            return node

    def node(self, node_id: str) -> GraphNode:
        with self._lock:
            try:
                return self._nodes[node_id]
            except KeyError as exc:
                raise KeyError(f"Unknown graph node: {node_id}") from exc

    def create_edge(self, edge: GraphEdge) -> GraphEdge:
        self._validate_scores(edge.weight, edge.confidence, edge.importance)
        with self._lock:
            if edge.edge_id in self._edges:
                raise ValueError(f"Graph edge already exists: {edge.edge_id}")
            if edge.source_node_id not in self._nodes or edge.target_node_id not in self._nodes:
                raise KeyError("Graph edges require existing source and target nodes.")
            self._edges[edge.edge_id] = edge
            self._outbound[edge.source_node_id].add(edge.edge_id)
            self._inbound[edge.target_node_id].add(edge.edge_id)
            return edge

    def edge(self, edge_id: str) -> GraphEdge:
        with self._lock:
            try:
                return self._edges[edge_id]
            except KeyError as exc:
                raise KeyError(f"Unknown graph edge: {edge_id}") from exc

    def delete_edge(self, edge_id: str, *, expected_version: int | None = None) -> GraphEdge:
        """Remove one relationship without exposing internal edge indexes."""
        with self._lock:
            edge = self.edge(edge_id)
            if expected_version is not None and edge.version != expected_version:
                raise GraphVersionConflict(f"Expected version {expected_version}, found {edge.version}.")
            del self._edges[edge_id]
            self._outbound[edge.source_node_id].discard(edge_id)
            self._inbound[edge.target_node_id].discard(edge_id)
            return edge

    def delete_node(self, node_id: str, *, expected_version: int | None = None) -> GraphNode:
        """Remove an entity and its relationships atomically."""
        with self._lock:
            node = self.node(node_id)
            if expected_version is not None and node.version != expected_version:
                raise GraphVersionConflict(f"Expected version {expected_version}, found {node.version}.")
            for edge_id in tuple(self._outbound[node_id] | self._inbound[node_id]):
                self.delete_edge(edge_id)
            del self._nodes[node_id]
            del self._outbound[node_id]
            del self._inbound[node_id]
            return node

    def neighbors(
        self,
        node_id: str,
        *,
        direction: TraversalDirection = TraversalDirection.BOTH,
        relationships: tuple[RelationshipType, ...] = (),
    ) -> GraphSubgraph:
        """Public one-hop neighborhood view for adapters and graph clients."""
        return self.traverse(GraphTraversal(node_id, max_depth=1, direction=direction, relationships=relationships))

    def update(self, update: GraphUpdate) -> GraphNode | GraphEdge:
        with self._lock:
            if update.kind is GraphUpdateKind.NODE:
                current = self.node(update.identifier)
                replacement = self._updated(current, update)
                self._nodes[update.identifier] = replacement
                return replacement
            current = self.edge(update.identifier)
            replacement = self._updated(current, update)
            self._edges[update.identifier] = replacement
            return replacement

    def query(self, query: GraphQuery) -> GraphQueryResult:
        with self._lock:
            nodes = [node for node in self._nodes.values() if self._matches(node, query)]
            if query.relationships:
                relation_ids = {
                    edge.source_node_id for edge in self._edges.values() if edge.relationship in query.relationships
                } | {
                    edge.target_node_id for edge in self._edges.values() if edge.relationship in query.relationships
                }
                nodes = [node for node in nodes if node.node_id in relation_ids]
        nodes.sort(key=lambda node: (-node.importance, -node.confidence, node.label.lower()))
        selected = tuple(nodes[:max(0, query.limit)])
        selected_ids = {node.node_id for node in selected}
        with self._lock:
            edges = tuple(
                sorted(
                    (
                        edge for edge in self._edges.values()
                        if edge.source_node_id in selected_ids
                        and edge.target_node_id in selected_ids
                        and (not query.relationships or edge.relationship in query.relationships)
                    ),
                    key=lambda edge: edge.edge_id,
                )
            )
        return GraphQueryResult(selected, edges)

    def traverse(self, traversal: GraphTraversal) -> GraphSubgraph:
        if traversal.max_depth < 0:
            raise ValueError("Traversal depth cannot be negative.")
        with self._lock:
            if traversal.start_node_id not in self._nodes:
                raise KeyError(f"Unknown graph node: {traversal.start_node_id}")
            visited = {traversal.start_node_id}
            edges_seen: set[str] = set()
            pending = deque(((traversal.start_node_id, 0),))
            while pending:
                node_id, depth = pending.popleft()
                if depth >= traversal.max_depth:
                    continue
                for edge_id in self._incident_edges(node_id, traversal.direction):
                    edge = self._edges[edge_id]
                    if traversal.relationships and edge.relationship not in traversal.relationships:
                        continue
                    edges_seen.add(edge_id)
                    neighbor = self._neighbor(edge, node_id, traversal.direction)
                    if neighbor is not None and neighbor not in visited:
                        visited.add(neighbor)
                        pending.append((neighbor, depth + 1))
            return GraphSubgraph(
                tuple(self._nodes[node_id] for node_id in sorted(visited)),
                tuple(self._edges[edge_id] for edge_id in sorted(edges_seen)),
            )

    def similar_nodes(self, node_id: str, *, limit: int = 10, minimum_similarity: float = 0.0) -> tuple[tuple[GraphNode, float], ...]:
        with self._lock:
            source = self.node(node_id)
            if not source.embedding:
                return ()
            matches = []
            for candidate in self._nodes.values():
                if candidate.node_id == node_id or not candidate.embedding:
                    continue
                similarity = self._cosine_similarity(source.embedding, candidate.embedding)
                if similarity >= minimum_similarity:
                    matches.append((candidate, similarity))
        return tuple(sorted(matches, key=lambda item: (-item[1], item[0].label))[:max(0, limit)])

    def subgraph(self, node_ids: tuple[str, ...]) -> GraphSubgraph:
        selected = set(node_ids)
        with self._lock:
            nodes = tuple(self.node(node_id) for node_id in sorted(selected))
            edges = tuple(
                edge for edge in self._edges.values()
                if edge.source_node_id in selected and edge.target_node_id in selected
            )
        return GraphSubgraph(nodes, tuple(sorted(edges, key=lambda edge: edge.edge_id)))

    @staticmethod
    def _matches(node: GraphNode, query: GraphQuery) -> bool:
        return (
            (not query.entity_types or node.entity_type in query.entity_types)
            and (not query.tags or set(query.tags).issubset(node.tags))
            and node.confidence >= query.minimum_confidence
            and node.importance >= query.minimum_importance
            and (query.label_contains is None or query.label_contains.lower() in node.label.lower())
        )

    @staticmethod
    def _updated(current: GraphNode | GraphEdge, update: GraphUpdate) -> GraphNode | GraphEdge:
        if current.version != update.expected_version:
            raise GraphVersionConflict(f"Expected version {update.expected_version}, found {current.version}.")
        changes = {"version": current.version + 1, "updated_at": datetime.now(timezone.utc)}
        fields = ("attributes", "tags", "weight", "confidence", "importance", "metadata")
        if isinstance(current, GraphNode):
            fields = (*fields, "embedding")
        elif update.embedding is not None:
            raise ValueError("Only graph nodes can contain embeddings.")
        for field in fields:
            value = getattr(update, field)
            if value is not None:
                changes[field] = value
        replacement = replace(current, **changes)
        KnowledgeGraph._validate_scores(replacement.weight, replacement.confidence, replacement.importance)
        return replacement

    @staticmethod
    def _validate_scores(weight: float, confidence: float, importance: float) -> None:
        if weight < 0:
            raise ValueError("Graph weight cannot be negative.")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("Graph confidence must be between 0 and 1.")
        if not 0.0 <= importance <= 1.0:
            raise ValueError("Graph importance must be between 0 and 1.")

    def _incident_edges(self, node_id: str, direction: TraversalDirection) -> tuple[str, ...]:
        if direction is TraversalDirection.OUTBOUND:
            return tuple(self._outbound[node_id])
        if direction is TraversalDirection.INBOUND:
            return tuple(self._inbound[node_id])
        return tuple(self._outbound[node_id] | self._inbound[node_id])

    @staticmethod
    def _neighbor(edge: GraphEdge, current_node_id: str, direction: TraversalDirection) -> str | None:
        if direction is TraversalDirection.OUTBOUND and edge.source_node_id == current_node_id:
            return edge.target_node_id
        if direction is TraversalDirection.INBOUND and edge.target_node_id == current_node_id:
            return edge.source_node_id
        if direction is TraversalDirection.BOTH:
            return edge.target_node_id if edge.source_node_id == current_node_id else edge.source_node_id
        return None

    @staticmethod
    def _cosine_similarity(first: tuple[float, ...], second: tuple[float, ...]) -> float:
        if len(first) != len(second) or not first or not second:
            return 0.0
        denominator = math.sqrt(sum(value * value for value in first)) * math.sqrt(sum(value * value for value in second))
        if denominator == 0:
            return 0.0
        return sum(left * right for left, right in zip(first, second)) / denominator
