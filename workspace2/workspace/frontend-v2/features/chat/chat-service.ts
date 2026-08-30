import { apiUrl } from "../../services/backend";

export type ChatStreamEvent = { type: string; payload: Record<string, unknown> };

/** "auto" lets the backend pick the engine per request from the intent it classified. */
export type ChatProvider = "local" | "cloud" | "auto";

/** The engine the backend chose for one turn, and whether it ended up running. */
export type ChatRoute = {
  provider: string;
  task: string;
  model: string;
  engine: string;
  reason: string;
  requested?: string;
  used?: boolean;
  answered_by?: string;
  rerouted_from?: string;
};

/** A generated or retrieved image/video the backend cached locally. */
export type ChatMediaItem = {
  media_id: string;
  kind: string;
  media_type: string;
  url: string;
  caption?: string;
  source?: string;
  bytes?: number;
};

export type ChatSource = { title: string; url: string };

/** Optional callbacks for the frames that are not plain text deltas. */
export type ChatStreamHooks = {
  onRoute?: (route: ChatRoute) => void;
  onMedia?: (items: ChatMediaItem[]) => void;
  onSources?: (items: ChatSource[]) => void;
  onDone?: (payload: Record<string, unknown>) => void;
};

/** Base64 for an arbitrary file. Chunked because `String.fromCharCode(...bytes)`
 *  overflows the call stack somewhere around a hundred kilobytes, which is a
 *  small image -- attaching one used to throw before the request was sent. */
async function encodeFile(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let index = 0; index < bytes.length; index += 8192) {
    binary += String.fromCharCode(...bytes.subarray(index, index + 8192));
  }
  return btoa(binary);
}

export async function streamChat(
  text: string,
  files: File[],
  provider: ChatProvider,
  signal: AbortSignal,
  onToken: (token: string) => void,
  onEvent?: (event: ChatStreamEvent) => void,
  hooks?: ChatStreamHooks
) {
  const attachments = await Promise.all(
    files.map(async file => ({ name: file.name, media_type: file.type, base64: await encodeFile(file) }))
  );
  const response = await fetch(apiUrl("/v1/chat/stream"), {
    method: "POST",
    headers: { "content-type": "application/json", accept: "text/event-stream, application/json" },
    body: JSON.stringify({ text, attachments, provider }),
    signal,
  });
  if (!response.ok) {
    // Surface the backend's own message: a 422 from a validation change is a
    // very different problem from a 500 in a tool, and "request failed" hides
    // both.
    const detail = await response.text().catch(() => "");
    throw new Error(`Chat request failed (${response.status})${detail ? `: ${detail.slice(0, 300)}` : ""}`);
  }
  if ((response.headers.get("content-type") ?? "").includes("json")) {
    const body = await response.json();
    onToken(body.reply ?? body.content ?? "");
    if (body.route) hooks?.onRoute?.(body.route as ChatRoute);
    if (Array.isArray(body.media) && body.media.length) hooks?.onMedia?.(body.media as ChatMediaItem[]);
    if (Array.isArray(body.sources) && body.sources.length) hooks?.onSources?.(body.sources as ChatSource[]);
    hooks?.onDone?.(body as Record<string, unknown>);
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) return;
  const decoder = new TextDecoder();
  let pending = "";

  const consume = (frame: string) => {
    let type = "message";
    const data: string[] = [];
    for (const line of frame.split("\n")) {
      if (line.startsWith("event:")) type = line.slice(6).trim();
      if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
    }
    const raw = data.join("\n");
    if (!raw || raw === "[DONE]") return;
    let payload: Record<string, unknown>;
    try {
      payload = JSON.parse(raw) as Record<string, unknown>;
    } catch {
      payload = { text: raw };
    }
    if (type === "delta") {
      onToken(String(payload.text ?? ""));
      return;
    }
    if (type === "error") throw new Error(String(payload.message ?? "Chat stream failed"));
    if (type === "route") hooks?.onRoute?.(payload as unknown as ChatRoute);
    if (type === "media") hooks?.onMedia?.((payload.items ?? []) as ChatMediaItem[]);
    if (type === "sources") hooks?.onSources?.((payload.items ?? []) as ChatSource[]);
    if (type === "done") hooks?.onDone?.(payload);
    onEvent?.({ type, payload });
  };

  while (true) {
    const { done, value } = await reader.read();
    pending += decoder.decode(value, { stream: !done });
    const frames = pending.split("\n\n");
    pending = done ? "" : frames.pop() ?? "";
    for (const frame of frames) consume(frame);
    if (done) break;
  }
}
