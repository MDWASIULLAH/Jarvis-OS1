"use client";

import { Activity } from "lucide-react";
import { useToolStore } from "./stores/tool-store";

export function ToolPanel() {
  const activities = useToolStore(state => state.activities);
  return <aside className="tool-panel" aria-label="Live execution activity"><h3><Activity size={15}/> Live execution</h3>
    {activities.length ? activities.map(item => <div className="tool-activity" key={`${item.name}:${item.status}`}><strong>{item.name}</strong><span>{item.status}</span>{item.detail && <small>{item.detail}</small>}</div>) : <p className="empty-inline">No execution events are available for this response.</p>}
    <h3>Artifacts</h3><p className="empty-inline">Artifacts appear when the backend includes them in a response.</p>
  </aside>;
}
