import { realtimeClient, type RealtimeEvent } from "../../services/realtime-client";
import { apiUrl } from "../../services/backend";
import type { ToolActivity } from "./stores/tool-store";

/**
 * Subscribes to the backend event stream (SSE, `GET /v1/events/stream`).
 *
 * This previously required NEXT_PUBLIC_JARVIS_EVENTS_URL and returned a no-op
 * when unset, so the activity panel never showed live tool progress. The URL now
 * resolves from the same backend base as every other call.
 */
export function subscribeToolEvents(onActivity: (activity: ToolActivity) => void) {
  return realtimeClient.connect(apiUrl("/v1/events/stream"), (event: RealtimeEvent) => {
    const payload = event.payload as { source?: string; status?: string; detail?: string };
    onActivity({ name: payload.source ?? event.type, status: payload.status ?? event.type, detail: payload.detail });
  });
}
