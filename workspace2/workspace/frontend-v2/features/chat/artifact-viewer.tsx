"use client";

import { useEffect, useState } from "react";
import type { ChatAttachment } from "./types";

function AttachmentPreview({ attachment }: { attachment: ChatAttachment }) {
  const { file } = attachment; const [url, setUrl] = useState(""); const [text, setText] = useState("");
  useEffect(() => { const objectUrl = URL.createObjectURL(file); setUrl(objectUrl); if (file.type.startsWith("text/") || file.type.includes("json") || file.name.endsWith(".csv") || file.name.endsWith(".md")) void file.text().then(setText); return () => URL.revokeObjectURL(objectUrl); }, [file]);
  if (file.type.startsWith("image/")) return <img src={url} alt={file.name} />;
  if (file.type === "application/pdf") return <object data={url} aria-label={`PDF preview: ${file.name}`} />;
  if (file.type.startsWith("audio/")) return <audio controls src={url} />;
  if (file.type.startsWith("video/")) return <video controls src={url} />;
  if (text) return <details className="text-artifact"><summary>{file.name}</summary><pre>{file.type.includes("json") ? prettyJson(text) : text}</pre></details>;
  return <a href={url} download={file.name}>{file.name}{file.type.includes("zip") ? ` (${Math.ceil(file.size / 1024)} KB archive)` : ""}</a>;
}
function prettyJson(value: string) { try { return JSON.stringify(JSON.parse(value), null, 2); } catch { return value; } }
export function ArtifactViewer({ attachments }: { attachments: ChatAttachment[] }) { return attachments.length ? <section className="artifact-viewer" aria-label="Message artifacts">{attachments.map(item => <AttachmentPreview key={item.id} attachment={item}/>)}</section> : null; }
