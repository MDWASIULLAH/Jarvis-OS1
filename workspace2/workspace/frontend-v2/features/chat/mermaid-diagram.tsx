"use client";

import { useEffect, useId, useState } from "react";

export function MermaidDiagram({ definition }: { definition: string }) {
  const id = `jarvis-mermaid-${useId().replace(/:/g, "")}`; const [svg, setSvg] = useState(""); const [error, setError] = useState("");
  useEffect(() => { let active = true; import("mermaid").then(({ default: mermaid }) => { mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "dark" }); return mermaid.render(id, definition); }).then(result => { if (active) setSvg(result.svg); }).catch(() => { if (active) setError("The diagram could not be rendered."); }); return () => { active = false; }; }, [definition, id]);
  if (error) return <pre className="mermaid-error">{error}</pre>;
  return <div className="mermaid-diagram" aria-label="Mermaid diagram" dangerouslySetInnerHTML={{ __html: svg }} />;
}
