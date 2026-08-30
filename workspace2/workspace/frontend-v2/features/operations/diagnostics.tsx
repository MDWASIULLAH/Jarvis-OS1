"use client";
import type { DiagnosticComponent, DiagnosticsReport, DiagnosticStatus } from "./types";

/**
 * Live subsystem health from GET /v1/system/diagnostics.
 *
 * This panel used to hardcode `available: false` for eleven of fifteen rows, so
 * Planner, Memory, Knowledge, Swarm, Mission Control, Reflection, Security and
 * friends all read "Unavailable" while they were serving traffic. Every row is
 * now a measured probe result with the fact that proves it.
 */
const TIER_LABELS: Record<string, string> = {
  core: "Core runtime",
  cognition: "Cognition",
  memory: "Memory & knowledge",
  operations: "Operations",
  platform: "Platform",
};

// The stylesheet names the red pill "failed"; the API calls that state "offline".
const PILL: Record<DiagnosticStatus, string> = { healthy: "healthy", degraded: "degraded", offline: "failed" };
const PILL_TEXT: Record<DiagnosticStatus, string> = { healthy: "Healthy", degraded: "Degraded", offline: "Offline" };

export function Diagnostics({ report, reason }: { report?: DiagnosticsReport; reason?: string }) {
  if (!report) {
    return <section className="operations-card diagnostics-card">
      <h2>System diagnostics</h2>
      <p className="operations-unavailable">{reason ?? "Probing subsystems…"}</p>
    </section>;
  }

  const tiers = report.tiers.filter(tier => report.components.some(item => item.tier === tier));
  const unknownTiers = [...new Set(report.components.map(item => item.tier))].filter(tier => !report.tiers.includes(tier));

  return <section className="operations-card diagnostics-card">
    <header className="diagnostics-header">
      <h2>System diagnostics</h2>
      <div className="diagnostics-summary">
        <span className="healthy">{report.counts.healthy ?? 0} healthy</span>
        <span className="degraded">{report.counts.degraded ?? 0} degraded</span>
        <span className="failed">{report.counts.offline ?? 0} offline</span>
      </div>
    </header>
    {[...tiers, ...unknownTiers].map(tier => <div className="diagnostic-tier" key={tier}>
      <h3>{TIER_LABELS[tier] ?? tier}</h3>
      <div className="diagnostic-grid">
        {report.components.filter(item => item.tier === tier).map(item => <Row key={item.component} item={item}/>)}
      </div>
    </div>)}
  </section>;
}

function Row({ item }: { item: DiagnosticComponent }) {
  return <div>
    <div className="diagnostic-head">
      <strong title={item.component}>{item.component}</strong>
      <span className={PILL[item.status] ?? "unavailable"}>{PILL_TEXT[item.status] ?? item.status}</span>
    </div>
    <em title={item.detail}>{item.detail}</em>
  </div>;
}
