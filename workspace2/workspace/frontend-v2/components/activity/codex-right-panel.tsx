"use client";

import { useState } from "react";
import {
  Folder,
  Globe,
  Zap,
  Layers,
  X,
  FileCode,
  FileText,
  File,
  RotateCw,
  ArrowLeft,
  ArrowRight,
  ExternalLink,
  ChevronDown,
  ChevronRight,
  Search,
} from "lucide-react";
import { useUIStore, RightPanelTab } from "../../store/ui-store";

export function CodexRightPanel() {
  const { rightOpen, togglePanel, rightPanelTab, setRightPanelTab, activeDirectory, setActive } =
    useUIStore();

  const [searchQuery, setSearchQuery] = useState("");
  const [selectedFile, setSelectedFile] = useState<string | null>("app/page.tsx");
  const [browserUrl, setBrowserUrl] = useState("http://localhost:3000");
  const [expandedFolders, setExpandedFolders] = useState<Record<string, boolean>>({
    app: true,
    components: true,
    features: true,
  });

  if (!rightOpen) return null;

  const toggleFolder = (folder: string) => {
    setExpandedFolders((prev) => ({ ...prev, [folder]: !prev[folder] }));
  };

  const fileTree = [
    {
      name: "app",
      isDir: true,
      children: [
        { name: "layout.tsx", isDir: false, icon: FileCode },
        { name: "page.tsx", isDir: false, icon: FileCode },
      ],
    },
    {
      name: "components",
      isDir: true,
      children: [
        { name: "top-bar.tsx", isDir: false, icon: FileCode },
        { name: "app-sidebar.tsx", isDir: false, icon: FileCode },
        { name: "powershell-drawer.tsx", isDir: false, icon: FileCode },
        { name: "codex-right-panel.tsx", isDir: false, icon: FileCode },
      ],
    },
    {
      name: "features",
      isDir: true,
      children: [
        { name: "codex-harness.tsx", isDir: false, icon: FileCode },
        { name: "chat-experience.tsx", isDir: false, icon: FileCode },
        { name: "neural-nexus.tsx", isDir: false, icon: FileCode },
        { name: "mission-dashboard.tsx", isDir: false, icon: FileCode },
        { name: "operations-center.tsx", isDir: false, icon: FileCode },
      ],
    },
    { name: "package.json", isDir: false, icon: FileText },
    { name: "tsconfig.json", isDir: false, icon: FileCode },
    { name: "globals.css", isDir: false, icon: FileCode },
  ];

  return (
    <aside className="codex-right-panel" aria-label="Tools and Inspector Panel">
      {/* Right Panel Header & Tabs */}
      <div className="right-panel-header">
        <div className="right-panel-tabs">
          <button
            className={`right-tab-btn ${rightPanelTab === "files" ? "active" : ""}`}
            onClick={() => setRightPanelTab("files")}
            title="Files (Ctrl+P)"
          >
            <Folder size={14} />
            <span>Files</span>
          </button>
          <button
            className={`right-tab-btn ${rightPanelTab === "browser" ? "active" : ""}`}
            onClick={() => setRightPanelTab("browser")}
            title="Browser (Ctrl+T)"
          >
            <Globe size={14} />
            <span>Browser</span>
          </button>
          <button
            className={`right-tab-btn ${rightPanelTab === "harness" ? "active" : ""}`}
            onClick={() => setRightPanelTab("harness")}
            title="Agent Harness"
          >
            <Zap size={14} />
            <span>Harness</span>
          </button>
          <button
            className={`right-tab-btn ${rightPanelTab === "modules" ? "active" : ""}`}
            onClick={() => setRightPanelTab("modules")}
            title="JARVIS Modules"
          >
            <Layers size={14} />
            <span>Modules</span>
          </button>
        </div>

        <button
          className="header-icon-btn"
          onClick={() => togglePanel("rightOpen")}
          aria-label="Close Right Panel"
        >
          <X size={15} />
        </button>
      </div>

      {/* Right Panel Content */}
      <div className="right-panel-content">
        {/* Tab 1: Files */}
        {rightPanelTab === "files" && (
          <div className="file-tree-container">
            <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "4px 8px",
                  borderRadius: 6,
                  border: "1px solid var(--border-color)",
                  flex: 1,
                  background: "var(--bg-input)",
                }}
              >
                <Search size={13} color="var(--text-muted)" />
                <input
                  type="text"
                  placeholder="Filter files (Ctrl+P)..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  style={{
                    border: 0,
                    outline: 0,
                    background: "transparent",
                    fontSize: 12,
                    color: "var(--text-main)",
                    width: "100%",
                  }}
                />
              </div>
            </div>

            <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 6 }}>
              {activeDirectory}
            </div>

            {fileTree.map((item, idx) => {
              if (item.isDir) {
                const isOpen = expandedFolders[item.name] ?? false;
                return (
                  <div key={idx}>
                    <button
                      className="file-tree-item"
                      onClick={() => toggleFolder(item.name)}
                      style={{ fontWeight: 500 }}
                    >
                      <div className="file-item-left">
                        {isOpen ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                        <Folder size={14} color="#3b82f6" />
                        <span>{item.name}</span>
                      </div>
                    </button>

                    {isOpen && item.children && (
                      <div style={{ paddingLeft: 16 }}>
                        {item.children.map((child, cIdx) => (
                          <button
                            key={cIdx}
                            className={`file-tree-item ${
                              selectedFile === `${item.name}/${child.name}` ? "active" : ""
                            }`}
                            onClick={() => setSelectedFile(`${item.name}/${child.name}`)}
                          >
                            <div className="file-item-left">
                              <FileCode size={13} color="var(--text-secondary)" />
                              <span>{child.name}</span>
                            </div>
                            <span className="file-shortcut">Ctrl+P</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                );
              }

              return (
                <button
                  key={idx}
                  className={`file-tree-item ${selectedFile === item.name ? "active" : ""}`}
                  onClick={() => setSelectedFile(item.name)}
                >
                  <div className="file-item-left">
                    <FileText size={13} color="var(--text-secondary)" />
                    <span>{item.name}</span>
                  </div>
                </button>
              );
            })}

            {selectedFile && (
              <div
                style={{
                  marginTop: 16,
                  padding: 10,
                  borderRadius: 8,
                  border: "1px solid var(--border-color)",
                  background: "var(--bg-card-subtle)",
                }}
              >
                <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4 }}>
                  Selected: {selectedFile}
                </div>
                <div style={{ fontSize: 11, color: "var(--text-secondary)" }}>
                  Ready for editing, AI code diff, and automated refactoring.
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Live Browser */}
        {rightPanelTab === "browser" && (
          <div className="inapp-browser-frame">
            <div className="browser-address-bar">
              <button className="header-icon-btn" style={{ width: 22, height: 22 }}>
                <ArrowLeft size={12} />
              </button>
              <button className="header-icon-btn" style={{ width: 22, height: 22 }}>
                <ArrowRight size={12} />
              </button>
              <button className="header-icon-btn" style={{ width: 22, height: 22 }}>
                <RotateCw size={12} />
              </button>
              <input
                type="text"
                className="browser-url-input"
                value={browserUrl}
                onChange={(e) => setBrowserUrl(e.target.value)}
              />
              <button className="header-icon-btn" style={{ width: 22, height: 22 }}>
                <ExternalLink size={12} />
              </button>
            </div>

            <div className="browser-viewport">
              <div
                style={{
                  textAlign: "center",
                  padding: "20px 10px",
                  border: "1px dashed var(--border-color)",
                  borderRadius: 8,
                  marginTop: 10,
                }}
              >
                <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>
                  JARVIS Live Web DOM Preview
                </div>
                <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 12 }}>
                  Interactive live preview of {browserUrl}
                </div>
                <div
                  style={{
                    display: "inline-block",
                    padding: "4px 8px",
                    borderRadius: 999,
                    background: "#dcfce7",
                    color: "#15803d",
                    fontSize: 11,
                    fontWeight: 500,
                  }}
                >
                  ● Local Dev Server Connected (Port 3000)
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: Harness Agent */}
        {rightPanelTab === "harness" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ fontSize: 13, fontWeight: 600 }}>Active Agent Swarm</div>
            <div
              style={{
                padding: 10,
                borderRadius: 8,
                border: "1px solid var(--border-color)",
                background: "var(--bg-card-subtle)",
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 600, color: "#10a37f" }}>
                ● Autonomous Harness Engine
              </div>
              <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 4 }}>
                Full file read/write, bash terminal execution, live DOM inspector enabled.
              </div>
            </div>
            <div
              style={{
                padding: 10,
                borderRadius: 8,
                border: "1px solid var(--border-color)",
                background: "var(--bg-card-subtle)",
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 600 }}>Tool Executions (Last 5 mins)</div>
              <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
                • powershell.exe execution (status: active)
                <br />
                • file_writer: codex-harness.tsx (success)
                <br />• neural_nexus: topology synced (success)
              </div>
            </div>
          </div>
        )}

        {/* Tab 4: Modules */}
        {rightPanelTab === "modules" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
              Direct JARVIS Views
            </div>
            {[
              { id: "mission-control", label: "Mission Control" },
              { id: "neural-nexus", label: "Neural Nexus 3D" },
              { id: "operations", label: "Operations Center" },
              { id: "development-studio", label: "Development Studio" },
              { id: "agents", label: "Workforce Swarm" },
            ].map((m) => (
              <button
                key={m.id}
                className="file-tree-item"
                onClick={() => setActive(m.id as any)}
                style={{ padding: "8px 10px" }}
              >
                <span>{m.label}</span>
                <ChevronRight size={14} color="var(--text-muted)" />
              </button>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}
