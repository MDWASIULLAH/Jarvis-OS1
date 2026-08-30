"use client";
import type { MissionMetrics } from "./types";

export function OperationalAnalytics({ decisions = [], reflections = [], tools = [], connectors = [], metrics }: {
  decisions?: unknown[];
  reflections?: unknown[];
  tools?: unknown[];
  connectors?: unknown[];
  metrics?: MissionMetrics;
}) {
  // The last four cells used to be hardcoded "Unavailable"; they come from the
  // runtime mission's own counters now (GET /v1/missions/jarvis-runtime).
  const completed = metrics?.completed_tasks ?? 0;
  const failed = metrics?.failed_tasks ?? 0;
  const attempted = completed + failed;
  const cells = [
    { label: "Decision records", value: String(decisions?.length ?? 0) },
    { label: "Reflection records", value: String(reflections?.length ?? 0) },
    { label: "Registered tools", value: String(tools?.length ?? 0) },
    { label: "Connectors", value: String(connectors?.length ?? 0) },
    { label: "Task success rate", value: attempted ? `${Math.round((completed / attempted) * 100)}%` : "No tasks yet" },
    { label: "Active agents", value: metric(metrics?.active_agents, value => String(value)) },
    { label: "Execution latency", value: metric(metrics?.execution_latency_seconds, value => `${value.toFixed(2)}s`) },
    { label: "Throughput", value: metric(metrics?.throughput, value => `${value.toFixed(2)}/s`) },
  ];
  return <section className="operations-card">
    <h2>Operational analytics</h2>
    <div className="analytics-grid">{cells.map(cell =>
      <div key={cell.label}><span>{cell.label}</span><strong title={cell.value}>{cell.value}</strong></div>)}</div>
    {metrics ? <p className="operations-unavailable">
      {completed} completed, {failed} failed, {metrics.retries ?? 0} retried, {metrics.queue_size ?? 0} queued.
    </p> : null}
  </section>;
}

function metric(value: number | undefined, format: (value: number) => string) {
  return value === undefined ? "Unavailable" : format(value);
}
