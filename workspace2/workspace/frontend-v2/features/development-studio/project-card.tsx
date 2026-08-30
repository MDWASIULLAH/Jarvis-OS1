"use client";
import type { Project } from "./types";

/**
 * Progress is derived from the workflow stages the backend actually returns —
 * `milestones` is empty on a freshly created project, which is why the card used
 * to read "0/0 milestones".
 */
export function ProjectCard({ project, selected, onSelect }: {
  project: Project;
  selected?: boolean;
  onSelect?: (projectId: string) => void;
}) {
  const stages = project.workflow ?? [];
  const doneStages = stages.filter(stage => stage.completed).length;
  const gates = project.quality_gates ?? [];
  const passedGates = gates.filter(gate => gate.state === "passed" || gate.state === "approved").length;
  return <article
    className={`project-card${selected ? " selected" : ""}`}
    role="button"
    tabIndex={0}
    onClick={() => onSelect?.(project.project_id)}
    onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect?.(project.project_id); } }}
  >
    <span className={`studio-tag ${project.lifecycle === "active" ? "ok" : project.lifecycle === "blocked" || project.lifecycle === "cancelled" ? "bad" : "pending"}`}>{project.lifecycle}</span>
    <h3>{project.title}</h3>
    <p>{project.goal}</p>
    <div className="studio-progress" role="img" aria-label={`${stages.length ? Math.round((doneStages / stages.length) * 100) : 0}% of stages complete`}>
      <span style={{ width: `${stages.length ? (doneStages / stages.length) * 100 : 0}%` }}/>
    </div>
    <footer>{doneStages}/{stages.length} stages · {passedGates}/{gates.length} gates · priority {project.priority ?? 50}</footer>
  </article>;
}
