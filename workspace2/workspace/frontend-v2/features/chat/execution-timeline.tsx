"use client";
import type { ExecutionTrace } from "./types";
export function ExecutionTimeline({ events }: { events?: ExecutionTrace[] }) { return events?.length ? <details className="message-execution"><summary>Execution timeline ({events.length})</summary><ol>{events.map((event, index) => <li key={`${event.createdAt}-${index}`}><time>{new Date(event.createdAt).toLocaleTimeString()}</time><strong>{event.type}</strong><span>{event.detail}</span></li>)}</ol></details> : null; }
