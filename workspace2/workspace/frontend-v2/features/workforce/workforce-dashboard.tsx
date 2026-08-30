"use client";
import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { RefreshCw, Send } from "lucide-react";
import { useOperationalSelectionStore } from "../../store/operational-selection-store";
import { ActivityPanels } from "./activity-panels";
import { AgentDetails } from "./agent-details";
import { AgentGrid } from "./agent-grid";
import { AgentHierarchy } from "./agent-hierarchy";
import { CommunicationViewer } from "./communication-viewer";
import { PerformancePanel } from "./performance-panel";
import { useWorkforce } from "./hooks/use-workforce";

const AGENT_ACTIONS = ["pause", "resume", "cancel", "recover", "health-check"] as const;

export function WorkforceDashboard() {
  const { agents, communications, status, swarmTasks, activity, act, assignTask, broadcast, refreshAll } = useWorkforce();
  const { agentId, selectAgent } = useOperationalSelectionStore();
  const [taskTitle, setTaskTitle] = useState("");
  const [message, setMessage] = useState("");

  const data = agents.data?.data ?? [];
  const selected = useMemo(() => data.find(agent => agent.agent_id === agentId), [agentId, data]);
  const tasks = swarmTasks.data?.data ?? [];

  return <motion.div className="workforce-dashboard" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
    <header>
      <div><span>Operations</span><h1>AI Workforce Center</h1><p>Agent hierarchy, health, communication, task load, and real operational evidence.</p></div>
      <button onClick={refreshAll}><RefreshCw size={15} className={agents.isFetching ? "spin" : undefined}/> Refresh</button>
    </header>

    {!agents.data?.available && <p className="workforce-api-notice">{agents.data?.reason ?? "Checking workforce API availability…"}</p>}

    <form className="workforce-dispatch" onSubmit={event => {
      event.preventDefault();
      if (!taskTitle.trim()) return;
      assignTask.mutate({ title: taskTitle.trim() });
      setTaskTitle("");
    }}>
      <label>Dispatch a task to the swarm
        <input value={taskTitle} onChange={event => setTaskTitle(event.target.value)} placeholder="Audit the auth module for missing tests"/>
      </label>
      <button type="submit" className="primary" disabled={assignTask.isPending || !taskTitle.trim()}>
        <Send size={14}/> {assignTask.isPending ? "Dispatching…" : "Assign"}
      </button>
      {assignTask.isError && <p className="workforce-unavailable">Dispatch failed — no idle agent, or the backend is down.</p>}
      {assignTask.isSuccess && <p className="workforce-unavailable">Assigned to {assignTask.data?.assignment?.agent_id?.slice(0, 8) ?? "an agent"}.</p>}
    </form>

    <div className="workforce-layout">
      <AgentGrid agents={data} selectedId={agentId} onSelect={selectAgent}/>
      <AgentDetails agent={selected} actions={selected && <>
        <div className="agent-actions">{AGENT_ACTIONS.map(action =>
          <button key={action} disabled={act.isPending} onClick={() => act.mutate({ agentId: selected.agent_id, action })}>{action.replace("-", " ")}</button>)}
        </div>
        <form className="agent-broadcast" onSubmit={event => {
          event.preventDefault();
          if (!message.trim()) return;
          broadcast.mutate({ senderAgentId: selected.agent_id, content: message.trim() });
          setMessage("");
        }}>
          <input value={message} onChange={event => setMessage(event.target.value)} placeholder="Broadcast a message from this agent"/>
          <button type="submit" disabled={broadcast.isPending || !message.trim()}>Broadcast</button>
        </form>
      </>}/>
      <aside>
        <PerformancePanel agents={data} status={status.data?.data}/>
        <AgentHierarchy agents={data} onSelect={selectAgent}/>
        <CommunicationViewer communications={communications.data?.data ?? []}/>
        <ActivityPanels
          entries={activity.data?.data.entries ?? []}
          reason={activity.data && !activity.data.available ? activity.data.reason : undefined}
        />
        <section className="workforce-section">
          <h3>Swarm task queue</h3>
          {tasks.length ? <ul className="swarm-tasks">{tasks.map(task =>
            <li key={task.task_id}><strong>{task.title}</strong><span>{task.lifecycle}</span></li>)}</ul>
            : <p className="workforce-unavailable">No tasks are queued. Dispatch one above to see the swarm pick it up.</p>}
        </section>
      </aside>
    </div>
  </motion.div>;
}
