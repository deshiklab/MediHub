# Synthetic Observability & Metrics

The synthetic operations dashboard exposes a small Prometheus-compatible metrics endpoint at `GET /metrics`, alongside its existing `GET /healthz` readiness response. The endpoint is intended for local development and synthetic operations exercises; it does not connect to a monitoring service or change device/destination connectivity.

## Local scrape example

Start the dashboard in one terminal:

```bash
python -m medihub dashboard --host 127.0.0.1 --port 8000
```

A Prometheus server running on the same host can use a scrape job like:

```yaml
scrape_configs:
  - job_name: medihub-synthetic
    scrape_interval: 15s
    metrics_path: /metrics
    static_configs:
      - targets: ["127.0.0.1:8000"]
```

Adjust the target for the actual network namespace if Prometheus runs in a container. Do not expose this unauthenticated demo endpoint on an untrusted network.

## Exported metrics

The current CLI starts one Uvicorn process; its metrics registry and synthetic state are per-process, with no multi-worker aggregation. The custom registry exposes only MediHub-defined metrics (it does not register Python process, garbage-collection, or platform collectors):

| Metric | Type | Meaning |
|---|---|---|
| `medihub_http_requests_total` | Counter | HTTP request count, excluding `/metrics`, labeled only by normalized method, matched route template, and status class. |
| `medihub_http_request_duration_seconds` | Histogram | HTTP duration in seconds, excluding `/metrics`, labeled by normalized method and matched route template. |
| `medihub_synthetic_events_received_total` | Counter | Synthetic envelopes received by this runtime since startup, including duplicate redeliveries. |
| `medihub_synthetic_duplicate_events_total` | Counter | Duplicate synthetic envelopes observed since startup. |
| `medihub_synthetic_test_receiver_unique_receipts_total` | Counter | Distinct synthetic event IDs accepted by the in-process test receiver since startup. |
| `medihub_synthetic_events_retained` | Gauge | Synthetic event rows currently retained in the in-memory database. |
| `medihub_synthetic_routing_holds_retained` | Gauge | Synthetic routing holds currently retained. |
| `medihub_synthetic_audit_events_retained` | Gauge | Synthetic audit rows currently retained. |
| `medihub_synthetic_delivery_attempts_retained` | Gauge | Attempt count belonging to currently retained outbox rows. |
| `medihub_synthetic_outbox_deliveries{status}` | Gauge | Retained outbox rows by a fixed delivery-status enum value. |
| `medihub_runtime_ready` | Gauge | `1` when the synthetic runtime has initialized and has no current cycle error; otherwise `0`. |
| `medihub_runtime_uptime_seconds` | Gauge | Seconds since this in-process runtime started. |
| `medihub_synthetic_source_health{status}` | Gauge | One-hot health status for the synthetic source (`healthy`, `degraded`, `disconnected`, or `unknown`). |

`/healthz` remains the simple readiness probe and returns only the runtime mode, readiness status, and in-process receiver label. The metrics route samples only aggregate counters/statuses and never serializes the dashboard snapshot, event records, or raw payloads.

## Privacy and cardinality limits

HTTP route labels come from FastAPI's registered route templates (for example, `/api/management/deliveries/{event_id}`), not from the incoming URL. Unmatched URLs collapse to `unmatched`; query strings are never used. Methods outside the fixed standard-method allowlist collapse to `OTHER`, and response statuses collapse to a five-value class (`1xx`–`5xx`) or `other`.

No patient, encounter, event, device, destination, source-message, metric-code, or measurement-value identifiers are metric labels. Delivery labels use only the finite `DeliveryStatus` enum. The registry is app-local, so it does not expose the Python client's default process/runtime metrics.

Counters are in-memory and reset on process restart. The retained-row gauges reflect the dashboard's bounded event-history pruning and may decrease. These metrics are synthetic-demo observations, not facility SLO evidence, clinical monitoring, production capacity estimates, or a validated operations baseline. Production use would still require an approved hosting/network design, access control for the scrape endpoint, site-owned alert thresholds, durable monitoring storage, and privacy/security review.

## Public implementation reference

The implementation uses the official Prometheus Python client for metric types and text exposition. Its public label guide documents label-based grouping and recommends initializing known label sets; MediHub narrows label values further to code-owned route templates and fixed enums: [prometheus/client_python](https://github.com/prometheus/client_python) and [its labels guide](https://github.com/prometheus/client_python/blob/master/docs/content/instrumenting/labels.md).
