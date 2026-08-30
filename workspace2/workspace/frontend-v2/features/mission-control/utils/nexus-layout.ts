import type { Edge, Node } from "@xyflow/react";
import type { NexusSnapshot } from "../types";
export function nexusFlow(snapshot: NexusSnapshot): { nodes: Node[]; edges: Edge[] } {
  const columns = Math.max(1, Math.ceil(Math.sqrt(snapshot.nodes.length)));
  return {
    nodes: snapshot.nodes.map((node, index) => ({
      id: node.node_id,
      position: { x: (index % columns) * 230 + 40, y: Math.floor(index / columns) * 140 + 40 },
      data: { ...node, label: `${node.label} (${node.kind})` },
      type: "default",
    })),
    edges: snapshot.edges.map(edge => ({
      id: edge.edge_id,
      source: edge.source_id,
      target: edge.target_id,
      label: edge.relationship,
      animated: true,
    })),
  };
}
