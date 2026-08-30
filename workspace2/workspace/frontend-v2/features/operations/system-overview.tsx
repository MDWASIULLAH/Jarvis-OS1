"use client";
import type { RuntimeOverview, SystemSnapshot, WorkspaceEntry } from "./types";

export function SystemOverview({ runtime, system, taskCount, workspace }: {
  runtime?: RuntimeOverview;
  system?: SystemSnapshot;
  taskCount?: number;
  workspace?: WorkspaceEntry[];
}) {
  const rows = [
    { label: "System health", value: runtime ? "Connected" : "Unavailable" },
    { label: "Current model", value: stringValue(runtime?.model) },
    { label: "CPU", value: percent(system?.cpu_percent) },
    { label: "Memory", value: percent(system?.memory?.percent) },
    { label: "Running tasks", value: numberValue(taskCount) },
    // Backed by GET /v1/workspace/files; an empty workspace is a real answer, not a gap.
    { label: "Workspace", value: workspace ? `${workspace.length} item${workspace.length === 1 ? "" : "s"}` : "Unavailable" },
    { label: "Platform", value: system?.platform ?? "Unavailable" },
    { label: "Network", value: system?.network ? (system.network.is_local_only ? "Local only" : "Outbound allowed") : "Unavailable" },
  ];
  return <section className="operations-card overview-card">
    <h2>System overview</h2>
    <div className="overview-grid">{rows.map(row =>
      <div key={row.label}><span>{row.label}</span><strong title={row.value}>{row.value}</strong></div>)}</div>
  </section>;
}

function percent(value?: number) { return value === undefined ? "Unavailable" : `${Math.round(value)}%`; }
function numberValue(value?: number) { return value === undefined ? "Unavailable" : String(value); }
function stringValue(value?: Record<string, unknown>) {
  if (!value) return "Unavailable";
  return String(value.provider ?? value.name ?? value.model ?? value.default ?? "Available");
}
