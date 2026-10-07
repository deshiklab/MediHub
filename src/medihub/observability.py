"""Low-cardinality Prometheus metrics for the synthetic dashboard runtime."""

from collections.abc import Iterable
from dataclasses import dataclass
from threading import Lock

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily

from medihub.domain import AdapterHealthStatus, DeliveryStatus

HTTP_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"})
HTTP_STATUS_CLASSES = frozenset({"1xx", "2xx", "3xx", "4xx", "5xx", "other"})


@dataclass(frozen=True, slots=True)
class RuntimeMetricsSnapshot:
    """Privacy-minimized values exported from the ephemeral dashboard runtime."""

    ready: bool = False
    uptime_seconds: float = 0.0
    events_received: int = 0
    duplicate_events: int = 0
    events_retained: int = 0
    routing_holds_retained: int = 0
    audit_events_retained: int = 0
    delivery_attempts_retained: int = 0
    delivery_counts: tuple[tuple[DeliveryStatus, int], ...] = ()
    unique_test_receipts: int = 0
    source_health: AdapterHealthStatus | None = None


class _RuntimeCollector:
    """Expose one snapshot without adding event-, patient-, or device-level labels."""

    def __init__(self) -> None:
        self._snapshot = RuntimeMetricsSnapshot()
        self._lock = Lock()

    def set_snapshot(self, snapshot: RuntimeMetricsSnapshot) -> None:
        with self._lock:
            self._snapshot = snapshot

    def collect(self) -> Iterable[CounterMetricFamily | GaugeMetricFamily]:
        with self._lock:
            snapshot = self._snapshot

        events_received = CounterMetricFamily(
            "medihub_synthetic_events_received",
            "Synthetic event deliveries received by the local dashboard runtime since startup.",
        )
        events_received.add_metric([], max(0, snapshot.events_received))
        yield events_received

        duplicates = CounterMetricFamily(
            "medihub_synthetic_duplicate_events",
            "Synthetic duplicate event deliveries observed since startup.",
        )
        duplicates.add_metric([], max(0, snapshot.duplicate_events))
        yield duplicates

        test_receipts = CounterMetricFamily(
            "medihub_synthetic_test_receiver_unique_receipts",
            "Unique synthetic event IDs accepted by the in-process test receiver since startup.",
        )
        test_receipts.add_metric([], max(0, snapshot.unique_test_receipts))
        yield test_receipts

        retained = GaugeMetricFamily(
            "medihub_synthetic_events_retained",
            "Synthetic event records currently retained in the local in-memory store.",
        )
        retained.add_metric([], max(0, snapshot.events_retained))
        yield retained

        holds = GaugeMetricFamily(
            "medihub_synthetic_routing_holds_retained",
            "Synthetic routing holds currently retained in the local in-memory store.",
        )
        holds.add_metric([], max(0, snapshot.routing_holds_retained))
        yield holds

        audit_events = GaugeMetricFamily(
            "medihub_synthetic_audit_events_retained",
            "Synthetic audit records currently retained in the local in-memory store.",
        )
        audit_events.add_metric([], max(0, snapshot.audit_events_retained))
        yield audit_events

        attempts = GaugeMetricFamily(
            "medihub_synthetic_delivery_attempts_retained",
            "Delivery attempts associated with currently retained synthetic outbox rows.",
        )
        attempts.add_metric([], max(0, snapshot.delivery_attempts_retained))
        yield attempts

        outbox = GaugeMetricFamily(
            "medihub_synthetic_outbox_deliveries",
            "Currently retained synthetic outbox rows by fixed delivery status.",
            labels=["status"],
        )
        delivery_counts = dict(snapshot.delivery_counts)
        for status in DeliveryStatus:
            outbox.add_metric([status.value], max(0, delivery_counts.get(status, 0)))
        yield outbox

        runtime_ready = GaugeMetricFamily(
            "medihub_runtime_ready",
            "Whether the local synthetic dashboard runtime is ready.",
        )
        runtime_ready.add_metric([], int(snapshot.ready))
        yield runtime_ready

        uptime = GaugeMetricFamily(
            "medihub_runtime_uptime_seconds",
            "Time since the local dashboard runtime started.",
        )
        uptime.add_metric([], max(0.0, snapshot.uptime_seconds))
        yield uptime

        health = GaugeMetricFamily(
            "medihub_synthetic_source_health",
            "One-hot adapter health status for the synthetic event source.",
            labels=["status"],
        )
        current_health = snapshot.source_health or AdapterHealthStatus.UNKNOWN
        for status in AdapterHealthStatus:
            health.add_metric([status.value], int(status is current_health))
        yield health


class MediHubMetrics:
    """Render a dedicated Prometheus registry with bounded label values only."""

    def __init__(self) -> None:
        self._runtime_collector = _RuntimeCollector()
        self._registry = CollectorRegistry(auto_describe=True)
        self._registry.register(self._runtime_collector)
        self._route_templates: frozenset[str] = frozenset()
        self._http_requests = Counter(
            "medihub_http_requests",
            "HTTP requests handled by the synthetic dashboard, excluding metrics scrapes.",
            labelnames=("method", "route", "status_class"),
            registry=self._registry,
        )
        self._http_request_duration = Histogram(
            "medihub_http_request_duration_seconds",
            "HTTP request duration for the synthetic dashboard, excluding metrics scrapes.",
            labelnames=("method", "route"),
            registry=self._registry,
        )

    def set_runtime_snapshot(self, snapshot: RuntimeMetricsSnapshot) -> None:
        """Update the safe aggregate snapshot used by the metrics collector."""

        self._runtime_collector.set_snapshot(snapshot)

    def set_route_templates(self, route_templates: Iterable[str]) -> None:
        """Allow only code-registered route templates as HTTP metric labels."""

        self._route_templates = frozenset(
            route for route in route_templates if route.startswith("/")
        )

    def observe_http_request(
        self,
        *,
        method: str,
        route: str | None,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        """Record a request with normalized method, matched route, and status class."""

        normalized_method = method.upper()
        if normalized_method not in HTTP_METHODS:
            normalized_method = "OTHER"
        normalized_route = route if route in self._route_templates else "unmatched"
        status_class = f"{status_code // 100}xx" if 100 <= status_code <= 599 else "other"
        if status_class not in HTTP_STATUS_CLASSES:
            status_class = "other"
        self._http_requests.labels(
            method=normalized_method,
            route=normalized_route,
            status_class=status_class,
        ).inc()
        self._http_request_duration.labels(
            method=normalized_method,
            route=normalized_route,
        ).observe(max(0.0, duration_seconds))

    def render(self) -> bytes:
        """Return Prometheus text exposition from the custom, app-only registry."""

        return generate_latest(self._registry)


__all__ = ["MediHubMetrics", "RuntimeMetricsSnapshot"]
