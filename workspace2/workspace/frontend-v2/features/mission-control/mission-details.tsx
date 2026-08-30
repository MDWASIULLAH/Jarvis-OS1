"use client";
import type { ReactNode } from "react";
import { MissionReplay } from "./mission-replay";
import { MissionTimeline } from "./mission-timeline";
import type { Mission, MissionDetails as MissionDetailsPayload } from "./types";

/**
 * Detail is now passed in rather than fetched here, so the side rail can read
 * the same response (see use-mission-control). `actions` carries the lifecycle
 * buttons from the dashboard.
 */
export function MissionDetails({ mission, detail, reason, actions }: {
  mission?: Mission;
  detail?: MissionDetailsPayload;
  reason?: string;
  actions?: ReactNode;
}) {
  if (!mission) {
    return <section className="mission-details"><h2>Mission inspector</h2><p className="mission-unavailable">Select a mission to inspect its timeline, resources, logs, and related operational context.</p></section>;
  }
  const agents = detail?.agents ?? [];
  return <section className="mission-details">
    <header><div><span className={`mission-status ${mission.lifecycle}`}>{mission.lifecycle}</span><h2>{mission.title}</h2></div><code>{mission.mission_id}</code></header>
    <p>{mission.description}</p>
    {actions}
    <dl>
      <div><dt>Priority</dt><dd>{mission.priority ?? "medium"}</dd></div>
      <div><dt>Created</dt><dd>{new Date(mission.created_at).toLocaleString()}</dd></div>
      <div><dt>Updated</dt><dd>{mission.updated_at ? new Date(mission.updated_at).toLocaleString() : "—"}</dd></div>
      <div><dt>Revision</dt><dd>{mission.version ?? 1}</dd></div>
      <div><dt>Correlation</dt><dd>{mission.correlation_id?.trim() ? mission.correlation_id : "all events"}</dd></div>
      <div><dt>Assigned agents</dt><dd>{detail?.related_agents?.length ?? 0}</dd></div>
    </dl>
    {mission.metadata?.length ? <div className="mission-metadata">{mission.metadata.map(item => <span key={item.key}><b>{item.key}</b> {item.value}</span>)}</div> : null}
    {reason && <p className="mission-unavailable">{reason}</p>}
    {agents.length ? <section className="mission-section"><h3>Mission roster</h3><ul className="mission-roster">{agents.map(agent =>
      <li key={agent.agent_id}><strong>{agent.name}</strong><span>{agent.state ?? "unknown"}</span></li>)}</ul></section> : null}
    <MissionTimeline events={detail?.timeline}/>
    <MissionReplay events={detail?.flight_records ?? detail?.timeline}/>
  </section>;
}
