"use client";
import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Plus, RefreshCw, Search } from "lucide-react";
import { useOperationalSelectionStore } from "../../store/operational-selection-store";
import { NodeInspector } from "./node-inspector";
import { useKnowledgeGraph } from "./hooks/use-knowledge-graph";

export function KnowledgeGraphCenter() {
  const { nodeId, selectNode } = useOperationalSelectionStore();
  const [label, setLabel] = useState("");
  const [entityType, setEntityType] = useState("");
  const [depth, setDepth] = useState(2);
  const [composing, setComposing] = useState(false);
  const [newLabel, setNewLabel] = useState("");
  const [newType, setNewType] = useState("generic");
  const [newTags, setNewTags] = useState("");
  const [linkTarget, setLinkTarget] = useState("");
  const [relationship, setRelationship] = useState("related_to");

  const { overview, node, traversal, createNode, createEdge, deleteNode, refreshAll } = useKnowledgeGraph({ label, entityType, nodeId, depth });

  const data = overview.data?.data;
  const nodes = data?.nodes ?? [];
  const edges = data?.edges ?? [];
  const entityTypes = data?.entity_types ?? [];
  const relationships = data?.relationships ?? [];
  const detail = (node.data?.available ? node.data.data : undefined) ?? undefined;
  // traverse() counts the start node in its subgraph; reach means "everything else".
  const reach = Math.max((traversal.data?.data.nodes.length ?? 0) - 1, 0);

  // Degree per node, so the list can lead with the most connected entities.
  const degree = useMemo(() => {
    const counts = new Map<string, number>();
    for (const edge of edges) {
      counts.set(edge.source_node_id, (counts.get(edge.source_node_id) ?? 0) + 1);
      counts.set(edge.target_node_id, (counts.get(edge.target_node_id) ?? 0) + 1);
    }
    return counts;
  }, [edges]);
  const ordered = useMemo(() => [...nodes].sort((a, b) =>
    (degree.get(b.node_id) ?? 0) - (degree.get(a.node_id) ?? 0) || a.label.localeCompare(b.label)), [degree, nodes]);
  const byType = useMemo(() => {
    const counts = new Map<string, number>();
    for (const item of nodes) counts.set(item.entity_type, (counts.get(item.entity_type) ?? 0) + 1);
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [nodes]);

  const submitNode = async () => {
    if (!newLabel.trim()) return;
    const created = await createNode.mutateAsync({
      label: newLabel.trim(),
      entityType: newType,
      tags: newTags.split(",").map(tag => tag.trim()).filter(Boolean),
    });
    selectNode(created.node_id);
    setNewLabel(""); setNewTags(""); setComposing(false);
  };

  return <motion.div className="knowledge-graph" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
    <header>
      <div><span>Knowledge</span><h1>Knowledge Graph</h1><p>Entities, relationships, similarity, and traversal over the local knowledge store.</p></div>
      <div className="graph-header-actions">
        <button onClick={() => setComposing(value => !value)}><Plus size={15}/> New entity</button>
        <button onClick={refreshAll}><RefreshCw size={15} className={overview.isFetching ? "spin" : undefined}/> Refresh</button>
      </div>
    </header>

    {!overview.data?.available && <p className="graph-api-notice">{overview.data?.reason ?? "Checking knowledge graph availability…"}</p>}

    {composing && <form className="graph-composer" onSubmit={event => { event.preventDefault(); void submitNode(); }}>
      <label>Label<input value={newLabel} onChange={event => setNewLabel(event.target.value)} placeholder="Payments service" required/></label>
      <label>Entity type
        <select value={newType} onChange={event => setNewType(event.target.value)}>
          {(entityTypes.length ? entityTypes : ["generic"]).map(type => <option key={type} value={type}>{type}</option>)}
        </select>
      </label>
      <label>Tags<input value={newTags} onChange={event => setNewTags(event.target.value)} placeholder="backend, billing"/></label>
      <div className="graph-composer-actions">
        <button type="submit" className="primary" disabled={createNode.isPending || !newLabel.trim()}>{createNode.isPending ? "Creating…" : "Create entity"}</button>
        <button type="button" onClick={() => setComposing(false)}>Cancel</button>
      </div>
      {createNode.isError && <p className="graph-api-notice">Could not create the entity. Check that the backend is running.</p>}
    </form>}

    <div className="graph-stats">
      <div><span>Entities</span><strong>{data?.total_nodes ?? 0}</strong></div>
      <div><span>Relationships</span><strong>{data?.total_edges ?? 0}</strong></div>
      <div><span>Types in use</span><strong>{byType.length}/{entityTypes.length}</strong></div>
      <div><span>Most connected</span><strong>{ordered[0]?.label ?? "—"}</strong></div>
    </div>

    <div className="graph-layout">
      <section className="graph-card">
        <header className="graph-toolbar">
          <h2>Entities</h2>
          <label><Search size={14}/><input value={label} onChange={event => setLabel(event.target.value)} placeholder="Filter by label"/></label>
          <select value={entityType} onChange={event => setEntityType(event.target.value)} aria-label="Filter by entity type">
            <option value="">All types</option>
            {entityTypes.map(type => <option key={type} value={type}>{type}</option>)}
          </select>
          <span>{ordered.length}</span>
        </header>
        {ordered.length ? <ul className="graph-nodes">{ordered.map(item =>
          <li key={item.node_id}>
            <button className={item.node_id === nodeId ? "selected" : undefined} onClick={() => selectNode(item.node_id)}>
              <strong>{item.label}</strong>
              <em>{item.entity_type}</em>
              <span>{degree.get(item.node_id) ?? 0} link{(degree.get(item.node_id) ?? 0) === 1 ? "" : "s"}</span>
            </button>
          </li>)}</ul>
          : <p className="graph-unavailable">No entities match this filter. Create one, or clear the filters above.</p>}
      </section>

      <NodeInspector
        detail={detail}
        traversal={traversal.data?.data}
        reason={node.data && !node.data.available ? node.data.reason : undefined}
        onSelect={selectNode}
        onDelete={id => deleteNode.mutate(id)}
        deleting={deleteNode.isPending}
      />

      <aside className="graph-side">
        <section className="graph-card">
          <h2>Composition</h2>
          {byType.length ? <ul className="graph-breakdown">{byType.map(([type, count]) =>
            <li key={type}>
              <span>{type}</span>
              <div className="graph-bar"><span style={{ width: `${nodes.length ? (count / nodes.length) * 100 : 0}%` }}/></div>
              <strong>{count}</strong>
            </li>)}</ul>
            : <p className="graph-unavailable">No entities to summarise yet.</p>}
        </section>

        <section className="graph-card">
          <h2>Traversal depth</h2>
          <input type="range" min={1} max={6} value={depth} onChange={event => setDepth(Number(event.target.value))} aria-label="Traversal depth"/>
          <p className="graph-unavailable">{nodeId
            ? `Depth ${depth} reaches ${reach} entities and ${traversal.data?.data.edges.length ?? 0} relationships from the selected node.`
            : "Select an entity to measure how far the graph reaches from it."}</p>
        </section>

        <section className="graph-card">
          <h2>Link entities</h2>
          {nodeId ? <form className="graph-form" onSubmit={event => {
            event.preventDefault();
            if (!linkTarget) return;
            createEdge.mutate({ source: nodeId, target: linkTarget, relationship });
            setLinkTarget("");
          }}>
            <select value={relationship} onChange={event => setRelationship(event.target.value)} aria-label="Relationship">
              {(relationships.length ? relationships : ["related_to"]).map(item => <option key={item} value={item}>{item.replace(/_/g, " ")}</option>)}
            </select>
            <select value={linkTarget} onChange={event => setLinkTarget(event.target.value)} aria-label="Target entity">
              <option value="">Choose a target…</option>
              {nodes.filter(item => item.node_id !== nodeId).map(item => <option key={item.node_id} value={item.node_id}>{item.label}</option>)}
            </select>
            <button type="submit" className="primary" disabled={createEdge.isPending || !linkTarget}>{createEdge.isPending ? "Linking…" : "Create relationship"}</button>
            {createEdge.isError && <p className="graph-unavailable">Could not create the relationship.</p>}
          </form> : <p className="graph-unavailable">Select a source entity on the left to draw a relationship from it.</p>}
        </section>

        <section className="graph-card">
          <h2>Recent relationships</h2>
          {edges.length ? <ul className="graph-edges">{edges.slice(-12).reverse().map(edge =>
            <li key={edge.edge_id}>
              <button onClick={() => selectNode(edge.source_node_id)}>{nodes.find(item => item.node_id === edge.source_node_id)?.label ?? edge.source_node_id}</button>
              <em>{edge.relationship.replace(/_/g, " ")}</em>
              <button onClick={() => selectNode(edge.target_node_id)}>{nodes.find(item => item.node_id === edge.target_node_id)?.label ?? edge.target_node_id}</button>
            </li>)}</ul>
            : <p className="graph-unavailable">No relationships yet.</p>}
        </section>
      </aside>
    </div>
  </motion.div>;
}
