"use client";

import { create } from "zustand";
import type { Conversation } from "../types";

const STORAGE_KEY = "jarvis-chat-v2";
const newId = () => crypto.randomUUID();
const blankConversation = (): Conversation => ({
  id: newId(), title: "New conversation", messages: [], pinned: false, favorite: false, updatedAt: Date.now(),
});

type ConversationState = {
  conversations: Conversation[];
  activeId: string;
  hydrated: boolean;
  hydrate: () => void;
  create: () => void;
  select: (id: string) => void;
  update: (id: string, patch: Partial<Conversation>) => void;
  remove: (id: string) => void;
  replace: (conversations: Conversation[]) => void;
};

function persist(conversations: Conversation[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
}

export const useConversationStore = create<ConversationState>((set, get) => ({
  conversations: [], activeId: "", hydrated: false,
  hydrate: () => {
    if (get().hydrated) return;
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      const parsed = raw ? JSON.parse(raw) as Conversation[] : [];
      const conversations = parsed.length ? parsed : [blankConversation()];
      set({ conversations, activeId: conversations[0].id, hydrated: true });
    } catch { const conversation = blankConversation(); set({ conversations: [conversation], activeId: conversation.id, hydrated: true }); }
  },
  create: () => set(state => { const next = blankConversation(); const conversations = [next, ...state.conversations]; persist(conversations); return { conversations, activeId: next.id }; }),
  select: activeId => set({ activeId }),
  update: (id, patch) => set(state => { const conversations = state.conversations.map(item => item.id === id ? { ...item, ...patch, updatedAt: Date.now() } : item); persist(conversations); return { conversations }; }),
  remove: id => set(state => { const conversations = state.conversations.filter(item => item.id !== id); const retained = conversations.length ? conversations : [blankConversation()]; persist(retained); return { conversations: retained, activeId: state.activeId === id ? retained[0].id : state.activeId }; }),
  replace: conversations => { const retained = conversations.length ? conversations : [blankConversation()]; persist(retained); set({ conversations: retained, activeId: retained[0].id }); },
}));
