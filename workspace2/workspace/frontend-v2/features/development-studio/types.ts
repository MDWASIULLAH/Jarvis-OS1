/** Mirrors the AI Software Company models exposed by /v1/company/*. */
export type WorkflowStage = { stage_id: string; kind: string; required?: boolean; completed?: boolean };
export type QualityGate = { gate_id: string; title: string; state: string; required?: boolean };
export type Milestone = { milestone_id?: string; title: string; completed: boolean };
export type Project = {
  project_id: string;
  title: string;
  goal: string;
  lifecycle: string;
  priority?: number;
  mission_id?: string;
  milestones?: Milestone[];
  workflow?: WorkflowStage[];
  quality_gates?: QualityGate[];
  version?: number;
  created_at?: string;
};
export type ProjectState<T> = { available: boolean; data: T; reason?: string };
