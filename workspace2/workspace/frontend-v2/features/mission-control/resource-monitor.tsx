"use client";
import type { MissionResources, RuntimeStatus, SystemStatus } from "./types";

const gb = (bytes?: number) => (bytes === undefined ? undefined : `${(bytes / 1024 ** 3).toFixed(1)} GB`);
const pct = (value?: number | null) => (value === undefined || value === null ? undefined : `${value.toFixed(1)}%`);

/**
 * Reads the real host counters instead of hardcoding `undefined`.
 *
 * Every row here used to be `value: undefined`, which is why the panel showed a
 * column of "Unavailable" next to a live process. CPU/RAM/disk come from
 * GET /v1/system/status (psutil) with the mission's own ResourceSnapshot as a
 * fallback; GPU and network genuinely are not collected, and say so.
 */
export function ResourceMonitor({ runtime, system, resources, taskCount }: {
  runtime?: RuntimeStatus;
  system?: SystemStatus;
  resources?: MissionResources;
  taskCount?: number;
}) {
  const cpu = pct(system?.cpu_percent) ?? pct(resources?.cpu_percent);
  const ram = system?.memory?.percent !== undefined
    ? `${system.memory.percent.toFixed(1)}% · ${gb(system.memory.used)}`
    : resources?.memory_mb ? `${(resources.memory_mb / 1024).toFixed(1)} GB` : undefined;
  const disk = system?.storage?.percent !== undefined
    ? `${system.storage.percent.toFixed(1)}% · ${gb(system.storage.free)} free`
    : pct(resources?.disk_percent);

  const model = runtime?.model;
  const modelLabel = model
    ? model.cloud_configured && model.cloud_allowed ? `cloud (${model.provider ?? "configured"})`
      : model.generative_local ? `local · ${model.local_kind ?? "engine"}`
      : model.local_available ? `local · ${model.local_kind ?? "engine"} (retrieval)`
      : "not configured"
    : undefined;

  const entries = [
    { name: "Model", value: modelLabel },
    { name: "Running tasks", value: taskCount?.toString() ?? "0" },
    { name: "CPU", value: cpu },
    { name: "RAM", value: ram },
    { name: "Disk", value: disk },
    { name: "Cores", value: system?.cpu_count?.toString() },
    { name: "GPU", value: pct(resources?.gpu_percent) ?? "Not collected" },
    { name: "Network", value: system?.network?.is_local_only ? "Local only" : "Enabled" },
    { name: "Platform", value: system?.platform ? `${system.platform} ${system.platform_release ?? ""}`.trim() : undefined },
    { name: "Python", value: system?.python },
  ];

  return <section className="mission-section"><h3>Resources</h3><div className="resource-grid">{entries.map(entry =>
    <div key={entry.name}><span>{entry.name}</span><strong>{entry.value ?? "Unavailable"}</strong></div>)}</div></section>;
}
