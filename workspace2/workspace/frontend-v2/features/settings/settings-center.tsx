"use client";

import { FormEvent, useEffect, useState } from "react";
import { CheckCircle2, Cpu, KeyRound, LoaderCircle, RefreshCw, Save, SlidersHorizontal, Wifi } from "lucide-react";
import { useUIStore, type Theme } from "../../store/ui-store";
import { apiUrl } from "../../services/backend";

type Connector = { id: string; connected: boolean; values: Record<string, string>; fields: { key: string; label: string; placeholder: string; secret: boolean; required: boolean; kind: string }[] };
type ModelStatus = { default: string; local_kind: string; generative_local: boolean; local_available: boolean; cloud_configured: boolean; cloud_allowed: boolean; privacy: string };
type Tool = { id: string; name: string; description: string; category: string; enabled: boolean };
const themes: Theme[] = ["dark", "light", "system"];
const request = async <T,>(path: string, init?: RequestInit) => { const response = await fetch(apiUrl(path), { ...init, headers: { "content-type": "application/json", ...init?.headers } }); if (!response.ok) throw new Error((await response.json().catch(() => ({})) as { detail?: string }).detail ?? `Request failed (${response.status})`); return response.json() as Promise<T>; };

function ProviderForm({ connector, title, description, onChanged }: { connector?: Connector; title: string; description: string; onChanged: () => void }) {
  const [values, setValues] = useState<Record<string, string>>({}); const [message, setMessage] = useState(""); const [working, setWorking] = useState(false);
  useEffect(() => setValues(connector?.values ?? {}), [connector]);
  if (!connector) return <section className="provider-card"><h2>{title}</h2><p>Loading provider configuration…</p></section>;
  const save = async (event: FormEvent) => { event.preventDefault(); setWorking(true); setMessage(""); try { await request(`/v1/connectors/${connector.id}`, { method: "POST", body: JSON.stringify({ values }) }); setMessage("Saved securely on this device."); onChanged(); } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to save provider."); } finally { setWorking(false); } };
  const test = async () => { setWorking(true); setMessage(""); try { const result = await request<{ ok: boolean; message: string }>(`/v1/connectors/${connector.id}/test`, { method: "POST", body: JSON.stringify({ values }) }); setMessage(result.message); onChanged(); } catch (error) { setMessage(error instanceof Error ? error.message : "Connection test failed."); } finally { setWorking(false); } };
  return <section className="provider-card"><header><div><span><KeyRound size={13}/> AI provider</span><h2>{title}</h2><p>{description}</p></div><b className={connector.connected ? "connected" : "disconnected"}>{connector.connected ? "Connected" : "Not connected"}</b></header><form onSubmit={save}>{connector.fields.map(field => <label key={field.key}>{field.label}<input type={field.secret ? "password" : field.kind === "url" ? "url" : "text"} required={field.required} placeholder={field.placeholder} value={values[field.key] ?? ""} onChange={event => setValues(current => ({ ...current, [field.key]: event.target.value }))}/>{field.secret && <small>Saved encrypted; the full value is never displayed again.</small>}</label>)}<div className="provider-actions"><button type="submit" disabled={working}>{working ? <LoaderCircle className="spin" size={15}/> : <Save size={15}/>} Save</button><button type="button" onClick={test} disabled={working}><Wifi size={15}/> Test connection</button></div>{message && <p className="provider-message"><CheckCircle2 size={14}/>{message}</p>}</form></section>;
}

/**
 * What the runtime can actually do, read from /v1/status.
 *
 * Chat used to reply with a canned "tell me your requirements" template and
 * nothing in the UI explained why: no generative model is installed, so free-form
 * writing is unavailable while the deterministic capabilities all work. Guessing
 * at that from the chat transcript is impossible, hence this panel.
 */
function RuntimePanel() {
  const [status, setStatus] = useState<ModelStatus | null>(null);
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState("");

  const load = async () => {
    try {
      const result = await request<{ model: ModelStatus }>("/v1/status");
      setStatus(result.model);
      setError("");
    } catch {
      setError("The backend is unavailable, so the runtime cannot be inspected. Start JARVIS and refresh.");
    }
  };
  useEffect(() => { void load(); }, []);

  const reload = async () => {
    setWorking(true);
    setMessage("");
    try {
      await request("/v1/brain/reload-model", { method: "POST" });
      setMessage("Model reloaded. Provider changes are now live.");
      await load();
    } catch (failure) {
      setMessage(failure instanceof Error ? failure.message : "Reload failed.");
    } finally {
      setWorking(false);
    }
  };

  if (error) return <section><h2>Model &amp; runtime</h2><p className="settings-error">{error}</p></section>;
  if (!status) return <section><h2>Model &amp; runtime</h2><p>Reading runtime status…</p></section>;

  const generative = status.generative_local || (status.cloud_configured && status.cloud_allowed);
  const rows: { label: string; value: string; ok: boolean }[] = [
    { label: "Local reasoning engine", value: status.local_available ? status.local_kind : "unavailable", ok: status.local_available },
    { label: "Local generative model", value: status.generative_local ? "installed" : "not installed", ok: status.generative_local },
    { label: "Cloud provider", value: status.cloud_configured ? "configured" : "not configured", ok: status.cloud_configured },
    { label: "Cloud requests", value: status.cloud_allowed ? "allowed" : "blocked", ok: status.cloud_allowed },
  ];

  return (
    <section>
      <h2><Cpu size={15} /> Model &amp; runtime</h2>
      <div className={`runtime-banner ${generative ? "ok" : "warn"}`}>
        <strong>{generative ? "Free-form generation is available." : "No language model is connected."}</strong>
        <span>
          {generative
            ? "Chat can write and explain freely, on top of the deterministic capabilities below."
            : "Running code, maths, image generation, OCR, web reading, and memory all work without one. Only free-form writing and explanation need a model, which is why open-ended coding requests answer with a template instead of code."}
        </span>
      </div>
      <dl className="runtime-grid">
        {rows.map(row => (
          <div key={row.label} className={row.ok ? "ok" : "off"}>
            <dt>{row.label}</dt>
            <dd>{row.value}</dd>
          </div>
        ))}
      </dl>
      {!generative && (
        <p className="runtime-hint">
          To enable it, either install <code>Ollama</code> and pull a model (<code>ollama pull llama3.1:8b</code>), or fill in a
          provider below and start the backend with <code>JARVIS_ALLOW_CLOUD=true</code>. Then reload the model.
        </p>
      )}
      <p>{status.privacy}</p>
      <div className="provider-actions">
        <button type="button" onClick={reload} disabled={working}>
          {working ? <LoaderCircle className="spin" size={15} /> : <RefreshCw size={15} />} Reload model
        </button>
      </div>
      {message && <p className="provider-message"><CheckCircle2 size={14} />{message}</p>}
    </section>
  );
}

/**
 * Per-capability switches backed by /v1/tools and /v1/tools/toggle.
 *
 * These now gate real execution. The toggle used to be read back only by the
 * listing endpoint, so switching Code Runner off changed nothing.
 */
function ToolsPanel() {
  const [tools, setTools] = useState<Tool[]>([]);
  const [error, setError] = useState("");
  const [pending, setPending] = useState<string | null>(null);

  const load = async () => {
    try {
      const result = await request<{ tools: Tool[] }>("/v1/tools");
      // Several capabilities register more than one legacy id (image_search and
      // image_generation are one pipeline), which would render duplicate rows.
      const seen = new Set<string>();
      setTools(result.tools.filter(tool => !seen.has(tool.name) && seen.add(tool.name)));
      setError("");
    } catch {
      setError("Capabilities could not be listed. Start JARVIS and refresh.");
    }
  };
  useEffect(() => { void load(); }, []);

  const toggle = async (tool: Tool) => {
    setPending(tool.id);
    const next = !tool.enabled;
    setTools(current => current.map(item => (item.id === tool.id ? { ...item, enabled: next } : item)));
    try {
      await request("/v1/tools/toggle", { method: "POST", body: JSON.stringify({ tool_id: tool.id, enabled: next }) });
    } catch {
      // Revert rather than leave the switch showing a state the backend rejected.
      setTools(current => current.map(item => (item.id === tool.id ? { ...item, enabled: tool.enabled } : item)));
      setError(`Could not change ${tool.name}.`);
    } finally {
      setPending(null);
    }
  };

  const categories = Array.from(new Set(tools.map(tool => tool.category))).sort();

  return (
    <section>
      <h2><SlidersHorizontal size={15} /> Capabilities &amp; tools</h2>
      <p>Switching a capability off stops JARVIS from using it. Disabled tools are declined explicitly rather than failing silently.</p>
      {error && <p className="settings-error">{error}</p>}
      {categories.map(category => (
        <div key={category} className="tool-group">
          <h3>{category}</h3>
          {tools.filter(tool => tool.category === category).map(tool => (
            <label key={tool.id} className="tool-row">
              <input type="checkbox" checked={tool.enabled} disabled={pending === tool.id} onChange={() => void toggle(tool)} />
              <span>
                <strong>{tool.name}</strong>
                <small>{tool.description}</small>
              </span>
            </label>
          ))}
        </div>
      ))}
    </section>
  );
}

export function SettingsCenter() {
  const { theme, setTheme, leftOpen, rightOpen } = useUIStore(); const [connectors, setConnectors] = useState<Connector[]>([]); const [loadError, setLoadError] = useState("");
  const load = async () => { try { const result = await request<{ connectors: Connector[] }>("/v1/connectors"); setConnectors(result.connectors); setLoadError(""); } catch { setLoadError("The backend is unavailable. Start JARVIS before configuring providers."); } };
  // Theme application lives in ThemeManager (mounted app-wide); this only loads data.
  useEffect(() => { void load(); }, []);
  const byId = (id: string) => connectors.find(item => item.id === id);
  return <section className="settings-center"><header><span>Preferences</span><h1>Settings</h1><p>Configure local preferences and AI providers. Credentials are encrypted on this computer and are never returned to the browser.</p></header><section><h2>Appearance</h2><label>Theme<select value={theme} onChange={event => setTheme(event.target.value as Theme)}>{themes.map(item => <option key={item}>{item}</option>)}</select></label></section><RuntimePanel/><ToolsPanel/><section><h2>AI providers</h2>{loadError && <p className="settings-error">{loadError}</p>}<ProviderForm connector={byId("openrouter")} title="OpenRouter" description="Use any OpenRouter model in chat by selecting “OpenRouter / cloud” next to Send." onChanged={load}/><ProviderForm connector={byId("cloud_llm")} title="Custom OpenAI-compatible provider" description="For OpenAI, LM Studio, vLLM, or any compatible /v1 endpoint." onChanged={load}/></section><section><h2>Layout</h2><p>Navigation panel: {leftOpen ? "open" : "closed"}. Activity panel: {rightOpen ? "open" : "closed"}. The top-bar panel buttons toggle them.</p></section></section>;
}
