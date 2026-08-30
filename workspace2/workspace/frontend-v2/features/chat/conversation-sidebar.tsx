"use client";

import { ChangeEvent, useMemo, useRef, useState } from "react";
import { Archive, Download, FileUp, FolderCog, Pencil, Pin, Plus, Search, Star, Tag, Trash2 } from "lucide-react";
import { useConversationStore } from "./stores/conversation-store";

export function ConversationSidebar() {
  const { conversations, activeId, create, select, update, remove, replace } = useConversationStore();
  const [query, setQuery] = useState(""); const importer = useRef<HTMLInputElement>(null);
  const items = useMemo(() => conversations.filter(item => !item.archived && `${item.title} ${item.tags?.join(" ") ?? ""}`.toLowerCase().includes(query.toLowerCase())).sort((a, b) => Number(b.pinned) - Number(a.pinned) || b.updatedAt - a.updatedAt), [conversations, query]);
  const exportConversations = () => {
    const blob = new Blob([JSON.stringify(conversations, null, 2)], { type: "application/json" });
    const link = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: "jarvis-conversations.json" }); link.click(); URL.revokeObjectURL(link.href);
  };
  const importConversations = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]; if (!file) return;
    try { const parsed = JSON.parse(await file.text()); if (Array.isArray(parsed)) replace(parsed); } finally { event.target.value = ""; }
  };
  return <aside className="conversation-list" aria-label="Conversations">
    <div className="conversation-actions"><button onClick={create}><Plus size={15} /> New chat</button><button aria-label="Export conversations" onClick={exportConversations}><Download size={15} /></button><button aria-label="Import conversations" onClick={() => importer.current?.click()}><FileUp size={15} /></button><input ref={importer} type="file" accept="application/json" hidden onChange={importConversations}/></div>
    <label className="conversation-search"><Search size={14}/><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search conversations" /></label>
    <div className="conversation-scroll">{items.length ? items.map(item => <div className={`conversation-item ${item.id === activeId ? "active" : ""}`} key={item.id}>
      <button className="conversation-title" onClick={() => select(item.id)}>{item.pinned && <Pin size={12}/>} {item.favorite && <Star size={12}/>}<span>{item.title}</span></button>
      <div className="conversation-controls"><button aria-label="Rename conversation" onClick={() => { const title = window.prompt("Conversation name", item.title); if (title?.trim()) update(item.id, { title: title.trim() }); }}><Pencil size={12}/></button><button aria-label="Move conversation to folder" onClick={() => { const folder = window.prompt("Folder name", item.folder ?? ""); if (folder !== null) update(item.id, { folder: folder.trim() || undefined }); }}><FolderCog size={12}/></button><button aria-label="Edit conversation tags" onClick={() => { const tags = window.prompt("Comma-separated tags", item.tags?.join(", ") ?? ""); if (tags !== null) update(item.id, { tags: tags.split(",").map(tag => tag.trim()).filter(Boolean) }); }}><Tag size={12}/></button><button aria-label="Archive conversation" onClick={() => update(item.id, { archived: true })}><Archive size={12}/></button><button aria-label="Pin conversation" onClick={() => update(item.id, { pinned: !item.pinned })}><Pin size={12}/></button><button aria-label="Favorite conversation" onClick={() => update(item.id, { favorite: !item.favorite })}><Star size={12}/></button><button aria-label="Delete conversation" onClick={() => remove(item.id)}><Trash2 size={12}/></button></div>
    </div>) : <p className="empty-inline">No matching conversations.</p>}</div>
  </aside>;
}
