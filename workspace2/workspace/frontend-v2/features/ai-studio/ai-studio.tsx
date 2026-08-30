"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useRef, useState } from "react";
import {
  Download,
  FileText,
  Globe,
  Image as ImageIcon,
  LoaderCircle,
  ScanText,
  Search,
  Sparkles,
  Upload,
  Wand2,
} from "lucide-react";
import { apiUrl } from "../../services/backend";

/**
 * AI Studio — the UI for the generative capabilities that already worked.
 *
 * Image generation, image search, OCR, and page reading were all implemented and
 * reachable only with `curl`: nothing in the app called /v1/media/generate,
 * /v1/media/search, /v1/media, /v1/vision/ocr, or /v1/web/read. So the honest
 * answer to "can it generate images?" was yes, and the answer visible to the
 * user was no. This module is that missing surface.
 *
 * Everything here reports what actually happened — the engine that served a
 * generation, the sources a search tried, the real character count of a page —
 * rather than a generic success state, because these calls reach the network and
 * degrade in ways worth seeing.
 */

type MediaItem = {
  media_id: string;
  kind: string;
  media_type: string;
  url: string;
  bytes: number;
  caption?: string;
  source?: string;
  source_url?: string;
  width?: number | null;
  height?: number | null;
  created_at?: number;
};

type GenerateResponse = { item: MediaItem; engine: string; note: string };
type SearchResponse = { subject: string; images: MediaItem[]; found: number; sources_tried: string[]; article: unknown };
type PageResponse = { url: string; title: string; text: string; images: string[]; chars: number; truncated: boolean; ok: boolean };

const SIZES = [512, 768, 1024] as const;

/** POST/GET helper that surfaces the backend's `detail` instead of a bare status. */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: init?.body ? { "content-type": "application/json", ...init?.headers } : init?.headers,
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

const kb = (bytes: number) => `${Math.max(1, Math.round(bytes / 1024))} KB`;

/** Read a picked file as bare base64 (no data-URL prefix) for /v1/vision/ocr. */
function readAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("That file could not be read from disk."));
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1] ?? "");
    reader.readAsDataURL(file);
  });
}

// ------------------------------------------------------------------ generation

function GeneratePanel({ onSaved }: { onSaved: () => void }) {
  const [prompt, setPrompt] = useState("");
  const [size, setSize] = useState<number>(768);
  const [result, setResult] = useState<GenerateResponse | null>(null);
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const text = prompt.trim();
    if (!text) return;
    setWorking(true);
    setError("");
    try {
      const response = await request<GenerateResponse>("/v1/media/generate", {
        method: "POST",
        body: JSON.stringify({ prompt: text, size }),
      });
      setResult(response);
      onSaved();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Generation failed.");
    } finally {
      setWorking(false);
    }
  };

  return (
    <section className="studio-panel">
      <h2><Wand2 size={15} /> Generate an image</h2>
      <p>Describes an image in words and renders it. Generation runs on a free hosted model, so this needs an internet connection; the result is saved into the media library below.</p>
      <form onSubmit={submit}>
        <label>
          Prompt
          <textarea
            rows={3}
            value={prompt}
            maxLength={1000}
            placeholder="a red cube on a white table, studio lighting"
            onChange={event => setPrompt(event.target.value)}
          />
        </label>
        <label className="studio-inline">
          Size
          <select value={size} onChange={event => setSize(Number(event.target.value))}>
            {SIZES.map(option => <option key={option} value={option}>{option} x {option}</option>)}
          </select>
        </label>
        <div className="provider-actions">
          <button type="submit" disabled={working || !prompt.trim()}>
            {working ? <LoaderCircle className="spin" size={15} /> : <Sparkles size={15} />}
            {working ? "Generating…" : "Generate"}
          </button>
        </div>
      </form>
      {error && <p className="settings-error">{error}</p>}
      {result && (
        <figure className="studio-result">
          <img src={apiUrl(result.item.url)} alt={result.item.caption ?? prompt} />
          <figcaption>
            {/* The engine matters: a local placeholder render and a hosted
                diffusion model are very different results, and only the
                backend knows which one answered. */}
            <span><b>Engine</b> {result.engine}</span>
            <span><b>Size</b> {kb(result.item.bytes)}</span>
            {result.note && <span>{result.note}</span>}
            <a href={apiUrl(result.item.url)} download={`${result.item.media_id}.jpg`}><Download size={13} /> Download</a>
          </figcaption>
        </figure>
      )}
    </section>
  );
}

