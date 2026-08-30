import { apiClient } from "../../../services/api-client";
import type { AgentTask, Mission, MissionAction, MissionApiState, MissionDetails, RuntimeStatus, SystemStatus } from "../types";
import type { NexusSnapshot } from "../types";

/**
 * These calls used to be gated behind NEXT_PUBLIC_JARVIS_MISSIONS_API_URL, which
 * nothing ever set, so Mission Control always short-circuited to
 * "Mission API is not exposed by this deployment". The routes exist now
 * (`app/api/ops.py`), so the gate is gone -- but the MissionApiState envelope
 * stays, because a genuinely stopped backend should still degrade gracefully
 * instead of throwing inside a panel.
 */
async function state<T>(path: string, fallback: T): Promise<MissionApiState<T>> {
  try {
    return { available: true, data: await apiClient.request<T>(path) };
  } catch {
    return { available: false, data: fallback, reason: "Mission service is unavailable. Start the JARVIS backend and refresh." };
  }
}

const id = (value: string) => encodeURIComponent(value);

/**
 * A missing id must never become a URL.
 *
 * `encodeURIComponent(undefined)` returns the *string* `"undefined"`, so one
 * unguarded call site was enough to put `GET /v1/missions/undefined → 404` in the
 * console. Callers do guard with `enabled: Boolean(selectedId)`, but a 404 that
 * only appears while the app is mid-reload is precisely the kind of noise that
 * makes a working backend look disconnected -- so refuse at the boundary instead
 * of trusting every present and future caller to check first.
 */
async function keyed<T>(missionId: string | undefined, path: (key: string) => string, fallback: T): Promise<MissionApiState<T>> {
  if (!missionId) return { available: false, data: fallback, reason: "Select a mission to load this panel." };
  return state<T>(path(id(missionId)), fallback);
}

export const missionService = {
  missions: () => state<Mission[]>("/v1/missions", []),
  detail: (missionId?: string) => keyed<MissionDetails | null>(missionId, key => `/v1/missions/${key}`, null),
  nexus: (missionId?: string) => keyed<NexusSnapshot | null>(missionId, key => `/v1/missions/${key}/nexus`, null),
  nexusSnapshots: (missionId?: string) => keyed<NexusSnapshot[]>(missionId, key => `/v1/missions/${key}/nexus/snapshots`, []),
  replay: (missionId?: string) => keyed<MissionDetails | null>(missionId, key => `/v1/missions/${key}/replay`, null),
  runtime: () => apiClient.request<RuntimeStatus>("/v1/status"),
  system: () => apiClient.request<SystemStatus>("/v1/system/status"),
  tasks: () => apiClient.request<{ tasks: AgentTask[] }>("/v1/agents/tasks"),
  create: (title: string, description: string) => apiClient.post<Mission>("/v1/missions", { title, description }),
  transition: (missionId: string, action: MissionAction) => {
    // A mutation, so failing loudly is right: the caller has a real button to
    // re-enable and the error surfaces through `transition.isError`.
    if (!missionId) return Promise.reject(new Error("Select a mission before changing its lifecycle."));
    return apiClient.post<Mission>(`/v1/missions/${id(missionId)}/${action}`);
  },
};
