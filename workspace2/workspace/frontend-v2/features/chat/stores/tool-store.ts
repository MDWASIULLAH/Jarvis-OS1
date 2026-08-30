"use client";
import { create } from "zustand";
export type ToolActivity = { name: string; status: string; detail?: string };
export const useToolStore = create<{ activities: ToolActivity[]; setActivities: (activities: ToolActivity[]) => void }>(set => ({ activities: [], setActivities: activities => set({ activities }) }));
