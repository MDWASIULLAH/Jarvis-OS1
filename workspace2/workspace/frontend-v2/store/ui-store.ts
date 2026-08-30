import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { NavigationId } from "../types/navigation";

export type Theme = "dark" | "light" | "system";
export type ApprovalMode = "ask_approval" | "approve_for_me" | "full_access";
export type ModelOption =
  | "JARVIS J-3.1 Ultra"
  | "JARVIS J-4.0 Omni"
  | "JARVIS J-2.5 Pro"
  | "JARVIS J-1.1 Turbo"
  | "JARVIS J-1.0 Mini"
  | "JARVIS J-Local Core";
export type ReasoningEffort = "High" | "Medium" | "Low";
export type RightPanelTab = "files" | "browser" | "harness" | "modules";

export interface ProjectItem {
  id: string;
  name: string;
  subtitle: string;
  path: string;
  subitems?: string[];
}

export interface ScheduledTask {
  id: string;
  name: string;
  cron: string;
  action: string;
  enabled: boolean;
  lastRun?: string;
}

interface UIState {
  active: NavigationId;
  theme: Theme;
  paletteOpen: boolean;
  notificationsOpen: boolean;
  scheduledOpen: boolean;
  pluginsOpen: boolean;
  leftOpen: boolean;
  rightOpen: boolean;
  terminalOpen: boolean;
  rightPanelTab: RightPanelTab;
  approvalMode: ApprovalMode;
  selectedModel: ModelOption;
  reasoningEffort: ReasoningEffort;
  activeProject: string;
  activeDirectory: string;
  projects: ProjectItem[];
  scheduledTasks: ScheduledTask[];
  activePlugins: string[];

  setActive: (value: NavigationId) => void;
  setTheme: (value: Theme) => void;
  setPaletteOpen: (value: boolean) => void;
  setNotificationsOpen: (value: boolean) => void;
  setScheduledOpen: (value: boolean) => void;
  setPluginsOpen: (value: boolean) => void;
  setTerminalOpen: (value: boolean) => void;
  setRightPanelTab: (tab: RightPanelTab) => void;
  setApprovalMode: (mode: ApprovalMode) => void;
  setSelectedModel: (model: ModelOption) => void;
  setReasoningEffort: (effort: ReasoningEffort) => void;
  setActiveProject: (project: string) => void;
  setActiveDirectory: (dir: string) => void;
  addProject: (name: string, subtitle: string, path: string) => void;
  removeProject: (id: string) => void;
  togglePanel: (panel: "leftOpen" | "rightOpen" | "terminalOpen") => void;
  togglePlugin: (pluginId: string) => void;
  toggleScheduledTask: (taskId: string) => void;
  addScheduledTask: (task: Omit<ScheduledTask, "id">) => void;
}

const DEFAULT_SCHEDULED: ScheduledTask[] = [
  {
    id: "sched-1",
    name: "Repository Health & Architecture Scan",
    cron: "Daily at 00:00",
    action: "Run static checks, verify type definitions and API sync",
    enabled: true,
    lastRun: "8 hours ago (Passed)",
  },
  {
    id: "sched-2",
    name: "Neural Nexus Topology & Memory Indexing",
    cron: "Every 30 minutes",
    action: "Recompute knowledge embeddings and link cross-session nodes",
    enabled: true,
    lastRun: "14 mins ago (Synced 64 nodes)",
  },
];

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      active: "chat",
      theme: "light",
      paletteOpen: false,
      notificationsOpen: false,
      scheduledOpen: false,
      pluginsOpen: false,
      leftOpen: true,
      rightOpen: false,
      terminalOpen: false,
      rightPanelTab: "files",
      approvalMode: "full_access",
      selectedModel: "JARVIS J-3.1 Ultra",
      reasoningEffort: "High",
      activeProject: "Workspace",
      activeDirectory: "",
      projects: [],
      scheduledTasks: DEFAULT_SCHEDULED,
      activePlugins: [
        "code_interpreter",
        "file_system",
        "web_browser",
        "neural_nexus",
        "powershell_runner",
      ],

      setActive: (active) => set({ active }),
      setTheme: (theme) => set({ theme }),
      setPaletteOpen: (paletteOpen) => set({ paletteOpen }),
      setNotificationsOpen: (notificationsOpen) => set({ notificationsOpen }),
      setScheduledOpen: (scheduledOpen) => set({ scheduledOpen }),
      setPluginsOpen: (pluginsOpen) => set({ pluginsOpen }),
      setTerminalOpen: (terminalOpen) => set({ terminalOpen }),
      setRightPanelTab: (rightPanelTab) => set({ rightPanelTab }),
      setApprovalMode: (approvalMode) => set({ approvalMode }),
      setSelectedModel: (selectedModel) => set({ selectedModel }),
      setReasoningEffort: (reasoningEffort) => set({ reasoningEffort }),
      setActiveProject: (activeProject) => set({ activeProject }),
      setActiveDirectory: (activeDirectory) => set({ activeDirectory }),
      addProject: (name, subtitle, path) =>
        set((state) => ({
          projects: [
            ...state.projects.filter((p) => p.name !== name),
            { id: `proj-${Date.now()}`, name, subtitle, path, subitems: [] },
          ],
        })),
      removeProject: (id) =>
        set((state) => ({
          projects: state.projects.filter((p) => p.id !== id),
        })),
      togglePanel: (panel) =>
        set((state) => ({ [panel]: !state[panel] })),
      togglePlugin: (pluginId) =>
        set((state) => ({
          activePlugins: state.activePlugins.includes(pluginId)
            ? state.activePlugins.filter((p) => p !== pluginId)
            : [...state.activePlugins, pluginId],
        })),
      toggleScheduledTask: (taskId) =>
        set((state) => ({
          scheduledTasks: state.scheduledTasks.map((t) =>
            t.id === taskId ? { ...t, enabled: !t.enabled } : t
          ),
        })),
      addScheduledTask: (task) =>
        set((state) => ({
          scheduledTasks: [
            ...state.scheduledTasks,
            { ...task, id: `sched-${Date.now()}` },
          ],
        })),
    }),
    {
      name: "jarvis-ui-preferences-v5",
      partialize: (state) => ({
        active: state.active,
        theme: state.theme,
        leftOpen: state.leftOpen,
        rightOpen: state.rightOpen,
        approvalMode: state.approvalMode,
        selectedModel: state.selectedModel,
        reasoningEffort: state.reasoningEffort,
        activeProject: state.activeProject,
        activeDirectory: state.activeDirectory,
        projects: state.projects,
      }),
    }
  )
);
