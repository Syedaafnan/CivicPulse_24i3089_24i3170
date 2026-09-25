/**
 * Typed API client. Request/response types come from src/api/schema.d.ts,
 * which is generated from the backend's OpenAPI schema (`npm run gen:api`);
 * CI runs `npm run check:api` so the two cannot drift silently.
 */
import { getConfig } from "../config";
import type {
  Complaint,
  ComplaintCreate,
  ComplaintPage,
  Enums,
  FieldError,
  ListQuery,
  Providers,
  Stats,
  Status,
} from "./types";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly fieldErrors: FieldError[] = [],
    public readonly retryAfter: number | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<{ data: T; headers: Headers }> {
  const url = `${getConfig().apiBase}${path}`;
  let resp: Response;
  try {
    resp = await fetch(url, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, "Cannot reach the CivicPulse server. Check your connection and try again.");
  }
  const body: unknown = await resp.json().catch(() => null);
  if (!resp.ok) {
    const b = (body ?? {}) as { detail?: unknown; errors?: FieldError[] };
    // Surface the server's own message verbatim (e.g. the 409 transition message).
    const detail = typeof b.detail === "string" ? b.detail : `Request failed (${resp.status})`;
    const retry = resp.headers.get("Retry-After");
    throw new ApiError(resp.status, detail, b.errors ?? [], retry ? Number(retry) : null);
  }
  return { data: body as T, headers: resp.headers };
}

function qs(params: Record<string, string | number | null | undefined>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
  const s = q.toString();
  return s ? `?${s}` : "";
}

export const api = {
  async createComplaint(body: ComplaintCreate): Promise<Complaint> {
    return (await request<Complaint>("/complaints", { method: "POST", body: JSON.stringify(body) })).data;
  },
  async listComplaints(query: ListQuery): Promise<ComplaintPage> {
    return (await request<ComplaintPage>(`/complaints${qs(query)}`)).data;
  },
  async getComplaint(id: string): Promise<Complaint> {
    return (await request<Complaint>(`/complaints/${encodeURIComponent(id)}`)).data;
  },
  async changeStatus(id: string, status: Status): Promise<Complaint> {
    return (
      await request<Complaint>(`/complaints/${encodeURIComponent(id)}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      })
    ).data;
  },
  async getStats(): Promise<{ stats: Stats; cache: "HIT" | "MISS" | "unknown" }> {
    const { data, headers } = await request<Stats>("/stats");
    const x = headers.get("X-Cache");
    return { stats: data, cache: x === "HIT" || x === "MISS" ? x : "unknown" };
  },
  async getProviders(): Promise<Providers> {
    return (await request<Providers>("/meta/providers")).data;
  },
  async getEnums(): Promise<Enums> {
    return (await request<Enums>("/meta/enums")).data;
  },
};
