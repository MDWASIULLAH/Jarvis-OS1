"use client";
import type { AgentTask, Mission, MissionMetrics } from "./types";

/**
 * Mission-wide counters plus the selected mission's own MissionMetrics, which
 * MissionManager already computes. The old copy claimed latency/token/tool
 * metrics were unexposed; latency, queue depth, and throughput are exposed.
 */
export function MetricsPanel({ missions, tasks, metrics }: { missions: Mission[]; tasks: AgentTask[]; metrics?: MissionMetrics }) {
  const cells: { label: string; value: string }[] = [
    { label: "Active missions", value: String(missions.filter(mission => mission.lifecycle === "active").length) },
    { label: "Completed", value: String(missions.filter(mission => mission.lifecycle === "completed").length) },
    { label: "Failures", value: String(missions.filter(mission => mission.lifecycle === "failed").length) },
    { label: "Running tasks", value: String(tasks.filter(task => task.status === "running").length) },
  ];
  if (metrics) {
    cells.push(
      { label: "Mission agents", value: String(metrics.active_agents ?? 0) },
      { label: "Tasks done", value: String(metrics.completed_tasks ?? 0) },
      { label: "Task failures", value: String(metrics.failed_tasks ?? 0) },
      { label: "Retries", value: String(metrics.retries ?? 0) },
      { label: "Queue depth", value: String(metrics.queue_size ?? 0) },
      { label: "Latency", value: `${(metrics.execution_latency_seconds ?? 0).toFixed(2)}s` },
      { label: "Throughput", value: `${(metrics.throughput ?? 0).toFixed(2)}/s` },
      { label: "Helpers", value: String(metrics.helper_agents ?? 0) },
    );
  }
  return <section className="mission-section">
    <h3>Mission metrics</h3>
    <div className="metric-grid">{cells.map(cell => <div key={cell.label}><span>{cell.label}</span><strong>{cell.value}</strong></div>)}</div>
    {!metrics && <p className="mission-unavailable">Select a mission to see its agent, task, latency, and throughput metrics.</p>}
  </section>;
}
