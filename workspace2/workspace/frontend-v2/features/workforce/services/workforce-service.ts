import { apiClient } from "../../../services/api-client";
import type { AgentCommunication, WorkforceAgent, WorkforceState } from "../types";

/** Aggregate counters served by GET /v1/workforce/status. */
export type WorkforceStatus = {
  total_agents: number;
  executive_agents: number;
  worker_agents: number;
  helper_agents: number;
  open_tasks: number;
  messages: number;
  recoveries: number;
  planner_available: boolean;
  executor_available: boolean;
  lifecycle_breakdown: Record<string, number>;
  average_health: number;
};

export type WorkforceTask = { task_id: string; title: string; description: string; priority: number; lifecycle: string };

/** One row of GET /v1/system/audit — the trail every subsystem writes to. */
export type ActivityEvent = {
  id?: number;
  created_at?: string;
  event_type?: string;
  actor?: string;
  outcome?: string;
  detail?: Record<string, unknown> | string;
};

// The NEXT_PUBLIC_JARVIS_WORKFORCE_API_URL gate is gone; the swarm manager is
// exposed at /v1/workforce/*. The envelope remains for real outages only.
async function state<T>(path: string, fallback: T): Promise<WorkforceState<T>> {
  try {
    return { available: true, data: await apiClient.request<T>(path) };
  } catch {
    return { available: false, data: fallback, reason: "Workforce service is unavailable. Start the JARVIS backend and refresh." };
  }
}

const id = (value: string) => encodeURIComponent(value);

export const workforceService = {
  agents: () => state<WorkforceAgent[]>("/v1/workforce/agents", []),
  agent: (agentId: string) => state<WorkforceAgent | null>(`/v1/workforce/agents/${id(agentId)}`, null),
  communications: () => state<AgentCommunication[]>("/v1/workforce/communications", []),
  status: () => state<WorkforceStatus | null>("/v1/workforce/status", null),
  swarmTasks: () => state<WorkforceTask[]>("/v1/workforce/tasks", []),
  tasks: () => apiClient.request<{ tasks: unknown[] }>("/v1/agents/tasks"),
  /** Cross-system activity: every subsystem records to the shared audit trail. */
  activity: () => state<{ entries: ActivityEvent[] }>("/v1/system/audit?limit=200", { entries: [] }),
  act: (agentId: string, action: "pause" | "resume" | "cancel" | "recover" | "health-check") =>
    apiClient.post<WorkforceAgent>(`/v1/workforce/agents/${id(agentId)}/${action}`),
  createAgent: (name: string, kind = "worker") => apiClient.post<WorkforceAgent>("/v1/workforce/agents", { name, kind }),
  assignTask: (title: string, description = "", priority = 50) =>
    apiClient.post<{ task: WorkforceTask; assignment: { agent_id: string; task_id: string } }>("/v1/workforce/tasks", { title, description, priority }),
  broadcast: (senderAgentId: string, content: string) =>
    apiClient.post<AgentCommunication[]>("/v1/workforce/broadcast", { sender_agent_id: senderAgentId, content }),
};
