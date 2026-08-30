from __future__ import annotations

import pytest

from app.knowledge import (
    EntityType,
    GraphAttribute,
    GraphEdge,
    GraphNode,
    GraphQuery,
    GraphTraversal,
    GraphUpdate,
    GraphUpdateKind,
    GraphVersionConflict,
    KnowledgeGraph,
    RelationshipType,
    TraversalDirection,
)


def _graph() -> tuple[KnowledgeGraph, GraphNode, GraphNode, GraphNode]:
    graph = KnowledgeGraph()
    project = graph.create_node(GraphNode.create(EntityType.PROJECT, "JARVIS", tags=("assistant",), importance=0.9, embedding=(1.0, 0.0)))
    source = graph.create_node(GraphNode.create(EntityType.FILE, "app/main.py", tags=("python",), embedding=(0.9, 0.1)))
    technology = graph.create_node(GraphNode.create(EntityType.TECHNOLOGY, "FastAPI", tags=("python",), embedding=(0.0, 1.0)))
    return graph, project, source, technology


def test_graph_creates_typed_nodes_and_relationship_edges():
    graph, project, source, _ = _graph()
    edge = graph.create_edge(GraphEdge.create(project.node_id, source.node_id, RelationshipType.CONTAINS, confidence=0.95))

    assert graph.node(project.node_id) == project
    assert graph.edge(edge.edge_id).relationship is RelationshipType.CONTAINS
    assert edge.confidence == 0.95


def test_graph_traversal_supports_branching_and_relationship_filters():
    graph, project, source, technology = _graph()
    graph.create_edge(GraphEdge.create(project.node_id, source.node_id, RelationshipType.CONTAINS))
    graph.create_edge(GraphEdge.create(source.node_id, technology.node_id, RelationshipType.USES))

    subgraph = graph.traverse(GraphTraversal(project.node_id, max_depth=2, relationships=(RelationshipType.CONTAINS, RelationshipType.USES)))

    assert {node.label for node in subgraph.nodes} == {"JARVIS", "app/main.py", "FastAPI"}
    assert {edge.relationship for edge in subgraph.edges} == {RelationshipType.CONTAINS, RelationshipType.USES}


def test_graph_queries_entities_tags_and_weighted_attributes():
    graph, project, source, technology = _graph()
    relation = graph.create_edge(GraphEdge.create(source.node_id, technology.node_id, RelationshipType.USES))
    result = graph.query(GraphQuery(entity_types=(EntityType.FILE, EntityType.TECHNOLOGY), tags=("python",), minimum_confidence=0.8))

    assert {node.node_id for node in result.nodes} == {source.node_id, technology.node_id}
    assert graph.query(GraphQuery(label_contains="jar")).nodes == (project,)
    relationship_result = graph.query(GraphQuery(relationships=(RelationshipType.USES,)))
    assert relationship_result.edges == (relation,)


def test_graph_similarity_and_subgraph_are_typed_and_deterministic():
    graph, project, source, technology = _graph()
    first = graph.create_edge(GraphEdge.create(project.node_id, source.node_id, RelationshipType.CONTAINS))
    graph.create_edge(GraphEdge.create(project.node_id, technology.node_id, RelationshipType.USES))

    matches = graph.similar_nodes(project.node_id)
    subgraph = graph.subgraph((project.node_id, source.node_id))

    assert matches[0][0] == source
    assert matches[0][1] > 0.9
    assert subgraph.edges == (first,)


def test_graph_updates_are_versioned_and_detect_stale_writers():
    graph, project, _, _ = _graph()
    update = GraphUpdate(
        GraphUpdateKind.NODE,
        project.node_id,
        expected_version=1,
        attributes=(GraphAttribute("status", "active"),),
        importance=1.0,
    )

    updated = graph.update(update)

    assert updated.version == 2
    assert updated.attributes == (GraphAttribute("status", "active"),)
    with pytest.raises(GraphVersionConflict):
        graph.update(update)
