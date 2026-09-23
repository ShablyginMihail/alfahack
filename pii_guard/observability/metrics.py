from __future__ import annotations

import os
import re
from collections.abc import Iterable

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    multiprocess,
)

_KNOWN_ENDPOINTS = frozenset(
    {
        "/process",
        "/api/v1/mask",
        "/api/v1/unmask",
        "/v1/chat/completions",
        "/health",
        "/ready",
        "/metrics",
    }
)

_TOKEN_RE = re.compile(r"\w+|[^\w\s]")


def endpoint_label(path: str) -> str:
    if path in _KNOWN_ENDPOINTS:
        return path
    if path.startswith("/admin/"):
        return "/admin/..."
    return "other"


def count_tokens(text: str) -> int:
    return len(_TOKEN_RE.findall(text))


class Metrics:
    def __init__(self, registry: CollectorRegistry) -> None:
        self.requests_total = Counter(
            "pii_requests_total",
            "Total HTTP requests by endpoint and status",
            ("endpoint", "status"),
            registry=registry,
        )
        self.request_duration = Histogram(
            "pii_request_duration_seconds",
            "HTTP request duration in seconds by endpoint",
            ("endpoint",),
            buckets=(0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0),
            registry=registry,
        )
        self.stage_duration = Histogram(
            "pii_stage_duration_seconds",
            "Processing stage duration in seconds",
            ("stage",),
            buckets=(0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0),
            registry=registry,
        )
        self.tokens_total = Counter(
            "pii_tokens_total",
            "Approximate number of tokens processed by endpoint",
            ("endpoint",),
            registry=registry,
        )
        self.entities_total = Counter(
            "pii_entities_total",
            "Number of detected PII entities by type and system",
            ("pii_type", "system"),
            registry=registry,
        )
        self.recognizer_failures_total = Counter(
            "pii_recognizer_failures_total",
            "Number of recognizer failures by recognizer",
            ("recognizer",),
            registry=registry,
        )
        self.store_degraded = Gauge(
            "pii_store_degraded",
            "1 if the store is in degraded (redis-degraded) mode",
            registry=registry,
        )


def _build_registry() -> CollectorRegistry:
    multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if multiproc_dir:
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)  # type: ignore[no-untyped-call]
        return registry
    return CollectorRegistry()


_registry = _build_registry()
metrics = Metrics(_registry)


def metrics_response() -> bytes:
    return generate_latest(_registry)


def observe_request(endpoint: str, status: int, duration_seconds: float) -> None:
    metrics.requests_total.labels(endpoint=endpoint, status=str(status)).inc()
    metrics.request_duration.labels(endpoint=endpoint).observe(duration_seconds)


def observe_stage(stage: str, duration_seconds: float) -> None:
    metrics.stage_duration.labels(stage=stage).observe(duration_seconds)


def observe_tokens(endpoint: str, text: str) -> None:
    metrics.tokens_total.labels(endpoint=endpoint).inc(count_tokens(text))


def observe_entities(system: str, counts: Iterable[tuple[str, int]]) -> None:
    for pii_type, count in counts:
        metrics.entities_total.labels(pii_type=pii_type, system=system).inc(count)


def observe_recognizer_failure(recognizer: str) -> None:
    metrics.recognizer_failures_total.labels(recognizer=recognizer).inc()


def set_store_degraded(degraded: bool) -> None:
    metrics.store_degraded.set(1 if degraded else 0)
