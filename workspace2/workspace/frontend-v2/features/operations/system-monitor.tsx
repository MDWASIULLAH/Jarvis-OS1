"use client";
import type { MissionResources, SystemSnapshot } from "./types";

const bytes = (value?: number) => value === undefined ? "Unavailable" : `${(value / 1024 / 1024 / 1024).toFixed(1)} GB`;

export function SystemMonitor({ system, resources }: { system?: SystemSnapshot; resources?: MissionResources }) {
  const rows = [
    { label: "CPU", value: system?.cpu_percent === undefined ? "Unavailable" : `${system.cpu_percent}%` },
    { label: "RAM used", value: bytes(system?.memory?.used) },
    { label: "Disk used", value: bytes(system?.storage?.used) },
    { label: "Disk free", value: bytes(system?.storage?.free) },
    { label: "CPU cores", value: system?.cpu_count?.toString() ?? "Unavailable" },
    // The mission resource snapshot reports GPU and network only when the host
    // exposes a counter for them, so say "not reported" rather than "unavailable".
    { label: "GPU load", value: reported(resources?.gpu_percent, value => `${Math.round(value)}%`) },
    { label: "Bandwidth", value: reported(resources?.network_bytes_per_second, rate) },
    { label: "Disk pressure", value: reported(resources?.disk_percent, value => `${value.toFixed(1)}%`) },
  ];
  return <section className="operations-card">
    <h2>System monitoring</h2>
    <div className="monitor-grid">{rows.map(row =>
      <div key={row.label}><span>{row.label}</span><strong title={row.value}>{row.value}</strong></div>)}</div>
    {system?.metrics_detail && <p className="operations-unavailable">{system.metrics_detail}</p>}
  </section>;
}

function reported(value: number | null | undefined, format: (value: number) => string) {
  if (value === undefined) return "Unavailable";
  if (value === null) return "Not reported";
  return format(value);
}

function rate(value: number) {
  if (value < 1024) return `${Math.round(value)} B/s`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB/s`;
  return `${(value / 1024 / 1024).toFixed(1)} MB/s`;
}
