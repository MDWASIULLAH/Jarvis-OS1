"use client";

import { memo } from "react";
import { Copy } from "lucide-react";
import { ArtifactViewer } from "./artifact-viewer";
import { ExecutionTimeline } from "./execution-timeline";
import { MarkdownRenderer } from "./markdown-renderer";
import { MessageActions } from "./message-actions";
import type { ChatMessage } from "./types";

export const MessageList = memo(function MessageList({ messages }: { messages: ChatMessage[] }) {
  return <>{messages.map(message => <article className={`chat-message ${message.role}${message.failed ? " failed" : ""}`} key={message.id}>
    <header><b>{message.role === "assistant" ? "JARVIS" : message.role}</b><time dateTime={new Date(message.createdAt).toISOString()}>{new Date(message.createdAt).toLocaleTimeString()}</time><button aria-label="Copy message" onClick={() => void navigator.clipboard.writeText(message.content)}><Copy size={13}/></button><MessageActions id={message.id} content={message.content}/></header>
    {message.content && <MarkdownRenderer content={message.content}/>}<ExecutionTimeline events={message.execution}/><ArtifactViewer attachments={message.attachments}/>
  </article>)}</>;
});
