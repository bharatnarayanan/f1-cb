"""Prometheus metrics (Phase 8, F8.3) — counters/histograms only, no I/O
beyond in-process registry state. Route modules import and `.inc()`/
`.observe()` these directly rather than the route computing its own
ad-hoc counting, so every metric name/label set lives in one place.

GET /metrics (src/main.py) exposes these in Prometheus text format.
"""

from prometheus_client import Counter, Histogram

http_requests_total = Counter(
    "tip_http_requests_total",
    "Total HTTP requests handled, by method/path template/status code.",
    ["method", "path", "status"],
)

http_request_duration_seconds = Histogram(
    "tip_http_request_duration_seconds",
    "HTTP request latency in seconds, by method/path template.",
    ["method", "path"],
)

recommendations_created_total = Counter(
    "tip_recommendations_created_total",
    "Recommendations persisted, by category.",
    ["category"],
)

recommendations_suppressed_total = Counter(
    "tip_recommendations_suppressed_total",
    "Recommendation candidates suppressed by a risk guardrail before persisting, by reason.",
    ["reason"],
)

alerts_dispatched_total = Counter(
    "tip_alerts_dispatched_total",
    "Alert dispatch attempts, by channel and outcome (sent/failed).",
    ["channel", "status"],
)

backtests_run_total = Counter(
    "tip_backtests_run_total",
    "Strategy Marketplace backtests run.",
    [],
)

api_errors_total = Counter(
    "tip_api_errors_total",
    "Requests that ended in a registered error handler, by error code.",
    ["code"],
)
