import { apiClient } from "../../../services/api-client";
import type { AuditRecord, EvaluationResult, SecurityApproval, SecurityOverview, SecurityState, TrustScore } from "../types";

const EMPTY: SecurityOverview = {
  policies: [], approvals: [], incidents: [], trust_scores: [], quarantined: [], audit_records: [],
  counts: { policies: 0, pending_approvals: 0, incidents: 0, audit_records: 0 },
  vocabulary: { domains: [], permissions: [] },
};

async function state<T>(path: string, fallback: T): Promise<SecurityState<T>> {
  try {
    return { available: true, data: await apiClient.request<T>(path) };
  } catch {
    return { available: false, data: fallback, reason: "The security framework API is unreachable. Start the JARVIS backend on port 8000 and refresh." };
  }
}

export type EvaluateInput = { title: string; target?: string; domain: string; permissions: string[] };

export const securityService = {
  overview: () => state<SecurityOverview>("/v1/security/overview", EMPTY),
  audit: (text = "") => state<AuditRecord[]>(`/v1/security/audit${text ? `?text=${encodeURIComponent(text)}` : ""}`, []),
  evaluate: (input: EvaluateInput) => apiClient.post<EvaluationResult>("/v1/security/evaluate", { target: "", ...input }),
  requestApproval: (input: EvaluateInput) =>
    apiClient.post<{ approval: SecurityApproval }>("/v1/security/approvals", { target: "", ...input }),
  decide: (approvalId: string, granted: boolean) =>
    apiClient.post<SecurityApproval>(`/v1/security/approvals/${encodeURIComponent(approvalId)}/decide`, { granted, decided_by: "operator" }),
  setTrust: (subjectId: string, score: number, rationale = "") =>
    apiClient.post<TrustScore>("/v1/security/trust", { subject_id: subjectId, score, rationale }),
};
