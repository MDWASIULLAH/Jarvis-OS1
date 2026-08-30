"use client";
import type { MissionEvent } from "./types";

/** Newest-first timeline, capped so a busy mission stays scannable. */
export function MissionTimeline({ events, limit = 40 }: { events?: MissionEvent[]; limit?: number }) {
  const visible = (events ?? []).slice(-limit).reverse();
  return <section className="mission-section">
    <h3>Event timeline</h3>
    {visible.length ? <>
      <ol className="mission-timeline">{visible.map(event =>
        <li key={event.event_id}>
          <time>{new Date(event.timestamp).toLocaleTimeString()}</time>
          <strong>{event.event_type}</strong>
          <span>{event.source}</span>
          {event.detail && <p>{event.detail}</p>}
        </li>)}
      </ol>
      {(events?.length ?? 0) > limit && <p className="mission-unavailable">Showing the latest {limit} of {events?.length} events.</p>}
    </> : <p className="mission-unavailable">No timeline events are available for this mission.</p>}
  </section>;
}
