"use client";
import type { WorkforceStatus } from "./services/workforce-service";
import type { WorkforceAgent } from "./types";

/**
 * Renders the aggregate counters from GET /v1/workforce/status.
 *
 * This used to read `status.queue_size`, a field the backend never sends, so the
 * panel showed "Unavailable" even when the swarm was healthy. It now reads the
 * real payload and derives the rest from the agent roster.
 */
export function PerformancePanel({ agents, status }: { agents: WorkforceAgent[]; status?: WorkforceStatus | null }) {
  const busy = agents.filter(agent => agent.lifecycle === "busy").length;
  const failed = agents.filter(agent => agent.lifecycle === "failed").length;
  const health = status ? `${Math.round(status.average_health * 100)}%` : "—";
  const lifecycle = Object.entries(status?.lifecycle_breakdown ?? {});
  return (
    <section className="workforce-section">
      <h3>Performance</h3>
      <div className="workforce-metrics">
        <div><span>Total agents</span><strong>{status?.total_agents ?? agents.length}</strong></div>
        <div><span>Working</span><strong>{busy}</strong></div>
        <div><span>Failed</span><strong>{failed}</strong></div>
        <div><span>Open tasks</span><strong>{status?.open_tasks ?? 0}</strong></div>
        <div><span>Messages</span><strong>{status?.messages ?? 0}</strong></div>
        <div><span>Recoveries</span><strong>{status?.recoveries ?? 0}</strong></div>
        <div><span>Avg. health</span><strong>{health}</strong></div>
        <div><span>Executives</span><strong>{status?.executive_agents ?? 0}</strong></div>
      </div>
      <div className="workforce-chips">
        <span className={status?.planner_available ? "chip chip-ok" : "chip chip-off"}>Planner {status?.planner_available ? "online" : "offline"}</span>
        <span className={status?.executor_available ? "chip chip-ok" : "chip chip-off"}>Executor {status?.executor_available ? "online" : "offline"}</span>
        {lifecycle.map(([state, count]) => <span key={state} className="chip">{state} · {count}</span>)}
      </div>
    </section>
  );
}
