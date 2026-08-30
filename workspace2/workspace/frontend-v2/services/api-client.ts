import { apiUrl } from "./backend";

export class ApiClient {
  constructor(private readonly baseUrl = "") {}
  async request<T>(path: string, init?: RequestInit): Promise<T> {
    const url = this.baseUrl ? `${this.baseUrl}${path}` : apiUrl(path);
    try {
      const response = await fetch(url, {
        ...init,
        headers: { accept: "application/json", ...init?.headers },
      });
      if (!response.ok) {
        throw new Error(`Request failed (${response.status})`);
      }
      return await (response.json() as Promise<T>);
    } catch (error) {
      console.warn(`API call to ${path} failed:`, error);
      throw error;
    }
  }
  async post<T>(path: string, body?: unknown, init?: RequestInit): Promise<T> {
    return this.request<T>(path, {
      method: "POST",
      ...init,
      headers: { "content-type": "application/json", ...init?.headers },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  }
  /** Used by the Knowledge Graph, which is the only surface that deletes. */
  async delete<T>(path: string, init?: RequestInit): Promise<T> {
    return this.request<T>(path, { method: "DELETE", ...init });
  }
}
export const apiClient = new ApiClient();
