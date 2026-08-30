/** Shapes returned by /v1/security/* — see SecurityManager in the backend. */
export type SecurityPolicy = { policy_id: string; domain: string; allowed_permissions: string[]; max_risk: string; enabled: boolean };
export type SecurityApproval = { approval_id: string; action_id: string; requested_by: string; state: string; decided_by?: string | null; rationale?: string; requested_at?: string; decided_at?: string | null };
export type SecurityIncident = { incident_id: string; action_id?: string; severity?: string; summary?: string; detail?: string; timestamp?: string };
export type TrustScore = { subject_id: string; score: number; rationale?: string; updated_at?: string };
export type AuditRecord = { record_id: string; action_id?: string; event: string; detail?: string; timestamp?: string };
export type SecurityOverview = {
  policies: SecurityPolicy[];
  approvals: SecurityApproval[];
  incidents: SecurityIncident[];
  trust_scores: TrustScore[];
  quarantined: string[];
  audit_records: AuditRecord[];
  counts: { policies: number; pending_approvals: number; incidents: number; audit_records: number };
  vocabulary: { domains: string[]; permissions: string[] };
};
export type RiskAssessment = { level: string; rationale?: string[] };
export type PolicyDecision = { allowed: boolean; rationale?: string[]; risk?: RiskAssessment };
export type SecurityThreat = { threat_id?: string; category?: string; severity?: string; detail?: string };
export type EvaluationResult = {
  action: { action_id: string; title: string; permissions: string[]; domain: string; target?: string };
  report: { action_id: string; decision: PolicyDecision; approval?: SecurityApproval | null; threats?: SecurityThreat[]; audits?: AuditRecord[] };
  threats: SecurityThreat[];
};
export type SecurityState<T> = { available: boolean; data: T; reason?: string };
