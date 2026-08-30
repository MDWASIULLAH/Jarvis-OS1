"use client";

import { X, Puzzle, Check, Power } from "lucide-react";
import { useUIStore } from "../../store/ui-store";

export function PluginsModal() {
  const { pluginsOpen, setPluginsOpen, activePlugins, togglePlugin } = useUIStore();

  if (!pluginsOpen) return null;

  const pluginsList = [
    {
      id: "code_interpreter",
      name: "Python & TypeScript Code Execution Sandbox",
      category: "Compute",
      description:
        "Execute Python, Node.js scripts, perform data analytics, math calculations, and visual generation.",
      icon: "💻",
    },
    {
      id: "file_system",
      name: "Local Filesystem & Workspace Harness",
      category: "IO",
      description:
        "Full read, write, multi-file edits, ripgrep semantic search, and project tree navigation.",
      icon: "📁",
    },
    {
      id: "web_browser",
      name: "Live In-App Browser & DOM Subagent",
      category: "Web",
      description:
        "Interactive web browsing, web search, DOM snapshot inspection, and UI automated verification.",
      icon: "🌐",
    },
    {
      id: "neural_nexus",
      name: "3D Neural Nexus & Memory Fabric",
      category: "AI",
      description:
        "Interactive 3D graph visualization of agent memory, topology, and cross-session knowledge nodes.",
      icon: "🧠",
    },
    {
      id: "powershell_runner",
      name: "PowerShell & Shell Command Engine",
      category: "OS",
      description:
        "Execute commands directly in PowerShell terminal with live streaming output and exit codes.",
      icon: "⚡",
    },
  ];

  return (
    <div className="modal-overlay" onClick={() => setPluginsOpen(false)}>
      <div className="modal-dialog-card" onClick={(e) => e.stopPropagation()}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            paddingBottom: 8,
            borderBottom: "1px solid var(--border-color)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 600 }}>
            <Puzzle size={17} color="#8b5cf6" />
            <span>JARVIS Capability Plugins & Tool Harness</span>
          </div>
          <button
            onClick={() => setPluginsOpen(false)}
            style={{
              border: 0,
              background: "transparent",
              cursor: "pointer",
              color: "var(--text-secondary)",
            }}
          >
            <X size={17} />
          </button>
        </div>

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 8,
            maxHeight: 380,
            overflowY: "auto",
          }}
        >
          {pluginsList.map((p) => {
            const isEnabled = activePlugins.includes(p.id);
            return (
              <div
                key={p.id}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  justifyContent: "space-between",
                  gap: 12,
                  padding: "10px 12px",
                  borderRadius: 8,
                  border: "1px solid var(--border-color)",
                  background: "var(--bg-card-subtle)",
                }}
              >
                <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                  <span style={{ fontSize: 20 }}>{p.icon}</span>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{ fontWeight: 500, fontSize: 13 }}>{p.name}</span>
                      <span
                        style={{
                          fontSize: 10,
                          padding: "1px 6px",
                          borderRadius: 4,
                          background: "var(--bg-pill)",
                          color: "var(--text-muted)",
                        }}
                      >
                        {p.category}
                      </span>
                    </div>
                    <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 2 }}>
                      {p.description}
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => togglePlugin(p.id)}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 4,
                    padding: "4px 10px",
                    borderRadius: 6,
                    border: 0,
                    background: isEnabled ? "#10a37f" : "var(--bg-pill)",
                    color: isEnabled ? "#ffffff" : "var(--text-secondary)",
                    cursor: "pointer",
                    fontSize: 11,
                    fontWeight: 500,
                    flexShrink: 0,
                  }}
                >
                  {isEnabled ? <Check size={12} /> : <Power size={12} />}
                  <span>{isEnabled ? "Active" : "Enable"}</span>
                </button>
              </div>
            );
          })}
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            paddingTop: 8,
            borderTop: "1px solid var(--border-color)",
          }}
        >
          <button
            onClick={() => setPluginsOpen(false)}
            style={{
              padding: "5px 14px",
              borderRadius: 6,
              background: "var(--bg-pill)",
              color: "var(--text-main)",
              border: "1px solid var(--border-color)",
              cursor: "pointer",
              fontSize: 12,
            }}
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
