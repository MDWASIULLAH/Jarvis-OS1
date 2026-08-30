import { apiClient } from "../../../services/api-client";
import type { Project, ProjectState } from "../types";

export type CompanyTask = { task_id: string; project_id: string; title: string; department_id?: string | null; role?: string | null; assigned_agent_id?: string | null; completed: boolean };
export type Department = { department_id: string; project_id: string; kind: string; name: string; roles: string[] };
export type ProjectDashboard = { project: Project; departments: Department[]; tasks: CompanyTask[]; reviews: { review_id: string; kind: string; approved: boolean | null; findings: string[] }[]; release_ready: boolean; progress: number };

// NEXT_PUBLIC_JARVIS_DEVELOPMENT_API_URL is no longer consulted: the AI Software
// Company manager is exposed at /v1/company/*. The envelope is kept so a stopped
// backend degrades instead of throwing inside the Studio panel.
async function state<T>(path: string, fallback: T): Promise<ProjectState<T>> {
  try {
    return { available: true, data: await apiClient.request<T>(path) };
  } catch {
    return { available: false, data: fallback, reason: "Development Studio source is unavailable. Start the JARVIS backend and refresh." };
  }
}

const id = (value: string) => encodeURIComponent(value);

export const projectService = {
  projects: () => state<Project[]>("/v1/company/projects", []),
  dashboard: (projectId: string) => state<ProjectDashboard | null>(`/v1/company/projects/${id(projectId)}`, null),
  departments: () => state<Department[]>("/v1/company/departments", []),
  companyTasks: () => state<CompanyTask[]>("/v1/company/tasks", []),
  vocabulary: () => state<{ roles: string[]; departments: string[]; reviews: string[] } | null>("/v1/company/roles", null),
  goals: () => apiClient.request<{ goals: unknown[] }>("/v1/goals"),
  tasks: () => apiClient.request<{ tasks: unknown[] }>("/v1/agents/tasks"),
  create: (title: string, goal: string, priority = 50) => apiClient.post<Project>("/v1/company/projects", { title, goal, priority }),
  addDepartment: (projectId: string, kind: string, roles: string[] = []) =>
    apiClient.post<Department>(`/v1/company/projects/${id(projectId)}/departments`, { kind, roles }),
  requestReview: (projectId: string, kind: string) =>
    apiClient.post<{ review_id: string; kind: string }>(`/v1/company/projects/${id(projectId)}/reviews`, { kind, requested_by: "operator" }),
};
