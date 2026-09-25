import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { Complaint, ComplaintPage, ListQuery, Status } from "../api/types";
import { Badge } from "../components/Badge";
import { useEnums } from "../components/useEnums";

const PAGE_SIZE = 10;

export function DashboardPage() {
  const enums = useEnums();
  const [filters, setFilters] = useState<{ category: string; priority: string; status: string }>({
    category: "",
    priority: "",
    status: "",
  });
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ComplaintPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ kind: "error" | "ok"; text: string } | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const query: ListQuery = { page, page_size: PAGE_SIZE };
      if (filters.category) query.category = filters.category as ListQuery["category"];
      if (filters.priority) query.priority = filters.priority as ListQuery["priority"];
      if (filters.status) query.status = filters.status as ListQuery["status"];
      setData(await api.listComplaints(query));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load complaints.");
    } finally {
      setLoading(false);
    }
  }, [filters, page]);

  useEffect(() => {
    void load();
  }, [load]);

  const setFilter = (key: keyof typeof filters) => (e: { target: { value: string } }) => {
    setFilters((f) => ({ ...f, [key]: e.target.value }));
    setPage(1);
  };

  async function move(c: Complaint, target: Status) {
    setBusyId(c.id);
    setNotice(null);
    try {
      const updated = await api.changeStatus(c.id, target);
      setData((d) => d && { ...d, items: d.items.map((x) => (x.id === updated.id ? updated : x)) });
      setNotice({ kind: "ok", text: `Complaint moved to ${updated.status.replace("_", " ")}.` });
    } catch (err) {
      // The server's 409 message is shown verbatim — it names the attempted transition.
      setNotice({ kind: "error", text: err instanceof ApiError ? err.message : "Status change failed." });
    } finally {
      setBusyId(null);
    }
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <div className="card">
      <div className="toolbar">
        <h1>Operations dashboard</h1>
        <button className="secondary" onClick={() => void load()} disabled={loading}>
          Refresh
        </button>
      </div>

      <div className="filters">
        <label>
          Category
          <select aria-label="Category filter" value={filters.category} onChange={setFilter("category")}>
            <option value="">All</option>
            {enums?.categories.map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
        </label>
        <label>
          Priority
          <select aria-label="Priority filter" value={filters.priority} onChange={setFilter("priority")}>
            <option value="">All</option>
            {enums?.priorities.map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
        </label>
        <label>
          Status
          <select aria-label="Status filter" value={filters.status} onChange={setFilter("status")}>
            <option value="">All</option>
            {enums?.statuses.map((v) => <option key={v} value={v}>{v.replace("_", " ")}</option>)}
          </select>
        </label>
      </div>

      {notice && (
        <div role={notice.kind === "error" ? "alert" : "status"} className={`banner banner-${notice.kind}`}>
          {notice.text}
          <button className="link" onClick={() => setNotice(null)} aria-label="Dismiss">
            ×
          </button>
        </div>
      )}
      {error && <div role="alert" className="banner banner-error">{error}</div>}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Complaint</th>
              <th>Category</th>
              <th>Priority</th>
              <th>Status</th>
              <th>Triaged by</th>
              <th>Change status</th>
            </tr>
          </thead>
          <tbody>
            {loading && !data ? (
              <tr><td colSpan={6} className="muted">Loading…</td></tr>
            ) : data && data.items.length === 0 ? (
              <tr><td colSpan={6} className="muted">No complaints match these filters.</td></tr>
            ) : (
              data?.items.map((c) => (
                <tr key={c.id} data-testid="complaint-row">
                  <td>
                    <div className="summary-cell">{c.ai_summary ?? c.text}</div>
                    <div className="muted small">
                      {c.location} · {new Date(c.created_at).toLocaleString()}
                    </div>
                  </td>
                  <td><Badge kind="category" value={c.category} /></td>
                  <td><Badge kind="priority" value={c.priority} /></td>
                  <td><Badge kind="status" value={c.status} /></td>
                  <td className="small">{c.triaged_by}</td>
                  <td>
                    <select
                      aria-label={`Change status of ${c.id}`}
                      value=""
                      disabled={busyId === c.id}
                      onChange={(e) => e.target.value && void move(c, e.target.value as Status)}
                    >
                      <option value="">Move to…</option>
                      {c.allowed_transitions.length > 0 && (
                        <optgroup label="Allowed next (from server)">
                          {c.allowed_transitions.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
                        </optgroup>
                      )}
                      <optgroup label="Other">
                        {enums?.statuses
                          .filter((s) => s !== c.status && !c.allowed_transitions.includes(s))
                          .map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
                      </optgroup>
                    </select>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <nav className="pager" aria-label="Pagination">
        <button className="secondary" onClick={() => setPage((p) => p - 1)} disabled={page <= 1 || loading}>
          ← Previous
        </button>
        <span>
          Page {page} of {totalPages} · {data?.total ?? 0} complaints
        </span>
        <button className="secondary" onClick={() => setPage((p) => p + 1)} disabled={page >= totalPages || loading}>
          Next →
        </button>
      </nav>
    </div>
  );
}
