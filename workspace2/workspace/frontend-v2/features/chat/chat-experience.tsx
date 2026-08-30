"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import { RotateCcw } from "lucide-react";
import { streamChat } from "./chat-service";
import { Composer } from "./composer";
import { ConversationSidebar } from "./conversation-sidebar";
import { MessageList } from "./message-list";
import { useConversationStore } from "./stores/conversation-store";
import { useStreamStore } from "./stores/stream-store";
import { useUploadStore } from "./stores/upload-store";
import { useToolStore } from "./stores/tool-store";
import { ToolPanel } from "./tool-panel";
import { subscribeToolEvents } from "./tool-events";
import { TypingIndicator } from "./typing-indicator";
import type { ChatAttachment, ChatMessage } from "./types";

const createId = () => crypto.randomUUID();
const attachment = (file: File): ChatAttachment => ({ id: createId(), file, status: "ready", progress: 100 });

export function ChatExperience() {
  const { conversations, activeId, hydrated, hydrate, update } = useConversationStore();
  const { queue, setQueue } = useUploadStore(); const { status, setStatus } = useStreamStore();
  const { setActivities } = useToolStore();
  const [draft, setDraft] = useState(""); const [provider, setProvider] = useState<"local" | "cloud">("local"); const controller = useRef<AbortController | null>(null);
  const conversation = useMemo(() => conversations.find(item => item.id === activeId), [conversations, activeId]);

  useEffect(hydrate, [hydrate]);
  useEffect(() => { if (activeId) setDraft(localStorage.getItem(`jarvis-draft:${activeId}`) ?? ""); setQueue([]); }, [activeId, setQueue]);
  useEffect(() => { if (activeId) localStorage.setItem(`jarvis-draft:${activeId}`, draft); }, [activeId, draft]);
  useEffect(() => subscribeToolEvents(activity => setActivities([...useToolStore.getState().activities, activity].slice(-30))), [setActivities]);

  const addFiles = (files: FileList | File[]) => setQueue([...queue, ...Array.from(files).map(attachment)]);
  const cancel = () => controller.current?.abort();
  const send = async (content = draft, supplied = queue) => {
    if (!conversation || (!content.trim() && !supplied.length) || status === "streaming") return;
    const user: ChatMessage = { id: createId(), role: "user", content, createdAt: Date.now(), attachments: supplied };
    const assistant: ChatMessage = { id: createId(), role: "assistant", content: "", createdAt: Date.now(), attachments: [], execution: [] };
    update(conversation.id, { title: conversation.messages.length ? conversation.title : content.trim().slice(0, 56) || "Attachment", messages: [...conversation.messages, user, assistant] });
    setDraft(""); setQueue([]); localStorage.removeItem(`jarvis-draft:${conversation.id}`); setStatus("streaming"); controller.current = new AbortController();
    try {
      await streamChat(content, supplied.map(item => item.file), provider, controller.current.signal, token => {
        const latest = useConversationStore.getState().conversations.find(item => item.id === conversation.id);
        if (!latest) return;
        update(conversation.id, { messages: latest.messages.map(message => message.id === assistant.id ? { ...message, content: message.content + token } : message) });
      }, event => {
        const detail = event.type === "intent" ? String(event.payload.intent ?? "Intent resolved") : event.type === "tool" ? String(event.payload.name ?? event.payload.capability ?? "Capability") : String(event.payload.message ?? event.payload.status ?? "Completed");
        const name = event.type === "intent" ? "Planner" : event.type === "tool" ? "Tool execution" : event.type === "done" ? "Response" : event.type;
        setActivities([...useToolStore.getState().activities, { name, status: event.type, detail }].slice(-30));
        const latest = useConversationStore.getState().conversations.find(item => item.id === conversation.id);
        if (latest) update(conversation.id, { messages: latest.messages.map(message => message.id === assistant.id ? { ...message, execution: [...(message.execution ?? []), { type: event.type, detail, createdAt: Date.now() }] } : message) });
      });
      setStatus("idle");
    } catch (error) {
      if ((error as DOMException).name === "AbortError") { setStatus("idle"); return; }
      const latest = useConversationStore.getState().conversations.find(item => item.id === conversation.id);
      if (latest) update(conversation.id, { messages: latest.messages.map(message => message.id === assistant.id ? { ...message, failed: true, content: message.content || "The response could not be completed. Retry when ready." } : message) });
      setStatus("failed", error instanceof Error ? error.message : "Response failed");
    }
  };
  const regenerate = () => { const lastUser = [...(conversation?.messages ?? [])].reverse().find(message => message.role === "user"); if (lastUser) void send(lastUser.content, lastUser.attachments); };
  const continueResponse = () => { const lastAssistant = [...(conversation?.messages ?? [])].reverse().find(message => message.role === "assistant" && message.content); if (lastAssistant) void send(`Continue the prior response from this point:\n\n${lastAssistant.content}`); };
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [conversation?.messages, status]);

  if (!hydrated) return <section className="chat-loading" aria-live="polite">Loading conversations…</section>;
  return <div className="premium-chat">
    <ConversationSidebar />
    <section className="chat-thread" onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); addFiles(event.dataTransfer.files); }}>
      <div className="chat-thread-scroll" ref={scrollRef}><MessageList messages={conversation?.messages ?? []}/>{status === "streaming" && <TypingIndicator/>}</div>
      {status === "failed" && <button className="retry-message" onClick={regenerate}><RotateCcw size={14}/> Retry response</button>}
      {status === "idle" && Boolean(conversation?.messages.length) && <button className="retry-message" onClick={continueResponse}>Continue response</button>}
      <motion.div className="chat-composer-dock" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}><Composer value={draft} onChange={setDraft} queue={queue} onFiles={addFiles} onRemove={id => setQueue(queue.filter(item => item.id !== id))} onSend={() => void send()} onCancel={cancel} sending={status === "streaming"} provider={provider} onProviderChange={setProvider}/></motion.div>
    </section>
    <ToolPanel />
  </div>;
}
