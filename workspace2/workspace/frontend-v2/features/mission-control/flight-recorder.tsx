"use client";
import type { MissionEvent } from "./types";

/**
 * The dashboard now passes the mission's immutable flight records; this used to
 * be rendered with no props at all, so it always claimed none were exposed.
 * Newest first, capped so a long-running mission cannot blow out the side rail.
 */
export function FlightRecorder({ records, limit = 25 }: { records?: MissionEvent[]; limit?: number }) {
  const visible = (records ?? []).slice(-limit).reverse();
  return <section className="mission-section">
    <h3>Flight recorder</h3>
    {visible.length ? <>
      <ul className="flight-recorder">{visible.map(record =>
        <li key={record.event_id}>
          <time>{new Date(record.timestamp).toLocaleTimeString()}</time>
          <strong>{record.event_type}</strong>
          <span>{record.source}</span>
        </li>)}
      </ul>
      {(records?.length ?? 0) > limit && <p className="mission-unavailable">Showing the latest {limit} of {records?.length} records.</p>}
    </> : <p className="mission-unavailable">Select a mission to read its immutable flight records.</p>}
  </section>;
}
