/**
 * Resolves where the JARVIS FastAPI backend lives.
 *
 * Two deployments have to work without any per-machine configuration:
 *   1. Production — FastAPI serves the exported UI from its own origin, so the
 *      API is already reachable at a relative path and the base must stay "".
 *   2. Development — `next dev` serves the UI on 3000/3001 while FastAPI runs
 *      on 8000, so relative calls would hit Next and 404. That is exactly why
 *      every panel used to render "Unavailable".
 *
 * NEXT_PUBLIC_JARVIS_API_URL overrides both (e.g. the backend on another host).
 */
const CONFIGURED = process.env.NEXT_PUBLIC_JARVIS_API_URL?.replace(/\/+$/, "");

/** Port uvicorn binds by default; also the signal that we are same-origin. */
export const BACKEND_PORT = process.env.NEXT_PUBLIC_JARVIS_API_PORT ?? "8000";

export function backendBase(): string {
  if (CONFIGURED) return CONFIGURED;
  // Server-side render / build: talk to the loopback backend.
  if (typeof window === "undefined") return `http://127.0.0.1:${BACKEND_PORT}`;
  const { protocol, hostname, port } = window.location;
  // Already served by FastAPI (or behind a reverse proxy on 80/443) — relative wins.
  if (port === BACKEND_PORT || port === "") return "";
  return `${protocol}//${hostname}:${BACKEND_PORT}`;
}

/** Absolute (or correctly relative) URL for an API path such as "/v1/status". */
export function apiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  return `${backendBase()}${path.startsWith("/") ? path : `/${path}`}`;
}

/** Same as apiUrl but for EventSource/WebSocket transports. */
export function streamUrl(path: string): string {
  const url = apiUrl(path);
  if (path.startsWith("ws:") || path.startsWith("wss:")) return path;
  return url;
}
