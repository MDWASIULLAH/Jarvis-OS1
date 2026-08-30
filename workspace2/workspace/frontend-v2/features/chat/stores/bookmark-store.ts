"use client";
import { create } from "zustand";
const key = "jarvis-chat-bookmarks";
const load = (): string[] => { try { return JSON.parse(localStorage.getItem(key) ?? "[]") as string[]; } catch { return []; } };
export const useBookmarkStore = create<{ ids: string[]; hydrated: boolean; hydrate: () => void; toggle: (id: string) => void }>((set, get) => ({ ids: [], hydrated: false, hydrate: () => { if (!get().hydrated) set({ ids: load(), hydrated: true }); }, toggle: id => set(state => { const ids = state.ids.includes(id) ? state.ids.filter(value => value !== id) : [...state.ids, id]; localStorage.setItem(key, JSON.stringify(ids)); return { ids }; }) }));
