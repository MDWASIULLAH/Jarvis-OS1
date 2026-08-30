"use client";
import { useState } from "react";
import type { ProjectDashboard } from "./services/project-service";
import type { Project } from "./types";

type Vocabulary = { roles: string[]; departments: string[]; reviews: string[] } | null | undefined;

const GATE_TONE: Record<string, string> = { passed: "ok", approved: "ok", failed: "bad", blocked: "bad", pending: "pending", waived: "pending" };

/**
 * The project workspace. Every block here reads a field the backend really
 * returns from GET /v1/company/projects/{id}; previously this whole area was a
 * hardcoded list of "Unavailable: no public Company API data" rows.
 */
export function StudioPanels({ project, dashboard, reason, vocabulary, goals, tasks, onAddDepartment, onRequestReview, busy }: {
  project?: Project;
  dashboard?: ProjectDashboard | null;
  reason?: string;
  vocabulary?: Vocabulary;
  goals: unknown[];
  tasks: unknown[];
  onAddDepartment: (kind: string, roles: string[]) => void;
  onRequestReview: (kind: string) => void;
  busy?: boolean;
}) {
  const [kind, setKind] = useState("");
  const [role, setRole] = useState("");
  const [reviewKind, setReviewKind] = useState("");

  if (!project) {
    return <div className="studio-side">
      <section className="studio-card">
        <h2>Project workspace</h2>
        <p className="studio-unavailable">Select a project to see its engineering workflow, quality gates, departments, task board, and review queue.</p>
        <div className="studio-metrics">
          <div><span>Planner goals</span><strong>{goals.length}</strong></div>
          <div><span>Agent tasks</span><strong>{tasks.length}</strong></div>
        </div>
      </section>
    </div>;
  }

  const stages = dashboard?.project.workflow ?? project.workflow ?? [];
  const gates = dashboard?.project.quality_gates ?? project.quality_gates ?? [];
  const departments = dashboard?.departments ?? [];
  const projectTasks = dashboard?.tasks ?? [];
  const reviews = dashboard?.reviews ?? [];
  const progress = Math.round((dashboard?.progress ?? 0) * 100);
  const departmentOptions = vocabulary?.departments ?? [];
  const roleOptions = vocabulary?.roles ?? [];
  const reviewOptions = vocabulary?.reviews ?? [];

  return <div className="studio-side">
    <section className="studio-card">
      <header className="studio-card-header">
        <div><h2>{project.title}</h2><p className="studio-unavailable">{project.goal}</p></div>
        <span className={`studio-tag ${dashboard?.release_ready ? "ok" : "pending"}`}>{dashboard?.release_ready ? "release ready" : "in progress"}</span>
      </header>
      {reason && <p className="studio-api-notice">{reason}</p>}
      <div className="studio-progress"><span style={{ width: `${progress}%` }}/></div>
      <div className="studio-metrics">
        <div><span>Progress</span><strong>{progress}%</strong></div>
        <div><span>Priority</span><strong>{project.priority ?? 50}</strong></div>
        <div><span>Departments</span><strong>{departments.length}</strong></div>
        <div><span>Tasks</span><strong>{projectTasks.length}</strong></div>
        <div><span>Reviews</span><strong>{reviews.length}</strong></div>
        <div><span>Revision</span><strong>{dashboard?.project.version ?? project.version ?? 1}</strong></div>
      </div>
      {project.mission_id && <p className="studio-unavailable">Tracked by mission <code>{project.mission_id}</code></p>}
    </section>

    <section className="studio-card">
      <h2>Engineering workflow</h2>
      {stages.length ? <ol className="studio-stages">{stages.map(stage =>
        <li key={stage.stage_id} className={stage.completed ? "done" : undefined}>
          <span>{stage.kind.replace(/_/g, " ")}</span>
          <em>{stage.completed ? "complete" : stage.required ? "required" : "optional"}</em>
        </li>)}</ol> : <p className="studio-unavailable">This project has no workflow stages.</p>}
    </section>

    <section className="studio-card">
      <h2>Quality gates</h2>
      {gates.length ? <ul className="studio-gates">{gates.map(gate =>
        <li key={gate.gate_id}><strong>{gate.title}</strong><span className={`studio-tag ${GATE_TONE[gate.state] ?? "pending"}`}>{gate.state}</span></li>)}</ul>
        : <p className="studio-unavailable">No quality gates are defined.</p>}
    </section>

    <section className="studio-card">
      <h2>Departments &amp; roles</h2>
      <form className="studio-form" onSubmit={event => { event.preventDefault(); if (!kind) return; onAddDepartment(kind, role ? [role] : []); setRole(""); }}>
        <select value={kind} onChange={event => setKind(event.target.value)} aria-label="Department kind">
          <option value="">Choose a department…</option>
          {departmentOptions.map(option => <option key={option} value={option}>{option.replace(/_/g, " ")}</option>)}
        </select>
        <select value={role} onChange={event => setRole(event.target.value)} aria-label="Role to staff">
          <option value="">No role yet</option>
          {roleOptions.map(option => <option key={option} value={option}>{option.replace(/_/g, " ")}</option>)}
        </select>
        <button type="submit" className="primary" disabled={busy || !kind}>Add department</button>
      </form>
      {departments.length ? <ul className="studio-departments">{departments.map(department =>
        <li key={department.department_id}>
          <strong>{department.name || department.kind.replace(/_/g, " ")}</strong>
          <div>{department.roles?.length ? department.roles.map(item => <span key={item} className="chip">{item.replace(/_/g, " ")}</span>) : <span className="chip">unstaffed</span>}</div>
        </li>)}</ul>
        : <p className="studio-unavailable">No departments yet. Add one to staff this project with specialist roles.</p>}
    </section>

    <section className="studio-card">
      <h2>Task board</h2>
      {projectTasks.length ? <ul className="studio-tasks">{projectTasks.map(task =>
        <li key={task.task_id}>
          <strong>{task.title}</strong>
          <span className={`studio-tag ${task.completed ? "ok" : "pending"}`}>{task.completed ? "done" : "open"}</span>
          {task.role && <em>{task.role.replace(/_/g, " ")}</em>}
        </li>)}</ul>
        : <p className="studio-unavailable">No tasks on the board. Tasks appear as departments break the goal down.</p>}
    </section>

    <section className="studio-card">
      <h2>Review queue</h2>
      <form className="studio-form" onSubmit={event => { event.preventDefault(); if (!reviewKind) return; onRequestReview(reviewKind); }}>
        <select value={reviewKind} onChange={event => setReviewKind(event.target.value)} aria-label="Review kind">
          <option value="">Choose a review…</option>
          {reviewOptions.map(option => <option key={option} value={option}>{option.replace(/_/g, " ")}</option>)}
        </select>
        <button type="submit" className="primary" disabled={busy || !reviewKind}>Request review</button>
      </form>
      {reviews.length ? <ul className="studio-tasks">{reviews.map(review =>
        <li key={review.review_id}>
          <strong>{review.kind.replace(/_/g, " ")}</strong>
          <span className={`studio-tag ${review.approved === true ? "ok" : review.approved === false ? "bad" : "pending"}`}>
            {review.approved === true ? "approved" : review.approved === false ? "rejected" : "awaiting"}
          </span>
          {review.findings?.length ? <em>{review.findings.length} finding{review.findings.length === 1 ? "" : "s"}</em> : null}
        </li>)}</ul>
        : <p className="studio-unavailable">No reviews requested yet.</p>}
    </section>

    <section className="studio-card">
      <h2>Operational planning records</h2>
      <div className="studio-metrics">
        <div><span>Planner goals</span><strong>{goals.length}</strong></div>
        <div><span>Agent tasks</span><strong>{tasks.length}</strong></div>
      </div>
    </section>
  </div>;
}
