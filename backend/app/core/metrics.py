"""Low-cardinality Prometheus metrics for HTTP request volume and latency."""

from __future__ import annotations

from time import perf_counter

from prometheus_client import CollectorRegistry, Counter, Histogram
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REGISTRY = CollectorRegistry(auto_describe=True)
HTTP_REQUESTS = Counter(
    "docwise_http_requests",
    "Completed HTTP requests, excluding the metrics scrape endpoint.",
    ("method", "route", "status"),
    registry=REGISTRY,
)
HTTP_REQUEST_DURATION = Histogram(
    "docwise_http_request_duration_seconds",
    "HTTP request duration in seconds, excluding the metrics scrape endpoint.",
    ("method", "route"),
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
    registry=REGISTRY,
)

_KNOWN_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}


class HttpMetricsMiddleware:
    """Record status and latency with route templates, never raw URL paths."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.requests = HTTP_REQUESTS
        self.duration = HTTP_REQUEST_DURATION

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = str(scope.get("path", ""))
        if scope.get("type") != "http" or path == "/metrics" or path.startswith("/metrics/"):
            await self.app(scope, receive, send)
            return

        started = perf_counter()
        status = 500

        async def capture_status(message: Message) -> None:
            nonlocal status
            if message.get("type") == "http.response.start":
                status = int(message.get("status", 500))
            await send(message)

        try:
            await self.app(scope, receive, capture_status)
        finally:
            method = str(scope.get("method", "OTHER")).upper()
            if method not in _KNOWN_METHODS:
                method = "OTHER"
            route = scope.get("route")
            route_name = getattr(route, "path", "unmatched")
            if not isinstance(route_name, str):
                route_name = "unmatched"
            self.requests.labels(method=method, route=route_name, status=str(status)).inc()
            self.duration.labels(method=method, route=route_name).observe(perf_counter() - started)
