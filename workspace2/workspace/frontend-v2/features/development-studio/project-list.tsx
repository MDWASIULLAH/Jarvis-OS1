"use client";
import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { ProjectCard } from "./project-card";
import type { Project } from "./types";

export function ProjectList({ projects, selectedId, onSelect }: {
  projects: Project[];
  selectedId?: string;
  onSelect?: (projectId: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [lifecycle, setLifecycle] = useState("all");
  const states = useMemo(() => Array.from(new Set(projects.map(project => project.lifecycle))).sort(), [projects]);
  const filtered = useMemo(() => projects.filter(project =>
    (lifecycle === "all" || project.lifecycle === lifecycle) &&
    `${project.title} ${project.goal}`.toLowerCase().includes(query.toLowerCase())), [lifecycle, projects, query]);

  return <section className="studio-card project-list">
    <header>
      <h2>Projects</h2>
      <label><Search size={14}/><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search projects"/></label>
      <select value={lifecycle} onChange={event => setLifecycle(event.target.value)} aria-label="Filter by lifecycle">
        <option value="all">All states</option>
        {states.map(state => <option key={state} value={state}>{state}</option>)}
      </select>
      <span>{filtered.length}/{projects.length}</span>
    </header>
    {filtered.length
      ? <div>{filtered.map(project => <ProjectCard key={project.project_id} project={project} selected={project.project_id === selectedId} onSelect={onSelect}/>)}</div>
      : <p className="studio-unavailable">{projects.length ? "No project matches this filter." : "No projects yet. Create one above and the AI software company will open a mission for it."}</p>}
  </section>;
}
