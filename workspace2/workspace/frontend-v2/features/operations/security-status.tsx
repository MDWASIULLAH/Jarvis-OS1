"use client";
import type { SecuritySummary } from "./types";

/**
 * Live Security Framework counters from GET /v1/security/overview.
 *
 * This slot previously rendered "Approvals, policies, incidents, trust… require
 * a public Security Framework endpoint" — that endpoint exists, so the panel
 * reports the real registry instead of four "Unavailable" rows.
 */
export function SecurityStatus({ summary, reason }: { summary?: SecuritySummary; reason?: string }) {
  const counts = summary?.counts;
  const rows = [
    { label: "Active policies", value: counts?.policies },
    { label: "Pending approvals", value: counts?.pending_approvals },
    { label: "Open incidents", value: counts?.incidents },
    { label: "Audit records", value: counts?.audit_records },
    { label: "Trust scores", value: summary?.trust_scores?.length },
    { label: "Quarantined", value: summary?.quarantined?.length },
  ];
  return <section className="operations-card">
    <h2>Security Center</h2>
    {summary
      ? <div className="analytics-grid security-status-grid">{rows.map(row =>
          <div key={row.label}><span>{row.label}</span><strong>{row.value ?? 0}</strong></div>)}</div>
      : <p className="operations-unavailable">{reason ?? "Reading the security registry…"}</p>}
  </section>;
}
