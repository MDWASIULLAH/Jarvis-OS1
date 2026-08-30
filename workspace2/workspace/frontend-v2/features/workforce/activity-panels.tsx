"use client";
import { useMemo } from "react";
import type { ActivityEvent } from "./services/workforce-service";

/**
 * Cross-system activity, grouped by the subsystem that recorded it.
 *
 * This panel used to be five hardcoded rows reading "Unavailable from current
 * operational API". Every subsystem already writes to the shared audit trail
 * (GET /v1/system/audit) with its source attached, so the real activity is
 * grouped out of that instead.
 */
export function ActivityPanels({ entries = [], reason }: { entries?: ActivityEvent[]; reason?: string }) {
  const groups = useMemo(() => {
    const bySource = new Map<string, { count: number; last?: string; latest: string }>();
    for (const entry of entries) {
      const source = sourceOf(entry);
      const current = bySource.get(source);
      const when = entry.created_at ?? "";
      if (!current) bySource.set(source, { count: 1, last: when, latest: labelOf(entry) });
      else {
        current.count += 1;
        // The API returns newest first, so only fill gaps rather than overwrite.
        if (when && (!current.last || when > current.last)) { current.last = when; current.latest = labelOf(entry); }
      }
    }
    return [...bySource.entries()].sort((a, b) => b[1].count - a[1].count);
  }, [entries]);

  return <section className="workforce-section">
    <h3>Cross-system activity</h3>
    {groups.length ? <ul className="activity-groups">{groups.map(([source, group]) =>
      <li key={source}>
        <div className="activity-head">
          <strong>{source.replace(/_/g, " ")}</strong>
          <span>{group.count} event{group.count === 1 ? "" : "s"}</span>
        </div>
        <em title={group.latest}>{group.latest}</em>
        <time>{group.last ? new Date(group.last).toLocaleTimeString() : "—"}</time>
      </li>)}</ul>
      : <p className="workforce-unavailable">{reason ?? "No cross-system activity recorded yet. Dispatch a task or run a capability to populate the trail."}</p>}
  </section>;
}

/** Domain events name their originating subsystem inside `detail.source`. */
function sourceOf(entry: ActivityEvent) {
  const detail = entry.detail;
  if (detail && typeof detail === "object") {
    const source = detail.source;
    if (typeof source === "string" && source) return source;
  }
  return entry.event_type || "runtime";
}

function labelOf(entry: ActivityEvent) {
  const detail = entry.detail;
  const inner = detail && typeof detail === "object" && typeof detail.event_type === "string" ? detail.event_type : undefined;
  return (inner ?? entry.event_type ?? "event").replace(/[._]/g, " ");
}