// --------------------------------------------------------------------- search

function SearchPanel({ onSaved }: { onSaved: () => void }) {
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(4);
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const text = query.trim();
    if (!text) return;
    setWorking(true);
    setError("");
    try {
      const response = await request<SearchResponse>("/v1/media/search", {
        method: "POST",
        body: JSON.stringify({ query: text, limit }),
      });
      setResult(response);
      onSaved();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Search failed.");
    } finally {
      setWorking(false);
    }
  };

  return (
    <section className="studio-panel">
      <h2><Search size={15} /> Find real photos</h2>
      <p>Searches Wikipedia, Wikimedia Commons, and Openverse for openly licensed images, then downloads them locally. Use this instead of generation when the subject is a real thing.</p>
      <form onSubmit={submit}>
        <label>
          Subject
          <input value={query} maxLength={300} placeholder="Saturn" onChange={event => setQuery(event.target.value)} />
        </label>
        <label className="studio-inline">
          Results
          <select value={limit} onChange={event => setLimit(Number(event.target.value))}>
            {[2, 4, 6, 8].map(option => <option key={option} value={option}>{option}</option>)}
          </select>
        </label>
        <div className="provider-actions">
          <button type="submit" disabled={working || !query.trim()}>
            {working ? <LoaderCircle className="spin" size={15} /> : <Search size={15} />}
            {working ? "Searching…" : "Search"}
          </button>
        </div>
      </form>
      {error && <p className="settings-error">{error}</p>}
      {result && (
        <>
          <p className="studio-meta">
            Subject <b>{result.subject}</b> · {result.found} candidate{result.found === 1 ? "" : "s"} found ·
            downloaded {result.images.length} · sources tried: {result.sources_tried.join(", ") || "none"}
          </p>
          {/* An empty result is a real outcome for an obscure subject, and
              silently rendering nothing reads as a broken panel. */}
          {result.images.length === 0 && <p className="settings-error">No openly licensed image was found for that subject. Try a broader term, or generate one instead.</p>}
          <MediaGrid items={result.images} />
        </>
      )}
    </section>
  );
}

// ------------------------------------------------------------------------ OCR

function OcrPanel({ available }: { available: boolean | null }) {
  const [text, setText] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [preview, setPreview] = useState("");
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const pick = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setWorking(true);
    setError("");
    setText(null);
    setName(file.name);
    try {
      const base64 = await readAsBase64(file);
      setPreview(`data:${file.type};base64,${base64}`);
      const response = await request<{ text: string }>("/v1/vision/ocr", {
        method: "POST",
        body: JSON.stringify({ image_base64: base64 }),
      });
      setText(response.text);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Text extraction failed.");
    } finally {
      setWorking(false);
      // Allow re-picking the same file, which otherwise fires no change event.
      if (input.current) input.current.value = "";
    }
  };

  return (
    <section className="studio-panel">
      <h2><ScanText size={15} /> Read text from an image</h2>
      <p>Extracts text from a screenshot, scan, or photo. Runs entirely on this computer — the image is never uploaded anywhere.</p>
      {available === false && (
        <p className="studio-hint">
          OCR needs the Tesseract engine, which is not installed. Install it from{" "}
          <code>github.com/UB-Mannheim/tesseract</code> on Windows (or <code>brew install tesseract</code> on macOS),
          then restart JARVIS. Everything else in this module works without it.
        </p>
      )}
      <div className="provider-actions">
        <button type="button" onClick={() => input.current?.click()} disabled={working || available === false}>
          {working ? <LoaderCircle className="spin" size={15} /> : <Upload size={15} />}
          {working ? "Reading…" : "Choose an image"}
        </button>
        {name && <span className="studio-meta">{name}</span>}
      </div>
      <input ref={input} type="file" accept="image/*" hidden onChange={pick} />
      {error && <p className="settings-error">{error}</p>}
      {text !== null && (
        <div className="studio-ocr">
          {preview && <img src={preview} alt={name} />}
          {/* Tesseract legitimately returns "" for an image with no legible
              text; saying so beats an empty box that looks like a failure. */}
          <pre>{text.trim() || "No readable text was found in that image."}</pre>
        </div>
      )}
    </section>
  );
}

// ----------------------------------------------------------------- web reading

