"use client";
import { create } from "zustand";
export const useMissionStore = create<{ selectedId?: string; replaying: boolean; replayIndex: number; speed: number; select: (id?: string) => void; setReplay: (playing: boolean) => void; setReplayIndex: (index: number) => void; setSpeed: (speed: number) => void }>(set => ({ selectedId: undefined, replaying: false, replayIndex: 0, speed: 1, select: selectedId => set({ selectedId, replayIndex: 0 }), setReplay: replaying => set({ replaying }), setReplayIndex: replayIndex => set({ replayIndex }), setSpeed: speed => set({ speed }) }));
