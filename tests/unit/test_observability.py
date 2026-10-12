from medihub.observability import MediHubMetrics


def test_http_metric_labels_reject_unbounded_methods_and_unregistered_paths() -> None:
    metrics = MediHubMetrics()
    metrics.set_route_templates(("/healthz", "/api/deliveries/{event_id}"))
    metrics.observe_http_request(
        method="UNBOUNDED-METHOD-MARKER",
        route="/api/deliveries/raw-id-marker",
        status_code=429,
        duration_seconds=-1.0,
    )

    body = metrics.render().decode("utf-8")

    assert 'method="OTHER",route="unmatched",status_class="4xx"' in body
    assert "UNBOUNDED-METHOD-MARKER" not in body
    assert "raw-id-marker" not in body
    assert "-1.0" not in body
