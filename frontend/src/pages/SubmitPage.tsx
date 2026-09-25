import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../api/client";
import type { Complaint } from "../api/types";
import { Badge } from "../components/Badge";
import { LIMITS, validateComplaint, type FormErrors } from "../validation";

const EMPTY = { text: "", location: "", reporter_contact: "" };

export function SubmitPage() {
  const [form, setForm] = useState(EMPTY);
  const [errors, setErrors] = useState<FormErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [result, setResult] = useState<Complaint | null>(null);
  const [banner, setBanner] = useState<string | null>(null);

  // Honest loading state: AI triage can take seconds, so show that time is passing.
  useEffect(() => {
    if (!submitting) return;
    setElapsed(0);
    const t = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [submitting]);

  const update = (field: keyof typeof EMPTY) => (e: { target: { value: string } }) => {
    setForm((f) => ({ ...f, [field]: e.target.value }));
    setErrors((er) => ({ ...er, [field]: undefined }));
  };

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBanner(null);
    const clientErrors = validateComplaint(form);
    setErrors(clientErrors);
    if (Object.keys(clientErrors).length > 0) return;

    setSubmitting(true);
    try {
      const created = await api.createComplaint({
        text: form.text.trim(),
        location: form.location.trim(),
        reporter_contact: form.reporter_contact.trim() || null,
      });
      setResult(created);
      setForm(EMPTY);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.fieldErrors.length) {
          setErrors(Object.fromEntries(err.fieldErrors.map((f) => [f.field, f.message])) as FormErrors);
        }
        setBanner(err.status === 429 && err.retryAfter ? `${err.message}` : err.message);
      } else {
        setBanner("Unexpected error. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="grid-2">
      <form className="card" onSubmit={onSubmit} noValidate aria-busy={submitting}>
        <h1>Report a problem</h1>
        <p className="muted">Describe it in your own words — we'll work out the category and urgency.</p>

        <label htmlFor="text">What is the problem?</label>
        <textarea
          id="text"
          rows={6}
          value={form.text}
          onChange={update("text")}
          aria-invalid={!!errors.text}
          aria-describedby="text-help"
          placeholder="e.g. Burst water main flooding Street 12 since fajr, water entering ground floors"
          disabled={submitting}
        />
        <div id="text-help" className="field-help">
          {errors.text ? <span className="field-error">{errors.text}</span> : <span />}
          <span className="muted">
            {form.text.trim().length}/{LIMITS.text.max}
          </span>
        </div>

        <label htmlFor="location">Location</label>
        <input
          id="location"
          value={form.location}
          onChange={update("location")}
          aria-invalid={!!errors.location}
          placeholder="e.g. G-11/3, Street 12, Islamabad"
          disabled={submitting}
        />
        {errors.location && <span className="field-error">{errors.location}</span>}

        <label htmlFor="contact">
          Contact <span className="muted">(optional)</span>
        </label>
        <input
          id="contact"
          value={form.reporter_contact}
          onChange={update("reporter_contact")}
          aria-invalid={!!errors.reporter_contact}
          placeholder="Phone or email, if you want updates"
          disabled={submitting}
        />
        {errors.reporter_contact && <span className="field-error">{errors.reporter_contact}</span>}

        {banner && (
          <div role="alert" className="banner banner-error">
            {banner}
          </div>
        )}

        <button type="submit" disabled={submitting}>
          {submitting ? "Submitting…" : "Submit complaint"}
        </button>
        {submitting && (
          <p className="loading" role="status">
            <span className="spinner" aria-hidden /> Triaging with AI… {elapsed}s — this can take a few seconds.
          </p>
        )}
      </form>

      <section className="card" aria-live="polite">
        <h2>Triage result</h2>
        {!result ? (
          <p className="muted">Submit a complaint to see how it was classified.</p>
        ) : (
          <div data-testid="triage-result">
            <p className="summary">“{result.ai_summary ?? "No summary"}”</p>
            <dl className="kv">
              <dt>Category</dt>
              <dd>
                <Badge kind="category" value={result.category} />
              </dd>
              <dt>Priority</dt>
              <dd>
                <Badge kind="priority" value={result.priority} />
              </dd>
              <dt>Triaged by</dt>
              <dd>
                <Badge kind="provider" value={result.triaged_by} />
                {result.triaged_by === "rules:fallback" && (
                  <span className="muted"> (AI unavailable — keyword rules were used)</span>
                )}
              </dd>
              <dt>Triage time</dt>
              <dd>{result.triage_latency_ms} ms</dd>
              <dt>Reference</dt>
              <dd>
                <code>{result.id}</code>
              </dd>
            </dl>
          </div>
        )}
      </section>
    </div>
  );
}
