"use client";
import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Plus, RefreshCw } from "lucide-react";
import { FlightRecorder } from "./flight-recorder";
import { MetricsPanel } from "./metrics-panel";
import { MissionDetails } from "./mission-details";
import { MissionList } from "./mission-list";
import { NeuralNexus } from "./neural-nexus";
import { ResourceMonitor } from "./resource-monitor";
import { SystemHealth } from "./system-health";
import { useMissionControl } from "./hooks/use-mission-control";
import { useMissionStore } from "./stores/mission-store";
import { useReconciledSelection } from "../../hooks/use-reconciled-selection";
import type { MissionAction } from "./types";

const ACTIONS: MissionAction[] = ["pause", "resume", "complete", "cancel", "archive"];

export function MissionDashboard() {
  const { selectedId, select } = useMissionStore();
  const { missions, detail, runtime, system, tasks, create, transition, refreshAll } = useMissionControl(selectedId);
  const [composing, setComposing] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");

  const missionData = missions.data?.data ?? [];
  const selected = useMemo(() => missionData.find(mission => mission.mission_id === selectedId), [missionData, selectedId]);
  // Missions live in an in-memory registry, so a restart invalidates the id the
  // inspector is holding; without this the detail query polls a 404 every 10s.
  useReconciledSelection(
    selectedId,
    missionData.map(mission => mission.mission_id),
    missions.data?.available === true,
    () => select(undefined)
  );
  const taskData = tasks.data?.tasks ?? [];
  // `detail.data.data` is `MissionDetails | null` -- the route answers with a
  // null payload when the id is unknown, so collapse null into undefined here.
  const resolved = (detail.data?.available ? detail.data.data : undefined) ?? undefined;

  const submit = async () => {
    if (!title.trim()) return;
    const mission = await create.mutateAsync({ title: title.trim(), description: description.trim() });
    select(mission.mission_id);
    setTitle(""); setDescription(""); setComposing(false);
  };

  return <motion.div className="mission-dashboard" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
    <header className="mission-dashboard-header">
      <div><span>Operations</span><h1>Mission Control</h1><p>Live mission state and operational evidence from the connected JARVIS runtime.</p></div>
      <div className="mission-header-actions">
        <button onClick={() => setComposing(value => !value)}><Plus size={15}/> New mission</button>
        <button aria-label="Refresh operational data" onClick={refreshAll}><RefreshCw size={15} className={missions.isFetching ? "spin" : undefined}/> Refresh</button>
      </div>
    </header>

    {composing && <form className="mission-composer" onSubmit={event => { event.preventDefault(); void submit(); }}>
      <label>Title<input value={title} onChange={event => setTitle(event.target.value)} placeholder="Ship the release pipeline" required/></label>
      <label>Description<input value={description} onChange={event => setDescription(event.target.value)} placeholder="What should this mission track?"/></label>
      <div className="mission-composer-actions">
        <button type="submit" className="primary" disabled={create.isPending || !title.trim()}>{create.isPending ? "Creating…" : "Create mission"}</button>
        <button type="button" onClick={() => setComposing(false)}>Cancel</button>
      </div>
      {create.isError && <p className="mission-api-notice">Could not create the mission. Check that the JARVIS backend is running.</p>}
    </form>}

    {!missions.data?.available && <p className="mission-api-notice">{missions.data?.reason ?? "Checking mission API availability…"}</p>}

    <div className="mission-dashboard-grid">
      <MissionList missions={missionData} selectedId={selectedId} onSelect={select}/>
      <MissionDetails mission={selected} detail={resolved} reason={detail.data && !detail.data.available ? detail.data.reason : undefined}
        actions={selected && <div className="mission-transitions">{ACTIONS.map(action =>
          <button key={action} disabled={transition.isPending} onClick={() => transition.mutate({ missionId: selected.mission_id, action })}>{action}</button>)}</div>}/>
      <aside className="mission-side">
        <SystemHealth runtime={runtime.data} error={runtime.isError}/>
        <ResourceMonitor runtime={runtime.data} system={system.data} resources={resolved?.resources} taskCount={taskData.length}/>
        <MetricsPanel missions={missionData} tasks={taskData} metrics={resolved?.metrics}/>
        <FlightRecorder records={resolved?.flight_records}/>
      </aside>
    </div>
    <NeuralNexus missionId={selectedId}/>
  </motion.div>;
}
