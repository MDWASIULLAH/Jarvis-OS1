import { apiClient } from "../../../services/api-client";
import type {
  AuditEntry, DiagnosticsReport, RuntimeMission, RuntimeOverview,
  SearchProbe, SecuritySummary, SystemSnapshot, WorkspaceEntry,
} from "../types";

/** The mission that records this JARVIS process — see runtime.SYSTEM_MISSION_ID. */
const SYSTEM_MISSION = "jarvis-runtime";

export const operationsService = {
  runtime: () => apiClient.request<RuntimeOverview>("/v1/status"),
  system: () => apiClient.request<SystemSnapshot>("/v1/system/status"),
  audit: () => apiClient.request<{ entries: AuditEntry[] }>("/v1/system/audit"),
  brain: () => apiClient.request<Record<string, unknown>>("/v1/brain/status"),
  tools: () => apiClient.request<{ tools: unknown[] }>("/v1/tools"),
  connectors: () => apiClient.request<{ connectors: unknown[] }>("/v1/connectors"),
  decisions: () => apiClient.request<{ history: unknown[] }>("/v1/decision/history"),
  reflections: () => apiClient.request<{ history: unknown[]; total: number }>("/v1/reflection/history"),
  tasks: () => apiClient.request<{ tasks: unknown[] }>("/v1/agents/tasks"),
  diagnostics: () => apiClient.request<DiagnosticsReport>("/v1/system/diagnostics"),
  mission: () => apiClient.request<RuntimeMission>(`/v1/missions/${SYSTEM_MISSION}`),
  security: () => apiClient.request<SecuritySummary>("/v1/security/overview"),
  workspace: () => apiClient.request<WorkspaceEntry[]>("/v1/workspace/files"),
  /** Fires a real query, so it is only called when the operator asks for a probe. */
  searchProbe: (query: string) => apiClient.request<SearchProbe>(`/v1/search?query=${encodeURIComponent(query)}`),
};
