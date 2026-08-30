"use client";
import { Activity } from "lucide-react";
import type { RuntimeStatus } from "./types";

/**
 * Runtime health plus the feature flags /v1/status already reports, so the panel
 * shows what the backend can actually do instead of a single word.
 */
export function SystemHealth({ runtime, error }: { runtime?: RuntimeStatus; error?: boolean }) {
  const state = error ? "Disconnected" : runtime ? "Healthy" : "Checking";
  const features = Object.entries(runtime?.features ?? {});
  return <section className="mission-section system-health">
    <h3><Activity size={15}/> System health</h3>
    <strong className={state.toLowerCase()}>{state}</strong>
    <p>{error ? "Backend unreachable — start the JARVIS API on port 8000." : runtime?.name ?? "Backend status has not been received."}</p>
    {runtime?.time && <time>{new Date(runtime.time).toLocaleString()}</time>}
    {features.length > 0 && <div className="health-flags">{features.map(([name, enabled]) =>
      <span key={name} className={enabled ? "chip chip-ok" : "chip chip-off"}>{name.replace(/_/g, " ")}</span>)}</div>}
  </section>;
}
