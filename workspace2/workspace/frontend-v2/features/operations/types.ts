export type SystemSnapshot = { platform?: string; platform_release?: string; python?: string; cpu_count?: number; cpu_percent?: number; memory?: { total?: number; used?: number; percent?: number }; storage?: { total?: number; used?: number; free?: number; percent?: number }; network?: { is_local_only?: boolean }; metrics_detail?: string };
/** The audit store writes created_at/event_type/actor/outcome; the older
    timestamp/category/action/status names are kept for legacy payloads. */
export type AuditEntry = { id?: number; created_at?: string; event_type?: string; actor?: string; outcome?: string; timestamp?: string; category?: string; action?: string; status?: string; detail?: string | Record<string, unknown>; payload?: Record<string, unknown>; [key: string]: unknown };
export type RuntimeOverview = { name?: string; time?: string; model?: Record<string, unknown>; features?: Record<string, boolean> };
export type OperationalState<T> = { available: boolean; data: T; reason?: string };

/** One row of GET /v1/system/diagnostics — measured, never hardcoded. */
export type DiagnosticStatus = "healthy" | "degraded" | "offline";
export type DiagnosticComponent = { component: string; tier: string; status: DiagnosticStatus; detail: string };
export type DiagnosticsReport = {
  components: DiagnosticComponent[];
  counts: Record<DiagnosticStatus, number>;
  total: number;
  overall: DiagnosticStatus;
  tiers: string[];
};

/** Live counters the mission record keeps for this JARVIS process. */
export type MissionMetrics = {
  active_agents?: number; helper_agents?: number; completed_tasks?: number; failed_tasks?: number;
  retries?: number; execution_latency_seconds?: number; queue_size?: number; throughput?: number;
};
export type MissionResources = {
  cpu_percent?: number; memory_mb?: number; disk_percent?: number;
  gpu_percent?: number | null; network_bytes_per_second?: number | null;
};
export type RuntimeMission = { metrics?: MissionMetrics; resources?: MissionResources; timeline?: unknown[]; agents?: unknown[] };

export type SecurityCounts = { policies?: number; pending_approvals?: number; incidents?: number; audit_records?: number };
export type SecuritySummary = { counts?: SecurityCounts; quarantined?: string[]; trust_scores?: unknown[] };
export type WorkspaceEntry = { name?: string; path?: string; is_dir?: boolean; [key: string]: unknown };
export type SearchProbe = { answer?: string; engine?: string; query?: string };
