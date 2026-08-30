export type RealtimeEvent = { type: string; payload: unknown };
export class RealtimeClient {
  connect(url: string, onEvent: (event: RealtimeEvent) => void) {
    if (url.startsWith("ws:" ) || url.startsWith("wss:")) {
      const socket = new WebSocket(url); socket.onmessage = message => { try { onEvent(JSON.parse(message.data) as RealtimeEvent); } catch { /* Ignore malformed transport messages. */ } };
      return () => socket.close();
    }
    const source = new EventSource(url); source.onmessage = message => { try { onEvent(JSON.parse(message.data) as RealtimeEvent); } catch { /* Ignore malformed transport messages. */ } };
    return () => source.close();
  }
}
export const realtimeClient = new RealtimeClient();
