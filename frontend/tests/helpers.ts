import { vi } from "vitest";

type Handler = (url: string, init?: RequestInit) => { status?: number; body: unknown; headers?: Record<string, string> };

/** Replace global fetch with a tiny router. No network in component tests. */
export function mockFetch(handler: Handler) {
  const spy = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const { status = 200, body, headers = {} } = handler(String(input), init);
    return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", ...headers } });
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

export const ENUMS = {
  categories: ["water", "electricity", "sanitation", "roads", "streetlights", "other"],
  priorities: ["high", "normal", "low"],
  statuses: ["open", "in_progress", "resolved", "rejected"],
};

export function complaint(overrides: Record<string, unknown> = {}) {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    text: "Burst water main flooding Street 12 since fajr",
    location: "G-11/3",
    reporter_contact: null,
    category: "water",
    priority: "high",
    status: "open",
    ai_summary: "Burst main flooding Street 12",
    triaged_by: "llm:groq",
    triage_latency_ms: 812,
    created_at: "2026-09-25T09:00:00Z",
    updated_at: "2026-09-25T09:00:00Z",
    allowed_transitions: ["in_progress", "rejected"],
    ...overrides,
  };
}
