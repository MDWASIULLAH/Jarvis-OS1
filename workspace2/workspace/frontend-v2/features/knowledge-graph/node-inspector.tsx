"use client";
import { Trash2 } from "lucide-react";
import type { GraphNode, GraphNodeDetail, GraphSubgraph } from "./types";

const pct = (value?: number) => (value === undefined || value === null ? "—" : `${Math.round(value * 100)}%`);

/**
 * `neighbors()` is `traverse(depth=1)` on the backend, so the subgraph it returns
 * includes the centre node itself. Walk the edges instead of the node list: that
 * drops the centre and hands us the relationship label for free.
 */
function neighbours(subgraph: GraphSubgraph | undefined, centre: string, side: "outbound" | "inbound") {
  if (!subgraph) return [];
  const byId = new Map(subgraph.nodes.map(node => [node.node_id, node]));
  const rows: { node: GraphNode; relationship: string; edgeId: string }[] = [];
  for (const edge of subgraph.edges) {
    const otherId = side === "outbound" ? edge.target_node_id : edge.source_node_id;
    const anchorId = side === "outbound" ? edge.source_node_id : edge.target_node_id;
    if (anchorId !== centre || otherId === centre) continue;
    const node = byId.get(otherId);
    if (node) rows.push({ node, relationship: edge.relationship, edgeId: edge.edge_id });
  }
  return rows;
}

/**
 * Neighbourhood + similarity view for one node, backed by
 * GET /v1/graph/nodes/{id} and GET /v1/graph/traverse/{id}.
 */
export function NodeInspector({ detail, traversal, reason, onSelect, onDelete, deleting }: {
  detail?: GraphNodeDetail | null;
  traversal?: GraphSubgraph;
  reason?: string;
  onSelect: (nodeId: string) => void;
  onDelete: (nodeId: string) => void;
  deleting?: boolean;
}) {
  if (!detail) {
    return <section className="graph-card">
      <h2>Node inspector</h2>
      <p className="graph-unavailable">{reason ?? "Select a node to see its attributes, inbound and outbound relationships, similar entities, and traversal reach."}</p>
    </section>;
  }
  const { node, similar } = detail;
  const out = neighbours(detail.outbound, node.node_id, "outbound");
  const inn = neighbours(detail.inbound, node.node_id, "inbound");
  // traverse() also counts the start node, so subtract it for a true reach.
  const reach = Math.max((traversal?.nodes.length ?? 0) - 1, 0);
  return <section className="graph-card graph-inspector">
    <header className="graph-card-header">
      <div>
        <span className="chip">{node.entity_type}</span>
        <h2>{node.label}</h2>
        <code>{node.node_id}</code>
      </div>
      <button className="graph-danger" onClick={() => onDelete(node.node_id)} disabled={deleting} title="Delete this node">
        <Trash2 size={14}/> Delete
      </button>
    </header>

    <dl className="graph-facts">
      <div><dt>Importance</dt><dd>{pct(node.importance)}</dd></div>
      <div><dt>Confidence</dt><dd>{pct(node.confidence)}</dd></div>
      <div><dt>Weight</dt><dd>{node.weight ?? "—"}</dd></div>
      <div><dt>Revision</dt><dd>{node.version ?? 1}</dd></div>
      <div><dt>Outbound</dt><dd>{out.length}</dd></div>
      <div><dt>Inbound</dt><dd>{inn.length}</dd></div>
      <div><dt>Traversal reach</dt><dd>{reach} node{reach === 1 ? "" : "s"}</dd></div>
      <div><dt>Updated</dt><dd>{node.updated_at ? new Date(node.updated_at).toLocaleString() : "—"}</dd></div>
    </dl>

    {node.tags?.length ? <div className="graph-chips">{node.tags.map(tag => <span key={tag} className="chip">{tag}</span>)}</div> : null}

    {node.attributes?.length ? <section className="graph-subsection">
      <h3>Attributes</h3>
      <ul className="graph-attributes">{node.attributes.map(attribute =>
        <li key={attribute.key}><strong>{attribute.key}</strong><span>{attribute.value}</span></li>)}</ul>
    </section> : null}

    <section className="graph-subsection">
      <h3>Outbound ({out.length})</h3>
      {out.length ? <ul className="graph-neighbours">{out.map(row =>
        <li key={row.edgeId}><button onClick={() => onSelect(row.node.node_id)}>
          <strong>{row.node.label}</strong><em>{row.relationship.replace(/_/g, " ")}</em>
        </button></li>)}</ul>
        : <p className="graph-unavailable">This node points at nothing yet.</p>}
    </section>

    <section className="graph-subsection">
      <h3>Inbound ({inn.length})</h3>
      {inn.length ? <ul className="graph-neighbours">{inn.map(row =>
        <li key={row.edgeId}><button onClick={() => onSelect(row.node.node_id)}>
          <strong>{row.node.label}</strong><em>{row.relationship.replace(/_/g, " ")}</em>
        </button></li>)}</ul>
        : <p className="graph-unavailable">Nothing references this node yet.</p>}
    </section>

    <section className="graph-subsection">
      <h3>Similar entities</h3>
      {similar.length ? <ul className="graph-neighbours">{similar.map(item =>
        <li key={item.node.node_id}><button onClick={() => onSelect(item.node.node_id)}>
          <strong>{item.node.label}</strong><em>{Math.round(item.similarity * 100)}% match</em>
        </button></li>)}</ul>
        : <p className="graph-unavailable">No similar entities — similarity needs shared tags or attributes.</p>}
    </section>
  </section>;
}
