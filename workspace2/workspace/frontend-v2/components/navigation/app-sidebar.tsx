"use client";

import { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Search,
  Bell,
  PanelLeftClose,
  Plus,
  Clock,
  Puzzle,
  Folder,
  ChevronUp,
  Activity,
  CircuitBoard,
  Code2,
  Users,
  Brain,
  Shield,
  Settings,
  Workflow,
  Sparkles,
  FolderPlus,
  Trash2,
  Wand2,
} from "lucide-react";
import { useUIStore, ModelOption } from "../../store/ui-store";
import type { NavigationId } from "../../types/navigation";
import { useConversationStore } from "../../features/chat/stores/conversation-store";

export function AppSidebar() {
  const {
    active,
    setActive,
    activeProject,
    setActiveProject,
    setActiveDirectory,
    projects,
    addProject,
    removeProject,
    selectedModel,
    setSelectedModel,
    togglePanel,
    setPaletteOpen,
    setNotificationsOpen,
    setScheduledOpen,
    setPluginsOpen,
  } = useUIStore();

  const { create: createNewChat } = useConversationStore();

  const [brandMenuOpen, setBrandMenuOpen] = useState(false);
  const [modulesExpanded, setModulesExpanded] = useState(true);
  const [newProjectModal, setNewProjectModal] = useState(false);
  const [newProjName, setNewProjName] = useState("");
  const [newProjSubtitle, setNewProjSubtitle] = useState("");
  const [newProjPath, setNewProjPath] = useState("");

  const jarvisModels: ModelOption[] = [
    "JARVIS J-3.1 Ultra",
    "JARVIS J-4.0 Omni",
    "JARVIS J-2.5 Pro",
    "JARVIS J-1.1 Turbo",
    "JARVIS J-1.0 Mini",
    "JARVIS J-Local Core",
  ];

  const jarvisModules: { id: NavigationId; label: string; icon: React.ElementType }[] = [
    { id: "mission-control", label: "Mission Control", icon: Workflow },
    { id: "neural-nexus", label: "Neural Nexus 3D", icon: CircuitBoard },
    { id: "operations", label: "Operations Center", icon: Activity },
    { id: "development-studio", label: "Development Studio", icon: Code2 },
    { id: "ai-studio", label: "AI Studio", icon: Wand2 },
    { id: "agents", label: "Workforce Swarm", icon: Users },
    { id: "knowledge", label: "Knowledge Graph", icon: Brain },
    { id: "security", label: "Security Framework", icon: Shield },
    { id: "settings", label: "Settings", icon: Settings },
  ];

  const handleCreateProject = () => {
    if (!newProjName.trim()) return;
    addProject(
      newProjName,
      newProjSubtitle || "Workspace Directory",
      newProjPath || newProjName
    );
    setActiveProject(newProjName);
    if (newProjPath) setActiveDirectory(newProjPath);
    setNewProjName("");
    setNewProjSubtitle("");
    setNewProjPath("");
    setNewProjectModal(false);
  };

  return (
    <aside className="codex-sidebar">
      {/* Sidebar Header */}
      <div className="sidebar-header">
        <div style={{ position: "relative" }}>
          <button
            className="brand-trigger"
            onClick={() => setBrandMenuOpen(!brandMenuOpen)}
            aria-label="Switch Model"
          >
            <span>{selectedModel.split(" ")[0]}</span>
            <ChevronDown size={14} />
          </button>

          {brandMenuOpen && (
            <div className="menu-dropdown" style={{ top: "100%", left: 0, width: 230 }}>
              {jarvisModels.map((m) => (
                <button
                  key={m}
                  onClick={() => {
                    setSelectedModel(m);
                    setBrandMenuOpen(false);
                  }}
                  style={{
                    fontWeight: selectedModel === m ? 600 : 400,
                    color: selectedModel === m ? "var(--text-main)" : "var(--text-secondary)",
                  }}
                >
                  <span>{m}</span>
                  {selectedModel === m && <Sparkles size={13} color="#10a37f" />}
                </button>
              ))}
              <hr />
              <button
                onClick={() => {
                  setActive("settings");
                  setBrandMenuOpen(false);
                }}
              >
                Model & Provider Settings...
              </button>
            </div>
          )}
        </div>

        <div className="sidebar-header-actions">
          <button
            className="header-icon-btn"
            title="Search Workspace (Ctrl+K)"
            aria-label="Search"
            onClick={() => setPaletteOpen(true)}
          >
            <Search size={15} />
          </button>
          <button
            className="header-icon-btn"
            title="Notifications"
            aria-label="Notifications"
            onClick={() => setNotificationsOpen(true)}
          >
            <Bell size={15} />
          </button>
          <button
            className="header-icon-btn"
            title="Collapse Sidebar"
            aria-label="Collapse Sidebar"
            onClick={() => togglePanel("leftOpen")}
          >
            <PanelLeftClose size={16} />
          </button>
        </div>
      </div>

      {/* Sidebar Quick Action Items */}
      <div className="sidebar-quick-nav">
        <button
          className={`sidebar-action-btn ${active === "chat" ? "active" : ""}`}
          onClick={() => {
            setActive("chat");
            createNewChat();
          }}
        >
          <Plus size={16} />
          <span>New chat</span>
        </button>

        <button
          className="sidebar-action-btn"
          onClick={() => setScheduledOpen(true)}
        >
          <Clock size={16} />
          <span>Scheduled</span>
        </button>

        <button
          className="sidebar-action-btn"
          onClick={() => setPluginsOpen(true)}
        >
          <Puzzle size={16} />
          <span>@ Plugins</span>
        </button>
      </div>

      {/* Projects Section */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          paddingRight: 10,
        }}
      >
        <div className="sidebar-section-title">Projects</div>
        <button
          className="header-icon-btn"
          title="Open or Add Project Folder"
          onClick={() => setNewProjectModal(true)}
          style={{ width: 22, height: 22 }}
        >
          <FolderPlus size={14} />
        </button>
      </div>

      <div className="sidebar-scroll-area">
        {projects.length === 0 ? (
          <div style={{ padding: "8px 6px" }}>
            <button
              onClick={() => setNewProjectModal(true)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                width: "100%",
                padding: "8px 10px",
                border: "1px dashed var(--border-color)",
                borderRadius: 8,
                background: "transparent",
                color: "var(--text-secondary)",
                fontSize: 12,
                cursor: "pointer",
                textAlign: "left",
              }}
            >
              <FolderPlus size={14} color="#3b82f6" />
              <span>+ Open or Add Project</span>
            </button>
          </div>
        ) : (
          projects.map((project) => {
            const isSelected = activeProject === project.name;

            return (
              <div key={project.id} className="project-item-group" style={{ position: "relative" }}>
                <button
                  className={`project-item ${isSelected ? "active" : ""}`}
                  onClick={() => {
                    setActiveProject(project.name);
                    if (project.path) setActiveDirectory(project.path);
                    setActive("chat");
                  }}
                >
                  <Folder size={16} className="project-item-icon" />
                  <div className="project-item-text">
                    <div className="project-item-name">{project.name}</div>
                    <div className="project-item-sub">{project.subtitle}</div>
                  </div>
                </button>

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    removeProject(project.id);
                  }}
                  title="Remove Project"
                  style={{
                    position: "absolute",
                    right: 6,
                    top: 8,
                    border: 0,
                    background: "transparent",
                    color: "var(--text-muted)",
                    cursor: "pointer",
                    padding: 2,
                    opacity: 0.6,
                  }}
                >
                  <Trash2 size={12} />
                </button>
              </div>
            );
          })
        )}

        {/* Deep JARVIS Modules Accordion */}
        <div className="sidebar-modules-accordion">
          <button
            className="modules-toggle-btn"
            onClick={() => setModulesExpanded(!modulesExpanded)}
          >
            <span>JARVIS Modules</span>
            {modulesExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>

          {modulesExpanded && (
            <div className="modules-list">
              {jarvisModules.map((mod) => {
                const Icon = mod.icon;
                const isModActive = active === mod.id;
                return (
                  <button
                    key={mod.id}
                    className={`module-nav-btn ${isModActive ? "active" : ""}`}
                    onClick={() => setActive(mod.id)}
                  >
                    <Icon size={14} />
                    <span>{mod.label}</span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* New Project Modal */}
      {newProjectModal && (
        <div className="modal-overlay" onClick={() => setNewProjectModal(false)}>
          <div
            className="modal-dialog-card"
            style={{ maxWidth: 400 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>
              Open or Add Project
            </div>
            <p style={{ fontSize: 12, color: "var(--text-secondary)", margin: 0, marginBottom: 10 }}>
              Add a real local project directory to your JARVIS workspace.
            </p>
            <input
              type="text"
              placeholder="Project Name (e.g. My Next.js App)"
              value={newProjName}
              onChange={(e) => setNewProjName(e.target.value)}
              style={{
                width: "100%",
                padding: "8px 10px",
                borderRadius: 6,
                border: "1px solid var(--border-color)",
                marginBottom: 8,
                background: "var(--bg-input)",
                color: "var(--text-main)",
                fontSize: 13,
              }}
            />
            <input
              type="text"
              placeholder="Description (e.g. Production frontend codebase)"
              value={newProjSubtitle}
              onChange={(e) => setNewProjSubtitle(e.target.value)}
              style={{
                width: "100%",
                padding: "8px 10px",
                borderRadius: 6,
                border: "1px solid var(--border-color)",
                marginBottom: 8,
                background: "var(--bg-input)",
                color: "var(--text-main)",
                fontSize: 13,
              }}
            />
            <input
              type="text"
              placeholder="Full Folder Path (e.g. /home/user/my-project or C:\workspace\my-app)"
              value={newProjPath}
              onChange={(e) => setNewProjPath(e.target.value)}
              style={{
                width: "100%",
                padding: "8px 10px",
                borderRadius: 6,
                border: "1px solid var(--border-color)",
                marginBottom: 12,
                background: "var(--bg-input)",
                color: "var(--text-main)",
                fontSize: 13,
              }}
            />
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button
                onClick={() => setNewProjectModal(false)}
                style={{
                  padding: "6px 12px",
                  borderRadius: 6,
                  border: "1px solid var(--border-color)",
                  background: "transparent",
                  color: "var(--text-secondary)",
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleCreateProject}
                style={{
                  padding: "6px 14px",
                  borderRadius: 6,
                  border: 0,
                  // Inverted pill: hardcoding #111827 made this button disappear
                  // into the dark theme's surface.
                  background: "var(--text-main)",
                  color: "var(--bg-app)",
                  cursor: "pointer",
                  fontWeight: 500,
                }}
              >
                Add Project
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Sidebar Footer User Profile */}
      <footer className="sidebar-footer">
        <div className="profile-card">
          <div className="profile-avatar">J</div>
          <div className="profile-info">
            <span className="profile-name">JARVIS Agent</span>
            <span className="profile-status">{selectedModel} · Ready</span>
          </div>
        </div>

        <button
          className="sync-status-btn"
          title="JARVIS Neural Engine Active"
          aria-label="JARVIS Neural Engine Active"
        >
          <Sparkles size={13} />
        </button>
      </footer>
    </aside>
  );
}
