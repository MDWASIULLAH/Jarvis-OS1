"use client";
import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Plus, RefreshCw } from "lucide-react";
import { useOperationalSelectionStore } from "../../store/operational-selection-store";
import { useReconciledSelection } from "../../hooks/use-reconciled-selection";
import { ProjectList } from "./project-list";
import { StudioPanels } from "./studio-panels";
import { useDevelopmentStudio } from "./hooks/use-development-studio";

export function DevelopmentStudio() {
  const { projectId, selectProject } = useOperationalSelectionStore();
  const { projects, dashboard, vocabulary, goals, tasks, create, addDepartment, requestReview, refreshAll } = useDevelopmentStudio(projectId);
  const [composing, setComposing] = useState(false);
  const [title, setTitle] = useState("");
  const [goal, setGoal] = useState("");
  const [priority, setPriority] = useState(50);

  const projectData = projects.data?.data ?? [];
  const selected = useMemo(() => projectData.find(project => project.project_id === projectId), [projectData, projectId]);
  const resolved = (dashboard.data?.available ? dashboard.data.data : undefined) ?? undefined;

  // Company projects are not persisted across backend restarts, so a selection
  // made before a restart would otherwise poll a dead id forever.
  useReconciledSelection(
    projectId,
    projectData.map(project => project.project_id),
    projects.data?.available === true,
    () => selectProject(undefined)
  );

  const submit = async () => {
    if (!title.trim() || !goal.trim()) return;
    const project = await create.mutateAsync({ title: title.trim(), goal: goal.trim(), priority });
    selectProject(project.project_id);
    setTitle(""); setGoal(""); setComposing(false);
  };

  return <motion.div className="development-studio" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
    <header>
      <div><span>AI software engineering</span><h1>Development Studio</h1><p>Projects, quality gates, teams, reviews, releases, documentation, and engineering evidence.</p></div>
      <div className="studio-header-actions">
        <button onClick={() => setComposing(value => !value)}><Plus size={15}/> New project</button>
        <button onClick={refreshAll}><RefreshCw size={15} className={projects.isFetching ? "spin" : undefined}/> Refresh</button>
      </div>
    </header>

    {composing && <form className="studio-composer" onSubmit={event => { event.preventDefault(); void submit(); }}>
      <label>Title<input value={title} onChange={event => setTitle(event.target.value)} placeholder="Payments service v2" required/></label>
      <label>Goal<input value={goal} onChange={event => setGoal(event.target.value)} placeholder="What should the AI software company build?" required/></label>
      <label>Priority<input type="number" min={0} max={100} value={priority} onChange={event => setPriority(Number(event.target.value))}/></label>
      <div className="studio-composer-actions">
        <button type="submit" className="primary" disabled={create.isPending || !title.trim() || !goal.trim()}>{create.isPending ? "Creating…" : "Create project"}</button>
        <button type="button" onClick={() => setComposing(false)}>Cancel</button>
      </div>
      {create.isError && <p className="studio-api-notice">Could not create the project. Check that the JARVIS backend is running on port 8000.</p>}
    </form>}

    {!projects.data?.available && <p className="studio-api-notice">{projects.data?.reason ?? "Checking project source availability…"}</p>}

    <div className="studio-grid">
      <ProjectList projects={projectData} selectedId={projectId} onSelect={selectProject}/>
      <StudioPanels
        project={selected}
        dashboard={resolved}
        reason={dashboard.data && !dashboard.data.available ? dashboard.data.reason : undefined}
        vocabulary={vocabulary.data?.data}
        goals={goals.data?.goals ?? []}
        tasks={tasks.data?.tasks ?? []}
        busy={addDepartment.isPending || requestReview.isPending}
        onAddDepartment={(kind, roles) => { if (projectId) addDepartment.mutate({ projectId, kind, roles }); }}
        onRequestReview={kind => { if (projectId) requestReview.mutate({ projectId, kind }); }}
      />
    </div>
  </motion.div>;
}
