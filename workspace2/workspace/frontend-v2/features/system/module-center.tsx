"use client";

import { useEffect, useState } from "react";
import { RefreshCw, Settings } from "lucide-react";
import type { NavigationId } from "../../types/navigation";
import { useUIStore } from "../../store/ui-store";
import { apiUrl } from "../../services/backend";

/**
 * Fall-through panel for NavigationIds without a dedicated dashboard.
 *
 * `knowledge` and `security` used to appear here too, which is why they read as
 * generic stubs; both now have real dashboards that the shell routes directly,
 * so their entries were dead weight.
 */
const copy: Partial<Record<NavigationId, { title: string; description: string; api: string }>> = {
  workspace: { title: "Workspace", description: "Your local workspace is ready for file operations through the connected JARVIS runtime.", api: "/v1/workspace/files" },
  memory: { title: "Memory", description: "Local facts and conversation context are stored on this device.", api: "/v1/memory/facts" },
  reflection: { title: "Reflection", description: "Review the current runtime and its recent operational state.", api: "/v1/reflection/history" },
  evolution: { title: "Evolution", description: "Evolution proposals are analysis-only and require no remote provider.", api: "/v1/status" },
  search: { title: "Search", description: "Web and local knowledge search becomes available from chat and configured tools.", api: "/v1/tools" },
  installation: { title: "Installation", description: "Use this module to verify the local runtime configuration.", api: "/v1/system/diagnostics" },
  company: { title: "Company", description: "Agent roles and organizational surfaces appear as their backend APIs are enabled.", api: "/v1/agents/tasks" },
  plugins: { title: "Plugins", description: "Installed JARVIS plugins and optional integrations are listed by the backend.", api: "/v1/plugins" },
};

export function ModuleCenter({ id }: { id: NavigationId }) {
  const module = copy[id] ?? { title: "Workspace module", description: "This module is ready to connect to the local JARVIS backend.", api: "/v1/status" };
  const setActive = useUIStore(state => state.setActive);
  const [result, setResult] = useState("Checking local runtime…");

  const load = async () => {
    try {
      const response = await fetch(apiUrl(module.api));
      if (!response.ok) throw new Error(String(response.status));
      setResult(summarise(await response.json()));
    } catch {
      setResult("Backend data is unavailable. Start JARVIS and refresh.");
    }
  };
  useEffect(() => { void load(); }, [id]);

  return <section className="module-center"><span>JARVIS module</span><h1>{module.title}</h1><p>{module.description}</p><div className="module-status"><strong>{result}</strong><button onClick={() => void load()}><RefreshCw size={15}/> Refresh</button></div><section><h2>Configure integrations</h2><p>Connect OpenRouter, OpenAI-compatible servers, and other credentials in Settings. Chat stays local until you explicitly select a cloud provider.</p><button onClick={() => setActive("settings")}><Settings size={15}/> Open settings</button></section></section>;
}

/** Report whatever the endpoint actually counts, instead of a fixed guess at
    `facts`/`tasks` that left most modules reading "Local backend connected". */
function summarise(data: unknown): string {
  if (Array.isArray(data)) return `${data.length} record${data.length === 1 ? "" : "s"}`;
  if (data && typeof data === "object") {
    for (const [key, value] of Object.entries(data as Record<string, unknown>)) {
      if (Array.isArray(value)) return `${value.length} ${key.replace(/_/g, " ")}`;
    }
    const counts = (data as { counts?: Record<string, number> }).counts;
    if (counts) return Object.entries(counts).map(([key, value]) => `${value} ${key}`).join(" · ");
  }
  return "Local backend connected";
}
