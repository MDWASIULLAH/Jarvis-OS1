"use client";
import { create } from "zustand";

/** Selection shared by the operational dashboards (workforce, studio, graph). */
export const useOperationalSelectionStore = create<{
  agentId?: string;
  projectId?: string;
  nodeId?: string;
  selectAgent: (agentId?: string) => void;
  selectProject: (projectId?: string) => void;
  selectNode: (nodeId?: string) => void;
}>(set => ({
  agentId: undefined,
  projectId: undefined,
  nodeId: undefined,
  selectAgent: agentId => set({ agentId }),
  selectProject: projectId => set({ projectId }),
  selectNode: nodeId => set({ nodeId }),
}));
