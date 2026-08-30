"use client";
import { create } from "zustand";
export type StreamStatus = "idle" | "streaming" | "failed";
export const useStreamStore = create<{ status: StreamStatus; error?: string; setStatus: (status: StreamStatus, error?: string) => void }>(set => ({ status: "idle", setStatus: (status, error) => set({ status, error }) }));
