"use client";
import { create } from "zustand";
import type { ChatAttachment } from "../types";
export const useUploadStore = create<{ queue: ChatAttachment[]; setQueue: (queue: ChatAttachment[]) => void }>(set => ({ queue: [], setQueue: queue => set({ queue }) }));
