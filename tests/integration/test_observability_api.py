import asyncio

from httpx import ASGITransport, AsyncClient
from prometheus_client.parser import text_string_to_metric_families

from medihub.application.operations import SyntheticOperationsDashboard
from medihub.dashboard import create_dashboard_app


def test_metrics_are_aggregate_and_use_bounded_route_templates() -> None:
    runtime = SyntheticOperationsDashboard(
        refresh_interval_seconds=60,
        duplicate_every=1,
    )
    app = create_dashboard_app(runtime)

    async def exercise_metrics() -> None:
        async with app.router.lifespan_context(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                snapshot = (await client.get("/api/dashboard")).json()
                event_id = snapshot["recent_events"][0]["event_id"]
                detail = await client.get(f"/api/management/deliveries/{event_id}")
                assert detail.status_code == 200

                query_marker = "not-for-metrics-fixture"
                unmatched = await client.get(
                    f"/unregistered/{query_marker}",
                    params={"patient": query_marker},
                )
                assert unmatched.status_code == 404

                response = await client.get("/metrics")
                body = response.text
                families = list(text_string_to_metric_families(body))

                assert response.status_code == 200
                assert any(family.name == "medihub_runtime_ready" for family in families)
                assert "text/plain" in response.headers["content-type"]
                assert response.headers["cache-control"] == "no-store"
                assert "medihub_synthetic_events_received_total 2.0" in body
                assert "medihub_synthetic_duplicate_events_total 1.0" in body
                assert 'medihub_synthetic_outbox_deliveries{status="acknowledged"} 1.0' in body
                assert 'medihub_synthetic_source_health{status="healthy"} 1.0' in body
                assert (
                    'medihub_http_requests_total{method="GET",route="/api/dashboard",'
                    'status_class="2xx"} 1.0'
                ) in body
                assert 'route="/api/management/deliveries/{event_id}"' in body
                assert 'route="unmatched"' in body
                assert "/metrics" not in body
                assert event_id not in body
                assert "sim-device-001" not in body
                assert query_marker not in body
                assert "patient" not in body.lower()

    asyncio.run(exercise_metrics())
