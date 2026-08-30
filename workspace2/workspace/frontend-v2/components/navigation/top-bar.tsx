"use client";

import { useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Minus,
  Square,
  X,
  Columns2,
  Terminal,
  Sun,
  Moon,
  Bell,
  Search,
  FolderGit2,
} from "lucide-react";
import { useUIStore } from "../../store/ui-store";

export function TopBar() {
  const {
    togglePanel,
    rightOpen,
    terminalOpen,
    theme,
    setTheme,
    setPaletteOpen,
    setNotificationsOpen,
    activeProject,
  } = useUIStore();

  const [activeMenu, setActiveMenu] = useState<string | null>(null);

  const toggleMenu = (menuName: string) => {
    setActiveMenu(activeMenu === menuName ? null : menuName);
  };

  const closeMenu = () => setActiveMenu(null);

  return (
    <header className="desktop-titlebar">
      {/* Titlebar Left: Navigation Arrows & Menubar */}
      <div className="titlebar-left">
        <div className="titlebar-nav-arrows">
          <button className="nav-arrow-btn" aria-label="Go Back" title="Back">
            <ChevronLeft size={16} />
          </button>
          <button className="nav-arrow-btn" aria-label="Go Forward" title="Forward">
            <ChevronRight size={16} />
          </button>
        </div>

        <nav className="desktop-menubar" onMouseLeave={closeMenu}>
          {/* File Menu */}
          <div style={{ position: "relative" }}>
            <button
              className={`menu-item-btn ${activeMenu === "file" ? "open" : ""}`}
              onClick={() => toggleMenu("file")}
            >
              File
            </button>
            {activeMenu === "file" && (
              <div className="menu-dropdown">
                <button onClick={closeMenu}>New Workspace Session</button>
                <button onClick={closeMenu}>Open Project Folder...</button>
                <button onClick={closeMenu}>Save Workspace Snapshot</button>
                <hr />
                <button onClick={closeMenu}>Export Execution Logs</button>
                <button onClick={closeMenu}>Close Window</button>
              </div>
            )}
          </div>

          {/* Edit Menu */}
          <div style={{ position: "relative" }}>
            <button
              className={`menu-item-btn ${activeMenu === "edit" ? "open" : ""}`}
              onClick={() => toggleMenu("edit")}
            >
              Edit
            </button>
            {activeMenu === "edit" && (
              <div className="menu-dropdown">
                <button onClick={closeMenu}>Undo</button>
                <button onClick={closeMenu}>Redo</button>
                <hr />
                <button onClick={closeMenu}>Cut</button>
                <button onClick={closeMenu}>Copy</button>
                <button onClick={closeMenu}>Paste</button>
              </div>
            )}
          </div>

          {/* View Menu */}
          <div style={{ position: "relative" }}>
            <button
              className={`menu-item-btn ${activeMenu === "view" ? "open" : ""}`}
              onClick={() => toggleMenu("view")}
            >
              View
            </button>
            {activeMenu === "view" && (
              <div className="menu-dropdown">
                <button onClick={() => { togglePanel("leftOpen"); closeMenu(); }}>
                  Toggle Sidebar
                </button>
                <button onClick={() => { togglePanel("rightOpen"); closeMenu(); }}>
                  Toggle Files & Browser Panel
                </button>
                <button onClick={() => { togglePanel("terminalOpen"); closeMenu(); }}>
                  Toggle PowerShell Terminal
                </button>
                <hr />
                <button onClick={() => { setTheme(theme === "dark" ? "light" : "dark"); closeMenu(); }}>
                  Switch to {theme === "dark" ? "Light" : "Dark"} Mode
                </button>
              </div>
            )}
          </div>

          {/* Help Menu */}
          <div style={{ position: "relative" }}>
            <button
              className={`menu-item-btn ${activeMenu === "help" ? "open" : ""}`}
              onClick={() => toggleMenu("help")}
            >
              Help
            </button>
            {activeMenu === "help" && (
              <div className="menu-dropdown">
                <button onClick={closeMenu}>JARVIS Codex Architecture</button>
                <button onClick={closeMenu}>Keyboard Shortcuts</button>
                <hr />
                <button onClick={closeMenu}>About JARVIS AI Harness</button>
              </div>
            )}
          </div>
        </nav>
      </div>

      {/* Titlebar Center: Active Project Indicator */}
      <div className="titlebar-center">
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "3px 12px",
            borderRadius: 999,
            background: "var(--bg-pill)",
            fontSize: 12,
            fontWeight: 500,
            color: "var(--text-main)",
            border: "1px solid var(--border-subtle)",
          }}
        >
          <FolderGit2 size={13} color="#3b82f6" />
          <span>{activeProject}</span>
        </div>
      </div>

      {/* Titlebar Right: Action Controls & Windows Buttons */}
      <div className="titlebar-right">
        <button
          className="header-icon-btn"
          title="Search Workspace (Ctrl+K)"
          aria-label="Search Workspace"
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
          className={`header-icon-btn ${terminalOpen ? "active" : ""}`}
          title="Toggle PowerShell Terminal Drawer (Ctrl+`)"
          aria-label="Toggle Terminal Drawer"
          onClick={() => togglePanel("terminalOpen")}
        >
          <Terminal size={15} />
        </button>

        <button
          className={`header-icon-btn ${rightOpen ? "active" : ""}`}
          title="Toggle Right Panel (Files / Browser)"
          aria-label="Toggle Right Panel"
          onClick={() => togglePanel("rightOpen")}
        >
          <Columns2 size={16} />
        </button>

        <button
          className="header-icon-btn"
          title="Toggle Theme"
          aria-label="Toggle Theme"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        >
          {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
        </button>

        <div className="window-controls">
          <button className="window-ctrl-btn" aria-label="Minimize" title="Minimize">
            <Minus size={13} />
          </button>
          <button className="window-ctrl-btn" aria-label="Maximize" title="Maximize">
            <Square size={11} />
          </button>
          <button className="window-ctrl-btn close" aria-label="Close" title="Close">
            <X size={13} />
          </button>
        </div>
      </div>
    </header>
  );
}
