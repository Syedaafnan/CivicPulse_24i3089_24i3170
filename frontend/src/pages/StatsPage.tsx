import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { Providers, Stats } from "../api/types";
import { Badge } from "../components/Badge";

function Bars({ title, data }: { title: string; data: Record<string, number> }) {
  const max = Math.max(1, ...Object.values(data));
  return (
    <section className="card">
      <h2>{title}</h2>
      <ul className="bars">
        {Object.entries(data).map(([k, v]) => (
          <li key={k}>
            <span className="bar-label">{k.replace("_", " ")}</span>
            <span className="bar-track">
              <span className="bar-fill" style={{ width: `${(v / max) * 100}%` }} />
            </span>
            <span className="bar-value" data-testid={`count-${k}`}>{v}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function StatsPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [cache, setCache] = useState<string>("unknown");
  const [providers, setProviders] = useState<Providers | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [s, p] = await Promise.all([api.getStats(), api.getProviders()]);
      setStats(s.stats);
      setCache(s.cache);
      setProviders(p);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load statistics.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div>
      <div className="toolbar card">
        <div>
          <h1>Statistics</h1>
          <p className="muted">
            {stats ? `${stats.total} complaints · generated ${new Date(stats.generated_at).toLocaleTimeString()}` : "…"}
          </p>
        </div>
        <div className="cache-indicator" title="From the X-Cache response header of GET /api/stats">
          Served from cache: <Badge kind="cache" value={cache} />
          <button className="secondary" onClick={() => void load()}>Refresh</button>
        </div>
      </div>
      {error && <div role="alert" className="banner banner-error">{error}</div>}

      {stats && (
        <div className="grid-3">
          <Bars title="By category" data={stats.by_category} />
          <Bars title="By priority" data={stats.by_priority} />
          <Bars title="By status" data={stats.by_status} />
        </div>
      )}

      {providers && (
        <section className="card">
          <h2>AI triage</h2>
          <p>
            Active provider <Badge kind="provider" value={providers.active} /> · fallback{" "}
            <Badge kind="provider" value={providers.fallback} /> · triage cache hit rate{" "}
            <strong data-testid="hit-rate">
              {providers.cache_hit_rate === null ? "n/a" : `${Math.round(providers.cache_hit_rate * 100)}%`}
            </strong>{" "}
            <span className="muted">({providers.cache_hits} hits / {providers.cache_misses} misses)</span>
            {stats?.avg_triage_latency_ms != null && <> · avg triage {stats.avg_triage_latency_ms} ms</>}
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>When</th><th>Provider</th><th>Latency</th><th>Fallback</th><th>Cached</th></tr>
              </thead>
              <tbody>
                {providers.recent.length === 0 ? (
                  <tr><td colSpan={5} className="muted">No triage calls since the cache was last cleared.</td></tr>
                ) : (
                  providers.recent.map((r) => (
                    <tr key={`${r.complaint_id}-${r.at}`}>
                      <td className="small">{new Date(r.at).toLocaleTimeString()}</td>
                      <td>{r.provider}</td>
                      <td>{r.latency_ms} ms</td>
                      <td>{r.fallback ? `yes (${r.error ?? "error"})` : "no"}</td>
                      <td>{r.cached ? "yes" : "no"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
