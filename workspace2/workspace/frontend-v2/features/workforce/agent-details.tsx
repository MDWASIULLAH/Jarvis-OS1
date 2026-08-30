"use client";
import type { ReactNode } from "react";
import type { WorkforceAgent } from "./types";

const num = (value?: number, suffix = "") => (value === undefined || value === null ? "Unavailable" : `${value}${suffix}`);

export function AgentDetails({ agent, actions }: { agent?: WorkforceAgent; actions?: ReactNode }) {
  if (!agent) {
    return <section className="agent-details"><h2>Agent inspector</h2><p className="workforce-unavailable">Select a live agent to inspect its resources, activity, dependencies, and related operational history.</p></section>;
  }
  return <section className="agent-details">
    <h2>Agent inspector</h2>
    <header>
      <div><span className={`agent-state ${agent.lifecycle}`}>{agent.lifecycle}</span><h3>{agent.name}</h3><p>{agent.kind}</p></div>
      <code>{agent.agent_id}</code>
    </header>
    {actions}
    <dl>
      <div><dt>Current task</dt><dd>{agent.current_task ?? "Idle"}</dd></div>
      <div><dt>Mission</dt><dd>{agent.mission_id ?? "Unassigned"}</dd></div>
      <div><dt>Parent</dt><dd>{agent.parent_agent_id ?? "None"}</dd></div>
      <div><dt>Health</dt><dd>{agent.health?.score === undefined ? "Unavailable" : `${Math.round(agent.health.score * 100)}%`}</dd></div>
      <div><dt>CPU</dt><dd>{num(agent.health?.cpu_percent, "%")}</dd></div>
      <div><dt>RAM</dt><dd>{num(agent.health?.memory_mb, " MB")}</dd></div>
      <div><dt>Execution</dt><dd>{num(agent.health?.execution_seconds, "s")}</dd></div>
      <div><dt>Queue</dt><dd>{num(agent.health?.queue_size)}</dd></div>
    </dl>
    {/* The orchestrator's instruction text for this specialist, surfaced by
        GET /v1/workforce/agents as `brief` -- this is what the agent is for. */}
    {agent.brief && <section className="agent-brief"><h4>Role brief</h4><p>{agent.brief}</p></section>}
    <section>
      <h4>Capabilities</h4>
      {agent.capabilities?.length
        ? agent.capabilities.map(item => <span key={item.capability_id}>{item.capability_id}</span>)
        : <p>No capabilities are bound to this agent yet; they attach when a task requiring a tool is assigned.</p>}
    </section>
  </section>;
}
