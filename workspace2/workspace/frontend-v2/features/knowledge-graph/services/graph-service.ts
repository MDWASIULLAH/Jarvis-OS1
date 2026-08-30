import { apiClient } from "../../../services/api-client";
import type { GraphEdge, GraphNode, GraphNodeDetail, GraphOverview, GraphState, GraphSubgraph } from "../types";

const EMPTY: GraphOverview = { nodes: [], edges: [], total_nodes: 0, total_edges: 0, entity_types: [], relationships: [] };

/** Wraps failures so a stopped backend degrades the panel instead of throwing. */
async function state<T>(path: string, fallback: T): Promise<GraphState<T>> {
  try {
    return { available: true, data: await apiClient.request<T>(path) };
  } catch {
    return { available: false, data: fallback, reason: "The knowledge graph API is unreachable. Start the JARVIS backend on port 8000 and refresh." };
  }
}

const id = (value: string) => encodeURIComponent(value);

export const graphService = {
  overview: (label = "", entityType = "", limit = 250) =>
    state<GraphOverview>(`/v1/graph?limit=${limit}${label ? `&label=${encodeURIComponent(label)}` : ""}${entityType ? `&entity_type=${encodeURIComponent(entityType)}` : ""}`, EMPTY),
  node: (nodeId: string) => state<GraphNodeDetail | null>(`/v1/graph/nodes/${id(nodeId)}`, null),
  traverse: (nodeId: string, depth = 2, direction = "both") =>
    state<GraphSubgraph>(`/v1/graph/traverse/${id(nodeId)}?depth=${depth}&direction=${direction}`, { nodes: [], edges: [] }),
  createNode: (label: string, entityType: string, tags: string[] = []) =>
    apiClient.post<GraphNode>("/v1/graph/nodes", { label, entity_type: entityType, tags }),
  createEdge: (sourceNodeId: string, targetNodeId: string, relationship: string) =>
    apiClient.post<GraphEdge>("/v1/graph/edges", { source_node_id: sourceNodeId, target_node_id: targetNodeId, relationship }),
  deleteNode: (nodeId: string) => apiClient.delete<GraphNode>(`/v1/graph/nodes/${id(nodeId)}`),
};
