import asyncio

from httpx import ASGITransport, AsyncClient

from medihub.application.operations import SyntheticOperationsDashboard
from medihub.dashboard import create_dashboard_app


async def _request_workbench():
    runtime = SyntheticOperationsDashboard(
        refresh_interval_seconds=60,
        duplicate_every=0,
    )
    app = create_dashboard_app(runtime)
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            devices = await client.get("/api/management/devices")
            assert devices.status_code == 200
            assert devices.json()["physical_device_connections_enabled"] is False
            assert devices.json()["persistent"] is False
            assert devices.json()["devices"][0]["device_id"] == "sim-device-001"

            registered = await client.post("/api/management/devices")
            assert registered.status_code == 201
            assert registered.json()["device_id"] == "sim-device-002"
            assert registered.json()["model"] == "scalar-simulator-v1"

            disabled = await client.patch(
                "/api/management/devices/sim-device-002",
                json={"enabled": False},
            )
            assert disabled.status_code == 200
            assert disabled.json()["enabled"] is False
            rejected_sample = await client.post("/api/management/devices/sim-device-002/emit")
            assert rejected_sample.status_code == 409
            assert rejected_sample.json() == {"error": "simulator_device_disabled"}

            reenabled = await client.patch(
                "/api/management/devices/sim-device-002",
                json={"enabled": True},
            )
            assert reenabled.status_code == 200
            sample = await client.post("/api/management/devices/sim-device-002/emit")
            assert sample.status_code == 200
            assert sample.json()["status"] == "passed"
            assert sample.json()["network_enabled"] is False

            mappings = (await client.get("/api/management/mappings")).json()
            assert mappings["mapping_activation_enabled"] is False
            assert mappings["mapping_set"]["scope"] == "synthetic_only"
            assert len(mappings["mapping_set"]["entries"]) == 1
            initial_vectors = (await client.get("/api/management/mapping-tests")).json()
            assert initial_vectors["status"] == "not_run"
            assert len(initial_vectors["vectors"]) == 1
            initial_test = await client.post("/api/management/mapping-tests/run")
            assert initial_test.status_code == 200
            assert initial_test.json()["status"] == "passed"
            assert initial_test.json()["passed"] == 1
            assert initial_test.json()["activation_enabled"] is False

            draft = await client.post(
                "/api/management/mappings/entries",
                json={
                    "source_metric_code": "simulated-test-input",
                    "source_unit_code": "1",
                    "normalized_metric_code": "mapped-test-output",
                    "normalized_unit_code": "1",
                    "operation": "linear",
                    "scale": "2",
                    "offset": "1",
                    "decimal_places": 2,
                },
            )
            assert draft.status_code == 200
            assert draft.json()["mapping_activation_enabled"] is False
            assert draft.json()["mapping_set"]["version"] == "1.0.1"
            invalidated_vectors = (await client.get("/api/management/mapping-tests")).json()
            assert invalidated_vectors["status"] == "stale"
            assert invalidated_vectors["last_run_mapping_version"] == "1.0.0"
            assert invalidated_vectors["last_report"]["status"] == "passed"

            vector = await client.post(
                "/api/management/mapping-tests/vectors",
                json={
                    "device_id": "sim-device-001",
                    "source_metric_code": "simulated-test-input",
                    "source_unit_code": "1",
                    "input_value": "3.5",
                    "expected_metric_code": "mapped-test-output",
                    "expected_unit_code": "1",
                    "expected_value": "8.00",
                },
            )
            assert vector.status_code == 200
            test_report = await client.post("/api/management/mapping-tests/run")
            assert test_report.status_code == 200
            assert test_report.json()["status"] == "passed"
            assert test_report.json()["mapping_version"] == "1.0.1"
            assert test_report.json()["vectors_run"] == 2
            assert test_report.json()["passed"] == 2
            assert test_report.json()["failed"] == 0
            assert test_report.json()["activation_enabled"] is False
            await client.post(
                "/api/management/mapping-tests/vectors",
                json={
                    "device_id": "sim-device-001",
                    "source_metric_code": "simulated-test-input",
                    "source_unit_code": "1",
                    "input_value": "3.5",
                    "expected_metric_code": "mapped-test-output",
                    "expected_unit_code": "1",
                    "expected_value": "9.00",
                },
            )
            mismatch_report = await client.post("/api/management/mapping-tests/run")
            assert mismatch_report.json()["status"] == "failed"
            assert mismatch_report.json()["failed"] == 1
            assert mismatch_report.json()["results"][-1]["code"] == (
                "mapping_test_expected_output_mismatch"
            )

            preview = await client.post(
                "/api/management/mappings/preview",
                json={
                    "device_id": "sim-device-001",
                    "source_metric_code": "simulated-test-input",
                    "source_unit_code": "1",
                    "value": 3.5,
                },
            )
            assert preview.status_code == 200
            assert preview.json()["mapping_activation_enabled"] is False
            assert preview.json()["result"]["normalized_value"] == "8.00"
            assert preview.json()["result"]["origin"] == "synthetic"
            assert "patient" not in preview.text.lower()

            rejected = await client.post(
                "/api/management/mappings/entries",
                json={
                    "source_metric_code": "secret-not-allowed",
                    "source_unit_code": "1",
                    "normalized_metric_code": "not-added",
                    "normalized_unit_code": "1",
                    "private_note": "SENSITIVE-DEMO-STRING",
                },
            )
            assert rejected.status_code == 422
            assert "SENSITIVE-DEMO-STRING" not in rejected.text
            assert "private_note" not in rejected.text

            destinations = (await client.get("/api/management/destinations")).json()
            assert destinations["external_connections_enabled"] is False
            assert destinations["destinations"][0]["network_enabled"] is False
            assert destinations["destinations"][0]["endpoint_configurable"] is False
            assert destinations["destinations"][0]["credentials_configurable"] is False
            receiver_test = await client.post("/api/management/destinations/test")
            assert receiver_test.status_code == 200
            assert receiver_test.json()["status"] == "passed"
            assert receiver_test.json()["network_enabled"] is False

            return await client.get("/")


def test_management_workbench_is_strict_synthetic_only_and_operational() -> None:
    page = asyncio.run(_request_workbench())

    assert page.status_code == 200
    assert "Register simulator" in page.text
    assert "Preview mapping" in page.text
    assert "Golden test vectors" in page.text
    assert "Run all mapping tests" in page.text
    assert "Endpoint and credential fields are not available" in page.text
    assert "no live connections" in page.text.lower()