function ReaderPanel() {
  const [url, setUrl] = useState("");
  const [page, setPage] = useState<PageResponse | null>(null);
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const target = url.trim();
    if (!target) return;
    setWorking(true);
    setError("");
    try {
      const response = await request<PageResponse>("/v1/web/read", {
        method: "POST",
        // The endpoint needs a scheme; typing "example.com" is the common case.
        body: JSON.stringify({ url: /^https?:\/\//i.test(target) ? target : `https://${target}` }),
      });
      setPage(response);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "That page could not be read.");
    } finally {
      setWorking(false);
    }
  };

  return (
    <section className="studio-panel">
      <h2><Globe size={15} /> Read a web page</h2>
      <p>Fetches a URL and strips it down to readable text, so a page can be summarised or quoted without opening a browser.</p>
      <form onSubmit={submit}>
        <label>
          URL
          <input value={url} maxLength={2000} placeholder="https://example.com" onChange={event => setUrl(event.target.value)} />
        </label>
        <div className="provider-actions">
          <button type="submit" disabled={working || !url.trim()}>
            {working ? <LoaderCircle className="spin" size={15} /> : <FileText size={15} />}
            {working ? "Fetching…" : "Read page"}
          </button>
        </div>
      </form>
      {error && <p className="settings-error">{error}</p>}
      {page && (
        <div className="studio-page">
          <h3>{page.title}</h3>
          <p className="studio-meta">
            <a href={page.url} target="_blank" rel="noreferrer noopener">{page.url}</a> · {page.chars.toLocaleString()} characters
            {page.truncated && " · showing the first portion only"}
          </p>
          <pre>{page.text}</pre>
        </div>
      )}
    </section>
  );
}

// --------------------------------------------------------------- media library

function MediaGrid({ items }: { items: MediaItem[] }) {
  if (items.length === 0) return null;
  return (
    <ul className="studio-grid">
      {items.map(item => (
        <li key={item.media_id}>
          <a href={apiUrl(item.url)} target="_blank" rel="noreferrer noopener">
            <img src={apiUrl(item.url)} alt={item.caption ?? "generated image"} loading="lazy" />
          </a>
          <strong title={item.caption}>{item.caption ?? "untitled"}</strong>
          <small>{item.source ?? "local"} · {kb(item.bytes)}</small>
        </li>
      ))}
    </ul>
  );
}

function LibraryPanel({ items, error, onRefresh }: { items: MediaItem[]; error: string; onRefresh: () => void }) {
  return (
    <section className="studio-panel">
      <h2><ImageIcon size={15} /> Media library</h2>
      <p>Everything JARVIS has generated or downloaded, newest first. Files live on this computer under the JARVIS data directory.</p>
      <div className="provider-actions">
        <button type="button" onClick={onRefresh}><LoaderCircle size={15} /> Refresh</button>
        <span className="studio-meta">{items.length} item{items.length === 1 ? "" : "s"}</span>
      </div>
      {error && <p className="settings-error">{error}</p>}
      {!error && items.length === 0 && <p className="studio-meta">Nothing yet — generate or search for an image above.</p>}
      <MediaGrid items={items} />
    </section>
  );
}

// ----------------------------------------------------------------------- shell

export function AIStudio() {
  const [items, setItems] = useState<MediaItem[]>([]);
  const [libraryError, setLibraryError] = useState("");
  const [ocr, setOcr] = useState<boolean | null>(null);

  const loadLibrary = useCallback(async () => {
    try {
      const response = await request<{ items: MediaItem[] }>("/v1/media?limit=40");
      setItems(response.items);
      setLibraryError("");
    } catch {
      setLibraryError("The media library could not be listed. Start JARVIS and refresh.");
    }
  }, []);

  useEffect(() => {
    void loadLibrary();
    // Probed once so the OCR panel can explain a missing Tesseract before the
    // user picks a file rather than after.
    void request<{ features: { ocr?: boolean } }>("/v1/status")
      .then(status => setOcr(Boolean(status.features?.ocr)))
      .catch(() => setOcr(null));
  }, [loadLibrary]);

  return (
    <section className="studio-center">
      <header>
        <span>Generative</span>
        <h1>AI Studio</h1>
        <p>
          Image generation, openly licensed image search, on-device text extraction, and web page reading.
          These run as real calls against the local JARVIS backend, not previews.
        </p>
      </header>
      <div className="studio-columns">
        <GeneratePanel onSaved={loadLibrary} />
        <SearchPanel onSaved={loadLibrary} />
        <OcrPanel available={ocr} />
        <ReaderPanel />
      </div>
      <LibraryPanel items={items} error={libraryError} onRefresh={loadLibrary} />
    </section>
  );
}
