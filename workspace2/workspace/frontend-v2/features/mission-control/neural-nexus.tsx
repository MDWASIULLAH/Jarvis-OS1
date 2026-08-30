"use client";
import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Box, Network, Pause, Play, RefreshCw, SkipBack, SkipForward } from "lucide-react";
import { realtimeClient } from "../../services/realtime-client";
import { apiUrl } from "../../services/backend";
import { useOperationalSelectionStore } from "../../store/operational-selection-store";
import { missionService } from "./services/mission-service";
import { NexusGraph } from "./nexus-graph";
import { NexusInspector } from "./nexus-inspector";
import type { NexusNode } from "./types";
const Nexus3DView = dynamic(() => import("./nexus-3d-view").then(module => module.Nexus3DView), { ssr: false });

const localSnapshot = {
  snapshot_id: "local-runtime", mission_id: "local-runtime", created_at: new Date(0).toISOString(),
  nodes: [
    { node_id: "jarvis", kind: "orchestrator", label: "JARVIS runtime", status: "online", health: "local" },
    { node_id: "brain", kind: "reasoning", label: "Brain Core", status: "ready", health: "local" },
    { node_id: "model", kind: "model", label: "Model router", status: "ready", health: "local" },
    { node_id: "tools", kind: "capability", label: "Tools & attachments", status: "ready", health: "local" },
    { node_id: "memory", kind: "memory", label: "Local memory", status: "ready", health: "local" },
  ],
  edges: [
    { edge_id: "jarvis-brain", source_id: "jarvis", target_id: "brain", relationship: "coordinates" },
    { edge_id: "brain-model", source_id: "brain", target_id: "model", relationship: "requests" },
    { edge_id: "brain-tools", source_id: "brain", target_id: "tools", relationship: "uses" },
    { edge_id: "brain-memory", source_id: "brain", target_id: "memory", relationship: "reads" },
  ],
};

export function NeuralNexus({ missionId }: { missionId?: string }) {
  const [mode, setMode] = useState<"2d" | "3d">("2d"); const [selected, setSelected] = useState<NexusNode>(); const [replaying, setReplaying] = useState(false); const [snapshotIndex, setSnapshotIndex] = useState(0); const client = useQueryClient(); const { agentId, selectAgent } = useOperationalSelectionStore();
  const snapshot = useQuery({ queryKey: ["nexus", missionId], queryFn: () => missionService.nexus(missionId), enabled: Boolean(missionId), staleTime: 5_000 });
  const snapshots = useQuery({ queryKey: ["nexus-snapshots", missionId], queryFn: () => missionService.nexusSnapshots(missionId), enabled: Boolean(missionId), staleTime: 5_000 });
  useEffect(() => { if (!missionId) return; return realtimeClient.connect(apiUrl("/v1/events/stream"), event => { if (event.type.includes("graph_updated") || event.type.includes("mission") || event.type.includes("agent")) { void client.invalidateQueries({ queryKey: ["nexus", missionId] }); void client.invalidateQueries({ queryKey: ["nexus-snapshots", missionId] }); } }); }, [client, missionId]);
  const history = snapshots.data?.available ? snapshots.data.data : []; const graph = history[snapshotIndex] ?? (snapshot.data?.available ? snapshot.data.data : null) ?? localSnapshot; useEffect(() => { if (!replaying || history.length < 2) return; const timer = window.setTimeout(() => { if (snapshotIndex >= history.length - 1) setReplaying(false); else setSnapshotIndex(index => index + 1); }, 1000); return () => window.clearTimeout(timer); }, [history.length, replaying, snapshotIndex]);
  useEffect(() => { const agent = graph?.nodes.find(node => node.node_id === agentId); if (agent) setSelected(agent); }, [agentId, graph]); const reason = useMemo(() => !missionId ? "Select a mission with a live graph to open Neural Nexus." : snapshot.data?.reason ?? "Neural Nexus is not exposed by this deployment.", [missionId, snapshot.data?.reason]);
  const chooseNode = (node: NexusNode) => { setSelected(node); if (node.kind.includes("agent")) selectAgent(node.node_id); }; return <section className="neural-nexus"><header><div><span>Visual intelligence</span><h2>Neural Nexus</h2><p className="nexus-unavailable">{missionId ? "Live mission graph when available." : "Showing the local runtime map; select a mission for its live agent graph."}</p></div><div className="nexus-actions"><button className={mode === "2d" ? "active" : ""} onClick={() => setMode("2d")}><Network size={14}/> 2D</button><button className={mode === "3d" ? "active" : ""} onClick={() => setMode("3d")}><Box size={14}/> 3D</button><button onClick={() => void snapshot.refetch()} aria-label="Refresh Neural Nexus"><RefreshCw size={14}/></button></div></header><div className="nexus-layout">{mode === "2d" ? <NexusGraph snapshot={graph} onSelect={chooseNode}/> : <Nexus3DView snapshot={graph}/>}<NexusInspector node={selected} onClose={() => setSelected(undefined)}/></div>{history.length > 1 && <div className="nexus-replay"><button onClick={() => setSnapshotIndex(0)} aria-label="First graph snapshot"><SkipBack size={14}/></button><button onClick={() => setReplaying(value => !value)} aria-label={replaying ? "Pause graph replay" : "Play graph replay"}>{replaying ? <Pause size={14}/> : <Play size={14}/>}</button><button onClick={() => setSnapshotIndex(index => Math.min(history.length - 1, index + 1))} aria-label="Next graph snapshot"><SkipForward size={14}/></button><input type="range" min="0" max={history.length - 1} value={snapshotIndex} onChange={event => setSnapshotIndex(Number(event.target.value))} aria-label="Graph replay position"/></div>}</section>;
}
