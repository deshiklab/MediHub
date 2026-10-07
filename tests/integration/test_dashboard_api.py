"""Read-only synthetic operations dashboard tests."""

import asyncio
import time

from httpx import ASGITransport, AsyncClient

from medihub.application.operations import SyntheticOperationsDashboard
from medihub.dashboard import create_dashboard_app


def test_dashboard_is_synthetic_curated_and_read_only() -> None:
    runtime = SyntheticOperationsDashboard(
        refresh_interval_seconds=60,
        duplicate_every=1,
    )
    app = create_dashboard_app(runtime)

    async def exercise_dashboard() -> None:
        async with app.router.lifespan_context(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                health = await client.get("/healthz")
                assert health.status_code == 200
                assert health.json() == {
                    "status": "ready",
                    "mode": "synthetic_demo",
                    "receiver": "in_process_test_sink",
                }

                response = await client.get("/api/dashboard")
                assert response.status_code == 200
                assert response.headers["cache-control"] == "no-store"
                snapshot = response.json()
                assert snapshot["mode"] == "synthetic_demo"
                assert snapshot["ready"] is True
                assert snapshot["source"]["status"] == "healthy"
                assert snapshot["receiver"]["status"] == "in_process"
                assert snapshot["totals"] == {
                    "events_received": 2,
                    "events_inserted": 1,
                    "duplicate_events": 1,
                    "blocked_routes": 1,
                    "audit_events": 5,
                    "delivery_attempts": 1,
                    "acknowledged_deliveries": 1,
                    "pending_deliveries": 0,
                    "retryable_failures": 0,
                    "permanent_failures": 0,
                    "rejected_deliveries": 0,
                    "unique_test_receipts": 1,
                }
                assert len(snapshot["recent_events"]) == 1
                assert set(snapshot["recent_events"][0]) == {
                    "event_id",
                    "device_id",
                    "received_at",
                    "observed_at",
                    "label",
                    "value",
                    "source_sequence",
                }
                assert snapshot["recent_events"][0]["label"] == "Synthetic scalar"
                assert len(snapshot["recent_holds"]) == 1
                assert snapshot["recent_holds"][0]["reason_code"] == "synthetic_not_accepted"
                assert snapshot["recent_holds"][0]["destination_id"] == (
                    "medihub.synthetic-ineligible-route"
                )
                assert len(snapshot["recent_activity"]) == 5
                assert {entry["action"] for entry in snapshot["recent_activity"]} == {
                    "event_stored",
                    "route_held",
                    "delivery_intent_created",
                    "delivery_attempt_started",
                    "delivery_acknowledged",
                }
                assert all(
                    set(entry) == {"action", "resource_type", "reason_code", "occurred_at"}
                    for entry in snapshot["recent_activity"]
                )
                assert all(
                    "actor_id" not in entry and "resource_id" not in entry
                    for entry in snapshot["recent_activity"]
                )
                assert "patient" not in str(snapshot).lower()
                assert "encounter_reference" not in str(snapshot)

                page = await client.get("/")
                assert page.status_code == 200
                assert "Development data only" in page.text
                assert "Register simulator" in page.text
                assert "Live activation disabled" in page.text
                assert (await client.post("/api/dashboard")).status_code == 405
                assert (await client.get("/openapi.json")).status_code == 404

    asyncio.run(exercise_dashboard())


def test_dashboard_tabs_render_distinct_page_routes() -> None:
    runtime = SyntheticOperationsDashboard(
        refresh_interval_seconds=60,
        duplicate_every=0,
    )
    app = create_dashboard_app(runtime)
    pages = {
        "/": "operations",
        "/operations": "operations",
        "/devices": "devices",
        "/mappings": "mappings",
        "/api-setup": "api-setup",
    }

    async def exercise_pages() -> None:
        async with app.router.lifespan_context(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                for path, page in pages.items():
                    response = await client.get(path)
                    assert response.status_code == 200
                    assert f'<body data-current-page="{page}">' in response.text
                    assert 'href="/#overview" data-page-link="operations"' in response.text
                    assert (
                        'href="/devices#device-workbench" data-page-link="devices"' in response.text
                    )
                    assert (
                        'href="/mappings#mapping-workbench" data-page-link="mappings"'
                        in response.text
                    )
                    assert (
                        'href="/api-setup#destination-workbench" data-page-link="api-setup"'
                        in response.text
                    )

                assert "window.location.replace(legacyPages[window.location.hash])" in response.text

                device_page = await client.get("/devices")
                for feature in (
                    "Device integration catalog",
                    "Managed devices",
                    "Set inactive",
                    "Device API configuration",
                    "Device-wise data flow",
                    "Device-wise data mapping",
                    "Data export",
                    "Export selected device",
                    "not a device-facing integration API",
                ):
                    assert feature in device_page.text
                assert "No physical device is discovered or connected" in device_page.text
                assert "createObjectURL(blob)" in device_page.text

                api_page = await client.get("/api-setup")
                assert "FHIR R4 / EMR connection API" in api_page.text
                assert "HL7 v2 / interface engine / EMS connection API" in api_page.text
                assert "Connection API controls are locked" in api_page.text

    asyncio.run(exercise_pages())


def test_dashboard_background_feed_advances_without_mutation_endpoints() -> None:
    runtime = SyntheticOperationsDashboard(
        refresh_interval_seconds=0.1,
        duplicate_every=0,
    )
    app = create_dashboard_app(runtime)

    async def exercise_dashboard() -> None:
        async with app.router.lifespan_context(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                initial = (await client.get("/api/dashboard")).json()["totals"]["events_inserted"]
                deadline = time.monotonic() + 2
                updated = initial
                while updated <= initial and time.monotonic() < deadline:
                    await asyncio.sleep(0.05)
                    updated = (await client.get("/api/dashboard")).json()["totals"][
                        "events_inserted"
                    ]
                assert updated > initial

    asyncio.run(exercise_dashboard())


def test_dashboard_prunes_ephemeral_store_and_receiver_history() -> None:
    runtime = SyntheticOperationsDashboard(
        refresh_interval_seconds=60,
        duplicate_every=0,
        max_retained_events=2,
        prune_every_events=1,
    )
    app = create_dashboard_app(runtime)

    async def exercise_dashboard() -> None:
        async with app.router.lifespan_context(app):
            await runtime._ingest_cycle()
            await runtime._ingest_cycle()
            await runtime._ingest_cycle()
            snapshot = await runtime.snapshot()

            assert snapshot["totals"]["events_received"] == 4
            assert snapshot["totals"]["events_inserted"] == 2
            assert snapshot["totals"]["blocked_routes"] == 2
            assert snapshot["totals"]["audit_events"] == 10
            assert snapshot["totals"]["delivery_attempts"] == 2
            assert snapshot["totals"]["acknowledged_deliveries"] == 2
            assert snapshot["totals"]["unique_test_receipts"] == 4
            assert len(snapshot["recent_events"]) == 2
            assert len(snapshot["recent_deliveries"]) == 2
            assert len(snapshot["recent_holds"]) == 2
            assert len(snapshot["recent_activity"]) == 10

    asyncio.run(exercise_dashboard())
