export type MissionStatus = "draft" | "active" | "paused" | "completed" | "cancelled" | "archived" | "failed";
export type MissionPriority = "low" | "medium" | "high" | "critical";
export type MissionAction = "pause" | "resume" | "complete" | "cancel" | "archive";
export type Mission = { mission_id: string; title: string; description: string; lifecycle: MissionStatus; priority?: MissionPriority; tags?: string[]; created_at: string; updated_at?: string; correlation_id?: string; metadata?: { key: string; value: string }[]; version?: number };
export type MissionEvent = { event_id: string; sequence?: number; event_type: string; timestamp: string; source: string; detail?: string; metadata?: Record<string, unknown> };
/** GET /v1/missions/{id}.resources — nulls mean the host counter is unreadable. */
export type MissionResources = { cpu_percent?: number | null; memory_mb?: number | null; disk_percent?: number | null; gpu_percent?: number | null; network_bytes_per_second?: number | null };
export type MissionMetrics = { active_agents?: number; helper_agents?: number; completed_tasks?: number; failed_tasks?: number; retries?: number; cpu_percent?: number; memory_mb?: number; execution_latency_seconds?: number; queue_size?: number; throughput?: number };
export type MissionAgent = { agent_id: string; name: string; state?: string; parent_agent_id?: string | null };
export type MissionDetails = Mission & { timeline?: MissionEvent[]; flight_records?: MissionEvent[]; metrics?: MissionMetrics; resources?: MissionResources; related_agents?: string[]; agents?: MissionAgent[]; related_conversations?: string[] };
export type MissionApiState<T> = { available: boolean; data: T; reason?: string };
/** GET /v1/status. `model` mirrors the router's real capability flags. */
export type RuntimeModelStatus = { default?: string; local_kind?: string; generative_local?: boolean; local_available?: boolean; cloud_configured?: boolean; cloud_allowed?: boolean; privacy?: string; provider?: string; available?: boolean };
export type RuntimeStatus = { name: string; time: string; model?: RuntimeModelStatus; features?: Record<string, boolean> };
/** GET /v1/system/status — real host counters collected by SystemMonitor. */
export type SystemStatus = { platform?: string; platform_release?: string; python?: string; cpu_count?: number; cpu_percent?: number; memory?: { total?: number; used?: number; percent?: number }; storage?: { total?: number; used?: number; free?: number; percent?: number }; network?: { is_local_only?: boolean } };
export type AgentTask = { id?: string; task_id?: string; status?: string; text?: string; created_at?: string; [key: string]: unknown };
export type NexusNode = { node_id: string; kind: string; label: string; metadata?: { key: string; value: string }[]; status?: string; health?: string; created_at?: string; updated_at?: string };
export type NexusEdge = { edge_id: string; source_id: string; target_id: string; relationship: string };
export type NexusSnapshot = { snapshot_id: string; mission_id: string; nodes: NexusNode[]; edges: NexusEdge[]; created_at: string };
