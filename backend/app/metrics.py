"""Prometheus metrics. Exposed in text format on GET /metrics."""

from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "HTTP requests handled",
    ["method", "path", "status"],
)
HTTP_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
TRIAGE_LATENCY = Histogram(
    "triage_latency_seconds",
    "Time spent in the triage provider (including fallback)",
    ["provider"],
    buckets=(0.001, 0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 20),
)
TRIAGE_FALLBACKS = Counter(
    "triage_fallback_total",
    "Triage calls that fell back to RuleBasedTriage",
    ["provider", "error"],
)
TRIAGE_CACHE = Counter(
    "triage_cache_total",
    "Content-hash triage cache lookups",
    ["result"],
)
RATE_LIMITED = Counter("rate_limited_total", "Requests rejected by the rate limiter")
