"use client";

import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import { CodeBlock } from "./code-block";
import { MermaidDiagram } from "./mermaid-diagram";

export function MarkdownRenderer({ content }: { content: string }) {
  return <div className="markdown-renderer"><ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]} components={{
    code: ({ className, children }) => {
      const language = /language-([\w+-]+)/.exec(className ?? "")?.[1]; const code = String(children).replace(/\n$/, "");
      return language === "mermaid" ? <MermaidDiagram definition={code} /> : language ? <CodeBlock code={code} language={language} /> : <code>{children}</code>;
    },
    a: ({ href, children }) => <a href={href} target="_blank" rel="noreferrer">{children}</a>,
  }}>{content}</ReactMarkdown></div>;
}
