"use client";
import { useEffect, useMemo, useState } from "react";
import { Background, Controls, MiniMap, ReactFlow, useEdgesState, useNodesState } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { NexusNode, NexusSnapshot } from "./types";
import { nexusFlow } from "./utils/nexus-layout";

export function NexusGraph({ snapshot, onSelect }: { snapshot: NexusSnapshot; onSelect: (node: NexusNode) => void }) {
  const graph = useMemo(() => nexusFlow(snapshot), [snapshot]);
  const [nodes, setNodes, onNodesChange] = useNodesState(graph.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(graph.edges);
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("all");

  useEffect(() => {
    setNodes(graph.nodes);
    setEdges(graph.edges);
  }, [graph, setEdges, setNodes]);

  const visibleNodes = useMemo(
    () =>
      nodes.filter((node) => {
        const data = node.data as unknown as NexusNode;
        return (
          (kind === "all" || data.kind === kind) &&
          `${data.label ?? ""} ${data.kind ?? ""}`.toLowerCase().includes(query.toLowerCase())
        );
      }),
    [kind, nodes, query]
  );

  const visibleIds = new Set(visibleNodes.map((node) => node.id));

  return (
    <section className="nexus-graph">
      <header>
        <label>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search graph" />
        </label>
        <select value={kind} onChange={(event) => setKind(event.target.value)} aria-label="Filter graph node type">
          <option value="all">All nodes</option>
          {[...new Set(snapshot.nodes.map((node) => node.kind))].map((value) => (
            <option key={value}>{value}</option>
          ))}
        </select>
        <button onClick={() => setNodes(graph.nodes)}>Auto layout</button>
        <span>
          {visibleNodes.length}/{nodes.length} nodes
        </span>
      </header>
      <div className="nexus-canvas">
        <ReactFlow
          nodes={visibleNodes}
          edges={edges.filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target))}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={(_, node) => onSelect(node.data as unknown as NexusNode)}
          fitView
          minZoom={0.1}
          maxZoom={2}
        >
          <Background />
          <Controls />
          <MiniMap />
        </ReactFlow>
      </div>
    </section>
  );
}
