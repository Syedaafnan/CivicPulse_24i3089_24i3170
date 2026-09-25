import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { StatsPage } from "../src/pages/StatsPage";
import { mockFetch } from "./helpers";

const STATS = {
  total: 34,
  by_category: { water: 9, electricity: 7, sanitation: 8, roads: 5, streetlights: 4, other: 1 },
  by_priority: { high: 12, normal: 17, low: 5 },
  by_status: { open: 18, in_progress: 9, resolved: 4, rejected: 3 },
  by_triaged_by: { rules: 34 },
  avg_triage_latency_ms: 2,
  generated_at: "2026-09-25T09:00:00Z",
};
const PROVIDERS = {
  active: "llm:groq", fallback: "rules:fallback", available: ["llm", "ollama", "rules", "simulated"],
  cache_hits: 3, cache_misses: 9, cache_hit_rate: 0.25,
  recent: [{ complaint_id: "a", provider: "rules:fallback", latency_ms: 10012, fallback: true, cached: false, error: "TriageTimeout", at: "2026-09-25T09:00:00Z" }],
};

describe("StatsPage", () => {
  it("renders aggregates and the X-Cache state, updating on refresh", async () => {
    let n = 0;
    mockFetch((url) =>
      url.endsWith("/stats")
        ? { body: STATS, headers: { "X-Cache": n++ === 0 ? "MISS" : "HIT" } }
        : { body: PROVIDERS },
    );
    render(<StatsPage />);
    expect(await screen.findByTestId("count-water")).toHaveTextContent("9");
    expect(screen.getByTestId("count-high")).toHaveTextContent("12");
    expect(screen.getByText("MISS")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /refresh/i }));
    expect(await screen.findByText("HIT")).toBeInTheDocument();
  });

  it("shows provider, hit rate and fallback history", async () => {
    mockFetch((url) => (url.endsWith("/stats") ? { body: STATS, headers: { "X-Cache": "HIT" } } : { body: PROVIDERS }));
    render(<StatsPage />);
    expect(await screen.findByTestId("hit-rate")).toHaveTextContent("25%");
    expect(screen.getByText(/yes \(TriageTimeout\)/)).toBeInTheDocument();
  });
});
