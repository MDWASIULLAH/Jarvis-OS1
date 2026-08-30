/** Shapes returned by /v1/graph* — see KnowledgeGraph in the backend. */
export type GraphAttribute = { key: string; value: string };
export type GraphNode = {
  node_id: string;
  entity_type: string;
  label: string;
  attributes?: GraphAttribute[];
  tags?: string[];
  metadata?: GraphAttribute[];
  weight?: number;
  confidence?: number;
  importance?: number;
  version?: number;
  created_at?: string;
  updated_at?: string;
};
export type GraphEdge = {
  edge_id: string;
  source_node_id: string;
  target_node_id: string;
  relationship: string;
  weight?: number;
  confidence?: number;
  importance?: number;
  created_at?: string;
};
export type GraphOverview = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  total_nodes: number;
  total_edges: number;
  entity_types: string[];
  relationships: string[];
};
/** `graph.neighbors()` and `graph.traverse()` both encode to a subgraph, not a list. */
export type GraphSubgraph = { nodes: GraphNode[]; edges: GraphEdge[] };
export type GraphNodeDetail = {
  node: GraphNode;
  outbound: GraphSubgraph;
  inbound: GraphSubgraph;
  similar: { node: GraphNode; similarity: number }[];
};
export type GraphState<T> = { available: boolean; data: T; reason?: string };
