"use client";
import { useMemo, useState } from "react";
import { Download, Search } from "lucide-react";
import type { AuditEntry } from "./types";

/**
 * Audit feed from GET /v1/system/audit.
 *
 * The rows were reading `timestamp` / `action` / `status`, but the audit store
 * writes `created_at` / `event_type` / `outcome` — so every event stamped
 * "Unavailable · event · recorded" no matter what it actually recorded.
 */
export function EventExplorer({ entries = [] }: { entries?: AuditEntry[] }) {
  const [query, setQuery] = useState("");
  const list = Array.isArray(entries) ? entries : [];
  const visible = useMemo(
    () => list.filter(entry => JSON.stringify(entry).toLowerCase().includes(query.toLowerCase())),
    [list, query],
  );

  const exportEvents = () => {
    const blob = new Blob([JSON.stringify(visible, null, 2)], { type: "application/json" });
    const link = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: "jarvis-audit-events.json" });
    link.click();
    URL.revokeObjectURL(link.href);
  };

  return <section className="operations-card event-explorer">
    <header>
      <h2>Event explorer</h2>
      <button onClick={exportEvents} disabled={!visible.length} aria-label="Export visible events"><Download size={14}/></button>
    </header>
    <label><Search size={14}/><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search audit events"/></label>
    {visible.length ? <ol>{visible.map((entry, index) => {
      const when = stamp(entry);
      return <li key={`${entry.id ?? when ?? "event"}-${index}`}>
        <time dateTime={when ?? undefined}>{when ? new Date(when).toLocaleString() : "No timestamp"}</time>
        <strong>{label(entry)}</strong>
        <span>{String(entry.outcome ?? entry.status ?? "recorded")}</span>
        <p>{describe(entry)}</p>
      </li>;
    })}</ol> : <p className="operations-unavailable">No audit events are currently available.</p>}
  </section>;
}

const text = (value: unknown) => (typeof value === "string" && value ? value : undefined);
const stamp = (entry: AuditEntry) => text(entry.created_at) ?? text(entry.timestamp) ?? null;

/** Domain events carry their real name inside `detail.event_type`. */
function label(entry: AuditEntry) {
  const detail = entry.detail as Record<string, unknown> | undefined;
  const inner = detail && typeof detail === "object" ? text(detail.event_type) : undefined;
  const outer = text(entry.event_type) ?? text(entry.action) ?? text(entry.category) ?? "event";
  return (inner ?? outer).replace(/[._]/g, " ");
}

function describe(entry: AuditEntry) {
  const detail = entry.detail;
  if (typeof detail === "string" && detail) return detail;
  const source = (typeof detail === "object" && detail !== null ? detail : entry.payload) as Record<string, unknown> | undefined;
  if (!source) return "No payload recorded.";
  // `event_type` is already the row's title, and actor is a separate column.
  const fields = Object.entries(source).filter(([key]) => key !== "event_type" && key !== "event_id");
  const body = fields.slice(0, 4).map(([key, value]) => `${key.replace(/_/g, " ")}: ${String(value)}`).join(" · ");
  const actor = text(entry.actor);
  return [body || "No payload recorded.", actor ? `by ${actor}` : ""].filter(Boolean).join(" — ");
}
