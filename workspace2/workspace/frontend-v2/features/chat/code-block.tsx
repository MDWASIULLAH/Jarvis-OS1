"use client";

import { useState } from "react";
import { Copy, Download, ExternalLink, WrapText } from "lucide-react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";

export function CodeBlock({ code, language }: { code: string; language?: string }) {
  const [collapsed, setCollapsed] = useState(false); const [wrapped, setWrapped] = useState(false); const [editorNotice, setEditorNotice] = useState(false);
  const download = `data:text/plain;charset=utf-8,${encodeURIComponent(code)}`;
  return <section className="code-block" aria-label={`${language ?? "plain text"} code block`}>
    <header><span>{language ?? "text"}</span><div><button aria-label="Toggle code wrapping" onClick={() => setWrapped(value => !value)}><WrapText size={13}/></button><button aria-label="Copy code" onClick={() => void navigator.clipboard.writeText(code)}><Copy size={13}/></button><a aria-label="Download code" href={download} download={`jarvis.${language ?? "txt"}`}><Download size={13}/></a><button aria-label="Open code in editor" onClick={() => setEditorNotice(true)}><ExternalLink size={13}/></button><button onClick={() => setCollapsed(value => !value)}>{collapsed ? "Expand" : "Collapse"}</button></div></header>
    {!collapsed && <SyntaxHighlighter language={language ?? "text"} style={oneDark} wrapLongLines={wrapped} customStyle={{ margin: 0, padding: "12px", maxHeight: "420px" }}>{code}</SyntaxHighlighter>}
    {editorNotice && <p className="code-notice" role="status">The Monaco Editor is not connected in this deployment.</p>}
  </section>;
}
